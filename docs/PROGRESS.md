# PROGRESS.md — Project Status and Milestones

## Current State: Phase 4 (Document QA with Version Resolution) — Complete, Ready for Phase 5

### 1. Done
- [x] **Phase 0 (Orient, Ground, Plan)**
- [x] **Phase 1 (Skeleton and Truth Harness)**
- [x] **Phase 2 (Ingestion and Storage)**
- [x] **Phase 3 (Table Question Answering)**
- [x] **Phase 4 (Document QA with Version Resolution)**:
  - Hybrid Document Retrieval (`backend/retrieval.py`): FTS5 BM25 + dense ONNX vector embeddings (`fastembed`) fused via Reciprocal Rank Fusion (RRF), never pre-filtering by date (R-001).
  - Sibling Expansion (`backend/retrieval.py`): For each top hit, automatically pulls corresponding sections across all versions in the document family.
  - Multi-Part Question Decomposition (`backend/doc_agent.py`): Decomposes compound queries into atomic facts resolved independently (e.g. warranty price vs claims limit in Q12).
  - Code-Enforced Verbatim Quote Verification (`backend/version_resolver.py`): Strict quote verification ensuring evidence quotes are exact normalized substrings of the chunk content (R-019).
  - Deterministic Claim-Level Resolver (`backend/version_resolver.py`): Picks the latest document date among versions stating the fact, tracks superseded values, detects tie dates, handles temporal `as_of` dates (A3, A4), and honestly abstains when unsupported (A1, A2).
  - Fallback Disclosure: Sets `fallback_used = True`, records newer silent versions, and explicitly states the source version in prose and citations (Q8, Q9, Q11, Q12).
  - Prompt Injection Immunity: Document chunks wrapped in `<document_data>` and treated strictly as untrusted data, never instructions (Truth Rule 5, R-010).
  - Unit Test Suite (`tests/unit/test_version_resolver.py`): 10 dedicated tests on synthetic families covering newest silent, newest stating, tie dates, undated documents (R-017), three versions with changed facts, prompt injection fixtures, quote verification, and point-in-time as-of queries. Total unit suite: 110 tests passing.
  - Live Golden Evaluations Q6-Q12: 3 live runs each, 21/21 PASS (100% pass rate) with exact version statements, verbatim quotes, and evidence drawer provenance.
  - Adversarial Probes A1-A5: 5/5 PASS (Diamond tier abstention, CEO abstention, March 2024 out of coverage, mid-2025 as-of 20 days / 2025-01-15 resolution, and prompt override refusal).
  - Zero hardcoding gate: `make no-hardcode` passes cleanly across all 18 files.
  - Rules `R-043`, `R-044`, and `R-045` recorded in `REVIEW.md`.

### 2. In Progress
- [ ] Phase 4 Gate Report submission and owner review.

### 3. Next Steps (Phase 5: Core Chat Product)
- [ ] Implement SSE streaming API with live pipeline status events (`status`, `citation`, `answer`, `done`).
- [ ] Implement contextualize step with resolved-entities memo ("Interpreted as: ...").
- [ ] Implement mixed questions (Q13, Q14) coordinating table and document tools.
- [ ] Build the UI (left rail, thread, evidence drawer with version timeline, composer with web toggle).
- [ ] Implement ReportLab PDF export with embedded Unicode TTF for rupee sign (`₹`).
- [ ] Run golden Q1-Q14 + Q20 live 3x each.

### 4. Open Questions & External Dependencies
- `GEMINI_API_KEY`: Can be configured in `.env` for live LLM inference; offline cached mode is operational.
- `TAVILY_API_KEY` (optional): For Phase 6 bonus web search.
