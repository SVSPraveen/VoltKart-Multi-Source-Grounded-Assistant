# PROGRESS.md — Project Status and Milestones

## Current State: Phase 5 (Core Chat Product) — Complete, Ready for Phase 6 Bonus

### 1. Done
- [x] **Phase 0 (Orient, Ground, Plan)**
- [x] **Phase 1 (Skeleton and Truth Harness)**
- [x] **Phase 2 (Ingestion and Storage)**
- [x] **Phase 3 (Table Question Answering)**
- [x] **Phase 4 (Document QA with Version Resolution)**
- [x] **Phase 5 (Core Chat Product — Complete Gate)**:
  - Multi-Source Mixed Questions (`backend/mixed_agent.py`):
    - Q13: Order O00174 return eligibility resolved across tables (orders, order_items, products, customers) and return policy documents (v3.0). Correctly applies smartphone 7-day policy override over Platinum 45-day window, notes user-supplied delivery date (R-007), calculates 10% restocking fee waived for Platinum with standard half-up decimal rounding (R-050), and outputs multi-source citations.
    - Q14: Store operations notice closure claim vs December 2025 order reconciliation. Extracts notice directive (store S03 closed for renovations; use online channel), queries December 2025 orders by channel (6 online, 3 in-store totaling 94,094.55 INR), concludes PARTIALLY agrees, and outputs multi-source citations.
  - Conversational Memory & Contextualization (`backend/assistant.py`, `backend/storage.py`):
    - SQLite persistence for chats and messages with statuses, timestamps, citations, and metadata.
    - Contextualization step with resolved-entities memo (e.g. `store_id = 'S04', year = 2025`), emitting quiet "Interpreted as: ..." line in UI and metadata.
    - Restart persistence test: Process restart retains chat history; Q20 summarizes Chat 2 strictly without leaking Chat 1 topics (R-012).
  - Server-Sent Events (SSE) Streaming API (`backend/api.py`, ADR-005):
    - `POST /api/chats/{chat_id}/messages` streaming live status events (`status: Searching documents...`, `status: Executing SQL...`, `status: Verifying citations...`), followed by citations, answer content, and completion signal.
    - Added full CRUD REST endpoints for chats and files (`/api/chats`, `/api/files`).
  - ReportLab PDF Export (`backend/export_pdf.py`, ADR-006):
    - `GET /api/chats/{chat_id}/export.pdf`: Title, export time with timezone (UTC, R-022), chronological message thread with roles, formatted citations (monospace SQL box + preview table for tables; verbatim quotes + section/page for documents), web toggle state per message.
    - Bundled Unicode TTF font family (Noto Sans Regular & Bold) in `backend/fonts/` enabling native Indian Rupee (`₹`, U+20B9) rendering (R-013). Tested via pdfplumber text extraction and pypdfium2 page rasterization.
  - React Frontend (`frontend/`, DESIGN.md):
    - Vite + React + TypeScript application with editorial instrument-panel layout matching DESIGN.md tokens: warm paper (`#FDFCF7`), surface (`#F5F3EC`), hairline rules (`#E5E2D9`), deep ink (`#111827`), Volt yellow-green accent (`#D4E815`).
    - Left rail (chats + versioned files library), center message thread (inline citation badges, quiet interpreted line), right collapsible Evidence Drawer (monospace SQL preview + tabular rows; document version timeline with superseded facts + quotes), composer with file attachment and web toggle.
    - Responsive mobile layout with collapsible off-canvas sidebar (R-051).
    - WASM Rollup build fallback for Windows Application Control environments (`frontend/patch-rollup.js`, R-052).
    - Playwright automated E2E tests capturing responsive screenshots at 360, 768, 1280, 1920 px in `reports/screens/`.
  - CORE COMPLETE GATE Verification:
    - Live evaluation of all 15 core questions (Q1–Q14 and Q20) across 3 consecutive live runs: 15/15 PASS on all 3 runs (45/45 = 100% pass rate).
    - Adversarial probes A1–A10: 10/10 PASS.
    - Unit test suite: 114/114 PASS.
    - Zero hardcoding gate: `make no-hardcode` passes cleanly across all 30 files in `backend/` and `frontend/src/`.
    - Rules `R-049`, `R-050`, `R-051`, `R-052` added to `REVIEW.md`.

### 2. In Progress
- [ ] Phase 5 Gate Report submission and owner review.

### 3. Next Steps (Phase 6: Bonus Features)
- [ ] B9: Multi-chat management and cross-chat isolation verification.
- [ ] B10: Analytical charts (bar, line) with stored query row grounding and PDF export re-rendering.
- [ ] B8: Web search integration with server-side gating (Tavily / DDGS keyless fallback).
- [ ] Run golden Q15-Q19 live 3x each.

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: Can be configured in `.env` for live LLM inference; offline cached mode is operational.
- `TAVILY_API_KEY` (optional): For Phase 6 bonus web search.
