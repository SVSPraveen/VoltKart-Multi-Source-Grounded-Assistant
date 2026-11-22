#!/usr/bin/env python3
"""scripts/verify_golden_numbers.py - Independent mathematical re-derivation.

Independently computes table metrics from raw CSV files using pandas (without
referencing application code or golden.yaml values) and compares against
the golden expectations to prove the truth anchor is 100% exact.
"""

from pathlib import Path

import pandas as pd


def resolve_tables_dir() -> Path:
    candidates = [
        Path("assignment/VoltKart_Sample_Bundle/tables"),
        Path("ml-intern-assignment/assignment/VoltKart_Sample_Bundle/tables"),
    ]
    for c in candidates:
        if c.exists() and (c / "orders.csv").exists():
            return c.resolve()
    raise FileNotFoundError("Could not locate tables directory.")


def main():
    tables_dir = resolve_tables_dir()
    print(f"Reading raw CSV tables from: {tables_dir}\n")

    orders = pd.read_csv(tables_dir / "orders.csv")
    order_items = pd.read_csv(tables_dir / "order_items.csv")
    stores = pd.read_csv(tables_dir / "stores.csv")
    customers = pd.read_csv(tables_dir / "customers.csv")
    products = pd.read_csv(tables_dir / "products.csv")
    returns = pd.read_csv(tables_dir / "returns.csv")

    print("=" * 60)
    print("1. Re-deriving Golden Q1: Highest 2025 Revenue Store")
    print("=" * 60)
    # Delivered orders in 2025
    delivered_2025 = orders[
        (orders["order_status"] == "Delivered") & (orders["order_date"].str.startswith("2025"))
    ]
    merged_items = delivered_2025.merge(order_items, on="order_id")
    merged_items["line_revenue"] = (
        merged_items["quantity"]
        * merged_items["unit_price_inr"]
        * (1.0 - merged_items["discount_pct"] / 100.0)
    )
    store_rev = merged_items.groupby("store_id")["line_revenue"].sum().reset_index()
    store_rev = store_rev.merge(stores, on="store_id").sort_values(
        by="line_revenue", ascending=False
    )
    top_store = store_rev.iloc[0]

    q1_expected_rev = 5839148.75
    q1_diff = abs(top_store["line_revenue"] - q1_expected_rev)
    print(f"Top Store ID:       {top_store['store_id']}")
    print(f"Top Store Name:     {top_store['store_name']}")
    print(f"Manager:            {top_store['store_manager']}")
    print(f"Calculated Revenue: {top_store['line_revenue']:.2f} INR")
    print(f"Golden Expected:    {q1_expected_rev:.2f} INR")
    print(f"Difference:         {q1_diff:.6f} INR (tolerance: 0.01)")
    assert q1_diff < 0.01, f"Q1 revenue mismatch: {q1_diff}"
    print("-> Q1 MATCH EXACT: PASS\n")

    print("=" * 60)
    print("2. Re-deriving Golden Q4: Platinum Bengaluru Laptop Buyers in Q1 2026")
    print("=" * 60)
    plat_blr = customers[
        (customers["loyalty_tier"] == "Platinum") & (customers["home_city"] == "Bengaluru")
    ]
    q1_2026_orders = orders[
        (orders["order_date"] >= "2026-01-01") & (orders["order_date"] <= "2026-03-31")
    ]
    laptop_prods = products[products["category"] == "Laptops"]

    q4_merged = (
        plat_blr.merge(q1_2026_orders, on="customer_id")
        .merge(order_items, on="order_id")
        .merge(laptop_prods, on="product_id")
    )
    unique_custs = q4_merged[["customer_id", "full_name"]].drop_duplicates()
    cust_list = [f"{r['full_name']} ({r['customer_id']})" for _, r in unique_custs.iterrows()]
    print(f"Matching Buyers Count: {len(unique_custs)}")
    print(f"Matching Customer(s):  {', '.join(cust_list)}")
    print("Golden Expected:       1 customer -> Kabir Kapoor (C0037)")
    assert len(unique_custs) == 1
    assert unique_custs.iloc[0]["customer_id"] == "C0037"
    assert unique_custs.iloc[0]["full_name"] == "Kabir Kapoor"
    print("-> Q4 MATCH EXACT: PASS\n")

    print("=" * 60)
    print("3. Re-deriving Golden Q5: Total Refund Amount by Region")
    print("=" * 60)
    ret_items = returns.merge(order_items, on="order_item_id")
    ret_orders = ret_items.merge(orders, on="order_id")
    ret_stores = ret_orders.merge(stores, on="store_id")

    region_refunds = ret_stores.groupby("region")["refund_amount_inr"].sum().round(2).to_dict()
    grand_total = sum(region_refunds.values())

    golden_regions = {
        "East": 329242.20,
        "North": 141624.95,
        "South": 916002.70,
        "West": 569024.40,
    }
    golden_grand_total = 1955894.25

    print("Region Breakdown:")
    for region, expected_val in golden_regions.items():
        actual_val = region_refunds.get(region, 0.0)
        diff = abs(actual_val - expected_val)
        print(
            f"  {region:6s}: Actual={actual_val:10.2f} | Golden={expected_val:10.2f} | Diff={diff:.4f}"
        )
        assert diff < 0.01, f"Mismatch in {region}: diff {diff}"

    grand_diff = abs(grand_total - golden_grand_total)
    print(
        f"Grand Total: Actual={grand_total:10.2f} | Golden={golden_grand_total:10.2f} | Diff={grand_diff:.4f}"
    )
    assert grand_diff < 0.01, f"Grand total mismatch: {grand_diff}"
    print("-> Q5 MATCH EXACT: PASS\n")

    print("=" * 60)
    print("ALL 3 GOLDEN TABLE NUMBERS INDEPENDENTLY VERIFIED TO THE EXACT PAISA.")
    print("=" * 60)


if __name__ == "__main__":
    main()
