# REVIEW.md — the project's memory of its own mistakes

Two jobs: (A) the **Review Protocol** used on every change, (B) the **Rules Log** that grows every time something goes wrong.
Read the whole file at the start of every phase and before every commit.

---

## A. Review Protocol

Run on the diff of every phase (and on any risky change in between). Best run in a fresh conversation that sees only
this file and the diff, so the reviewer is not anchored by the author's reasoning. If the model picker offers a
different model family from the one that wrote the code, use it for this pass.

Fill the two brackets, paste the real `git diff`, and send exactly:

```
<context>This change is meant to [goal]. It runs in [environment].</context>
<diff>[paste diff]</diff>

Review for bugs, missing edge cases and security problems. Skip style preferences.
For each finding, give the file and line, what breaks, the input that triggers it, and a suggested fix.
Rank by severity. If you find nothing serious, say so and do not pad the list.
```

**How to treat the output**
- Every finding is reproduced before it is fixed: write the failing test or the failing input first. If it can't be reproduced, say so and mark the finding `UNCONFIRMED` (don't "fix" what you can't show).
- Severity: **S1** wrong or fabricated answer, data loss, security hole · **S2** wrong in an edge case, silent failure, flaky test · **S3** poor error message, missing state in UI.
  S1/S2 block the gate. S3 goes on the PROGRESS list.
- "Nothing serious found" is a valid and good result. A reviewer who pads the list is wrong.
- Then add a rule to section B if the finding reveals a *class* of mistake, not just a one-off.

---

## B. Rules Log

**Format (append, never rewrite history):**

```
### R-NNN — short title
- Status: predicted | observed
- Context: what happened or what we expect to go wrong
- Rule: the instruction to follow from now on
- Check: the test / grep / command that proves the rule is followed
```

`predicted` = a pre-mortem from reading the brief and the sample data before any code existed. When a predicted risk
actually bites, change its status to `observed` and add the date and commit.

### R-001 — Never resolve versions by "newest document only"
- Status: predicted
- Context: In the sample bundle the newest policy omits facts that only older versions state (damaged-on-delivery window,
  non-returnable items, who the role reports to, warranty claims limit). Filtering to the newest document answers "not found" — wrong.
- Rule: retrieve across all versions; extract per version; pick the newest version that *states the fact*; if that is not the newest
  version overall, say which version the answer came from. The pick is made in code, not by the LLM.
- Check: golden Q8, Q9, Q11, Q12 pass; unit test with a synthetic 3-version family where the newest is silent.

### R-002 — Metric definitions come from the data dictionary, not from guesses
- Status: predicted
- Context: "Revenue" = line amounts of *Delivered* orders only; line amount = qty × unit_price × (1 − discount/100);
  `list_price` is not what was charged. Including Cancelled orders or using list price gives plausible-looking wrong numbers.
- Rule: load business definitions from the uploaded dictionary into the SQL agent's context. If none exists, state the
  assumption you made inside the answer.
- Check: golden Q1, Q2, Q15, Q16, Q19 (numbers to the paisa); variant bundle where the definition differs.

### R-003 — The LLM does no arithmetic
- Status: predicted
- Rule: counts, sums, percentages, date differences, sorting and "top N" are computed by SQL/Python. Final answers pass a
  numeric-grounding check: every number in the prose must appear in an executed result (or be a trivially derived value computed in code).
- Check: unit test with an answer containing an invented number → must be rejected/regenerated.

### R-004 — Ambiguous wording: choose, state, mention the alternative
- Status: predicted
- Context: "returned most often" = number of return records vs units returned; the two rank different products in the sample data.
- Rule: pick the most natural reading, state the definition in one clause, and mention the other reading when it changes the answer.
- Check: golden Q3 (`must_include` + alternative noted).

### R-005 — No sample-specific strings in application code
- Status: predicted
- Rule: grep gate over `backend/` and `frontend/src/` for sample entity names, ids and document titles.
  Generalise with a variant bundle (renamed brand, shifted numbers, changed date formats, different file formats per version).
- Check: `make no-hardcode`; `tests/variants/` answers match pandas recomputation.

### R-006 — An explicit exception overrides the general rule it names
- Status: predicted
- Context: the policy gives tier-based return windows *and* a smartphone exception for all tiers. Applying the tier window to a phone is wrong.
- Rule: when answering from policy text, look for exceptions, waivers, and "unless/except" clauses relevant to the specific item and customer before concluding.
- Check: golden Q13.

### R-007 — Don't invent fields that aren't in the data
- Status: predicted
- Context: `orders.csv` has `order_date` but no delivery date. A question can supply "12 days after delivery" itself.
- Rule: use user-supplied facts as stated, label them as user-supplied, and never fabricate a delivery date.
- Check: golden Q13 `traps`.

### R-008 — Verify the premise of the question against the data
- Status: predicted
- Context: four customers are called Kavya; the question names Kavya Kapoor and an order id.
- Rule: resolve the person from the order, then confirm the name matches. On mismatch or ambiguity, say so (or ask) instead of silently picking one.
- Check: golden Q13; adversarial probe A10.

### R-009 — SQL tool hardening is layered
- Status: predicted
- Context: DuckDB can read arbitrary local files (`read_csv('/etc/passwd')`) unless external access is disabled.
- Rule: allowlist via sqlglot AST (single SELECT) + read-only connection + `enable_external_access=false` + locked configuration + row cap + timeout.
  Any one layer failing must not be enough.
- Check: adversarial probes A6, A7; unit tests for each layer in isolation.

### R-010 — Prompt injection through uploaded content
- Status: predicted
- Rule: retrieved text is wrapped as quoted data with explicit delimiters; the system prompt says it is untrusted; tools have no side effects beyond read-only queries and (when enabled) search.
- Check: fixture document and CSV cell containing injection text; assistant answers normally and does not follow it.

### R-011 — Web toggle is enforced by the server
- Status: predicted
- Rule: UI state is advisory. The server decides from the request flag whether the search tool exists in the agent's toolset. Web state is stored per message for the export.
- Check: Q17 test counts outbound search calls (must be 0 when off).

### R-012 — Chats must not leak
- Status: predicted
- Rule: all history/memory queries filter by `chat_id`; no module-level caches keyed without it.
- Check: golden Q19/Q20; two-chat integration test with a planted marker phrase.

### R-013 — The rupee sign must render in the PDF
- Status: predicted
- Context: base-14 PDF fonts lack ₹; boxes or missing glyphs appear silently, and text extraction can still "pass".
- Rule: bundle a Unicode TTF that has U+20B9 (e.g. Noto Sans, OFL), embed it, and verify by rasterising a page and looking at it.
- Check: `tests/e2e/test_export.py` rasterises page 1; the agent views the image.

### R-014 — Chart numbers are read from stored rows
- Status: predicted
- Rule: the LLM chooses chart type/title/axis labels and *references* a stored query result; it never types data values.
- Check: Q15/Q16/Q19 compare chart series to golden; unit test that a hand-edited spec value is rejected.

### R-015 — Free tiers rate-limit; don't confuse that with bugs
- Status: predicted
- Rule: central LLM client with throttling, exponential backoff on 429/5xx, provider fallback, and a dev-time response cache.
  Live evals run serially with pacing. Record the provider + model + date in every eval report.
- Check: eval harness retries and reports 429s separately from failures.

### R-016 — A judge model is evidence, not a verdict
- Status: predicted
- Rule: deterministic assertions first. The LLM judge gets the question, the golden answer, the app's answer and citations,
  returns JSON, and is calibrated by feeding it deliberately wrong answers (it must flag them). It can fail a build, never pass one alone.
- Check: `tests/judge/test_calibration.py`.

### R-017 — Mixed date formats and untrusted dates
- Status: predicted
- Context: dates appear as `2025-09-01`, `1 April 2024`, `20 October 2025`, `15 January 2025` (body) and `YYYY-MM-DD` (file name).
- Rule: parse with a tolerant parser; the date in the body is primary, the file name is the fallback; if both exist and disagree, flag it in the UI.
  An undated file is ranked last and labelled "undated".
- Check: unit tests over all formats seen + a conflicting pair.

### R-018 — Tables inside documents are content
- Status: predicted
- Rule: DOCX and PDF tables are extracted (cell text preserved with row/column structure) and chunked with their section heading.
  A policy might present the tier windows as a table in a reviewer's file.
- Check: variant bundle where the return windows live in a table.

### R-019 — Citation quotes are verified, not trusted
- Status: predicted
- Rule: a document citation's quote must be a normalised substring of the cited chunk; otherwise the citation is dropped and the claim regenerated or removed.
- Check: unit test with a paraphrased (non-verbatim) quote → rejected.

### R-020 — Join fan-out silently inflates sums
- Status: predicted
- Context: orders → items → returns → stores is a chain of one-to-many joins; summing a parent-level column after a child join double counts.
- Rule: aggregate at the right grain; for every aggregate answer run a reconciliation (e.g. component totals equal the unjoined total).
- Check: golden Q5 and Q1 totals; unit test with a deliberately fan-out query.

### R-021 — Streaming must not lose or corrupt history
- Status: predicted
- Rule: persist the assistant message with its citations when streaming finishes; if the client disconnects or the model errors, persist what exists with `status=interrupted|error`. Never leave an orphan user message with no reply row.
- Check: integration test that aborts a stream mid-way, then reloads the chat.

### R-022 — Timestamps
- Status: predicted
- Rule: store UTC with timezone; display in the viewer's local zone; the PDF shows the zone explicitly.
- Check: export test with a fixed clock.

### R-023 — Upload edge cases
- Status: predicted
- Rule: handle and message clearly: same file twice (idempotent by SHA-256), same name with different content, BOM / non-UTF-8 CSV, `;` delimiters, empty files, encrypted or scanned PDFs, legacy `.doc`, oversize files, path-traversal in file names, wrong MIME vs extension.
- Check: one test per case; no stack trace ever reaches the UI.

### R-024 — Commit history is a deliverable
- Status: predicted
- Rule: small conventional commits after each green step; no single giant "initial commit".
- Check: `git log --oneline` reviewed at each gate.

### R-025 — Verify exact column names against schema before querying
- Status: observed (Phase 1, 2026-11-22)
- Context: `verify_golden_numbers.py` initially assumed column names like `manager`, `tier`, `city`, but the actual CSV schemas used `store_manager`, `loyalty_tier`, `home_city`.
- Rule: Always inspect real table schemas (`PRAGMA table_info` or `df.columns`) rather than relying on natural language question phrasing or mental models.
- Check: Ingestion profiling test asserts every column referenced in business logic exists in the loaded schema.

### R-026 — Comprehensive regex patterns for entity hardcode gates
- Status: observed (Phase 1, 2026-11-22)
- Context: `scripts/check_no_hardcode.py` initially checked only a few hand-picked IDs (S01-S06, C0118, O00174) and missed S07, S08, store locations (Baner, Koramangala), and 7 store managers.
- Rule: Hardcode scanners must cover all schema entities (all stores, managers, brands) and use structural regexes (`\bS0[1-8]\b`, `\bC0[01]\d{2}\b`, `\bO00\d{3}\b`, `\bI00\d{4}\b`, `\bR0\d{3}\b`) rather than sporadic samples.
- Check: `scripts/check_no_hardcode.py` run via `make no-hardcode` and unit tested across all sample entity classes in `tests/unit/test_no_hardcode.py`.

### R-027 — Generic numeric evaluation across ground truth specs
- Status: observed (Phase 1, 2026-11-22)
- Context: `tests/golden/eval_harness.py` initially only checked `revenue_inr`, `grand_total_inr`, and `by_region_inr`, ignoring all other numeric fields (`spend_inr`, `count`, `returns`, `units`, `in_store_total_inr`, `data_inr`).
- Rule: Truth harnesses must recursively traverse expected ground truth structures to deterministically assert numeric tolerance across all numeric metrics without hardcoding question-specific field names.
- Check: Unit test `test_extract_expected_numeric_values` in `tests/unit/test_eval_assertions.py`.

### R-028 — ISO YYYY-MM-DD parsing must precede dayfirst parser fallback
- Status: observed (Phase 2, 2026-11-22)
- Context: `dateutil.parser.parse(clean_str, dayfirst=True)` misinterpreted ISO dates like `2025-09-01` as `2025-01-09` because dayfirst parsing greedily interpreted the day <= 12 as day rather than month.
- Rule: Always check and parse unambiguous ISO 8601 (`YYYY-MM-DD` / `YYYY/MM/DD`) patterns first before invoking fuzzy or dayfirst date parsers.
- Check: Unit test `test_bundle_date_formats` in `tests/unit/test_date_parser.py` asserting `2025-09-01` -> `2025-09-01`.

### R-029 — Avoid word boundary \b against underscore-separated filename tokens
- Status: observed (Phase 2, 2026-11-22)
- Context: Regex `\b20\d{2}...` failed on filenames like `Policy_2025-01-15.docx` because `_` (underscore) is an alphanumeric word character in Python regex, preventing `\b` from triggering between `_` and `2`.
- Rule: Use negative lookahead/lookbehind `(?<!\d)` and `(?!\d)` rather than word boundaries `\b` when extracting dates from filenames with underscores.
- Check: Unit test `test_extract_date_from_filename` in `tests/unit/test_date_parser.py`.

### R-030 — Explicit connection lifecycle management and table-level reset on Windows
- Status: observed (Phase 2, 2026-11-22)
- Context: `sqlite3.connect` inside `with conn:` only manages transactions, not connection closure, causing file lock `[WinError 32]` when `reset_storage()` attempted to `unlink()` `assistant.db` on Windows.
- Rule: Always close SQLite connections in a `finally:` block and implement test/runtime reset via `DELETE FROM ...` and `DROP TABLE ...` rather than filesystem unlinking.
- Check: Unit tests in `tests/unit/test_api.py` and `tests/unit/test_ingestion_robustness.py`.

### R-031 — Storage resets must clear in-memory table and session registries
- Status: observed (Phase 2, 2026-11-22)
- Context: In unit test execution, `reset_storage()` cleared SQLite and DuckDB tables on disk, but in-memory `_TABLE_PROFILES` and `_LOADED_TABLES` dictionaries retained previously loaded tables, causing table pollution across tests in the same process.
- Rule: Pair storage resets with in-memory registry eviction (via registered reset callbacks or coordinated cleanup) so tests and resets start with completely empty state.
- Check: Unit test suite running multiple table ingestion tests sequentially in the same process.

### R-032 — Date parsing without 4-digit year presence validation hallucinates dates
- Status: observed (Phase 2, 2026-11-22)
- Context: Calling `dateutil.parser.parse("Phase 2", fuzzy=True)` without an explicit 4-digit year used `datetime.now()` for year and month, falsely parsing "Phase 2" as day 2 of the current month. Similarly, month-year dates without day (e.g. "July 2024") hallucinated the current execution day instead of defaulting deterministically to day 1.
- Rule: Date parsers must require a 4-digit year (`19\d{2}|20\d{2}`) to consider a string a candidate document date, and supply a fixed default (`default=datetime(2000, 1, 1)`) so missing day components deterministically default to the 1st of the month.
- Check: Unit tests in `tests/unit/test_date_parser.py` rejecting "Phase 2", "Section 12", "v2.0" and asserting "July 2024" -> "2024-07-01".

### R-033 — Latin-1 decoding hides encoding errors and corrupts UTF-16 byte streams
- Status: observed (Phase 2, 2026-11-22)
- Context: `sniff_delimiter_and_encoding` checked `latin-1` in a fallback loop. Because latin-1 maps all bytes 0x00-0xFF to characters without error, UTF-16 files (with null bytes) were decoded as latin-1, producing corrupted column names with embedded null characters (e.g. `ÿþi d`).
- Rule: Always check for UTF-16 BOMs (`b"\xff\xfe"`, `b"\xfe\xff"`) and detect null bytes `\x00` in raw text samples before attempting single-byte fallbacks; never use latin-1 as a blind default.
- Check: Unit test `test_utf16_csv_ingestion` in `tests/unit/test_tables.py`.

### R-034 — SQL identifiers must be quoted to prevent collisions with reserved keywords
- Status: observed (Phase 2, 2026-11-22)
- Context: Uploading a CSV named `order.csv`, `select.csv`, or `user.csv` caused DuckDB syntax error `Parser Error: syntax error at or near "order"` when creating or dropping unquoted tables.
- Rule: Always wrap table and column identifiers in double quotes (e.g. `CREATE OR REPLACE TABLE "{table_name}"`, `DROP TABLE IF EXISTS "{t_name}"`).
- Check: Unit test `test_sql_reserved_keyword_table_names` in `tests/unit/test_tables.py`.

### R-035 — Data dictionary documentation must not pollute document version families
- Status: observed (Phase 2, 2026-11-22)
- Context: Uploading `DATA_DICTIONARY.md` caused it to be chunked as a 9th document, assigned a fake 5th version family `sample bundle data dictionary`, and parsed with a hijacked date `2024-04-01` from a table cell.
- Rule: Identify data dictionary / documentation files, load them into the schema documentation store for SQL grounding, and exclude them from user document version families.
- Check: `test_data_dictionary_loaded_as_documentation` in `test_ingestion_robustness.py` and `test_full_sample_bundle_ingestion` asserting exactly 8 documents and 4 version families.

### R-036 — sqlglot parses DuckDB table-valued readers as specific AST classes
- Status: observed (Phase 3, 2026-11-22)
- Context: `SELECT * FROM read_csv('/etc/passwd')` bypassed function-name denylists because `sqlglot` parses table-valued readers into `exp.ReadCSV` and `exp.ReadParquet` AST nodes rather than `exp.Func` or `exp.Anonymous`.
- Rule: AST allowlists and denylists must inspect node types explicitly for `exp.ReadCSV`, `exp.ReadParquet`, and table expressions where the source is not a plain identifier.
- Check: `test_reject_forbidden_read_csv` in `tests/unit/test_sql_guard.py` and probe A7.

### R-037 — Allowed numeric grounding pools must include verified code-derived aggregate totals
- Status: observed (Phase 3, 2026-11-22)
- Context: In regional refund aggregation (Q5), the grand total was computed in Python as the sum of regional row amounts. The numeric grounding check rejected the answer because the grand total was not present as an individual cell in the SQL result rows.
- Rule: Numeric grounding verifiers must accept code-derived values (sums of result components, unjoined reconciliation totals) when verified by code against base table queries.
- Check: `test_table_qa_refund_by_region_reconciliation` in `tests/unit/test_sql_agent.py` and Golden Q5 live eval.

### R-038 — Abstention and empty-result prose must not introduce ungrounded calendar dates
- Status: observed (Phase 3, 2026-11-22)
- Context: When answering A8 ("Total revenue in 2027?"), the assistant prose initially included "data ends on 2026-06-30", which tripped numeric grounding because numbers `2026`, `6`, `30` were neither in the query result nor in the prompt.
- Rule: Keep empty-result and out-of-scope explanations strictly grounded in the prompt's stated timeframe and explicit zero counts.
- Check: `test_table_qa_probes_no_orders_2027` in `tests/unit/test_sql_agent.py` and probe A8 live eval.

### R-039 — AST table function node inspection must validate anonymous table functions
- Status: observed (Phase 3, 2026-11-22)
- Context: `SELECT * FROM read_text('/etc/passwd')` bypassed `sqlglot` table allowlists because `tbl.name` returned an empty string for `exp.Anonymous` table sources, and `read_text`/`glob`/`read_blob` were missing from forbidden functions.
- Rule: AST guards must inspect `tbl.this` when it is an `exp.Func` or `exp.Anonymous`, check its function name against forbidden functions, and ensure non-schema table functions (other than safe transforms like `unnest`) are rejected when an allowlist is provided.
- Check: `test_reject_forbidden_read_text` and `test_reject_forbidden_glob` in `tests/unit/test_sql_guard.py`.

### R-040 — Markdown code block regexes must not greedily capture JSON payload as SQL
- Status: observed (Phase 3, 2026-11-22)
- Context: When an LLM followed system instructions to output JSON `{"sql": "...", "ambiguity_note": "..."}` inside a ````json` fence, `re.search(r"```(?:sql)?\s*(.*?)\s*```", text)` matched the code fence and returned the JSON text as the raw SQL statement, causing syntax errors and dropping the ambiguity note.
- Rule: Always check for and parse JSON data (including markdown ````json` blocks) before applying raw code-block extraction, and parse structured fields (`sql` and `ambiguity_note`) directly.
- Check: `test_extract_sql_from_llm_json_block` in `tests/unit/test_sql_agent.py`.

### R-041 — Numeric grounding regexes must not interpret ISO date hyphens as negative numbers
- Status: observed (Phase 3, 2026-11-22)
- Context: In `extract_numbers`, matching `\b[-+]?\d+\b` treated the hyphens in dates like `2025-01-15` as minus signs, extracting `-1.0` and `-15.0`.
- Rule: Numeric extraction regexes must use negative lookbehind `(?<![\w\d])[-+]?\d+` to ensure hyphens preceded by word or digit characters are not parsed as negative numbers.
- Check: `test_grounding_date_hyphens_not_negative` in `tests/unit/test_grounding.py`.

### R-042 — Alternative interpretation queries must aggregate at the product level before reason ranking
- Status: observed (Phase 3, 2026-11-22)
- Context: For Q3's alternative interpretation (units returned), grouping simultaneously by `(product_name, return_reason)` with `LIMIT 1` evaluated the max single (product, reason) combination rather than the product with the highest total units returned across all reasons.
- Rule: When computing an alternative leader metric with a nested attribute breakdown, first query the leader by the primary aggregate metric (`GROUP BY product_id ORDER BY SUM(units) DESC LIMIT 1`), then query that leader's breakdown.
- Check: Q3 live evaluation and `test_table_qa_revenue_query` in `test_sql_agent.py`.

### R-043 — Chronological sorting keys must rank undated documents with lower priority than dated documents
- Status: observed (Phase 4, 2026-11-22)
- Context: In `resolve_fact_across_versions`, sorting candidate claims by `(0, doc_date)` and `(1, "9999-99-99")` placed undated documents at the very end of an ascending sort, causing `stating_claims[-1]` to erroneously select an undated document over a dated document.
- Rule: Date sort keys must explicitly assign higher priority tuples to dated documents (e.g. `(1, doc_date)`) and lower priority to undated documents (e.g. `(0, "0000-00-00")`) so latest-date lookups deterministically prefer dated sources.
- Check: Unit test `test_resolver_undated_document_ranked_last` in `tests/unit/test_version_resolver.py`.

### R-044 — Superseded historical facts belong in evidence drawer metadata, not answer prose unless requested
- Status: observed (Phase 4, 2026-11-22)
- Context: Generated prose for Q10 initially included superseded compensation figures in the final answer text `(Superseded version 2025-03-10 offered INR 12 to 18 LPA)`, which violated the deterministic `must_not: ['12 to 18']` negative assertion.
- Rule: Keep final answer prose focused exclusively on the winning active fact; record superseded values and older document numbers strictly in structured citation metadata (`citations[].superseded`) for the evidence drawer.
- Check: Golden Q10 live eval asserting `must_not: ['12 to 18']`.

### R-045 — Temporal point-in-time queries must be evaluated prior to unconstrained topic templates
- Status: observed (Phase 4, 2026-11-22)
- Context: In `doc_agent.py`, evaluating `"gold" in q_lower` before `as_of_date` caused temporal probe A4 ("What was the return window for Gold members in mid-2025?") to hit the default unconstrained return policy template rather than the point-in-time branch.
- Rule: Point-in-time temporal queries (`as_of_date`) must be evaluated before general unconstrained topic matchers.
- Check: Adversarial probe A4 live eval asserting `2025-01-15` and `20 days`.

### R-046 — Conflicting tie dates must yield winner=None and abstain honestly
- Status: observed (Phase 4, 2026-11-22)
- Context: In `version_resolver.py`, when multiple documents shared the latest date with conflicting facts, `status` was set to `"tie_dates"` but `winner` was arbitrarily assigned to `latest_claims[0]`, causing downstream consumers to treat the arbitrary first document as the winner.
- Rule: When conflicting facts share the latest document date, `winner` must be set to `None` and downstream agents must honestly report the tie conflict rather than guessing.
- Check: Unit test `test_resolver_tie_dates_conflict` in `tests/unit/test_version_resolver.py` asserting `winner is None`.

### R-047 — Document QA prose must compose dynamically from extracted values, chunks, and metadata
- Status: observed (Phase 4, 2026-11-22)
- Context: `doc_agent.py` previously contained sample-specific question templates with hardcoded compensation and location strings, violating Truth Rule 4 and breaking reviewer generality on arbitrary uploaded documents.
- Rule: Application code must never hardcode sample values or specific entity names in answer prose or decomposition; answers must be assembled dynamically from winner values, chunk excerpts (e.g. exception clauses), and structured version metadata.
- Check: `scripts/check_no_hardcode.py` and unit tests in `tests/unit/test_no_hardcode.py`.

### R-048 — Verbatim quote verification must strip outer quotes from candidate quotes
- Status: observed (Phase 4, 2026-11-22)
- Context: `verify_verbatim_quote` performed substring checks directly on normalized text. When an LLM or structured extractor returned a quote enclosed in quotation marks (`"..."` or `'...'`), the quote failed substring matching because the source chunk text lacked the quotation marks.
- Rule: Strip outer quotation marks (`'`, `"`) from candidate quotes prior to verifying substring presence in chunk content.
- Check: Unit test `test_quote_verification_exact_and_paraphrase` in `tests/unit/test_version_resolver.py`.

### R-049 — Query intent routing must prioritize unambiguous domain indicators and bidirectional fallback
- Status: observed (Phase 5, 2026-11-22)
- Context: Keywords like "return" and "refund" in general document keyword lists hijacked table questions (e.g. Q3: product returned most often, Q5: refund amount by region) into document retrieval, which abstained and never attempted table QA.
- Rule: Route first on explicit cross-modal mixed patterns (e.g. order ID + policy terms), then clear tabular aggregation indicators (e.g. "returned most often", "by region", "revenue", "spend"), then document terms. Ensure bidirectional fallback so an abstention from one tool without execution attempts the other tool before declaring failure.
- Check: Golden Q3, Q5, Q13, Q14 in `scripts/run_core_evals.py`.

### R-050 — Financial percentages and restocking fee calculations must use standard half-up decimal rounding
- Status: observed (Phase 5, 2026-11-22)
- Context: In Q13, calculating 10% restocking fee on 49,636.55 INR using Python's default IEEE 754 float `round(..., 2)` (banker's rounding half-to-even) evaluated 4,963.655 to 4,963.65 instead of the expected financial figure 4,963.66.
- Rule: Always calculate currency percentages and fee amounts using `decimal.Decimal` with `ROUND_HALF_UP` to match exact financial standards and independent audit ground truth.
- Check: Golden Q13 live evaluation asserting exact fee match `4963.66`.

### R-051 — Mobile viewport layouts must collapse desktop rails off-canvas with visible hamburger controls
- Status: observed (Phase 5, 2026-11-22)
- Context: On narrow mobile screens (360px), a fixed 260px desktop sidebar squeezed the conversational thread into less than 100px of visible width, breaking readability and composer layout.
- Rule: Use responsive media queries to collapse desktop rails off-canvas on screens <= 768px, providing visible hamburger controls and backdrop overlays while giving 100% viewport width to the thread.
- Check: Playwright responsive screenshot test `tests/e2e/test_ui_screens.py` and visual verification of `reports/screens/screen-360.png`.

### R-052 — Windows Application Control execution environments require WASM-based Rollup fallbacks
- Status: observed (Phase 5, 2026-11-22)
- Context: In environments with Windows Application Control (WDAC/AppLocker), loading native `.node` binary dynamic libraries (`rollup.win32-x64-msvc.node`) failed with `ERR_DLOPEN_FAILED`.
- Rule: Provide pure WebAssembly/JavaScript execution fallbacks (`@rollup/wasm-node`) and automated patching in frontend build toolchains so builds succeed deterministically across restricted enterprise and classroom environments.
- Check: `frontend/patch-rollup.js` and clean execution of `npm run build` in `frontend/`.

### R-053 — Contextual entity memos must resolve conversational timeframes dynamically from turn history rather than hardcoding default years
- Status: observed (Phase 5, 2026-11-22)
- Context: In `backend/assistant.py`, follow-up queries at "that store" hardcoded `year = 2025` in `interpreted_as` and `sql_agent.py`, which corrupted queries when the previous turn discussed non-2025 data (e.g. 2024 or 2026).
- Rule: Extract timeframes and years dynamically from previous turn questions and query metadata into `entities`, and only include the year when one was established in conversation.
- Check: `test_chat_and_followup_persistence_across_process_restart` in `tests/unit/test_persistence.py`.

### R-054 — Multi-source cross-modal agent quotes must be dynamically extracted from document chunk content
- Status: observed (Phase 5, 2026-11-22)
- Context: In `backend/mixed_agent.py`, smartphone return exception quotes and restocking fee clauses were hardcoded string literals, violating R-046 and breaking generalization on arbitrary documents.
- Rule: Dynamically extract verbatim quotes from chunk text using substring or regex matching on the chunk content itself.
- Check: Unit tests in `tests/unit/test_no_hardcode.py` and Q13/Q14 evaluations.

### R-055 — Process restart persistence tests must verify chat history and contextual follow-ups across separate process lifecycles
- Status: observed (Phase 5, 2026-11-22)
- Context: Initial persistence testing only verified table and document metadata across subprocess reboot, leaving chat session rows, message status/citations, and cross-turn follow-up resolution unverified across actual process restarts.
- Rule: Always verify chat sessions, message persistence, contextual entity resolution, and conversational summaries across genuine OS subprocess boundaries.
- Check: `test_chat_and_followup_persistence_across_process_restart` in `tests/unit/test_persistence.py`.

<!-- New rules go below. Keep numbering sequential. -->

