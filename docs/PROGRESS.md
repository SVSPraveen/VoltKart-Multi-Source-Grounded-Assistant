# PROGRESS.md — Project Status and Milestones

## Current State: Phase 1 (Skeleton and Truth Harness) — Complete, Ready for Phase 2

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
  - Unit test suite established in `tests/unit/` (15 passing tests for eval assertions, scanner, and variants).
  - **RED BASELINE asserted**: running `pytest tests/golden/` executes against unpopulated skeleton and deterministically fails (30/30 failed with explicit assertion errors).
  - Independent mathematical verification script (`scripts/verify_golden_numbers.py`) re-derives Q1, Q4, Q5 to the exact paisa (diff 0.000000).
  - Verification reports generated at `reports/verify-<timestamp>.md`.
  - Repository hygiene: `.gitignore`, `.env.example`, `pyproject.toml`, `requirements.txt`, and `README.md` configured.

### 2. In Progress
- [ ] Phase 1 Gate Report submission and owner review.

### 3. Next Steps (Phase 2: Ingestion and Storage)
- [ ] Ingest CSV tables into DuckDB with schema cards, profiling, inferred foreign key relationships, and data dictionary grounding (spec section 7.1).
- [ ] Implement structure-aware document extraction (PDF pages, DOCX headings and tables, TXT).
- [ ] Tolerant multi-format date extraction with source recorded (R-017).
- [ ] Group documents into version families with chunking, FTS5 index, and local embeddings.
- [ ] Idempotent uploads (SHA-256) and graceful error handling for all R-023 upload edge cases.
- [ ] Ingestion summary API + UI card.
- [ ] Restart persistence test (data survives backend restart).

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: User must provide a Gemini API key in `.env` for Phase 3+ live evaluation runs.
- `TAVILY_API_KEY` (optional): If provided, used for bonus web search (B8); otherwise system falls back to keyless search.
