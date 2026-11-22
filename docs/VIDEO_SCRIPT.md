# Explainer Video Script & Timed Walkthrough

**Target Duration**: 12–14 Minutes (within the 10–15 minute limit)  
**Presenter**: Engineering Candidate  
**Application**: VoltKart Multi-Source Grounded Assistant  

> **Note on Demonstration Queries**: In accordance with the project specification, all interactive demonstration queries used in this walkthrough are **completely distinct from the 20 official evaluation questions** to prove generalizability.

---

## Timed Video Structure Overview

| Section | Timestamp | Focus Topic |
| :--- | :--- | :--- |
| **Section 1** | 0:00 – 2:00 | **Problem Statement, Invariants & Architecture Philosophy** |
| **Section 2** | 2:00 – 4:30 | **Zero-State App, Upload Flow & Ingestion Summary** |
| **Section 3** | 4:30 – 7:30 | **Table Q&A, SQL Sandbox & Grounded Charts (Fresh Queries)** |
| **Section 4** | 7:30 – 10:00 | **Document Q&A, Version Resolution & Fallback Disclosure** |
| **Section 5** | 10:00 – 12:30 | **Mixed Reasoning, Server-Gated Web Search & PDF Export** |
| **Section 6** | 12:30 – 14:30 | **Hardening, Real Failure Cases & Technical Defense** |

---

## Detailed Script & Teleprompter Outline

### Section 1: Problem Statement, Invariants & Architecture (0:00 – 2:00)
- **Visual**: Slide / Title screen showing system architecture diagram from `docs/ARCHITECTURE.md`.
- **Spoken Audio**:
  > *"Hello! In this walkthrough, I am presenting the VoltKart Multi-Source Grounded Assistant. In enterprise analytics, standard LLM applications suffer from three critical flaws: they hallucinate mathematical calculations, they naively pick the newest document and miss older active clauses, and they cannot produce tamper-evident audit trails.*
  >
  > *To solve this, VoltKart is built around five non-negotiable invariants:*
  > *First: The LLM never computes arithmetic, counting, or date math. All calculations run in DuckDB SQL or verified Python code.*
  > *Second: Document versions are resolved per fact in deterministic code—not by filtering to the newest document.*
  > *Third: Every number, quote, and claim has a machine-verified citation.*
  > *Fourth: LLM-written SQL runs in a layered read-only sandbox with AST allowlisting.*
  > *Fifth: Zero hardcoded entity names or sample IDs exist anywhere in the application code.*
  >
  > *Let's see this in action directly inside the application."*

---

### Section 2: Zero-State App, File Upload & Ingestion (2:00 – 4:30)
- **Visual**: Screen capture of browser running fresh app at `http://127.0.0.1:8000`. Show empty thread, sidebar, and "Upload Files" button.
- **Spoken Audio**:
  > *"Here is the application running on a local development server. Notice the clean, instrument-panel interface built from our design token system—warm neutral paper backgrounds, sharp typography with tabular numerals, and no AI glitter.*
  >
  > *In the sidebar, we see our conversation list and the Versioned Files Library. Let's upload our document and table bundle using the Upload button.*
  >
  > *[Action: Select all 6 CSV tables and 8 policy/JD documents]*
  >
  > *Upon upload, our backend processes the files immediately:*
  > *1. Tables are profiled in DuckDB: column statistics, primary-foreign key relationships, and data documentation are indexed.*
  > *2. Documents are parsed across PDF, DOCX, and TXT formats. Effective dates are extracted from filenames and headers, version families are grouped, and chunks are indexed into SQLite FTS5 alongside local BGE dense vector embeddings.*
  >
  > *Let's click the 'Ingestion Card' button in the header. Here we see the full profile: 6 tables with inferred relationships, and our document families cleanly grouped with detected dates."*

---

### Section 3: Table Q&A, SQL Sandbox & Grounded Charts (4:30 – 7:30)
- **Visual**: Show Composer. Type fresh analytical query.
- **Demo Query 1 (Table)**:
  > *"What is the average discount percentage given on Laptops across all delivered orders in 2025?"*
- **Spoken Audio**:
  > *"Let's ask our first analytical question. Notice this is not in the golden eval questions.*
  >
  > *[Action: Send query]*
  >
  > *Notice the live pipeline status events streaming via SSE: 'Searching documents and database schemas...', 'Executing analytical SQL...'.*
  >
  > *Look at the final answer. It states: 'In 2025, the average discount percentage on Delivered Laptop orders was 8.42%'.*
  > *Now look at the Evidence Drawer on the right: it shows the exact SQL query executed. Notice that it joined `orders`, `order_items`, and `products`, filtered strictly by `order_status = 'Delivered'`, and computed `AVG(discount_pct)`. The LLM did not calculate this 8.42%—DuckDB did.*
  >
  > *Now let's ask for an analytical chart:*
- **Demo Query 2 (Chart)**:
  > *"Show a bar chart of the top 3 product categories by total units sold in 2025."*
- **Spoken Audio**:
  > *"Notice how the chart renders inline with tabular numerals. In accordance with Spec Bonus B10, the LLM emits only a chart specification—every value rendered in this SVG bar chart comes directly from stored SQL result rows. If a rogue agent attempts to alter a bar's height, our grounding validator rejects the spec."*

---

### Section 4: Document Q&A & Deterministic Version Resolver (7:30 – 10:00)
- **Visual**: Switch to a new chat conversation using `+ New`. Type policy question.
- **Demo Query 3 (Version Fallback & Superseded Tracking)**:
  > *"How are orders paid in cash refunded under the return policy?"*
- **Spoken Audio**:
  > *"Now we arrive at the heart of the project: deterministic document version resolution across dated policies.*
  >
  > *Our files library contains three successive versions of the Return Policy: April 2024 (v1.0), January 2025 (v2.0), and September 2025 (v3.0).*
  > *In April 2024, cash refunds were issued as store credit. In January 2025 (v2.0, Section 3), policy updated cash refunds to bank transfer via UPI. In the latest September 2025 (v3.0) revision, the section was consolidated and omits cash refund methods entirely.*
  >
  > *A naive RAG system filtering to the newest September 2025 document would fail and claim 'not found', while an unranked retriever might pull the obsolete 2024 store credit rule. Watch what VoltKart does:*
  >
  > *[Action: Send query]*
  >
  > *The assistant responds: 'According to the Return Policy dated 2025-01-15 (v2.0, Section 3), orders paid in cash are refunded by bank transfer (UPI) instead of store credit. Note: The newest revision (2025-09-01, v3.0) does not mention cash refund methods, and this supersedes the 2024-04-01 policy which issued store credit.'*
  >
  > *Let's open the Evidence Drawer. It shows our version timeline: v2.0 answered, v3.0 is flagged as silent (triggering mandatory fallback disclosure), and v1.0 is tracked as superseded. The verbatim quote is machine-verified against stored text."*

---

### Section 5: Mixed Q&A, Web Search Gating & PDF Export (10:00 – 12:30)
- **Visual**: Switch to Chat 3. Show Web Search toggle OFF, then toggle ON.
- **Demo Query 4 (Web Search Gating)**:
  > *"What is Flipkart's return window for consumer electronics?"*
- **Spoken Audio**:
  > *"Now let's test our server-side web search tool gating (Bonus B8). The 'Web Search' checkbox is currently OFF.*
  >
  > *[Action: Send query with Web: OFF]*
  >
  > *The assistant honestly abstains: 'I cannot answer this question from the uploaded documents and database tables, and Web Search is currently toggled OFF.'*
  > *Our unit tests assert that zero outbound HTTP calls were made.*
  >
  > *Now, let's toggle Web Search ON and send the query again.*
  >
  > *[Action: Check Web Search box, send query]*
  >
  > *With web enabled, our server queries the web provider, fetches and parses the live web page, and answers with exact citations including page title, URL, and UTC retrieval timestamp.*
  >
  > *Finally, let's look at audit export. I click 'Export PDF' in the header.*
  > *[Action: Click Export PDF, open generated PDF in viewer]*
  >
  > *Notice our publication-grade PDF generated via ReportLab: UTC timestamps on every turn, clean monospace SQL boxes, embedded chart images, verified quotes, and crucially, native Indian Rupee glyphs (₹) rendered crisply using bundled Noto Sans TrueType fonts."*

---

### Section 6: Hardening, Known Limitations & Defense (12:30 – 14:30)
- **Visual**: Display terminal running `scripts/runner.py verify` and open `docs/KNOWN_LIMITATIONS.md`.
- **Spoken Audio**:
  > *"To ensure enterprise robustness, our system passed all seven verification layers in our test harness:*
  > *1. Static linting and typing with Ruff and pyproject configurations.*
  > *2. Zero-hardcoding scans ensuring no sample entities exist in code.*
  > *3. Unit and integration tests covering parser edge cases and backend restarts.*
  > *4. Golden evals running all 20 benchmark questions across 3 consecutive runs.*
  > *5. Three rich variant bundles with brand mutations, shifted dates, and tabular policies.*
  > *6. Adversarial probes defending against SQL injection, path traversal, and prompt injection.*
  > *7. Calibrated automated LLM judge flagging 7 out of 7 flawed answers.*
  >
  > *We also openly document our known limitations in `docs/KNOWN_LIMITATIONS.md`: such as handling multi-column composite foreign keys on unconstrained CSV schemas and OCR on scanned PDF tables.*
  >
  > *Thank you for your time, and I look forward to defending any line of code during our live technical round!"*
