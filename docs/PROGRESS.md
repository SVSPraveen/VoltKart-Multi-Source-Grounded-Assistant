# PROGRESS.md — Project Status and Milestones

## Current State: Phase 3 (Table Question Answering) — Complete, Ready for Phase 4

### 1. Done
- [x] **Phase 0 (Orient, Ground, Plan)**:
  - Workspace grounding, verification of artifacts, OS/Python/Node/Git detection.
  - Independent pandas re-derivation of golden metrics.
  - Pre-mortem catalog in `docs/RISKS.md`.
  - Research catalog in `docs/RESOURCES.md`.
  - Design specification in `DESIGN.md`.
  - Architecture Decision Records (ADR-001 through ADR-007).
  - Traceability matrix in `docs/TRACEABILITY.md`.
- [x] **Phase 1 (Skeleton and Truth Harness)**:
  - Isolated Python 3.12 virtual environment initialized at `.venv` with core dependencies (`pytest`, `ruff`, `pyyaml`, `pandas`, `duckdb`, `sqlglot`, `fastapi`, `pydantic`, `httpx`).
  - Repository structure scaffolded: `backend/`, `frontend/src/`, `tests/unit/`, `tests/golden/`, `tests/variants/`, `reports/`, `evaluation/`, `scripts/`.
  - Cross-platform runner implemented (`scripts/runner.py`) and wired to root `Makefile` supporting `verify`, `test`, `golden`, `lint`, `format`, `no-hardcode`, `clean`.
  - Sample entity hardcoding scanner implemented (`scripts/check_no_hardcode.py`, `make no-hardcode`) enforcing AGENTS.md Rule 4 and REVIEW.md R-005.
  - Variant dataset generator implemented (`tests/variants/make_variant.py`) supporting brand renaming, date shifting, price scaling, and presets.
  - Golden evaluation harness implemented (`tests/golden/eval_harness.py`, `tests/golden/test_golden.py`) with deterministic assertions: numeric tolerance 0.01, entities (`must_include`/`must_not`), citation provenance (table SQL, doc quotes), version disclosure, and abstention.
  - Unit test suite established in `tests/unit/` (23 passing tests for eval assertions, scanner, and variants).
  - **RED BASELINE asserted**: running `pytest tests/golden/` executes against unpopulated skeleton and deterministically fails (30/30 failed with explicit assertion errors).
  - Independent mathematical verification script (`scripts/verify_golden_numbers.py`) re-derives Q1, Q2, Q3, Q4, Q5 to the exact paisa and count (diff 0.000000).
  - Rules `R-025`, `R-026`, and `R-027` recorded in `REVIEW.md`.
  - Verification reports generated at `reports/verify-<timestamp>.md`.
  - Repository hygiene: `.gitignore`, `.env.example`, `pyproject.toml`, `requirements.txt`, and `README.md` configured.
- [x] **Phase 2 (Ingestion and Storage)**:
  - Tabular Ingestion & DuckDB Profiler (`backend/tables.py`): Delimiter sniffing (`,`, `;`, `\t`), BOM handling, column profiling (nulls, distinct, min/max, samples), primary key inference, foreign key relationship inference (name match + containment >= 0.98 against unique parent), and automatic data dictionary detection and integration.
  - Structure-Aware Document Parser (`backend/documents.py`): PDF parsing with 1-based page numbers and table extraction via `pdfplumber`, DOCX heading and table extraction via `python-docx`, TXT/MD splitting, title extraction, version family normalization, and verbatim quote preservation.
  - Tolerant Multi-Format Date Parser (`backend/date_parser.py`): Support for all sample bundle formats (`10 March 2025`, `2025-09-01`, `1 April 2024`, `15 January 2025`, `5 November 2025`, `1 July 2024`, `1 February 2026`), ordinals, filename fallback, date disagreement flagging, and ISO normalization.
  - Persistent SQLite & DuckDB Storage (`backend/storage.py`): SQLite schema with WAL mode, FTS5 BM25 full-text index, chunk table with BLOB embeddings, persistent `table_meta` table preserving profiling/relationships across restarts, dual-connection DuckDB sandbox with read-only connection enforcing `enable_external_access=false`, and clean Windows table-level reset.
  - Local Dense Vector Embeddings (`backend/embeddings.py`): Fast, offline, deterministic 384-dimensional ONNX embeddings via `fastembed` (`bge-small-en-v1.5`) with binary BLOB serialization.
  - Ingestion Orchestration & Robustness (`backend/ingestion.py`): SHA-256 idempotency, R-023 upload edge case validation (0-byte rejection, >50MB limit, legacy `.doc` rejection, corrupt zip archive rejection, path traversal sanitization, encrypted/scanned PDF handling), declared schema key parsing, and structured `IngestionSummary`.
  - FastAPI Ingestion HTTP Routes (`backend/api.py`): `/api/health`, `/api/upload`, `/api/ingestion-summary`, `/api/schema-card`, `/api/reset`.
  - Unit & Robustness Test Suite: 68 passing unit tests covering date formats and edge cases, profiling, declared and inferred relationships, chunking, R-023 edge cases, API endpoints, sample bundle validation, and cross-process restart persistence.
  - Sample bundle proven: All 8 documents correctly parsed with dates, exactly 4 version families, and section counts; all 6 tables profiled with exact row counts and inferred/declared relationships; data dictionary groundings loaded.
  - Rules `R-028`, `R-029`, `R-030`, `R-031`, `R-032`, `R-033`, `R-034`, and `R-035` recorded in `REVIEW.md`.
- [x] **Phase 3 (Table Question Answering)**:
  - AST SQL Validation & Guard (`backend/sql_guard.py`): Strict single SELECT-family validation, table allowlist, and rejection of all DDL, DML, PRAGMA, and table-valued file reader functions (`exp.ReadCSV`, `exp.ReadParquet`, `read_csv`, etc.) (R-009, R-036).
  - Hardened Multi-Layered SQL Sandbox (`backend/sql_sandbox.py`): Read-only secondary DuckDB connection, `enable_external_access = false`, row cap (LIMIT 100), execution timeout, and join fan-out reconciliation (R-020, R-037).
  - Deterministic Numeric Grounding Verifier (`backend/grounding.py`): Strict numeric check ensuring every float and integer in generated prose is grounded in executed SQL result rows, question prompt, row counts, or verified code-derived aggregate sums (R-003, R-037).
  - Central LLM Client & Dev Cache (`backend/llm.py`): Gemini API integration with rate-limit exponential backoff (R-015), persistent JSON response cache (`data/llm_cache.json`), and offline fallback support.
  - Text-to-SQL Agent (`backend/sql_agent.py`): Plan -> Generate -> Validate -> Execute -> Check -> Self-Correct -> Reconcile -> Compose -> Ground -> Cite pipeline. Delivers exact paisa-precision metrics, currency formatting (`₹` and Indian grouping), and ambiguous question handling (R-004, A8, A9, A10).
  - Assistant & API Integration (`backend/assistant.py`, `backend/api.py`): Contextual entity resolution across turns (Q2 resolving to Q1 store), SQLite message persistence, `/api/query`, and `/api/execute-sql` endpoints.
  - Live Golden Evaluations Q1-Q5: 3 live runs each, 15/15 PASS (100% pass rate) with exact paisa precision vs golden.yaml.
  - Adversarial Probes A6-A10: 5/5 PASS including DROP TABLE blocked (orders table intact with 900 rows), read_csv('/etc/passwd') blocked, 2027 revenue empty result, spend ambiguity disclosure, and Kavya disambiguation.
  - Unit test suite expanded to 100 tests across `sql_guard`, `sql_sandbox`, `grounding`, `sql_agent`, and ingestion (including join fan-out reconciliation, anonymous table reader blocking, and json LLM extraction).
  - Zero hardcoding gate: `make no-hardcode` passes cleanly with 0 sample entity strings in `backend/` or `frontend/src/` (including strict customer regexes).
  - Rules `R-036`, `R-037`, `R-038`, `R-039`, `R-040`, `R-041`, and `R-042` recorded in `REVIEW.md`.

### 2. In Progress
- [ ] Phase 3 Gate Report submission and owner review.

### 3. Next Steps (Phase 4: Document QA with Version Resolution)
- [ ] Implement document retrieval across ALL versions with sibling expansion (spec section 7.3).
- [ ] Implement structured per-version extraction and machine-verified verbatim quotes.
- [ ] Deterministic claim-level version resolver (latest document date stating fact, fallback disclosure).
- [ ] Unit-test resolver on synthetic multi-version families (newest silent, tie dates, undated).
- [ ] Execute golden evaluations Q6-Q12 live 3x and adversarial probes A1-A5.

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: Can be configured in `.env` for live LLM inference; offline cached mode is operational.
- `TAVILY_API_KEY` (optional): For Phase 6 bonus web search.
