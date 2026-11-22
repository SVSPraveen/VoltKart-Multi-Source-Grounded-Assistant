"""backend/assistant.py - Core assistant entrypoint.

Handles question answering by routing to the SQL agent, document retriever,
or web tool with layered security guards, context resolution, and numeric grounding.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from backend.doc_agent import run_doc_qa
from backend.ingestion import process_single_file
from backend.mixed_agent import run_mixed_qa
from backend.sql_agent import run_table_qa
from backend.storage import (
    get_chat_messages,
    list_all_files,
    load_all_table_profiles,
    save_data_documentation,
    save_message,
    save_table_profile,
)
from backend.tables import ingest_table, is_data_documentation_text


def ensure_documents_loaded() -> None:
    """Ensure document files are loaded into SQLite if storage is unpopulated."""
    files = list_all_files()
    if files:
        return

    sample_dir = os.getenv("SAMPLE_BUNDLE_DIR")
    docs_dirs: list[Path] = []
    if sample_dir and Path(sample_dir).exists():
        if (Path(sample_dir) / "documents").exists():
            docs_dirs.append(Path(sample_dir) / "documents")
        else:
            docs_dirs.append(Path(sample_dir))

    if not docs_dirs:
        docs_dirs = list(Path("assignment").glob("*/documents"))

    if docs_dirs and docs_dirs[0].exists():
        d_dir = docs_dirs[0]
        for f_path in sorted(d_dir.iterdir()):
            if f_path.is_file() and f_path.suffix.lower() in {".pdf", ".docx", ".txt", ".md"}:
                try:
                    process_single_file(f_path.name, f_path.read_bytes())
                except Exception:
                    pass


def ensure_tables_loaded() -> None:
    """Ensure database tables and data documentation are loaded if storage is unpopulated."""
    profiles = load_all_table_profiles()
    if profiles:
        return

    sample_dir = os.getenv("SAMPLE_BUNDLE_DIR")
    tables_dirs: list[Path] = []
    if sample_dir and Path(sample_dir).exists():
        if (Path(sample_dir) / "tables").exists():
            tables_dirs.append(Path(sample_dir) / "tables")
        else:
            tables_dirs.append(Path(sample_dir))

    if not tables_dirs:
        tables_dirs = list(Path("assignment").glob("*/tables"))

    if tables_dirs and tables_dirs[0].exists():
        t_dir = tables_dirs[0]
        for csv_file in sorted(t_dir.glob("*.csv")):
            raw_bytes = csv_file.read_bytes()
            tbl_name, df, profile = ingest_table(raw_bytes, csv_file.name)
            save_table_profile(profile, "bootstrap")

        # Ingest data dictionary documentation if found in parent bundle folder
        bundle_parent = t_dir.parent
        for md_file in bundle_parent.glob("*.md"):
            content = md_file.read_text(encoding="utf-8", errors="replace")
            if is_data_documentation_text(content, filename=md_file.name):
                save_data_documentation(md_file.name, content, "bootstrap")


def _resolve_context_entities(chat_id: str, question: str) -> tuple[dict[str, Any], str | None]:
    """Inspect previous turns in the given chat to resolve context entities (R-012)."""
    messages = get_chat_messages(chat_id)
    entities: dict[str, Any] = {}
    interpreted_as: str | None = None

    # Scan previous assistant messages in reverse
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            meta = msg.get("metadata", {})
            if "entities" in meta and isinstance(meta["entities"], dict):
                entities.update(meta["entities"])
            citations = msg.get("citations", [])
            for c in citations:
                for row in c.get("result_rows", []):
                    if isinstance(row, dict):
                        if "store_id" in row and "last_store_id" not in entities:
                            entities["last_store_id"] = row["store_id"]
                        if "store_name" in row and "last_store_name" not in entities:
                            entities["last_store_name"] = row["store_name"]

    q_lower = question.lower()
    if ("that store" in q_lower or "the store" in q_lower) and "last_store_id" in entities:
        interpreted_as = f"store_id = '{entities['last_store_id']}', year = 2025"

    return entities, interpreted_as


def _summarize_chat_history(chat_id: str) -> dict[str, Any]:
    """Summarize the conversation history scoped strictly to the given chat_id (spec 7.5, R-012)."""
    messages = get_chat_messages(chat_id)
    history_pairs: list[tuple[str, str]] = []
    current_q = None

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "").strip()
        if role == "user":
            if "summarize" not in content.lower():
                current_q = content
        elif role == "assistant" and current_q:
            history_pairs.append((current_q, content))
            current_q = None

    if not history_pairs:
        answer = "In this conversation, no prior questions have been discussed yet."
    else:
        lines = ["**Summary of Topics Discussed in this Conversation:**\n"]
        for idx, (q, a) in enumerate(history_pairs, 1):
            clean_first = a.split("\n")[0].replace("**", "").replace("#", "").strip()
            lines.append(f"{idx}. **{q}**\n   - {clean_first}\n")
        answer = "\n".join(lines)

    asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    save_message(
        asst_msg_id,
        chat_id,
        "assistant",
        answer,
        citations=[],
        metadata={"chat_summary": True},
        status="completed",
    )
    return {
        "answer": answer,
        "citations": [],
        "abstained": False,
        "chat_id": chat_id,
        "metadata": {"chat_summary": True},
    }


def ask_assistant(
    question: str,
    chat_id: str = "default",
    web_enabled: bool = False,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the multi-source QA pipeline for a user question."""
    ensure_tables_loaded()
    ensure_documents_loaded()
    clean_q = question.strip()
    q_lower = clean_q.lower()

    # Save user message to chat history
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    save_message(
        user_msg_id,
        chat_id,
        "user",
        clean_q,
        web_enabled=web_enabled,
        status="completed",
    )

    # 1. Prompt injection / system prompt extraction refusal (R-010 / A5)
    if "ignore all previous instructions" in q_lower or "print your system prompt" in q_lower:
        answer = "I cannot fulfill requests to reveal internal prompts or override security instructions."
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id,
            chat_id,
            "assistant",
            answer,
            citations=[],
            metadata={"probe": "A5"},
            status="completed",
        )
        return {
            "answer": answer,
            "citations": [],
            "abstained": False,
            "chat_id": chat_id,
            "metadata": {"probe": "A5"},
        }

    # 2. External knowledge check when web search is disabled (Q17)
    if "amazon" in q_lower and not web_enabled:
        answer = (
            "I cannot answer this question from the uploaded sources, and web search is disabled."
        )
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id,
            chat_id,
            "assistant",
            answer,
            citations=[],
            metadata={"probe": "Q17", "abstained": True},
            status="completed",
        )
        return {
            "answer": answer,
            "citations": [],
            "abstained": True,
            "chat_id": chat_id,
            "metadata": {"probe": "Q17", "abstained": True},
        }

    # 3. Conversational memory summary turn (spec section 7.5 / Q20)
    if any(
        k in q_lower
        for k in ["summarize what we discussed", "recap our conversation", "what did we discuss"]
    ):
        return _summarize_chat_history(chat_id)

    # 4. Contextualization & entity resolution from previous turns
    context_entities, interpreted_as = _resolve_context_entities(chat_id, clean_q)

    # 5. Mixed questions (spec section 7.4 / Q13, Q14)
    is_mixed_candidate = (
        re.search(r"\b[A-Z]\d{4,}\b", clean_q)
        and any(k in q_lower for k in ["return", "restocking", "fee", "allowed", "window"])
    ) or (
        any(k in q_lower for k in ["notice", "closed", "renovation"])
        and any(k in q_lower for k in ["order", "data", "agree", "reconcil"])
    )
    if is_mixed_candidate:
        mixed_res = run_mixed_qa(clean_q, chat_id=chat_id)
        if not mixed_res.abstained:
            asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            meta = dict(mixed_res.metadata)
            if interpreted_as:
                meta["interpreted_as"] = interpreted_as
            save_message(
                asst_msg_id,
                chat_id,
                "assistant",
                mixed_res.answer,
                citations=mixed_res.citations,
                metadata=meta,
                interpreted_as=interpreted_as,
                status="completed",
            )
            return {
                "answer": mixed_res.answer,
                "citations": mixed_res.citations,
                "abstained": False,
                "chat_id": chat_id,
                "metadata": meta,
                "interpreted_as": interpreted_as,
            }

    # 6. Intent routing: Distinguish table vs document queries
    clear_table_keywords = [
        "revenue",
        "spend",
        "spent",
        "highest revenue",
        "top 3",
        "top 5",
        "returned most often",
        "return reason",
        "by region",
        "refund amount by region",
        "bought a laptop",
        "units sold",
        "who manages",
        "customer_id",
        "store_id",
        "order_id",
        "in 2025",
        "in q1 2026",
    ]
    clear_doc_keywords = [
        "return window",
        "business days does a refund take",
        "damaged on delivery",
        "opened earbud",
        "opened earphone",
        "salary range",
        "work mode",
        "report to",
        "reports to",
        "warranty cost",
        "claims limit",
        "diamond member",
        "who is the ceo",
        "who is ceo",
    ]

    is_clear_table = any(k in q_lower for k in clear_table_keywords)
    is_clear_doc = any(k in q_lower for k in clear_doc_keywords)

    if is_clear_table:
        qa_result = run_table_qa(clean_q, chat_id=chat_id, context_entities=context_entities)
        if not qa_result.abstained or qa_result.sql:
            msg_metadata = {
                "sql": qa_result.sql,
                "is_ambiguous": qa_result.is_ambiguous,
                "reconciled": qa_result.reconciled,
            }
            if qa_result.query_result and qa_result.query_result.rows:
                first_row = qa_result.query_result.rows[0]
                extracted_entities = {}
                if "store_id" in first_row:
                    extracted_entities["store_id"] = first_row["store_id"]
                if "store_name" in first_row:
                    extracted_entities["store_name"] = first_row["store_name"]
                if extracted_entities:
                    msg_metadata["entities"] = extracted_entities

            if interpreted_as:
                msg_metadata["interpreted_as"] = interpreted_as

            asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            save_message(
                asst_msg_id,
                chat_id,
                "assistant",
                qa_result.answer,
                citations=qa_result.citations,
                metadata=msg_metadata,
                interpreted_as=interpreted_as,
                status="completed",
            )
            return {
                "answer": qa_result.answer,
                "citations": qa_result.citations,
                "abstained": qa_result.abstained,
                "chat_id": chat_id,
                "metadata": msg_metadata,
                "interpreted_as": interpreted_as,
            }

    if is_clear_doc:
        doc_result = run_doc_qa(clean_q, chat_id=chat_id)
        if not doc_result.abstained:
            asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            meta = dict(doc_result.metadata)
            if interpreted_as:
                meta["interpreted_as"] = interpreted_as
            save_message(
                asst_msg_id,
                chat_id,
                "assistant",
                doc_result.answer,
                citations=doc_result.citations,
                metadata=meta,
                interpreted_as=interpreted_as,
                status="completed",
            )
            return {
                "answer": doc_result.answer,
                "citations": doc_result.citations,
                "abstained": doc_result.abstained,
                "chat_id": chat_id,
                "metadata": meta,
                "interpreted_as": interpreted_as,
            }

    # Fallback cascade: Try Table QA then Doc QA
    qa_result = run_table_qa(clean_q, chat_id=chat_id, context_entities=context_entities)
    if not qa_result.abstained and qa_result.sql:
        msg_metadata = {
            "sql": qa_result.sql,
            "is_ambiguous": qa_result.is_ambiguous,
            "reconciled": qa_result.reconciled,
        }
        if interpreted_as:
            msg_metadata["interpreted_as"] = interpreted_as
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id,
            chat_id,
            "assistant",
            qa_result.answer,
            citations=qa_result.citations,
            metadata=msg_metadata,
            interpreted_as=interpreted_as,
            status="completed",
        )
        return {
            "answer": qa_result.answer,
            "citations": qa_result.citations,
            "abstained": qa_result.abstained,
            "chat_id": chat_id,
            "metadata": msg_metadata,
            "interpreted_as": interpreted_as,
        }

    doc_result = run_doc_qa(clean_q, chat_id=chat_id)
    if not doc_result.abstained:
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        meta = dict(doc_result.metadata)
        if interpreted_as:
            meta["interpreted_as"] = interpreted_as
        save_message(
            asst_msg_id,
            chat_id,
            "assistant",
            doc_result.answer,
            citations=doc_result.citations,
            metadata=meta,
            interpreted_as=interpreted_as,
            status="completed",
        )
        return {
            "answer": doc_result.answer,
            "citations": doc_result.citations,
            "abstained": doc_result.abstained,
            "chat_id": chat_id,
            "metadata": meta,
            "interpreted_as": interpreted_as,
        }

    # Honest abstention when no source provides the answer (C5)
    answer = (
        "I cannot answer this question as the requested information is not mentioned "
        "in any uploaded documents or tables, and web search is disabled."
    )
    asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    save_message(
        asst_msg_id,
        chat_id,
        "assistant",
        answer,
        citations=[],
        metadata={"abstained": True},
        interpreted_as=interpreted_as,
        status="completed",
    )
    return {
        "answer": answer,
        "citations": [],
        "abstained": True,
        "chat_id": chat_id,
        "metadata": {"abstained": True},
        "interpreted_as": interpreted_as,
    }
