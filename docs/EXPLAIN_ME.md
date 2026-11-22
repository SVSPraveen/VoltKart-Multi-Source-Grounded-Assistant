# EXPLAIN_ME.md — Live Technical Defense Guide

This guide is the module-by-module defense manual for the live technical review. It details the role of each module, the engineering rationale, alternatives evaluated and rejected, and three rigorous interview questions with verified code-level answers.

---

## 1. `backend/sql_guard.py` — AST Security Guard

### Role in Pipeline
Inspects, sanitizes, and authorizes LLM-generated SQL queries before they touch the database engine.

### Design Rationale
LLM agents cannot be trusted with raw SQL execution. Regex-based blacklists are notoriously easy to bypass with comments, whitespace obfuscation, or nested subqueries. `sql_guard.py` parses queries into an Abstract Syntax Tree (AST) using `sqlglot` under the DuckDB dialect and enforces structural allowlists.

### Alternatives Rejected
1. *Regex Keyword Blacklisting (`r"(?i)\bDROP\b"`) Rejected*: Trivial to evade using comments (e.g., `DROP/**/TABLE`), Unicode lookalikes, or dialect-specific escapes.
2. *Read-Only SQLite PRAGMA Rejected*: Does not prevent resource-exhaustion attacks (CPU/RAM locks) or access to internal introspection tables.

### Hard Interview Questions & Defense
- **Q1: What happens if an attacker crafts `SELECT 1; DROP TABLE orders;`?**
  - *Answer*: `sqlglot.parse(sql)` returns a list of expression trees. `sql_guard.py` asserts `len(expressions) == 1`. Multiple statements are rejected immediately before inspection.
- **Q2: Can an attacker leak data using `SELECT * FROM read_csv('/etc/passwd')`?**
  - *Answer*: No. `sql_guard.py` walks the AST nodes looking for `exp.Anonymous` and `exp.Func` calls. Any function matching `read_csv`, `read_parquet`, `httpfs`, or internal introspection prefixes (`duckdb_*`, `sqlite_*`, `pg_*`) triggers an immediate `SecurityError`.
- **Q3: Does the AST allow CTEs (`WITH` clauses) and nested subqueries?**
  - *Answer*: Yes. `WITH` expressions and subqueries are authorized as long as the parent and child AST structures belong strictly to the `Select` family and do not perform mutations or external file reads.

---

## 2. `backend/sql_sandbox.py` — Dual-Connection Sandbox

### Role in Pipeline
Manages connection lifecycles, configuration locking, row caps, and execution timeouts.

### Design Rationale
Security requires defense-in-depth: even if an AST parser had a flaw, the underlying database connection itself must be physically incapable of mutating data or reaching the filesystem.

### Alternatives Rejected
1. *Single Shared Read-Write Connection Rejected*: Leaving write privileges active on connections executing LLM queries introduces unacceptable risk of accidental or malicious data modification.
2. *In-Memory Temporary Copies per Query Rejected*: Copying tables on every request incurs high latency and memory overhead on multi-hundred-megabyte datasets.

### Hard Interview Questions & Defense
- **Q1: How do you guarantee the connection cannot write to disk?**
  - *Answer*: DuckDB connections are opened with `read_only = True`. Additionally, on connection initialization, we execute `SET enable_external_access = false;`, which disables all filesystem writes, external network sockets, and extension loading.
- **Q2: What prevents a malicious query from freezing the server with a Cartesian product?**
  - *Answer*: Query execution is offloaded to a `ThreadPoolExecutor` wrapped in `future.result(timeout=5.0)`. If execution exceeds 5 seconds, the task is cancelled, the thread connection is terminated, and a timeout error is raised.
- **Q3: How do you prevent out-of-memory errors from `SELECT * FROM big_table`?**
  - *Answer*: We never call `cursor.fetchall()`. Results are retrieved using `cursor.fetchmany(row_cap)` where `row_cap` defaults to 50, capping serialization overhead.

---

## 3. `backend/version_resolver.py` — Deterministic Version Resolver

### Role in Pipeline
Resolves the true answer and citation provenance across multi-version document families.

### Design Rationale
Naive RAG models fail when policies change across dates: filtering to the latest document produces silent false negatives if the latest revision omits older clauses, while unfiltered retrieval produces contradictory answers. `version_resolver.py` implements deterministic, code-based per-fact resolution.

### Alternatives Rejected
1. *"Filter to Newest Document" Rejected*: Fails when older versions state enduring rules that the newest revision omitted for brevity (e.g., damaged delivery reporting in 2024-04-01).
2. *LLM-as-a-Judge Version Arbitrator Rejected*: Non-deterministic, prone to recency bias, and susceptible to hallucinated compromise dates.

### Hard Interview Questions & Defense
- **Q1: If Version 3.0 is silent on a topic, how does the system know not to hallucinate that the topic is deprecated?**
  - *Answer*: The resolver extracts candidate facts per version. It identifies the most recent version that *explicitly states the fact* (e.g., Version 1.0). It compares this date to the newest document date in the family (Version 3.0). If the newest document is newer but silent, it answers from Version 1.0 and mandates an explicit version disclosure statement.
- **Q2: How are document effective dates extracted reliably from messy formats?**
  - *Answer*: `backend/date_parser.py` runs a multi-tier date extractor: ISO (`YYYY-MM-DD`), European (`DD/MM/YYYY`), US (`MM/DD/YYYY`), alphanumeric (`01-Sep-2025`), and spelled out (`September 1, 2025`). It records the extraction source (`filename` vs `header_text` vs `first_paragraph`) for auditing.
- **Q3: How do you handle two versions with the exact same date?**
  - *Answer*: The resolver uses version numbering tie-breaking (`v2.1` > `v2.0`). If version numbers are identical, it falls back to SHA-256 hash ordering to guarantee 100% deterministic reproducibility across runs.

---

## 4. `backend/grounding.py` — Numeric Grounding Engine

### Role in Pipeline
Verifies that numbers, currency values, and counts in assistant responses are derived strictly from executed SQL queries or document facts.

### Design Rationale
Truth Rule 3: The LLM must never perform arithmetic, sorting, or counting. `grounding.py` enforces this by scanning generated response text for numerical tokens and asserting that each token appears in the query result set within a 0.01 tolerance.

### Alternatives Rejected
1. *Relying on LLM System Prompts ("Do not guess numbers") Rejected*: Empirically proven to fail on complex joins, percentage calculations, and multi-tier filters.
2. *String Regex Matching Alone Rejected*: Fails on formatting differences (e.g., `5839148.75` vs `58,39,148.75` vs `₹58.39 Lakhs`).

### Hard Interview Questions & Defense
- **Q1: How do you handle formatted currency strings like `₹58,39,148.75`?**
  - *Answer*: The grounding normalizer strips currency symbols (`₹`, `$`, `INR`), removes Indian and Western comma delimiters, and parses the value into a standard IEEE float before comparing against the SQL result set.
- **Q2: What happens if an LLM rounds `5839148.75` to `58.39 Lakhs`?**
  - *Answer*: The normalizer understands multiplier suffixes (`Lakh`, `Crore`, `M`, `K`). It scales the value to its baseline float and asserts that `abs(parsed_val - raw_sql_val) <= 0.01`.
- **Q3: What if the LLM states a valid year (e.g., `2025`) that was not in the SQL result columns?**
  - *Answer*: The grounding validator differentiates *dimension constraints* present in the user query (e.g., `2025`, `Q1`) from *computed metric values*. Query parameters are whitelisted; computed metrics are strictly bound to query outputs.

---

## 5. `backend/retrieval.py` — Hybrid Search & Sibling Expansion

### Role in Pipeline
Retrieves relevant document chunks using lexical FTS5, dense semantic embeddings, and structural sibling expansion.

### Design Rationale
Lexical search excels at exact entity codes, policy clause numbers, and acronyms (`O00174`, `VoltCare`, `ANC`). Dense semantic embeddings excel at paraphrased questions. Combining them via Reciprocal Rank Fusion (RRF) yields higher recall than either method alone.

### Alternatives Rejected
1. *Pure Dense Vector Search Rejected*: Consistently misses exact SKU codes, order IDs, and clause section numbers.
2. *Pure Keyword Search Rejected*: Misses conceptual synonyms (e.g., "broken package" vs "damaged on delivery").

### Hard Interview Questions & Defense
- **Q1: What is "Sibling Expansion" and why is it essential for version resolution?**
  - *Answer*: Document chunks often split a policy rule across boundaries (e.g., Section 4 header in chunk A, conditions in chunk B). Sibling expansion retrieves neighboring chunks with the same `file_sha256` and adjacent `section_title` or page numbers, ensuring that the version resolver sees the full context rather than a truncated fragment.
- **Q2: What embedding model is used and does it require external network access?**
  - *Answer*: We use `fastembed` with `BAAI/bge-small-en-v1.5`. Embeddings run locally via ONNX runtime on the CPU, ensuring 100% offline functionality with zero external API calls or latency spikes.
- **Q3: How are verbatim quotes verified?**
  - *Answer*: When a citation is created, `grounding.py` searches for the exact substring inside the stored document text. If formatting differences exist, it runs whitespace-normalized substring matching. If the quote cannot be verified in the stored document, the citation is flagged as ungrounded.

---

## 6. `backend/export_pdf.py` — ReportLab Export Engine

### Role in Pipeline
Renders complete, auditable conversation transcripts into publication-grade PDF documents.

### Design Rationale
Judges and auditors require a tamper-evident, permanent record of the interaction, showing timestamps, role switches, executed SQL queries, verbatim quotes, and re-rendered charts.

### Alternatives Rejected
1. *Headless Browser HTML-to-PDF (e.g., Puppeteer / WeasyPrint) Rejected*: Fragile pagination, poor page-break control over tables/code blocks, and complex font dependencies across operating systems.
2. *Client-side JS PDF Generation Rejected*: Prone to font rendering differences, lacks cryptographic consistency, and cannot re-render server-side chart vectors cleanly.

### Hard Interview Questions & Defense
- **Q1: How do you prevent the Indian Rupee symbol (`₹`) from rendering as a tofu block or garbled character?**
  - *Answer*: ReportLab's standard Helvetica font does not contain glyph U+20B9. We bundle and register the open-source TrueType font `Noto Sans` (`NotoSans-Regular.ttf` and `NotoSans-Bold.ttf`) via `pdfmetrics.registerFont(TTFont(...))`.
- **Q2: How do you prevent long SQL queries and wide tables from clipping off the page?**
  - *Answer*: SQL statements are wrapped in Platypus `Paragraph` elements inside single-cell `Table` flowables with explicit column width constraints and line-breaking enabled, preventing horizontal overflow.
- **Q3: How are charts rendered in the PDF?**
  - *Answer*: Charts are not saved as client-side DOM screenshots. Instead, `backend/charts.py` takes the stored chart specification and queries rows, rendering a clean 300 DPI image via `matplotlib` which is embedded into the Platypus story using `reportlab.platypus.Image`.

---

## 7. `backend/web_search.py` — Server-Gated Search

### Role in Pipeline
Provides live web search capabilities (B8) with strict server-side gating.

### Design Rationale
Spec Section 7.8 & R-011 require server-side tool gating: when the web search toggle is OFF, the assistant must not have access to search tools and zero network calls must occur. When ON, top pages are fetched and read rather than trusting raw snippets.

### Alternatives Rejected
1. *Client-Side Only Toggle Rejected*: The LLM could still hallucinate search calls if the tool definition remained bound in the system prompt.
2. *Relying on Raw Snippets Rejected*: Search engine snippets are frequently outdated, truncated, or SEO-manipulated. Factual verification requires reading the live fetched HTML page.

### Hard Interview Questions & Defense
- **Q1: How do you prove that no network calls are made when web search is OFF?**
  - *Answer*: We maintain an audited call counter `_OUTBOUND_SEARCH_COUNT`. When `web_enabled == False`, the web tool is omitted from the agent's available tools. Unit test `test_server_gated_web_search_off` asserts that `_OUTBOUND_SEARCH_COUNT == 0` for question Q17.
- **Q2: What happens if Tavily API key is missing?**
  - *Answer*: The system gracefully falls back to a keyless DuckDuckGo scraper using `httpx` and `lxml`. This ensures the project builds and runs on a fresh machine without external accounts.
- **Q3: How does the system handle mixed web and document questions (Q18b)?**
  - *Answer*: The agent partitions the answer: the external fact (Amazon return window) is cited with web title, URL, and retrieval timestamp, while the internal fact (VoltKart return policy) is cited with document filename, date, and verbatim quote.
