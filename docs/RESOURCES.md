# RESOURCES.md — Verified Legally Free Reference Materials

All links below are verified freely accessible documentation, open-access research papers, or open textbooks informing the design decisions of this system.

## 1. Core Frameworks and Tools

### DuckDB Architecture & Security
- **URL:** https://duckdb.org/docs/configuration/overview
- **Decision Informed:** ADR-002 (Tabular Storage & SQL Sandbox)
- **Summary:** In DuckDB, arbitrary filesystem and network access can be disabled on a per-connection basis using `SET enable_external_access = false;`. Running analytical queries on a secondary read-only connection guarantees that generated SQL cannot access the host filesystem or modify database tables.

### sqlglot AST Parser & Transpiler
- **URL:** https://sqlglot.com/
- **Decision Informed:** R-009 / ADR-002 (Layered SQL Sandbox)
- **Summary:** sqlglot parses SQL queries into an Abstract Syntax Tree (AST). It enables deterministic validation: asserting exactly one root expression, checking that the root is strictly an `exp.Select`, and inspecting all identifiers against an allowlist derived from ingested tables and columns.

### SQLite FTS5 (Full-Text Search)
- **URL:** https://www.sqlite.org/fts5.html
- **Decision Informed:** ADR-003 (Document Retrieval Pipeline)
- **Summary:** Built directly into the Python standard library `sqlite3` without external daemons. Provides BM25 ranking over document chunks, tokenized exact matching (entity codes, section titles, names), and prefix queries with zero memory overhead.

### FastAPI & Pydantic v2
- **URL:** https://fastapi.tiangolo.com/
- **Decision Informed:** ADR-001 (Backend API & Contracts)
- **Summary:** High-performance asynchronous REST API framework with native Pydantic v2 validation and Server-Sent Events (SSE) streaming support for real-time trace events.

### LangGraph State Machine
- **URL:** https://langchain-ai.github.io/langgraph/
- **Decision Informed:** ADR-004 (Agent State Machine)
- **Summary:** Implements inspectable, cyclic or acyclic directed graphs. Eliminates unpredictable autonomous ReAct loops in favor of a deterministic sequence of state transitions: Route -> Contextualise -> Plan -> Tool Execution -> Verification -> Composition.

### ReportLab Open Source User Guide
- **URL:** https://www.reportlab.com/docs/reportlab-userguide.pdf
- **Decision Informed:** ADR-006 (Chat Export Engine)
- **Summary:** Pure-Python document generation library that supports embedding TrueType Unicode fonts (Noto Sans) to guarantee proper rendering of currency symbols like `₹` without external C library dependencies.

## 2. Research Papers & Methodologies

### DIN-SQL: Decomposed In-Context Learning of Text-to-SQL (Pourreza & Rafiei, NeurIPS 2023)
- **URL:** https://arxiv.org/abs/2304.11015
- **Decision Informed:** Section 7.2 (Table QA Pipeline)
- **Summary:** Decomposes complex SQL generation into schema linking, query classification, sub-query decomposition, generation, and self-correction. Demonstrates that execution feedback with syntax validation significantly reduces SQL generation error rates.

### Lost in the Middle: How Language Models Use Long Contexts (Liu et al., TACL 2024)
- **URL:** https://arxiv.org/abs/2307.03172
- **Decision Informed:** Section 7.3 (Document Retrieval & Sibling Expansion)
- **Summary:** Models retrieve and recall information placed at the very beginning or end of long contexts far more accurately than information in the middle. Informs our decision to chunk by section, filter tightly, and place candidate evidence prominently in prompt heads.

### Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (Zheng et al., NeurIPS 2023)
- **URL:** https://arxiv.org/abs/2306.05685
- **Decision Informed:** Section 10 (V7 Judge Design)
- **Summary:** Identifies systematic biases in LLM judges: position bias, verbosity bias, and self-enhancement bias. Informs our requirement that an LLM judge must be calibrated first against deliberate errors and may only fail builds, never pass them alone.

### Jurafsky & Martin: Speech and Language Processing (3rd ed. draft, 2024)
- **URL:** https://web.stanford.edu/~jurafsky/slp3/
- **Decision Informed:** Section 7.3 (Hybrid Search & RRF)
- **Summary:** Foundational textbook covering dense vs sparse vector search, BM25 scoring, and Reciprocal Rank Fusion for combining lexical and semantic rankings.

## 3. Needs from Human (`NEEDS_FROM_HUMAN`)
- None at this stage. All required technical references and documentation are legally free and verified.

