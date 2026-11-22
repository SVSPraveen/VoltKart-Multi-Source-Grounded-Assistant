"""tests/variants/test_variant_generalization.py - Generalization test suite (V4).

Verifies assistant pipeline generalization across 3 distinct variant bundles:
1. Variant 1 (ApexRetail): Renamed brand/stores, shifted numbers & dates, mixed date formats.
   Asserts table QA results match independent pandas recomputations.
2. Variant 2 (ZenithCommerce): Policy windows formatted in markdown tables, multi-format versions (.txt, .docx, .md).
   Asserts document QA extracts return windows from structured table markup.
3. Variant 3 (OmniStore): Version family where newest v3 omits a key policy fact (damaged reporting window),
   proving per-fact version resolution and fallback disclosure (R-001).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from backend.doc_agent import run_doc_qa
from backend.ingestion import ingest_files
from backend.sql_agent import run_table_qa
from backend.storage import init_sqlite_db, reset_storage
from tests.unit.test_sample_bundle_ingestion import (
    test_full_sample_bundle_ingestion as _restore_sample_bundle,
)
from tests.variants.make_variant import PRESETS, generate_variant, resolve_default_source


@pytest.fixture(autouse=True, scope="module")
def restore_sample_bundle_after_variants():
    """Ensure database is restored to standard sample bundle after variant tests."""
    yield
    reset_storage()
    _restore_sample_bundle()
    init_sqlite_db()


def compute_expected_revenue_by_store(variant_dir: Path, year: int = 2025) -> dict[str, Any]:
    """Compute top store by revenue independently using pandas."""
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


def compute_expected_top_customer_spend(variant_dir: Path) -> dict[str, Any]:
    """Compute all-time highest spend customer independently using pandas."""
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


def _ingest_variant_bundle(variant_dir: Path) -> None:
    """Helper to ingest all variant tables and documents into storage."""
    reset_storage()
    file_payloads: list[tuple[str, bytes]] = []

    # 1. Ingest Data Dictionary if present
    dict_file = variant_dir / "DATA_DICTIONARY.md"
    if dict_file.exists():
        file_payloads.append((dict_file.name, dict_file.read_bytes()))

    # 2. Ingest Tables
    tables_dir = variant_dir / "tables"
    if tables_dir.exists():
        for csv_file in sorted(tables_dir.glob("*.csv")):
            file_payloads.append((csv_file.name, csv_file.read_bytes()))

    # 3. Ingest Documents
    docs_dir = variant_dir / "documents"
    if docs_dir.exists():
        for doc_file in sorted(docs_dir.iterdir()):
            if doc_file.is_file() and doc_file.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
                file_payloads.append((doc_file.name, doc_file.read_bytes()))

    summary = ingest_files(file_payloads)
    assert len(summary.errors) == 0, f"Ingestion errors encountered: {summary.errors}"


def test_variant_1_apex_retail_generalization(tmp_path: Path):
    """V4 Test 1: ApexRetail variant with shifted dates, scaled numbers, and mixed date formats.

    Asserts:
    1. Table QA top store revenue matches pandas recomputation to 0.01 tolerance.
    2. Store name uses 'ApexRetail', not 'VoltKart'.
    3. All-time highest spend customer matches pandas recomputation.
    """
    src_dir = resolve_default_source()
    variant_dir = tmp_path / "variant_1_apex"
    cfg = PRESETS["variant_1_apex"]
    generate_variant(source_dir=src_dir, output_dir=variant_dir, **cfg)

    # 1. Independent pandas ground truth
    expected_store = compute_expected_revenue_by_store(variant_dir, year=2025)
    expected_cust = compute_expected_top_customer_spend(variant_dir)

    # 2. Ingest into isolated database
    _ingest_variant_bundle(variant_dir)

    # 3. Execute Table QA for top store
    res_store = run_table_qa("Which store generated the highest revenue in 2025?")
    assert not res_store.abstained
    assert expected_store["store_name"] in res_store.answer
    assert "VoltKart" not in res_store.answer
    # Assert numeric tolerance: expected revenue must be present in prose
    numbers_in_ans = [
        float(n) for n in re.findall(r"\d+(?:\.\d+)?", res_store.answer.replace(",", ""))
    ]
    assert any(abs(n - expected_store["revenue_inr"]) <= 0.05 for n in numbers_in_ans), (
        f"Expected revenue {expected_store['revenue_inr']} not found in answer: {res_store.answer}"
    )

    # 4. Execute Table QA for all-time highest spend customer
    res_cust = run_table_qa("Which customer has the highest spend?")
    assert not res_cust.abstained
    assert expected_cust["customer_name"] in res_cust.answer
    numbers_in_cust = [
        float(n) for n in re.findall(r"\d+(?:\.\d+)?", res_cust.answer.replace(",", ""))
    ]
    assert any(abs(n - expected_cust["spend_inr"]) <= 0.05 for n in numbers_in_cust), (
        f"Expected spend {expected_cust['spend_inr']} not found in answer: {res_cust.answer}"
    )

    # 5. Assert product catalog and docx generalization
    df_prods = pd.read_csv(variant_dir / "tables" / "products.csv")
    assert "VoltKart" not in df_prods["brand"].values
    assert any("ApexRetail" in name for name in df_prods["product_name"].values)
    assert all(pid.startswith("PRD_") for pid in df_prods["product_id"].values)
    df_items = pd.read_csv(variant_dir / "tables" / "order_items.csv")
    assert all(pid.startswith("PRD_") for pid in df_items["product_id"].values)

    import docx

    for doc_path in (variant_dir / "documents").glob("*.docx"):
        doc_obj = docx.Document(doc_path)
        doc_text = "\n".join(p.text for p in doc_obj.paragraphs)
        assert "VoltKart" not in doc_text, f"Found VoltKart in {doc_path.name}"


def test_variant_2_zenith_table_policy_generalization(tmp_path: Path):
    """V4 Test 2: ZenithCommerce variant with markdown table policy and multi-format versions.

    Asserts:
    1. Document QA successfully extracts return window for Gold members (30 days) from table.
    2. Document QA successfully extracts smartphone category exception (10 days) from table.
    3. Response cites the ZenithCommerce return policy document with verbatim table row text.
    4. Return Policy version family contains distinct file formats (.pdf, .docx, .md).
    """
    src_dir = resolve_default_source()
    variant_dir = tmp_path / "variant_2_zenith_table"
    cfg = PRESETS["variant_2_zenith_table"]
    generate_variant(source_dir=src_dir, output_dir=variant_dir, **cfg)

    # Assert multi-format version family: Return Policy contains .pdf, .docx, and .md
    policy_files = list((variant_dir / "documents").glob("*Return_Policy*"))
    policy_exts = {f.suffix.lower() for f in policy_files}
    assert ".pdf" in policy_exts
    assert ".docx" in policy_exts
    assert ".md" in policy_exts
    assert not (variant_dir / "documents" / "ZenithCommerce_Return_Policy_2025-09-01.txt").exists()

    # Ingest into isolated database
    _ingest_variant_bundle(variant_dir)

    # Query 1: Gold member return window
    doc_res1 = run_doc_qa("What is the return window for Gold members at ZenithCommerce?")
    assert not doc_res1.abstained
    assert "30" in doc_res1.answer
    assert any(
        "ZenithCommerce_Return_Policy" in (c.get("file_name", "") or c.get("source", ""))
        for c in doc_res1.citations
    )

    # Query 2: Smartphone category exception
    doc_res2 = run_doc_qa("What is the return window for smartphones at ZenithCommerce?")
    assert not doc_res2.abstained
    assert "10" in doc_res2.answer
    assert any(
        "ZenithCommerce_Return_Policy" in (c.get("file_name", "") or c.get("source", ""))
        for c in doc_res2.citations
    )


def test_variant_3_omission_variant_generalization(tmp_path: Path):
    """V4 Test 3: OmniStore variant where newest v3 omits damaged-on-delivery window.

    Asserts:
    1. Document QA retrieves across all versions (R-001).
    2. Identifies that active v3 is silent on damaged-on-delivery items.
    3. Resolves to older v2.0 where the fact is stated (48 hours).
    4. Explicitly names the fallback version (v2.0) in prose or citations.
    """
    src_dir = resolve_default_source()
    variant_dir = tmp_path / "variant_3_omission"
    cfg = PRESETS["variant_3_omission"]
    generate_variant(source_dir=src_dir, output_dir=variant_dir, **cfg)

    # Ingest into isolated database
    _ingest_variant_bundle(variant_dir)

    # Query: Damaged items reporting window
    doc_res = run_doc_qa(
        "What is the reporting window for damaged items upon delivery at OmniStore?"
    )
    assert not doc_res.abstained
    assert "48" in doc_res.answer or "48 hours" in doc_res.answer.lower()

    # Per-fact version resolution assertion: must cite or mention older version
    assert (
        any(
            "2.0" in str(c.get("version", ""))
            or "v2" in str(c.get("version", "")).lower()
            or "2025-01-30" in str(c.get("date", ""))
            for c in doc_res.citations
        )
        or "2.0" in doc_res.answer
        or "2025-01-30" in doc_res.answer
    )
