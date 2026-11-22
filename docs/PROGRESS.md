# PROGRESS.md — Project Status and Milestones

## Current State: Phase 8 (Release & Polish) — Complete, Public-Ready

### 1. Done
- [x] **Phase 0 (Orient, Ground, Plan)**
- [x] **Phase 1 (Skeleton and Truth Harness)**
- [x] **Phase 2 (Ingestion and Storage)**
- [x] **Phase 3 (Table Question Answering)**
- [x] **Phase 4 (Document QA with Version Resolution)**
- [x] **Phase 5 (Core Chat Product — Complete Gate)**
- [x] **Phase 6 (Bonus Features — Strict Order B9 -> B10 -> B8)**
- [x] **Phase 7 (Hardening — Full V0–V7 Verification Stack)**
- [x] **Phase 8 (Release & Polish — Final Deliverables & Public Release)**:
  - **Technical Defense & Documentation**:
    - `README.md`: Comprehensive setup guide, Mermaid end-to-end architecture diagram, requirement traceability table mapping C1–C7 and B8–B10 to source code and tests, bonuses built, known limitations, future improvements, Windows notes (PowerShell runner vs WSL2), and free-tier LLM privacy disclosures.
    - `.env.example`: Fully documented with all LLM provider, model, API keys, search provider, and runtime parameters.
    - `docs/ARCHITECTURE.md`: Deep dive into the multi-source pipeline, SSE lifecycle, DuckDB/SQLite dual-engine model, layered SQL AST sandbox, deterministic version resolver, and ReportLab PDF engine.
    - `docs/KNOWN_LIMITATIONS.md`: Detailed root-cause analysis and architectural fixes for 3 real reproduced failure edge cases (sparse baseline operational closures, multi-clause mixed provenance fusion, and surname collision entity aggregations).
    - `docs/EXPLAIN_ME.md`: Module-by-module defense manual for the live technical round covering role in pipeline, design rationale, alternatives rejected, and 3 hard interview questions per module with verified technical answers.
    - `docs/VIDEO_SCRIPT.md`: Timed 12–14 minute explainer video outline covering problem philosophy, zero-state app walkthrough, table Q&A, version resolution, web search gating, and hardening, using fresh demo queries completely distinct from the 20 golden evaluation questions.
  - **Official Evaluation PDF Bundle via Headless UI Export**:
    - Built `scripts/export_evaluation_pdfs.py` driving real browser through headless automation, executing the exact sequence specified in Spec Section 14:
      - Chat 1: Q1–Q5, Q15, Q16
      - Chat 2: Q6–Q14
      - Chat 1: Q19 (first question chart)
      - Chat 3: Q17 (web off), then Q18 turn 1 (web on), then Q18 turn 2 (comparison)
      - Restart backend process to test persistence across kills!
      - Chat 2: Q20 (conversation summary)
      - Trigger UI Export button for all three chats to `evaluation/chat1.pdf`, `evaluation/chat2.pdf`, `evaluation/chat3.pdf`.
    - Automated PDF verification: Parsed text and asserted timestamps (UTC), citations (monospace SQL, row counts, document quotes, dates), charts (re-rendered chart images), native Indian Rupee glyph (`₹`), and web-search toggle state per message. 100% checks passed across all 3 PDFs.
  - **V8 Fresh Clone Test**:
    - Implemented `python scripts/runner.py fresh-clone-test` (and `make fresh-clone-test`).
    - Clones repository into isolated temporary folder, sets up `.env`, executes `runner.py verify` across all 7 layers, and runs an end-to-end smoke query proving the codebase builds and passes verification untouched.
  - **All 7 Verification Layers Passing**:
    - Lint (Ruff), Format (Ruff), No-Hardcode (`check_no_hardcode.py`), Unit (`tests/unit`), Golden (`tests/golden`), Variants (`tests/variants`), Judge (`tests/judge`).

### 2. In Progress
- [x] Final Phase 8 Gate Report preparation.

### 3. Next Steps (Evaluation & Presentation)
- [ ] Record 10–15 minute explainer video following `docs/VIDEO_SCRIPT.md`.
- [ ] Prepare for live technical defense using `docs/EXPLAIN_ME.md`.
- [ ] Package git repository for final review submission.

### 4. Open Questions & External Dependencies
- None. The system operates 100% offline using verified response caches and bundled fonts; optional live API keys (`GEMINI_API_KEY`, `TAVILY_API_KEY`) can be provided in `.env` for real-time generative queries.
