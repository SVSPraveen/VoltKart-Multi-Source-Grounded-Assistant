# PROGRESS.md — Project Status and Milestones

## Current State: Phase 7 (Hardening) — Complete, Ready for Phase 8 Release

### 1. Done
- [x] **Phase 0 (Orient, Ground, Plan)**
- [x] **Phase 1 (Skeleton and Truth Harness)**
- [x] **Phase 2 (Ingestion and Storage)**
- [x] **Phase 3 (Table Question Answering)**
- [x] **Phase 4 (Document QA with Version Resolution)**
- [x] **Phase 5 (Core Chat Product — Complete Gate)**
- [x] **Phase 6 (Bonus Features — Strict Order B9 -> B10 -> B8)**
- [x] **Phase 7 (Hardening — Full V0–V7 Verification Stack)**:
  - **V4 Generalisation (Variant Bundles)**:
    - Implemented 3 rich variant presets in `tests/variants/make_variant.py`:
      1. `variant_1_apex` (ApexRetail): Renamed brand/stores/products, shifted dates (+30 days), scaled numbers (1.10x), and mixed date formats (DD/MM/YYYY and spelled out).
      2. `variant_2_zenith_table` (ZenithCommerce): Structured Markdown policy tables and multi-format versions (.txt, .docx, .md).
      3. `variant_3_omission` (OmniStore): Version family where newest v3 explicitly omits key policy facts (damaged reporting window), proving per-fact fallback to older v2.0 (R-001).
    - Built standalone evaluator `scripts/eval_variants.py` and test suite `tests/variants/test_variant_generalization.py`: Recomputes expected answers independently with `pandas` directly from variant CSVs and markdown. Proves 100% pass rate without hardcoding.
  - **V5 Adversarial Uploads & Probes**:
    - Built comprehensive fixture test suite `tests/unit/test_adversarial_fixtures.py`:
      1. Empty file (0 bytes) rejected cleanly with informative error message.
      2. Oversize file (>50MB) rejected cleanly.
      3. Legacy OLE `.doc` binary file rejected with `.docx` conversion guidance.
      4. Encrypted / password-protected PDF rejected cleanly with password removal instructions.
      5. Corrupted zip archive (.docx) and non-word zip archives rejected safely.
      6. Semicolon-delimited CSV and UTF-8 BOM CSV parsed with exact column preservation.
      7. Path traversal filenames (`../../etc/passwd`, `..\..\windows\system32`) neutralized cross-platform.
      8. Prompt injection files (formula injection in CSV cells, override tokens in document text) treated strictly as passive data, never obeyed (Truth Rule 5).
    - Verified all golden probes A1–A10 pass 10/10.
  - **Security Review (Threat Model: Internet-Reachable App executing LLM-written SQL)**:
    - Layered defense audited and hardened (`reports/security_review.md`):
      1. Single SELECT-family enforcement via `sqlglot` AST allowlist in `backend/sql_guard.py`.
      2. Wildcard blocking of all internal engine introspection functions (`duckdb_*`, `sqlite_*`, `pg_*`).
      3. DuckDB read-only connection + `SET enable_external_access = false;` + config locking.
      4. Execution timeout (5.0s ThreadPool) and enforced row cap (`fetchmany(row_cap)`).
      5. Cross-platform filename and API parameter sanitization (`validate_chat_id`, `validate_sha256`).
    - Added security test suite `tests/unit/test_security_audit.py` (7/7 PASS).
  - **V7 Calibrated Judge**:
    - Implemented `tests/judge/rubric.py` and `tests/judge/calibrated_judge.py` across 6 dimensions: correctness, provenance, citation sufficiency, abstention honesty, grounding faithfulness, formatting.
    - Hardened evaluation logic (R-066) to inspect native ground truth structures (nested numbers in `expected` and version constraints in `must_state_version`).
    - Calibrated (`tests/judge/test_judge_calibration.py`): Fed 7 deliberately flawed answers (wrong number, wrong version, missing citations, failed to abstain, fabricated delivery date, golden format revenue mismatch, golden format version mismatch) and proved the judge flags 7/7 (100%, exceeding >= 4 requirement). Proved 0 false rejections on genuine correct answers.
    - Evaluated golden outputs with `scripts/run_judge_eval.py`: 30/30 Passed (100.0%) across all 20 golden questions and 10 adversarial probes.
  - **V6 UI & Accessibility Audit**:
    - Injected axe-core into Playwright E2E suite (`tests/e2e/test_accessibility.py`).
    - Fixed color contrast on card surfaces by darkening `--text-dim` from `#9CA3AF` to `#525866` (yielding 6.24:1 contrast ratio, passing WCAG 2.1 AA and AAA).
    - Added explicit `aria-label` attributes across all interactive header, sidebar, and composer controls.
    - Verified keyboard Tab navigation, visible focus outlines, and responsive layouts across 360px, 768px, 1280px, 1920px (`reports/screens/`).
    - Eliminated duplicate `live_server` fixture in `test_ui_screens.py`.
  - **Verification & Gates**:
    - Added rules `R-062`, `R-063`, `R-064`, `R-065`, `R-066`, `R-067`, `R-068` to `REVIEW.md`.
    - Integrated `variants` and `judge` verification targets into `scripts/runner.py verify` (7/7 checks passing).

### 2. In Progress
- [ ] Phase 7 Gate Report submission and owner review.

### 3. Next Steps (Phase 8: Release)
- [ ] Comprehensive README (setup, Mermaid architecture diagram, requirements mapping table).
- [ ] Produce `evaluation/chat1.pdf`, `chat2.pdf`, `chat3.pdf` through UI export.
- [ ] Write `docs/ARCHITECTURE.md`, `KNOWN_LIMITATIONS.md`, `EXPLAIN_ME.md`, `VIDEO_SCRIPT.md`.
- [ ] Run fresh clone test (`make fresh-clone-test`).

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: Can be configured in `.env` for live LLM inference; offline cached mode is operational.
- `TAVILY_API_KEY` (optional): For Phase 6 bonus web search.
