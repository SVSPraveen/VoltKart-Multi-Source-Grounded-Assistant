# VoltKart Sample Bundle: Data Dictionary

## tables/

| File | Primary key | Foreign keys | Columns |
|---|---|---|---|
| stores.csv | store_id | | store_id, store_name, city, region, opened_date, store_manager |
| customers.csv | customer_id | | customer_id, full_name, home_city, signup_date, loyalty_tier (Silver / Gold / Platinum) |
| products.csv | product_id | | product_id, product_name, category, brand, list_price_inr, launch_date |
| orders.csv | order_id | customer_id -> customers, store_id -> stores | order_id, customer_id, store_id, order_date, channel (In-store / Online), payment_method, order_status (Delivered / Cancelled) |
| order_items.csv | order_item_id | order_id -> orders, product_id -> products | order_item_id, order_id, product_id, quantity, unit_price_inr, discount_pct |
| returns.csv | return_id | order_item_id -> order_items | return_id, order_item_id, return_date, return_reason, refund_amount_inr |

Business definitions:
- Line amount = quantity x unit_price_inr x (1 - discount_pct / 100)
- Revenue / sales = sum of line amounts for orders with order_status = Delivered. Cancelled orders are not revenue.
- unit_price_inr is the price actually charged on that order and can differ from list_price_inr.
- All monetary values are in Indian Rupees (INR). All dates are ISO (YYYY-MM-DD).

## documents/

Company documents, some of which exist in multiple dated versions. Each file carries its date in the file name and inside the document (as "Document Date" or "Effective Date").

| Document family | Versions |
|---|---|
| Return & Refund Policy | 2024-04-01 (PDF), 2025-01-15 (DOCX), 2025-09-01 (TXT) |
| Job Description: Machine Learning Engineer | 2025-03-10 (DOCX), 2025-10-20 (PDF) |
| VoltCare Extended Warranty Terms | 2024-07-01 (TXT), 2026-02-01 (DOCX) |
| Store Operations Notice | 2025-11-05 (PDF) |
