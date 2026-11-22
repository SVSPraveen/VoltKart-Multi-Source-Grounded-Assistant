"""scripts/eval_variants.py - Standalone Variant Evaluation Runner (V4 Generalisation).

Generates at least 3 distinct variant datasets and proves the assistant pipeline
succeeds against variants without hardcoding, validating all answers against independent
pandas recomputations.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.doc_agent import run_doc_qa  # noqa: E402
from backend.ingestion import ingest_files  # noqa: E402
from backend.sql_agent import run_table_qa  # noqa: E402
from backend.storage import init_sqlite_db, reset_storage  # noqa: E402
from tests.variants.make_variant import PRESETS, generate_variant, resolve_default_source  # noqa: E402


def compute_expected_revenue_by_store(variant_dir: Path, year: int = 2025) -> dict:
    tables_dir = variant_dir / "tables"
    df_orders = pd.read_csv(tables_dir / "orders.csv")
    df_items = pd.read_csv(tables_dir / "order_items.csv")
    df_stores = pd.read_csv(tables_dir / "stores.csv")

    df_orders["order_date"] = pd.to_datetime(df_orders["order_date"])
    delivered = df_orders[
        (df_orders["order_status"] == "Delivered") & (df_orders["order_date"].dt.year == year)
    ]
    merged = df_items.merge(delivered, on="order_id")
    merged["line_amount"] = (
        merged["quantity"] * merged["unit_price_inr"] * (1.0 - merged["discount_pct"] / 100.0)
    )
    store_rev = merged.groupby("store_id")["line_amount"].sum().reset_index()
    top_store = store_rev.sort_values(by="line_amount", ascending=False).iloc[0]
    store_info = df_stores[df_stores["store_id"] == top_store["store_id"]].iloc[0]

    return {
        "store_id": str(top_store["store_id"]),
        "store_name": str(store_info["store_name"]),
        "revenue_inr": round(float(top_store["line_amount"]), 2),
    }


def compute_expected_top_customer_spend(variant_dir: Path) -> dict:
    tables_dir = variant_dir / "tables"
    df_orders = pd.read_csv(tables_dir / "orders.csv")
    df_items = pd.read_csv(tables_dir / "order_items.csv")
    df_customers = pd.read_csv(tables_dir / "customers.csv")

    delivered = df_orders[df_orders["order_status"] == "Delivered"]
    merged = df_items.merge(delivered, on="order_id")
    merged["line_amount"] = (
        merged["quantity"] * merged["unit_price_inr"] * (1.0 - merged["discount_pct"] / 100.0)
    )
    cust_spend = merged.groupby("customer_id")["line_amount"].sum().reset_index()
    top_cust = cust_spend.sort_values(by="line_amount", ascending=False).iloc[0]
    cust_info = df_customers[df_customers["customer_id"] == top_cust["customer_id"]].iloc[0]

    return {
        "customer_id": str(top_cust["customer_id"]),
        "customer_name": str(cust_info["full_name"]),
        "spend_inr": round(float(top_cust["line_amount"]), 2),
    }


def ingest_variant(variant_dir: Path) -> None:
    reset_storage()
    init_sqlite_db()
    file_payloads: list[tuple[str, bytes]] = []

    dict_file = variant_dir / "DATA_DICTIONARY.md"
    if dict_file.exists():
        file_payloads.append((dict_file.name, dict_file.read_bytes()))

    tables_dir = variant_dir / "tables"
    if tables_dir.exists():
        for csv_file in sorted(tables_dir.glob("*.csv")):
            file_payloads.append((csv_file.name, csv_file.read_bytes()))

    docs_dir = variant_dir / "documents"
    if docs_dir.exists():
        for doc_file in sorted(docs_dir.iterdir()):
            if doc_file.is_file() and doc_file.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
                file_payloads.append((doc_file.name, doc_file.read_bytes()))

    summary = ingest_files(file_payloads)
    if summary.errors:
        print(f"Ingestion warnings/errors: {summary.errors}")


def run_variant_evals() -> int:
    src_dir = resolve_default_source()
    eval_dir = ROOT_DIR / "evaluation" / "variants"
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("PHASE 7 - V4 GENERALISATION EVALUATION (3 VARIANT BUNDLES)")
    print("=" * 80)

    results: list[dict] = []

    # 1. Variant 1: ApexRetail
    v1_dir = eval_dir / "variant_1_apex"
    print("\n[1/3] Generating & Evaluating Variant 1: ApexRetail...")
    generate_variant(source_dir=src_dir, output_dir=v1_dir, **PRESETS["variant_1_apex"])
    exp_store = compute_expected_revenue_by_store(v1_dir, 2025)
    exp_cust = compute_expected_top_customer_spend(v1_dir)
    ingest_variant(v1_dir)

    res_v1_store = run_table_qa("Which store generated the highest revenue in 2025?")
    nums_store = [
        float(n) for n in re.findall(r"\d+(?:\.\d+)?", res_v1_store.answer.replace(",", ""))
    ]
    store_ok = (
        exp_store["store_name"] in res_v1_store.answer
        and "VoltKart" not in res_v1_store.answer
        and any(abs(n - exp_store["revenue_inr"]) <= 0.05 for n in nums_store)
    )

    res_v1_cust = run_table_qa("Which customer has the highest spend?")
    nums_cust = [
        float(n) for n in re.findall(r"\d+(?:\.\d+)?", res_v1_cust.answer.replace(",", ""))
    ]
    cust_ok = exp_cust["customer_name"] in res_v1_cust.answer and any(
        abs(n - exp_cust["spend_inr"]) <= 0.05 for n in nums_cust
    )

    results.append(
        {
            "variant": "Variant 1 (ApexRetail)",
            "features": "Shifted dates (+30d), scaled prices (1.10x), renamed stores (STR_01..), mixed date formats",
            "test": "Top store revenue (2025)",
            "expected": f"{exp_store['store_name']} (₹{exp_store['revenue_inr']:,.2f})",
            "actual_found": f"Found: ₹{exp_store['revenue_inr']:,.2f}" if store_ok else "Mismatch",
            "passed": store_ok,
        }
    )
    results.append(
        {
            "variant": "Variant 1 (ApexRetail)",
            "features": "Shifted dates (+30d), scaled prices (1.10x), renamed stores (STR_01..), mixed date formats",
            "test": "Highest spend customer (all-time)",
            "expected": f"{exp_cust['customer_name']} (₹{exp_cust['spend_inr']:,.2f})",
            "actual_found": f"Found: ₹{exp_cust['spend_inr']:,.2f}" if cust_ok else "Mismatch",
            "passed": cust_ok,
        }
    )

    # 2. Variant 2: ZenithCommerce (Table-formatted policy & multi-format versions)
    v2_dir = eval_dir / "variant_2_zenith_table"
    print("\n[2/3] Generating & Evaluating Variant 2: ZenithCommerce...")
    generate_variant(source_dir=src_dir, output_dir=v2_dir, **PRESETS["variant_2_zenith_table"])
    ingest_variant(v2_dir)

    res_v2_gold = run_doc_qa("What is the return window for Gold members at ZenithCommerce?")
    gold_ok = "30" in res_v2_gold.answer and any(
        "ZenithCommerce_Return_Policy" in (c.get("file_name", "") or c.get("source", ""))
        for c in res_v2_gold.citations
    )

    res_v2_phone = run_doc_qa("What is the return window for smartphones at ZenithCommerce?")
    phone_ok = "10" in res_v2_phone.answer and any(
        "ZenithCommerce_Return_Policy" in (c.get("file_name", "") or c.get("source", ""))
        for c in res_v2_phone.citations
    )

    results.append(
        {
            "variant": "Variant 2 (ZenithCommerce)",
            "features": "Structured Markdown policy table, multi-format versions (.txt, .docx, .md)",
            "test": "Gold member return window",
            "expected": "30 days (from table)",
            "actual_found": "30 days" if gold_ok else "Mismatch",
            "passed": gold_ok,
        }
    )
    results.append(
        {
            "variant": "Variant 2 (ZenithCommerce)",
            "features": "Structured Markdown policy table, multi-format versions (.txt, .docx, .md)",
            "test": "Smartphone category exception window",
            "expected": "10 days (from table exception)",
            "actual_found": "10 days" if phone_ok else "Mismatch",
            "passed": phone_ok,
        }
    )

    # 3. Variant 3: OmniStore (Fact omission in newest v3, per-fact version resolution)
    v3_dir = eval_dir / "variant_3_omission"
    print("\n[3/3] Generating & Evaluating Variant 3: OmniStore...")
    generate_variant(source_dir=src_dir, output_dir=v3_dir, **PRESETS["variant_3_omission"])
    ingest_variant(v3_dir)

    res_v3_omiss = run_doc_qa(
        "What is the reporting window for damaged items upon delivery at OmniStore?"
    )
    omiss_ok = ("48" in res_v3_omiss.answer or "48 hours" in res_v3_omiss.answer.lower()) and (
        any(
            "2.0" in str(c.get("version", ""))
            or "v2" in str(c.get("version", "")).lower()
            or "2025-01-30" in str(c.get("date", ""))
            for c in res_v3_omiss.citations
        )
        or "2.0" in res_v3_omiss.answer
        or "2025-01-30" in res_v3_omiss.answer
    )

    results.append(
        {
            "variant": "Variant 3 (OmniStore)",
            "features": "Fact omission in active v3, per-fact version resolution and fallback disclosure (R-001)",
            "test": "Damaged items reporting window fallback",
            "expected": "48 hours (from v2.0 fallback, cited explicitly)",
            "actual_found": "48 hours with v2 provenance" if omiss_ok else "Mismatch",
            "passed": omiss_ok,
        }
    )

    # Print summary table
    print("\n" + "-" * 110)
    print(
        f"{'Variant Bundle':<26} | {'Test Case':<32} | {'Expected (Pandas / Truth)':<30} | {'Status':<8}"
    )
    print("-" * 110)
    all_passed = True
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        if not r["passed"]:
            all_passed = False
        print(f"{r['variant']:<26} | {r['test']:<32} | {r['expected']:<30} | {status_str:<8}")
    print("-" * 110)

    # Write report
    report_md = reports_dir / f"eval_variants_{time.strftime('%Y%m%d_%H%M%S')}.md"
    lines = [
        "# Variant Generalisation Evaluation Report (V4)",
        f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}",
        "- Total Variants Evaluated: 3",
        f"- Overall Status: {'ALL PASSED' if all_passed else 'FAILURES DETECTED'}",
        "",
        "## Results Table",
        "| Variant Bundle | Features | Test Case | Expected Ground Truth | Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in results:
        st = "**PASS**" if r["passed"] else "**FAIL**"
        lines.append(f"| {r['variant']} | {r['features']} | {r['test']} | {r['expected']} | {st} |")

    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nVariant evaluation report saved to: {report_md}")

    # Restore default sample bundle storage state
    print("\nRestoring default sample bundle storage state...")
    from tests.unit.test_sample_bundle_ingestion import test_full_sample_bundle_ingestion

    reset_storage()
    test_full_sample_bundle_ingestion()
    init_sqlite_db()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_variant_evals())
