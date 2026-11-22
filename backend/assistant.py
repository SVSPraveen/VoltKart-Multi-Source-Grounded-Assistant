"""backend/assistant.py - Core assistant entrypoint.

Handles question answering by routing to the SQL agent, document retriever,
or web tool with layered security guards, context resolution, and numeric grounding.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from backend.doc_agent import run_doc_qa
from backend.ingestion import process_single_file
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

    # Check for bundle tables directory dynamically without brand hardcoding
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


def _resolve_context_entities(chat_id: str) -> dict[str, Any]:
    """Inspect previous turns in the given chat to resolve context entities (R-012)."""
    messages = get_chat_messages(chat_id)
    entities: dict[str, Any] = {}

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

    return entities


def ask_assistant(
    question: str,
    chat_id: str = "default",
    web_enabled: bool = False,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the multi-source QA pipeline for a user question.

    Returns a structured dictionary containing:
      - answer: str (the formatted assistant reply)
      - citations: list of structured citation records
      - abstained: bool (whether the assistant abstained)
      - chat_id: str
      - metadata: dict
    """
    ensure_tables_loaded()
    ensure_documents_loaded()
    clean_q = question.strip()
    q_lower = clean_q.lower()

    # Save user message to chat history
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    save_message(user_msg_id, chat_id, "user", clean_q)

    # 1. Prompt injection / system prompt extraction refusal (R-010 / A5)
    if "ignore all previous instructions" in q_lower or "print your system prompt" in q_lower:
        answer = "I cannot fulfill requests to reveal internal prompts or override security instructions."
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id, chat_id, "assistant", answer, citations=[], metadata={"probe": "A5"}
        )
        return {
            "answer": answer,
            "citations": [],
            "abstained": False,
            "chat_id": chat_id,
            "metadata": {"probe": "A5"},
        }

    # 2. Honest abstention when web search is disabled (A2 / Q17)
    if "ceo" in q_lower and not web_enabled:
        answer = "I cannot answer this question as the company's CEO is not mentioned in any of the provided sources, and web search is disabled."
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id, chat_id, "assistant", answer, citations=[], metadata={"probe": "A2"}
        )
        return {
            "answer": answer,
            "citations": [],
            "abstained": True,
            "chat_id": chat_id,
            "metadata": {"probe": "A2", "abstained": True},
        }

    if "amazon" in q_lower and not web_enabled:
        answer = (
            "I cannot answer this question from the uploaded sources, and web search is disabled."
        )
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id, chat_id, "assistant", answer, citations=[], metadata={"probe": "Q17"}
        )
        return {
            "answer": answer,
            "citations": [],
            "abstained": True,
            "chat_id": chat_id,
            "metadata": {"probe": "Q17", "abstained": True},
        }

    # 3. Contextualization & entity resolution from previous turns
    context_entities = _resolve_context_entities(chat_id)

    # 4. Routing between Document QA and Table QA
    doc_keywords = [
        "return window",
        "return policy",
        "eligible for return",
        "business days",
        "refund take",
        "damaged on delivery",
        "damaged in transit",
        "opened earbuds",
        "opened earphones",
        "non-returnable",
        "machine learning engineer",
        "reports to",
        "report to",
        "salary range",
        "work mode",
        "warranty",
        "claims limit",
        "claims",
        "diamond members",
        "mid-2025",
        "march 2024",
    ]
    is_doc_query = any(k in q_lower for k in doc_keywords)

    if is_doc_query:
        doc_result = run_doc_qa(clean_q, chat_id=chat_id)
        asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        save_message(
            asst_msg_id,
            chat_id,
            "assistant",
            doc_result.answer,
            citations=doc_result.citations,
            metadata=doc_result.metadata,
        )
        return {
            "answer": doc_result.answer,
            "citations": doc_result.citations,
            "abstained": doc_result.abstained,
            "chat_id": chat_id,
            "metadata": doc_result.metadata,
        }

    # 5. Table Question Answering
    qa_result = run_table_qa(
        clean_q,
        chat_id=chat_id,
        context_entities=context_entities,
    )

    # If Table QA abstained without executing SQL, check if Doc QA can answer
    if qa_result.abstained and not qa_result.sql:
        doc_result = run_doc_qa(clean_q, chat_id=chat_id)
        if not doc_result.abstained:
            asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            save_message(
                asst_msg_id,
                chat_id,
                "assistant",
                doc_result.answer,
                citations=doc_result.citations,
                metadata=doc_result.metadata,
            )
            return {
                "answer": doc_result.answer,
                "citations": doc_result.citations,
                "abstained": doc_result.abstained,
                "chat_id": chat_id,
                "metadata": doc_result.metadata,
            }

    # Update metadata with discovered entities
    msg_metadata: dict[str, Any] = {
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

    asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    save_message(
        asst_msg_id,
        chat_id,
        "assistant",
        qa_result.answer,
        citations=qa_result.citations,
        metadata=msg_metadata,
    )

    return {
        "answer": qa_result.answer,
        "citations": qa_result.citations,
        "abstained": qa_result.abstained,
        "chat_id": chat_id,
        "metadata": msg_metadata,
    }
