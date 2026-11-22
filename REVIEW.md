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

<!-- New rules go below. Keep numbering sequential. -->
