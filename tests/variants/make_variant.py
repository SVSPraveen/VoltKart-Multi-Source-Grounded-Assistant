#!/usr/bin/env python3
"""tests/variants/make_variant.py - Variant bundle generator.

Generates variant datasets (tables and documents) to prove the assistant
pipeline generalizes beyond VoltKart sample data and does not rely on
hardcoded entities, specific dates, or fixed numbers (REVIEW.md R-005, R-018).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def shift_date_str(date_str: str, days: int) -> str:
    """Shift an ISO YYYY-MM-DD date string by a given number of days."""
    try:
        dt = datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
        new_dt = dt + timedelta(days=days)
        return new_dt.strftime("%Y-%m-%d")
    except Exception:
        return str(date_str)


def generate_variant(
    source_dir: Path,
    output_dir: Path,
    brand_name: str = "NovaMart",
    warranty_name: str = "NovaCare",
    shift_days: int = 0,
    price_scale: float = 1.0,
    store_prefix: str | None = None,
    product_prefix: str | None = None,
    mixed_date_formats: bool = False,
    table_policy: bool = False,
    different_formats: bool = False,
    omit_facts_in_v3: bool = False,
) -> dict[str, Any]:
    """Generate a full variant bundle from source bundle into output_dir.

    Returns metadata detailing transformations applied.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_in = source_dir / "tables"
    docs_in = source_dir / "documents"

    tables_out = output_dir / "tables"
    docs_out = output_dir / "documents"
    tables_out.mkdir(parents=True, exist_ok=True)
    docs_out.mkdir(parents=True, exist_ok=True)

    transform_log: dict[str, Any] = {
        "brand_name": brand_name,
        "warranty_name": warranty_name,
        "shift_days": shift_days,
        "price_scale": price_scale,
        "store_prefix": store_prefix,
        "product_prefix": product_prefix,
        "mixed_date_formats": mixed_date_formats,
        "table_policy": table_policy,
        "different_formats": different_formats,
        "omit_facts_in_v3": omit_facts_in_v3,
        "tables_modified": [],
        "documents_modified": [],
    }

    # 1. Transform Tables
    if tables_in.exists():
        # stores.csv
        stores_file = tables_in / "stores.csv"
        if stores_file.exists():
            df_stores = pd.read_csv(stores_file)
            if "store_name" in df_stores.columns:
                df_stores["store_name"] = (
                    df_stores["store_name"].astype(str).str.replace("VoltKart", brand_name)
                )
            if store_prefix and "store_id" in df_stores.columns:
                df_stores["store_id"] = (
                    df_stores["store_id"].astype(str).str.replace(r"^S", store_prefix, regex=True)
                )
            df_stores.to_csv(tables_out / "stores.csv", index=False)
            transform_log["tables_modified"].append("stores.csv")

        # products.csv
        products_file = tables_in / "products.csv"
        if products_file.exists():
            df_products = pd.read_csv(products_file)
            if "brand" in df_products.columns:
                df_products["brand"] = (
                    df_products["brand"].astype(str).str.replace("VoltKart", brand_name)
                )
            if "product_name" in df_products.columns:
                df_products["product_name"] = (
                    df_products["product_name"].astype(str).str.replace("VoltKart", brand_name)
                )
            if product_prefix and "product_id" in df_products.columns:
                df_products["product_id"] = (
                    df_products["product_id"]
                    .astype(str)
                    .str.replace(r"^P", product_prefix, regex=True)
                )
            if "list_price_inr" in df_products.columns and price_scale != 1.0:
                df_products["list_price_inr"] = (df_products["list_price_inr"] * price_scale).round(
                    2
                )
            df_products.to_csv(tables_out / "products.csv", index=False)
            transform_log["tables_modified"].append("products.csv")

        # customers.csv
        customers_file = tables_in / "customers.csv"
        if customers_file.exists():
            df_cust = pd.read_csv(customers_file)
            df_cust.to_csv(tables_out / "customers.csv", index=False)
            transform_log["tables_modified"].append("customers.csv")

        # orders.csv
        orders_file = tables_in / "orders.csv"
        if orders_file.exists():
            df_orders = pd.read_csv(orders_file)
            if shift_days != 0 and "order_date" in df_orders.columns:
                df_orders["order_date"] = df_orders["order_date"].apply(
                    lambda d: shift_date_str(d, shift_days)
                )
            if store_prefix and "store_id" in df_orders.columns:
                df_orders["store_id"] = (
                    df_orders["store_id"].astype(str).str.replace(r"^S", store_prefix, regex=True)
                )
            df_orders.to_csv(tables_out / "orders.csv", index=False)
            transform_log["tables_modified"].append("orders.csv")

        # order_items.csv
        order_items_file = tables_in / "order_items.csv"
        if order_items_file.exists():
            df_items = pd.read_csv(order_items_file)
            if product_prefix and "product_id" in df_items.columns:
                df_items["product_id"] = (
                    df_items["product_id"]
                    .astype(str)
                    .str.replace(r"^P", product_prefix, regex=True)
                )
            if price_scale != 1.0 and "unit_price_inr" in df_items.columns:
                df_items["unit_price_inr"] = (df_items["unit_price_inr"] * price_scale).round(2)
            df_items.to_csv(tables_out / "order_items.csv", index=False)
            transform_log["tables_modified"].append("order_items.csv")

        # returns.csv
        returns_file = tables_in / "returns.csv"
        if returns_file.exists():
            df_returns = pd.read_csv(returns_file)
            if shift_days != 0 and "return_date" in df_returns.columns:
                df_returns["return_date"] = df_returns["return_date"].apply(
                    lambda d: shift_date_str(d, shift_days)
                )
            if price_scale != 1.0 and "refund_amount_inr" in df_returns.columns:
                df_returns["refund_amount_inr"] = (
                    df_returns["refund_amount_inr"] * price_scale
                ).round(2)
            df_returns.to_csv(tables_out / "returns.csv", index=False)
            transform_log["tables_modified"].append("returns.csv")

    # 2. Transform Documents
    if docs_in.exists():
        for doc_file in docs_in.iterdir():
            if not doc_file.is_file():
                continue

            # Compute variant output filename (brand replacement and date shift)
            new_filename = doc_file.name.replace("VoltKart", brand_name).replace(
                "VoltCare", warranty_name
            )
            if shift_days != 0:
                new_filename = re.sub(
                    r"(\d{4}-\d{2}-\d{2})",
                    lambda m: shift_date_str(m.group(1), shift_days),
                    new_filename,
                )
            out_file = docs_out / new_filename

            if doc_file.suffix.lower() == ".txt":
                content = doc_file.read_text(encoding="utf-8", errors="replace")
                content = content.replace("VoltKart", brand_name)
                content = content.replace("VoltCare", warranty_name)
                if shift_days != 0:
                    content = re.sub(
                        r"(\d{4}-\d{2}-\d{2})",
                        lambda m: shift_date_str(m.group(1), shift_days),
                        content,
                    )

                if mixed_date_formats and "Document Date:" in content:
                    # Convert some ISO dates to DD/MM/YYYY or spelled out format
                    def _format_mixed(match: re.Match) -> str:
                        iso_val = match.group(1)
                        try:
                            dt = datetime.strptime(iso_val, "%Y-%m-%d")
                            return f"Document Date: {dt.strftime('%d/%m/%Y')} (Effective: {dt.strftime('%B %d, %Y')})"
                        except Exception:
                            return match.group(0)

                    content = re.sub(
                        r"Document Date:\s*(\d{4}-\d{2}-\d{2})", _format_mixed, content
                    )

                out_file.write_text(content, encoding="utf-8")
                transform_log["documents_modified"].append(new_filename)
            elif doc_file.suffix.lower() == ".docx":
                try:
                    import docx

                    doc = docx.Document(doc_file)
                    for p in doc.paragraphs:
                        if "VoltKart" in p.text or "VoltCare" in p.text:
                            p.text = p.text.replace("VoltKart", brand_name).replace(
                                "VoltCare", warranty_name
                            )
                        if shift_days != 0:
                            p.text = re.sub(
                                r"(\d{4}-\d{2}-\d{2})",
                                lambda m: shift_date_str(m.group(1), shift_days),
                                p.text,
                            )
                    for tbl in doc.tables:
                        for row in tbl.rows:
                            for cell in row.cells:
                                if "VoltKart" in cell.text or "VoltCare" in cell.text:
                                    cell.text = cell.text.replace("VoltKart", brand_name).replace(
                                        "VoltCare", warranty_name
                                    )
                                if shift_days != 0:
                                    cell.text = re.sub(
                                        r"(\d{4}-\d{2}-\d{2})",
                                        lambda m: shift_date_str(m.group(1), shift_days),
                                        cell.text,
                                    )
                    doc.save(out_file)
                except Exception:
                    shutil.copy2(doc_file, out_file)
                transform_log["documents_modified"].append(new_filename)
            else:
                # For binary files (.pdf), copy to maintain document family
                shutil.copy2(doc_file, out_file)
                transform_log["documents_modified"].append(new_filename)

        # 2b. Table-formatted policy generation and multi-format versions (spec section 10 & 15 V4)
        if table_policy or different_formats:
            table_policy_filename = f"{brand_name}_Return_Policy_2025-09-01.md"
            table_policy_path = docs_out / table_policy_filename
            table_policy_text = f"""# {brand_name} Return & Refund Policy
Document Date: 2025-09-01
Version: 3.0
Status: Active Policy

## Overview
This document outlines customer return privileges and statutory guidelines for {brand_name}.

## Customer Tier Return Windows
| Membership Tier | Return Window (Days) | Exceptions & Waivers |
| :--- | :--- | :--- |
| Standard | 14 days | Standard return window across categories |
| Silver | 21 days | Standard return window across categories |
| Gold | 30 days | All categories except smartphones (10 days) |
| Platinum | 45 days | All categories except smartphones (10 days) |

## Category Exceptions
| Category | Rule |
| :--- | :--- |
| Smartphones | 10 days return window regardless of customer tier |
| Major Appliances | 10 days replacement only |
| Perishables | Non-returnable items |

## Damaged on Delivery
Damaged items upon delivery must be reported within 48 hours for immediate refund.
"""
            table_policy_path.write_text(table_policy_text, encoding="utf-8")
            transform_log["documents_modified"].append(table_policy_filename)

            # Ensure version 3 in Return Policy family is exclusively .md by removing duplicate .txt
            txt_v3_dup = docs_out / f"{brand_name}_Return_Policy_2025-09-01.txt"
            if txt_v3_dup.exists():
                txt_v3_dup.unlink()
                if txt_v3_dup.name in transform_log["documents_modified"]:
                    transform_log["documents_modified"].remove(txt_v3_dup.name)

        # 2c. Fact omission in newest document version (spec section 10 & 15 V4, R-001)
        if omit_facts_in_v3:
            v3_date = shift_date_str("2025-09-01", shift_days)
            v3_filename = f"{brand_name}_Return_Policy_{v3_date}.txt"
            v3_path = docs_out / v3_filename
            v3_text = f"""# {brand_name} Return & Refund Policy
Document Date: {v3_date}
Version: 3.0
Status: Active Policy

## Customer Tier Return Windows
- Standard members: 14 days
- Silver members: 21 days
- Gold members: 30 days
- Platinum members: 45 days

## General Terms
Returns require original packaging and proof of purchase.
Items marked final sale cannot be returned.
"""
            v3_path.write_text(v3_text, encoding="utf-8")
            transform_log["documents_modified"].append(v3_filename)

            # Ensure older version v2 exists and explicitly states damaged items
            v2_date = shift_date_str("2025-01-15", shift_days)
            v2_filename = f"{brand_name}_Return_Policy_{v2_date}.txt"
            v2_path = docs_out / v2_filename
            v2_text = f"""# {brand_name} Return & Refund Policy
Document Date: {v2_date}
Version: 2.0
Status: Superseded

## Customer Tier Return Windows
- Standard members: 14 days
- Silver members: 21 days
- Gold members: 20 days
- Platinum members: 30 days

## Special Circumstances
Damaged items upon delivery must be reported within 48 hours for immediate refund.
Smartphones carry an exception window of 10 days across all membership tiers.
"""
            v2_path.write_text(v2_text, encoding="utf-8")
            transform_log["documents_modified"].append(v2_filename)

    # 3. Data Dictionary
    dict_in = source_dir / "DATA_DICTIONARY.md"
    if dict_in.exists():
        dict_text = dict_in.read_text(encoding="utf-8", errors="replace")
        dict_text = dict_text.replace("VoltKart", brand_name)
        if shift_days != 0:
            dict_text = re.sub(
                r"(\d{4}-\d{2}-\d{2})",
                lambda m: shift_date_str(m.group(1), shift_days),
                dict_text,
            )
        (output_dir / "DATA_DICTIONARY.md").write_text(dict_text, encoding="utf-8")

    return transform_log


PRESETS: dict[str, dict[str, Any]] = {
    "nova": {
        "brand_name": "NovaMart",
        "warranty_name": "NovaCare",
        "shift_days": 0,
        "price_scale": 1.0,
    },
    "shifted": {
        "brand_name": "VoltKart",
        "warranty_name": "VoltCare",
        "shift_days": 45,
        "price_scale": 1.0,
    },
    "scaled": {
        "brand_name": "VoltKart",
        "warranty_name": "VoltCare",
        "shift_days": 0,
        "price_scale": 1.25,
    },
    "full_variation": {
        "brand_name": "ApexRetail",
        "warranty_name": "ApexCare",
        "shift_days": 30,
        "price_scale": 1.10,
        "store_prefix": "STR_",
        "product_prefix": "PRD_",
    },
    "variant_1_apex": {
        "brand_name": "ApexRetail",
        "warranty_name": "ApexCare",
        "shift_days": 30,
        "price_scale": 1.10,
        "store_prefix": "STR_",
        "product_prefix": "PRD_",
        "mixed_date_formats": True,
    },
    "variant_2_zenith_table": {
        "brand_name": "ZenithCommerce",
        "warranty_name": "ZenithCare",
        "shift_days": 0,
        "price_scale": 1.0,
        "table_policy": True,
        "different_formats": True,
    },
    "variant_3_omission": {
        "brand_name": "OmniStore",
        "warranty_name": "OmniCare",
        "shift_days": 15,
        "price_scale": 1.0,
        "omit_facts_in_v3": True,
    },
}


def resolve_default_source() -> Path:
    """Find the default source sample bundle location."""
    candidates = [
        Path("assignment/VoltKart_Sample_Bundle"),
        Path("ml-intern-assignment/assignment/VoltKart_Sample_Bundle"),
    ]
    for c in candidates:
        if c.exists() and (c / "tables").exists():
            return c.resolve()
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate variant test bundles to prove pipeline generalization."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to source bundle (default: assignment/VoltKart_Sample_Bundle)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory to write variant bundle into",
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        default=None,
        help="Use a predefined mutation preset",
    )
    parser.add_argument("--brand", default="NovaMart", help="Brand name replacement")
    parser.add_argument("--warranty", default="NovaCare", help="Warranty program name replacement")
    parser.add_argument("--shift-days", type=int, default=0, help="Days to shift dates")
    parser.add_argument("--price-scale", type=float, default=1.0, help="Price scaling multiplier")
    parser.add_argument("--store-prefix", default=None, help="Prefix to replace store IDs")
    parser.add_argument("--product-prefix", default=None, help="Prefix to replace product IDs")

    args = parser.parse_args()
    source_dir = args.source if args.source else resolve_default_source()

    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    if args.preset:
        preset_cfg = PRESETS[args.preset]
        log = generate_variant(source_dir=source_dir, output_dir=args.output, **preset_cfg)
    else:
        log = generate_variant(
            source_dir=source_dir,
            output_dir=args.output,
            brand_name=args.brand,
            warranty_name=args.warranty,
            shift_days=args.shift_days,
            price_scale=args.price_scale,
            store_prefix=args.store_prefix,
            product_prefix=args.product_prefix,
        )

    print(
        f"Variant bundle generated at {args.output}:\n"
        f"  - Brand: {log['brand_name']}\n"
        f"  - Shift days: {log['shift_days']}\n"
        f"  - Price scale: {log['price_scale']}\n"
        f"  - Tables: {len(log['tables_modified'])}\n"
        f"  - Documents: {len(log['documents_modified'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
