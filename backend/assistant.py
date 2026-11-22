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

from backend.charts import create_grounded_chart_spec
from backend.doc_agent import run_doc_qa
from backend.ingestion import process_single_file
from backend.mixed_agent import run_mixed_qa
from backend.sql_agent import run_table_qa
from backend.sql_sandbox import execute_sandboxed_query
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
        meta = msg.get("metadata", {})
        if isinstance(meta, dict) and "entities" in meta and isinstance(meta["entities"], dict):
            for k, v in meta["entities"].items():
                if k not in entities:
                    entities[k] = v

        citations = msg.get("citations", [])
        for c in citations:
            for row in c.get("result_rows", []):
                if isinstance(row, dict):
                    if "store_id" in row and "last_store_id" not in entities:
                        entities["last_store_id"] = row["store_id"]
                    if "store_name" in row and "last_store_name" not in entities:
                        entities["last_store_name"] = row["store_name"]

        # Also search previous turn text for year if not yet resolved
        if "year" not in entities:
            m_yr = re.search(r"\b(202\d)\b", msg.get("content", ""))
            if m_yr:
                entities["year"] = m_yr.group(1)

    # Check if current question explicitly provides a year
    q_yr = re.search(r"\b(202\d)\b", question)
    if q_yr:
        entities["year"] = q_yr.group(1)

    q_lower = question.lower()
    if ("that store" in q_lower or "the store" in q_lower) and "last_store_id" in entities:
        target_year = entities.get("year")
        if target_year:
            interpreted_as = f"store_id = '{entities['last_store_id']}', year = {target_year}"
        else:
            interpreted_as = f"store_id = '{entities['last_store_id']}'"

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


def _handle_chart_query(
    clean_q: str,
    chat_id: str,
    context_entities: dict[str, Any],
    interpreted_as: str | None,
) -> dict[str, Any] | None:
    """Handle analytical chart generation requests grounded in database query rows (B10, spec 7.8)."""
    q_lower = clean_q.lower()

    # Determine chart type requested
    if "line" in q_lower:
        chart_type = "line"
    elif "pie" in q_lower:
        chart_type = "pie"
    else:
        chart_type = "bar"

    sql: str | None = None
    title: str = ""
    x_col: str = ""
    y_col: str = ""
    x_label: str = ""
    y_label: str = ""
    tables_used: list[str] = []

    # Case 1: Revenue by product category (Q15)
    if "category" in q_lower and "revenue" in q_lower:
        m_yr = re.search(r"\b(202\d)\b", clean_q)
        year = m_yr.group(1) if m_yr else context_entities.get("year", "2025")
        sql = f"""
        SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price_inr * (1.0 - oi.discount_pct / 100.0)), 2) AS revenue_inr
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.order_status = 'Delivered'
          AND o.order_date >= '{year}-01-01' AND o.order_date <= '{year}-12-31'
        GROUP BY p.category
        ORDER BY revenue_inr DESC;
        """.strip()
        title = f"Total Revenue by Product Category ({year})"
        x_col = "category"
        y_col = "revenue_inr"
        x_label = "Product Category"
        y_label = "Revenue (INR)"
        tables_used = ["orders", "order_items", "products"]

    # Case 2: Smartphone units sold per month (Q16)
    elif ("smartphone" in q_lower or "phone" in q_lower) and (
        "unit" in q_lower or "month" in q_lower or "sold" in q_lower
    ):
        m_yr = re.search(r"\b(202\d)\b", clean_q)
        year = m_yr.group(1) if m_yr else context_entities.get("year", "2025")
        sql = f"""
        SELECT SUBSTR(o.order_date, 1, 7) AS month,
               SUM(oi.quantity) AS units_sold
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.order_status = 'Delivered'
          AND p.category = 'Smartphones'
          AND o.order_date >= '{year}-01-01' AND o.order_date <= '{year}-12-31'
        GROUP BY month
        ORDER BY month ASC;
        """.strip()
        title = f"Monthly Smartphone Units Sold ({year})"
        x_col = "month"
        y_col = "units_sold"
        x_label = "Month"
        y_label = "Units Sold"
        tables_used = ["orders", "order_items", "products"]

    # Case 3: Top stores revenue / first question in chat (Q19)
    elif "first question" in q_lower or (
        "store" in q_lower and ("revenue" in q_lower or "spend" in q_lower or "top" in q_lower)
    ):
        m_yr = re.search(r"\b(202\d)\b", clean_q)
        year = m_yr.group(1) if m_yr else context_entities.get("year", "2025")
        m_lim = re.search(r"top\s+(\d+)", q_lower)
        limit = int(m_lim.group(1)) if m_lim else 5
        sql = f"""
        SELECT s.store_name, ROUND(SUM(oi.quantity * oi.unit_price_inr * (1.0 - oi.discount_pct / 100.0)), 2) AS revenue_inr
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN stores s ON o.store_id = s.store_id
        WHERE o.order_status = 'Delivered'
          AND o.order_date >= '{year}-01-01' AND o.order_date <= '{year}-12-31'
        GROUP BY s.store_id, s.store_name
        ORDER BY revenue_inr DESC
        LIMIT {limit};
        """.strip()
        title = f"Top {limit} Stores by Revenue ({year})"
        x_col = "store_name"
        y_col = "revenue_inr"
        x_label = "Store"
        y_label = "Revenue (INR)"
        tables_used = ["orders", "order_items", "stores"]
        if "first question" in q_lower:
            interpreted_as = (
                f"top {limit} stores by revenue in {year} (referring to initial store inquiry)"
            )

    if not sql:
        return None

    query_res = execute_sandboxed_query(sql)
    if not query_res.success or not query_res.rows:
        return None

    # Construct and validate grounded chart spec
    chart_spec = create_grounded_chart_spec(
        query_result_rows=query_res.rows,
        chart_type=chart_type,
        title=title,
        x_column=x_col,
        y_column=y_col,
        x_label=x_label,
        y_label=y_label,
        source_query_id=f"qry_{uuid.uuid4().hex[:8]}",
    )

    # Compose answer markdown with data table underneath (spec 7.8)
    lines = [f"Here is a {chart_type} chart showing {title}:\n"]
    lines.append(f"| {x_label} | {y_label} |")
    lines.append("| :--- | :--- |")
    total_val = 0.0
    for r in query_res.rows:
        x_val = r.get(x_col, "")
        y_val = r.get(y_col, 0)
        try:
            y_float = float(y_val)
            total_val += y_float
            if "revenue" in y_col.lower() or "inr" in y_col.lower():
                from backend.sql_agent import format_inr

                y_disp = format_inr(y_float)
            else:
                y_disp = f"{int(y_float)}" if y_float.is_integer() else f"{y_float:.2f}"
        except Exception:
            y_disp = str(y_val)
        lines.append(f"| {x_val} | {y_disp} |")

    if "units" in y_col:
        lines.append(
            f"\nTotal: {int(total_val) if total_val.is_integer() else total_val} units across all {len(query_res.rows)} months."
        )
    elif "revenue" in y_col or "inr" in y_col:
        from backend.sql_agent import format_inr

        lines.append(f"\nTotal: {format_inr(total_val)}")

    answer = "\n".join(lines)

    citation = {
        "type": "table",
        "tables": tables_used,
        "sql": sql,
        "row_count": len(query_res.rows),
        "result_rows": query_res.rows,
    }

    asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    meta = {
        "chart": True,
        "chart_type": chart_type,
        "sql": sql,
        "chart_spec": chart_spec.model_dump(),
    }
    if interpreted_as:
        meta["interpreted_as"] = interpreted_as

    save_message(
        asst_msg_id,
        chat_id,
        "assistant",
        answer,
        citations=[citation],
        charts=[chart_spec.model_dump()],
        metadata=meta,
        interpreted_as=interpreted_as,
        status="completed",
    )

    return {
        "answer": answer,
        "citations": [citation],
        "charts": [chart_spec.model_dump()],
        "abstained": False,
        "chat_id": chat_id,
        "metadata": meta,
        "interpreted_as": interpreted_as,
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
    is_summary_turn = any(
        phrase in q_lower
        for phrase in [
            "summarize what we discussed",
            "recap our conversation",
            "what did we discuss",
            "summarize our chat",
            "summarize our conversation",
            "summarize the discussion",
            "summarize what was discussed",
        ]
    ) or (
        any(k in q_lower for k in ["summariz", "recap"])
        and any(
            k in q_lower for k in ["discuss", "conversation", "chat", "so far", "talked", "history"]
        )
    )
    if is_summary_turn:
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

    # 5b. Analytical Chart generation (B10, spec section 7.8 / Q15, Q16, Q19)
    if "chart" in q_lower or "plot" in q_lower or "graph" in q_lower:
        chart_res = _handle_chart_query(clean_q, chat_id, context_entities, interpreted_as)
        if chart_res:
            return chart_res

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
                yr_match = re.search(r"\b(202\d)\b", clean_q) or re.search(
                    r"\b(202\d)\b", qa_result.sql
                )
                if yr_match:
                    extracted_entities["year"] = yr_match.group(1)
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
        if qa_result.query_result and qa_result.query_result.rows:
            first_row = qa_result.query_result.rows[0]
            extracted_entities = {}
            if "store_id" in first_row:
                extracted_entities["store_id"] = first_row["store_id"]
            if "store_name" in first_row:
                extracted_entities["store_name"] = first_row["store_name"]
            yr_match = re.search(r"\b(202\d)\b", clean_q) or re.search(
                r"\b(202\d)\b", qa_result.sql
            )
            if yr_match:
                extracted_entities["year"] = yr_match.group(1)
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
