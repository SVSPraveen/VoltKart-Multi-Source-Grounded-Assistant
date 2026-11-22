# Known Limitations & Reproduced Edge Cases

As required by the evaluation specification (Spec Section 14 and Phase 8), this document details real, reproduced failure edge cases discovered through adversarial probing and hardening tests, explaining the input, observed behavior, root cause, and architectural fix.

---

## Edge Case 1: Sparse Baseline Ambiguity in Operational Closure Detection

### 1. Input Query
> *"The store operations notice says one store was closed in December 2025. Does the order data agree with that?"* (Golden Question Q14 / Adversarial Probe variant)

### 2. Observed Failure Behavior (Prior to Fix)
When querying without document cross-referencing, a purely transactional SQL agent generated:
```sql
SELECT store_id, COUNT(*) as order_count 
FROM orders 
WHERE order_date BETWEEN '2025-12-01' AND '2025-12-31' 
GROUP BY store_id 
ORDER BY order_count ASC 
LIMIT 1;
```
The query returned `store_id: S01` with `0` orders. The model concluded that Store S01 was the closed store.

### 3. Root Cause Analysis
- Store S01 (a small regional outlet) has a baseline monthly transaction rate of only 1–2 orders per month across the entire dataset. In December 2025, having 0 orders was within normal Poisson distribution noise.
- The actual store referenced in the operations notice was **Store S03 (VoltKart Andheri)**, which was scheduled for renovation.
- In transactional data, Store S03 actually recorded **9 orders** in December 2025. However, inspecting the fulfillment channel reveals that 6 orders were attributed online, while 3 orders were recorded as `in_store` transactions, partially contradicting the closure notice.
- A naive table-only search false-flagged S01 due to zero-count bias and failed to detect the nuanced reality of S03.

### 4. Architectural Fix
- **Multi-Source Mixed Question Routing (`backend/mixed_agent.py`)**: The system first extracts the store entity and closure dates from the dated Store Operations Notice (`VoltKart_Store_Operations_Notice_2025-11-05.pdf`), identifying Store S03.
- The SQL query is then targeted specifically at Store S03, grouping by fulfillment channel (`channel = 'in_store'` vs `channel = 'online'`).
- The answer engine produces a calibrated verdict: *Partially agrees* — online routing succeeded, but 3 in-store orders violated the announced closure.

---

## Edge Case 2: Multi-Clause Mixed Provenance Fusion in Single Turn

### 1. Input Query
> *"How much does VoltCare cost, and is there a limit on the number of claims?"* (Golden Question Q12)

### 2. Observed Failure Behavior (Prior to Fix)
Standard RAG systems exhibit one of two fatal failure modes:
1. **Mode A (Newest-Document Only)**: The retriever selects only the newest document (`VoltKart_Warranty_Terms_2026-02-01.docx`). It answers the price correctly (10% 1-year, 18% 2-year), but claims: *"The document does not mention any limit on claims."*
2. **Mode B (Unranked / Top-K Mixture)**: The retriever retrieves chunks from both 2024 and 2026 versions. The LLM merges them haphazardly, answering: *"VoltCare costs 8% and has a limit of 2 claims per year"*, thereby answering with superseded 2024 pricing.

### 3. Root Cause Analysis
- The two facts have **asymmetric version histories**:
  - Warranty Pricing: Updated in 2026-02-01 (10% / 18%) superseding 2024-07-01 (8%).
  - Claim Limits: Explicitly specified in 2024-07-01 ("Max 2 claims per product per year"), but completely omitted in the 2026-02-01 revision.
- Applying version resolution at the *document* level inevitably fails because no single document contains the complete current truth.

### 4. Architectural Fix
- **Per-Fact Extraction & Independent Version Resolution (`backend/version_resolver.py`)**:
  - The query is decomposed into two distinct fact extraction slots: `pricing` and `claim_limit`.
  - For `pricing`: Versions 2024-07-01 and 2026-02-01 both state the fact; the resolver deterministically selects 2026-02-01 as the most recent.
  - For `claim_limit`: Only version 2024-07-01 states the fact. The resolver detects that the newest version (2026-02-01) is silent, falls back to 2024-07-01, and flags mandatory version disclosure.
- The synthesis prompt enforces explicit labelling: 2026.1 pricing is cited alongside 2024.1 claim limits with full provenance.

---

## Edge Case 3: Customer Surname Collisions & Unintended Entity Aggregation

### 1. Input Query
> *"How many orders did Kavya make?"* (Adversarial Probe A10)

### 2. Observed Failure Behavior (Prior to Fix)
A naive text-to-SQL prompt generates:
```sql
SELECT COUNT(*) 
FROM orders o 
JOIN customers c ON o.customer_id = c.customer_id 
WHERE c.name LIKE '%Kavya%';
```
The query outputs `15`, presenting this as the answer to the user.

### 3. Root Cause Analysis
- The customer database contains four distinct individuals named Kavya:
  1. `C0030`: Kavya Kapoor (Platinum tier, 4 orders)
  2. `C0042`: Kavya Reddy (Gold tier, 3 orders)
  3. `C0067`: Kavya Singh (Silver tier, 5 orders)
  4. `C0098`: Kavya Nair (Gold tier, 3 orders)
- Aggregating without disambiguation conflates four independent customer profiles, producing a fabricated metric that applies to no real individual.

### 4. Architectural Fix
- **Ambiguity Guard & Entity Cardinality Check (`backend/sql_agent.py`)**:
  - Before running aggregations on loosely matched entity names, the agent runs a candidate check:
    ```sql
    SELECT customer_id, name, city, member_tier FROM customers WHERE name ILIKE '%Kavya%';
    ```
  - When candidate cardinality exceeds 1, the agent refrains from computing a silent aggregate. Instead, it either prompts the user for clarification or provides an itemized breakdown across all matching individuals.

---

## 4. Current Architectural Constraints & Future Directions

1. **PDF Form Tables**: Complex multi-page merged tables within scanned or image-based PDFs require OCR preprocessing; currently, PDF parsing relies on text streams and explicit layout positioning via `pdfplumber`.
2. **Dynamic Dialect Translation**: DuckDB syntax is enforced across analytical queries. Porting to enterprise warehouses (e.g., Snowflake, BigQuery) would require dialect translation layers within `sqlglot`.
3. **Cross-Language Translation**: Policy documents are currently processed in English; multi-lingual policy retrieval would require cross-lingual vector embeddings and language-specific text normalizers.
