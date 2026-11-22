# PROGRESS.md — Project Status and Milestones

## Current State: Phase 6 (Bonus Features) — Complete, Ready for Phase 7 Hardening

### 1. Done
- [x] **Phase 0 (Orient, Ground, Plan)**
- [x] **Phase 1 (Skeleton and Truth Harness)**
- [x] **Phase 2 (Ingestion and Storage)**
- [x] **Phase 3 (Table Question Answering)**
- [x] **Phase 4 (Document QA with Version Resolution)**
- [x] **Phase 5 (Core Chat Product — Complete Gate)**
- [x] **Phase 6 (Bonus Features — Strict Order B9 -> B10 -> B8)**:
  - **B9 (Multiple Chats & Isolation, spec 7.8, R-012, R-056)**:
    - Full isolation by `chat_id` across SQLite persistence and agent execution state.
    - Added comprehensive isolation unit tests (`tests/unit/test_chat_isolation.py`):
      1. Planted secret marker isolation: planted secret token in Chat A remains completely unknown to Chat B.
      2. Conversational entity isolation & honest abstention: context referents ("that store") in a fresh chat without prior context trigger honest abstention rather than ungrounded execution (R-056).
      3. Summarization isolation: Chat summarization in Chat B contains zero topics from Chat A.
      4. Deletion lifecycle isolation: deleting Chat A cleans up its messages without affecting Chat B.
    - Re-verified core complete gate across 3 consecutive live runs (45/45 = 100%).
  - **B10 (Analytical Inline & Exported Charts, spec 7.8, R-057)**:
    - Implemented `backend/charts.py`: `ChartSpec`, deterministic validator `validate_chart_spec`, `create_grounded_chart_spec`, and server-side PNG rendering via Pillow (`render_chart_image`).
    - Every chart specification maps data points directly to database query result rows matching row IDs and column names.
    - Hand-edited or hallucinated numbers are rejected by `validate_chart_spec` (deterministic test `tests/unit/test_chart_validation.py`). Pie charts strictly enforce parts-of-a-whole percentage totals (100% ± 0.5%).
    - Integrated chart generation in `backend/assistant.py` for Golden Q15 (2025 category revenue bar chart), Q16 (2025 monthly smartphone units line chart), and Q19 (top 5 stores revenue bar chart).
    - Database schema & model update: Added `charts` JSON column to messages table (`backend/storage.py`, `backend/models.py`).
    - PDF export integration: ReportLab PDF export re-renders charts from stored query specs as embedded high-resolution raster images (`backend/export_pdf.py`).
    - React UI integration: Built `InlineChart.tsx` with SVG visualization, interactive tooltip hovering, and accessible data table rendering beneath each chart. Frontend build verified (`npm run build`).
  - **B8 (Server-Gated Web Search, spec 7.8, R-011, R-058)**:
    - Implemented `backend/web_search.py` with strict server-side gating (R-011). When `web_enabled` is False, search tools are unbound and an audit counter guarantees zero outbound network calls.
    - Outbound audit tests (`tests/unit/test_web_search.py`): Assert ZERO outbound search calls when web toggle is OFF (Q17). Direct calls to `run_web_qa(web_enabled=False)` raise security exceptions.
    - Multi-provider resilient search engine: Tavily when `TAVILY_API_KEY` is present; resilient keyless DuckDuckGo / Bing parsing fallback.
    - Full factual page retrieval: extracts target webpage text, parses factual claim, and formats citations with title, source URL, and ISO-8601 UTC `retrieved_at` timestamp.
    - Multi-source cross-modal comparison (Q18b): Seamlessly blends live web facts (Amazon India 7-day replacement window) with local active store policy document facts (7-day return and refund window).
  - **Verification & Gates**:
    - PHASE 6 BONUS GATE: Golden questions Q15–Q19 run live 3 consecutive times: 5/5 on all 3 runs (15/15 = 100% pass rate).
    - CORE COMPLETE GATE RE-VERIFICATION: All 15 core questions (Q1–Q14, Q20) run live 3 consecutive times: 15/15 on all 3 runs (45/45 = 100% pass rate).
    - Unit test suite: 129/129 PASS across all modules.
    - Golden test suite: 30/30 PASS (Q1–Q20, A1–A10).
    - Full `python scripts/runner.py verify` passes: `lint` (PASS), `format` (PASS), `no-hardcode` (PASS), `unit` (PASS), `golden` (PASS).
    - Rules `R-056`, `R-057`, `R-058`, `R-059`, `R-060`, `R-061` added to `REVIEW.md`.
    - Review hardening:
      1. Fixed `_handle_chart_query` to resolve contextual "first question" strictly within the active chat's history and honestly abstain when no prior question exists in that chat (R-059).
      2. Fixed `InlineChart.tsx` to implement full SVG rendering for pie charts (pie slices, angular arcs, and legend) alongside bar and line charts (R-061).
      3. Fixed `web_search.py` DuckDuckGo HTML endpoint integration with session referer and replaced static entity answer templates with dynamic fact extraction and honest abstention (R-060).
      4. Added unit tests for pie chart percentage validation (100% ± 0.5%), first question cross-chat isolation, and general web query grounding.

### 2. In Progress
- [ ] Phase 6 Gate Report submission and owner review.

### 3. Next Steps (Phase 7: Hardening, Polish, and Final Delivery)
- [ ] Adversarial testing suite expansion (probes A1–A10 under multiple chat sessions and load).
- [ ] Run variants generation and evaluation (`make variants`).
- [ ] Complete chat export PDF archive (`evaluation/*.pdf`).
- [ ] Run fresh clone test (`make fresh-clone-test`).
- [ ] Prepare explainer video talking points and live demo scripts.

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: Can be configured in `.env` for live LLM inference; offline cached mode is operational.
- `TAVILY_API_KEY` (optional): For Phase 6 bonus web search.
