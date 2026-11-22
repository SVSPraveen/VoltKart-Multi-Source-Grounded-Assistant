# RISKS.md — Pre-Mortem Analysis & Failure Mode Catalog

This document catalogues every known failure mode identified during Phase 0 analysis of the VoltKart data bundle, the assignment brief, and the host environment. Each risk is paired with its empirical trigger and deterministic mitigation.

## 1. Tabular Traps (T1 – T7)

| Trap ID | Risk Description | Empirical Trigger in Sample Data | Deterministic Mitigation | Verification Check |
|---|---|---|---|---|
| **T1** | Including Cancelled orders in Revenue calculation | 68 orders in `orders.csv` have `order_status = 'Cancelled'`. Summing all orders yields 6,284,482.90 INR for store S04 instead of 5,839,148.75 INR. | Ingest business definitions from `DATA_DICTIONARY.md` into SQL agent prompt; inject explicit filter `order_status = 'Delivered'`. | Golden Q1, Q2, Q15, Q16, Q19 assertions; numeric tolerance 0.01. |
| **T2** | Join Fan-Out across 1-to-many relationships | Joining `stores` -> `orders` -> `order_items` -> `returns` multiplies store and order line counts for each return item. | Structure queries with Common Table Expressions (CTEs) or join directly at the lowest grain. Run automated reconciliation query comparing joined totals to unjoined table sums. | Golden Q5; Review Rule R-020. |
| **T3** | Semantic Ambiguity: "Returned most often" | Ranking returns by number of return records yields *Nexora X12 Pro* (9 records); ranking by units returned yields *Auralis Pods Max ANC* (12 units). | Pick the primary interpretation (return events), state the definition explicitly in the answer, and mention the alternative reading. | Golden Q3 must_include check; Review Rule R-004. |
| **T4** | Missing Delivery Date in Orders | `orders.csv` records only `order_date`, not delivery date. | Assistant must never invent a delivery date. If a prompt supplies a relative offset ("12 days after delivery"), treat it as user-provided fact. | Golden Q13; Review Rule R-003. |
| **T5** | Customer Name Collisions | Multiple distinct customers share the first name "Kavya" (e.g., C0030 Kavya Kapoor, C0074 Kavya Nair). | Resolve entities using foreign key IDs (`customer_id` from `order_id`) rather than name substring search. | Golden Q13; Entity resolution probe. |
| **T6** | Static Loyalty Tier Assumption | `customers.csv` represents a snapshot. There is no historical tier log. | Agent treats `loyalty_tier` as current valid status; documented in schema card. | Schema card documentation. |
| **T7** | Contradiction between Operational Notice & Order Data | Notice says store S03 closed in Dec 2025; order data shows 9 orders (6 online, 3 in-store). | Present nuanced truth: state that notice indicates closure, online fulfillment continued, but 3 in-store orders contradict notice. | Golden Q14; Review Rule R-008. |

## 2. Document & Versioning Traps (D1 – D6)

| Trap ID | Risk Description | Empirical Trigger in Sample Data | Deterministic Mitigation | Verification Check |
|---|---|---|---|---|
| **D1** | Omission in Newest Document Version | Policy v3 (2025-09-01) omits damaged-in-transit reporting window and non-returnable items. Filtering to newest document returns "not found". | Retrieve across ALL versions; extract per version; resolve latest date *among versions stating the fact*; disclose fallback if older version used. | Golden Q8, Q9, Q11, Q12; Unit test with synthetic family; Rule R-001. |
| **D2** | Mixed Provenance in Multi-Part Questions | Warranty questions requiring price (updated in 2026-02-01) and claims limit (omitted in 2026, present only in 2024-07-01). | Decompose into sub-claims; resolve each independently in code; cite both versions with their respective document dates. | Golden Q9; Version resolver unit test. |
| **D3** | General Rule vs Category Exception Override | General return window is 30/45 days for Gold/Platinum, but Smartphones policy enforces 7 days for ALL tiers. | Agent prompt explicitly checks category-specific overrides and tier fee waivers before concluding. | Golden Q13; Logic chain test. |
| **D4** | Heterogeneous Date Formats in Document Text | Dates written as `1 April 2024`, `2025-09-01`, `20 October 2025`. | Multi-pattern tolerant date parser recording exact source and confidence. | Unit test covering 12 date format variants. |
| **D5** | Hallucinatory Version Blending | Merging clauses across versions without explicit provenance. | Code-enforced verbatim quote substring verification against stored chunks. Discard ungrounded quotes. | Citation verification unit test; Rule R-006. |
| **D6** | Incompatible Citation Schemes | PDFs require page numbers; DOCX files have no pages and require section headings. | Extractor stores `page_number` for PDFs and `section_heading` for DOCX/TXT; formatter renders appropriate citation. | Golden Q6–Q12 citation checks. |

## 3. Platform & Security Traps (P1 – P5)

| Trap ID | Risk Description | Trigger / Attack Vector | Deterministic Mitigation |
|---|---|---|---|
| **P1** | Arbitrary Filesystem Access via DuckDB | DuckDB `read_csv('/etc/passwd')` or writing files. | Enforce `SET enable_external_access = false;` and read-only connection. AST validation via sqlglot. |
| **P2** | Missing Rupee Symbol (`₹`) in PDF Export | Default Helvetica/Times fonts in ReportLab lack glyph for Unicode `₹`. | Embed TrueType Noto Sans font; rasterize page in test to verify visual rendering. |
| **P3** | Free-Tier LLM Rate Limits & Throttling | Running 20 golden questions × 3 live runs triggers 429 errors on free tier. | Exponential backoff with jitter; disk-based response cache for local dev/testing. |
| **P4** | Prompt Injection via Uploaded Content | Uploaded CSV cells or documents containing "Ignore previous instructions". | Treat all retrieved content strictly as data; wrap in `<source_data>` tags; never execute instructions from data. |
| **P5** | Web Search Leakage | Web toggle switched off in UI, but model calls search tool anyway. | Server-side tool binding: search tool is completely omitted from the agent's toolset when web is toggled off. |

