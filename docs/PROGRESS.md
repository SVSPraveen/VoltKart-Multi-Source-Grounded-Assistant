# PROGRESS.md — Project Status and Milestones

## Current State: Phase 2 (Ingestion and Storage) — Complete, Ready for Phase 3

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
  - Persistent SQLite & DuckDB Storage (`backend/storage.py`): SQLite schema with WAL mode, FTS5 BM25 full-text index, chunk table with BLOB embeddings, dual-connection DuckDB sandbox with read-only connection enforcing `enable_external_access=false`, and clean Windows table-level reset.
  - Local Dense Vector Embeddings (`backend/embeddings.py`): Fast, offline, deterministic 384-dimensional ONNX embeddings via `fastembed` (`bge-small-en-v1.5`) with binary BLOB serialization.
  - Ingestion Orchestration & Robustness (`backend/ingestion.py`): SHA-256 idempotency, R-023 upload edge case validation (0-byte rejection, >50MB limit, legacy `.doc` rejection, path traversal sanitization, scanned PDF warning), and structured `IngestionSummary`.
  - FastAPI Ingestion HTTP Routes (`backend/api.py`): `/api/health`, `/api/upload`, `/api/ingestion-summary`, `/api/schema-card`, `/api/reset`.
  - Unit & Robustness Test Suite: 56 passing unit tests covering date formats, profiling, relationships, chunking, R-023 edge cases, API endpoints, and cross-process restart persistence.
  - Sample bundle proven: All 8 documents correctly parsed with dates, 4 version families, and section counts; all 6 tables profiled with exact row counts and inferred relationships; data dictionary groundings loaded.
  - Rules `R-028`, `R-029`, and `R-030` recorded in `REVIEW.md`.

### 2. In Progress
- [ ] Phase 2 Gate Report submission and owner review.

### 3. Next Steps (Phase 3: Table QA)
- [ ] Implement text-to-SQL plan -> SQL -> validate -> execute -> check -> self-correct -> compose -> cite loop (spec section 7.2).
- [ ] Layered SQL sandbox: sqlglot single SELECT allowlist, read-only DuckDB connection, `enable_external_access=false`, timeout, row cap (R-009).
- [ ] Grounding check: LLM does no arithmetic (R-003), fan-out reconciliation (R-020).
- [ ] Execute golden evaluations Q1-Q5 live 3x and adversarial probes A6-A10.

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: User must provide a Gemini API key in `.env` for Phase 3+ live evaluation runs.
- `TAVILY_API_KEY` (optional): If provided, used for bonus web search (B8); otherwise system falls back to keyless search.
