# Explainer Video Master Script & Live Presentation Guide

**Presenter**: Praveen (Backend Systems & Production AI Architectures)  
**Target Duration**: 10–14 Minutes (Ideal sweet spot for screen recording with voice + webcam)  
**Application**: VoltKart Multi-Source Grounded Chat Assistant  
**Live UI URL**: `http://localhost:5173/`  
**Backend API URL**: `http://127.0.0.1:8000/api/health`  

---

## Quick Reference / Teleprompter Cue Sheet

| Section | Timing | Screen / Visual Target | Key Action / Spoken Focus |
|---|---|---|---|
| **1. Intro** | 0:00 – 1:00 | Webcam ON + Architecture Slide / App Header | Who you are (Praveen), what you built, 5 truth invariants. |
| **2. Live Walkthrough** | 1:00 – 6:30 | Browser (`http://localhost:5173/`) in **one continuous take** | Empty app $\rightarrow$ Upload bundle $\rightarrow$ Ingestion card $\rightarrow$ Table QA $\rightarrow$ Chart $\rightarrow$ Document QA $\rightarrow$ Web Toggle $\rightarrow$ PDF Export. |
| **3. Architecture** | 6:30 – 8:30 | Architecture Diagram (`docs/ARCHITECTURE.md`) | Follow query flow: Router $\rightarrow$ Sandboxed Tabular / Sibling Document / Web $\rightarrow$ Evidence Assembly $\rightarrow$ SSE. |
| **4. Code Walkthrough** | 8:30 – 11:00 | VS Code (`backend/`) | Open exact files: `sql_sandbox.py` (fan-out), `version_resolver.py` (quotes), `assistant.py` (routing), `pdf_export.py` (ReportLab). |
| **5. Design Decision** | 11:00 – 12:30 | Slide or `version_resolver.py` | Claim-level code resolution vs retrieval date-filtering / LLM prompting. |
| **6. Where It Fails** | 12:30 – 14:00 | Browser or Terminal (`docs/KNOWN_LIMITATIONS.md`) | Real reproduced failure (unnormalized category naming in DuckDB), mitigation, and conclusion. |

---

## Detailed Word-for-Word Video Script

### Part 1: 1-Minute Introduction (0:00 – 1:00)
**Visual Setup**: Webcam in top corner, browser or title slide on main screen.

> **Spoken Audio**:  
> *"Hi everyone, I’m Praveen. I specialize in building robust backend systems and production AI architectures. Today, I’m presenting the VoltKart Multi-Source Grounded Assistant—a full-stack analytical chat system that answers complex questions across uploaded relational CSV tables, multi-version dated documents, and live web search.*
>
> *In enterprise analytics, generic LLM apps fail in predictable ways: they hallucinate arithmetic, they naively pick the newest document while ignoring older active clauses, and they cannot produce tamper-evident audit trails.*
>
> *To eliminate these failure modes, I engineered this system around five non-negotiable truth invariants:*
> 1. *The LLM never computes arithmetic, sorting, or counting—all math is executed deterministically in DuckDB SQL or Python.*
> 2. *Document versions are resolved per fact in code—never by naive date filtering at retrieval time.*
> 3. *Every single number and claim has a machine-verified citation with verbatim quotes or executed SQL.*
> 4. *All generated SQL runs in a layered read-only DuckDB sandbox with AST allowlisting and fan-out reconciliation.*
> 5. *Zero hardcoding of brand names, stores, or IDs exists anywhere in the codebase—the system generalizes to any company data.*
>
> *Let's see the application in action in one continuous take."*

---

### Part 2: Live Walkthrough in One Continuous Take (1:00 – 6:30)
**Visual Setup**: Full browser view of `http://localhost:5173/`. Start with an empty library.

#### Step 1: Zero-State & File Upload (1:00 – 2:00)
> **Action**: Point to the clean, empty interface. Show the sidebar with no chats and empty Versioned Files Library.  
> **Spoken Audio**:  
> *"Here is the application in its clean initial state. Notice the deliberate instrument-panel design: warm neutral paper tones, high-contrast monospace tabular typography, and zero distracting AI gradients.*
>
> *Let's click 'Upload Files' in the sidebar and select our complete enterprise dataset: 6 relational CSV tables and 8 dated policy and job description documents across PDF, DOCX, and TXT formats.*
>
> *[Action: Select all files from `data/sample_bundle/` and click Open]*
>
> *As files upload, our backend processes them immediately:  
> Tables are statistically profiled into DuckDB, inferring primary and foreign key containment relationships.  
> Documents are parsed structurally, extracting effective dates from headers and filenames, grouping them into version families, and indexing chunks into SQLite FTS5 alongside dense vector embeddings.*
>
> *[Action: Click 'Ingestion Card' button in top header]*  
> *Notice our Ingestion Summary card: all 6 tables profiled with row counts, and our document families cleanly cataloged with active date ranges."*

#### Step 2: Table Analytics & Grounded Charts (2:00 – 3:30)
> **Action**: Click in chat input. Type Demo Query 1.  
> **Copy-Paste Query 1**:  
> ```text
> What was the total revenue for the Audio category in 2025?
> ```
> **Spoken Audio**:  
> *"Let's ask an analytical query against the relational database.*
>
> *[Action: Hit Enter. Point to SSE streaming status updates]*  
> *Notice the real-time pipeline telemetry streaming via SSE: 'Analyzing database schemas...', 'Executing sandboxed query...'.*
>
> *The assistant responds: 'In 2025, total revenue for the Audio category was ₹29,41,398.10 across Delivered orders.'  
> Now let's open the Evidence Drawer on the right.  
> Here is the exact SQL executed: it joined `order_items`, `orders`, and `products`, filtered strictly on `order_status = 'Delivered'`, and aggregated line amounts accounting for item discounts.  
> The LLM did not calculate this ₹29.41 Lakh—DuckDB calculated it, and our numeric grounding validator verified that the number appears in the executed result rows before displaying it.*
>
> *Now let's ask for an analytical chart:"*
>
> **Copy-Paste Query 2**:  
> ```text
> Show a bar chart of total revenue by product category in 2025.
> ```
> **Spoken Audio**:  
> *"[Action: Hit Enter. Observe inline chart rendering]*  
> *Look at that: an inline bar chart rendered with exact tabular numerals for Laptops, Smartphones, TVs, and Audio. In accordance with Spec Bonus B10, the LLM emits only a chart specification—every bar height and label is derived directly from stored SQL rows, verified against hallucination."*

#### Step 3: Multi-Version Document QA & Fallback Disclosure (3:30 – 4:45)
> **Action**: Click `+ New Chat` in sidebar.  
> **Spoken Audio**:  
> *"Now let's switch to a fresh conversation to see our deterministic version resolver.*
>
> *Our dataset contains three successive versions of the Return Policy: April 2024 (v1.0), January 2025 (v2.0), and September 2025 (v3.0).  
> In April 2024, cash refunds were issued as store credit. In January 2025 (Section 3), the rule was updated to bank transfer via UPI. In the latest September 2025 revision, that entire section was consolidated and omits cash refunds entirely.*
>
> *A standard RAG system filtering to the newest September 2025 document would fail and say 'not mentioned'. An unranked retriever might pull the obsolete 2024 store credit rule. Watch what VoltKart does:"*
>
> **Copy-Paste Query 3**:  
> ```text
> How are cash purchases refunded under the return policy?
> ```
> **Spoken Audio**:  
> *"[Action: Hit Enter]*  
> *The assistant responds: 'According to VoltKart_Return_Policy_2025-01-15.docx (dated 2025-01-15, Section 3): cash purchases are refunded via bank transfer (UPI). Note: Subsequent revision (2025-09-01) is silent on this matter, so the 2025-01-15 policy remains active.'*
>
> *[Action: Open Evidence Drawer]*  
> *Look at the Evidence Drawer: it shows the Version Timeline. January 2025 is the winner; September 2025 is flagged as silent (triggering mandatory fallback disclosure); and April 2024 is tracked as superseded. Every quote is verified against the stored text."*

#### Step 4: Server-Gated Web Search & Audit PDF Export (4:45 – 6:30)
> **Action**: Show the 'Web Search' checkbox in the composer. Ensure it is UNCHECKED.  
> **Copy-Paste Query 4**:  
> ```text
> What is Croma's return window for smartphones?
> ```
> **Spoken Audio**:  
> *"Now let's test our server-side web search gate (Bonus B8). With Web Search toggled OFF, let's ask about an external competitor.  
> [Action: Send query]*  
> *The assistant honestly abstains: 'I cannot answer this question from the uploaded sources, and web search is disabled.' Our automated test harness verifies that zero outbound HTTP calls were initiated.*
>
> *Now, let's toggle Web Search ON and ask for a live comparison:"*
>
> **Copy-Paste Query 5**:  
> ```text
> [web ON] What is Amazon India's return window for smartphones, and how does that compare with our store policy?
> ```
> **Spoken Audio**:  
> *"[Action: Send query with Web ON]*  
> *With web enabled, the assistant queries the live web, extracts Amazon India's 7-day service center replacement policy, cites the URL and UTC retrieval time, and compares it directly with our uploaded store policy's 7-day return and refund window.*
>
> *Now, let's export our conversation for auditing.  
> [Action: Click 'Export PDF' in the top header]*  
> *The backend generates a publication-grade PDF via ReportLab.  
> [Action: Open the downloaded PDF in browser]*  
> *Notice the clean layout: complete conversation history, UTC timestamps, monospace SQL blocks, embedded chart images, verbatim quotes, and crisp Indian Rupee (₹) glyphs using bundled Noto Sans TrueType fonts."*

---

### Part 3: Architecture Walkthrough (6:30 – 8:30)
**Visual Setup**: Display `docs/ARCHITECTURE.md` showing the Mermaid diagram.

> **Spoken Audio**:  
> *"Now let's examine the end-to-end architecture of how a question flows from the UI to the final verified answer.*
>
> *1. **Request Intake & Contextualization**:  
> When the user submits a prompt, it arrives at our FastAPI backend via Server-Sent Events. The contextualizer resolves pronouns and entity memos from preceding turns without letting context leak across different chat IDs.*
>
> *2. **Query Intent Classification**:  
> The router determines whether the inquiry requires Tabular SQL analytics, Document Version Resolution, Mixed Cross-Modal reasoning, or Web Search.*
>
> *3. **Tabular Execution Sandbox**:  
> For table queries, the planner constructs a single DuckDB SQL query against our generated schema card. Before execution, the SQL passes through a strict `sqlglot` AST allowlist: only a single `SELECT` is allowed; all DDL, DML, and filesystem calls like `read_csv` are rejected. The query runs in a read-only DuckDB sandbox with external access disabled and a 100-row cap.  
> Crucially, our Join Fan-Out Reconciliation check verifies that joined sums match unjoined base totals.*
>
> *4. **Document Pipeline & Claim Resolution**:  
> For policy queries, compound questions are decomposed into atomic facts. We perform hybrid retrieval combining SQLite FTS5 BM25 with local dense embeddings. Sibling section expansion pulls matching sections from all versions of the document family. We extract claims per version, machine-verify that quotes are exact normalized substrings of the source chunk, and pass them to our deterministic version resolver.*
>
> *5. **Response Assembly & Grounding**:  
> Our code-level numeric grounding validator scans the final prose text against the executed SQL query rows. If any number lacks provenance, the prose is discarded and replaced with a direct tabular rendering to guarantee zero hallucination."*

---

### Part 4: Code Walkthrough (8:30 – 11:00)
**Visual Setup**: VS Code open with project files.

#### 1. Table Joins & Sandbox Defense
> **Action**: Open [backend/sql_sandbox.py](file:///c:/Users/svspr/OneDrive/Desktop/Codemonk%20Assignment/backend/sql_sandbox.py). Highlight `reconcile_component_sum` and AST validation.  
> **Spoken Audio**:  
> *"Let's look at `backend/sql_sandbox.py`.  
> Here at line 75, we configure DuckDB with `read_only=True` and `SET enable_external_access = false`.  
> At line 140 is `reconcile_component_sum`. When an LLM joins `returns` to `orders` and `order_items`, multi-item orders can fan out and inflate refund amounts. This function queries the unjoined `returns` table directly and verifies that the sum of joined regional components matches the true unjoined total within a 0.01 tolerance.*
>
> *And in `backend/grounding.py`, `verify_numeric_grounding` extracts every float from the generated text and asserts that each appears in the DuckDB query rows or question text."*

#### 2. Document Version Resolution & Quote Verification
> **Action**: Open [backend/version_resolver.py](file:///c:/Users/svspr/OneDrive/Desktop/Codemonk%20Assignment/backend/version_resolver.py). Highlight `verify_verbatim_quote` and `resolve_fact_across_versions`.  
> **Spoken Audio**:  
> *"Now let's examine `backend/version_resolver.py`.  
> Here at line 34 is `verify_verbatim_quote`. It normalizes unicode punctuation and verifies that every line of an evidence quote exists verbatim in the chunk content before any claim can be accepted.  
> Below at line 81 is `resolve_fact_across_versions`. Notice that it sorts verified claims chronologically by document date. It picks the newest version that explicitly states the fact. If newer versions exist in the family but are silent, it sets `fallback_used = True`, records the newer silent files, and compiles superseded facts for complete provenance."*

#### 3. Citations, Memory & Chat Export
> **Action**: Open [backend/assistant.py](file:///c:/Users/svspr/OneDrive/Desktop/Codemonk%20Assignment/backend/assistant.py) and [backend/pdf_export.py](file:///c:/Users/svspr/OneDrive/Desktop/Codemonk%20Assignment/backend/pdf_export.py).  
> **Spoken Audio**:  
> *"In `backend/assistant.py`, every chat operation is strictly scoped by `chat_id` in SQLite WAL mode. Conversations survive backend process restarts without leakage across threads.  
> And in `backend/pdf_export.py`, we use ReportLab with bundled Noto Sans TrueType fonts to ensure publication-grade exports with native Indian Rupee glyphs and embedded analytical charts."*

---

### Part 5: One Design Decision & Rejected Alternative (11:00 – 12:30)
**Visual Setup**: VS Code open at `backend/version_resolver.py` or Architecture Diagram.

> **Spoken Audio**:  
> *"Now I want to discuss a critical architectural design decision: **Deterministic Code-Level Claim Resolution versus Retrieval-Time Date Filtering**.
>
> **The Alternative Rejected**:  
> A standard RAG pattern filters candidate documents by date at retrieval time, feeding only the 'newest document' into the LLM context. Another common alternative is dumping all document versions into the prompt and asking the LLM to 'figure out which policy is current'.
>
> **Why I Rejected Both**:  
> In real enterprise operations, policy revisions are modular. A new revision updates one specific term—like smartphone return days—while remaining completely silent on older terms, like cash refund methods or warranty limits.  
> If you filter at retrieval time, you discard the older active policy and falsely claim the fact is missing.  
> If you prompt the LLM to reconcile versions, models frequently suffer from recency bias or hallucinate merged terms.
>
> **The Decision Made**:  
> We retrieve across ALL document versions. We extract claims per version, verify quotes in code, and resolve facts in deterministic Python logic. The newest stating document wins, and silent newer revisions are explicitly disclosed. This is explainable, deterministic, and verifiable line by line."*

---

### Part 6: Where System Fails & Known Limitations (12:30 – 14:00)
**Visual Setup**: Display [docs/KNOWN_LIMITATIONS.md](file:///c:/Users/svspr/OneDrive/Desktop/Codemonk%20Assignment/docs/KNOWN_LIMITATIONS.md) and terminal.

> **Spoken Audio**:  
> *"No engineering defense is complete without showing where the system fails.
>
> **Real Failure Example: Unnormalized Category Slang**:  
> In our database, product categories are strictly named `'Audio'`, `'Laptops'`, `'Smartphones'`.  
> If a user asks: *'What was our revenue from sound equipment or audio gear in 2025?'*, an LLM may generate:  
> `WHERE category = 'Sound equipment'` or `WHERE category LIKE '%gear%'`.  
> Because DuckDB executes exact relational SQL without fuzzy word matching, the query returns 0 rows.  
> Rather than hallucinating revenue, our system outputs: *'Query returned 0 rows for category: Sound equipment'*.  
>
> **Mitigation & Future Work**:  
> We document this in `docs/KNOWN_LIMITATIONS.md`. In production, this is mitigated by injecting distinct column categorical values directly into the schema card and using vector similarity over categorical column distincts before SQL generation.
>
> **Verification Rigor**:  
> To guarantee reliability, our entire system passes seven verification layers: linting, formatting, no-hardcoding scans, 154 unit tests, golden evaluations, synthetic variant bundles, and a calibrated 6-dimension judge scoring 100%.
>
> *Thank you! I’m Praveen, and I look forward to walking through any line of code during our live technical discussion."*

---

## Comparison Table: What They Asked For vs. What We Built More

| Dimension | Take-Home Assignment Requirement | VoltKart Implementation (What We Built More) |
|---|---|---|
| **C1: Chat UI** | Web-based chat UI with user/assistant turns | Instrument-panel UI with design tokens, SSE real-time streaming, collapsible thought disclosures, and structured Evidence Drawer. |
| **C2: Ingestion** | Upload CSV, PDF, DOCX, TXT | Sniffs delimiters & encodings (UTF-8, UTF-16, latin-1), structure-aware chunking, date parser with 12 formats, and interactive Ingestion Summary card. |
| **C3: Table QA** | Answer questions from CSV tables | DuckDB SQL engine, `sqlglot` AST validator, read-only sandbox, join fan-out reconciliation check (`R-020`), and code-enforced numeric grounding (`R-003`). |
| **C4: Document QA** | Date-aware document question answering | Multi-version hybrid retrieval (FTS5 + dense vectors), sibling section expansion, code-level verbatim quote verification (`R-019`), and deterministic claim-level resolver (`R-001`). |
| **C5: Citations** | Document name + date + page/quote; SQL tables used | Machine-verified citations with exact normalized quotes, executed SQL, row previews, version timelines with fallback disclosure, and honest abstention. |
| **C6: Memory** | Conversational memory across turns; isolation | Thread isolation strictly scoped by `chat_id`, multi-turn entity memos (`interpreted_as`), and SQLite WAL persistence surviving hard process restarts. |
| **C7: PDF Export** | Export chat session to PDF | ReportLab publication-grade PDF generator with bundled TrueType Noto Sans font for `₹` glyphs, table formatting, and embedded charts. |
| **Bonus B8** | Web Search (external comparison) | Server-side web gate (asserts 0 outbound calls when OFF), live web page fetching, and dynamic multi-source comparative reasoning when ON. |
| **Bonus B9** | Multiple Chat Sessions | Full sidebar thread manager with thread creation, deletion, rename, and automated planted-marker cross-chat isolation verification. |
| **Bonus B10** | Analytical Charts | Native SVG bar and line charts rendered from stored SQL rows, verified against hallucinated values, and re-rendered into export PDFs. |
| **Engineering Rigor** | Standard functional implementation | **7-Layer Automated Verification Stack** (`scripts/runner.py verify`), Calibrated 6-Dimension Judge (100% score), and Synthetic Variant Generator testing generalization. |
