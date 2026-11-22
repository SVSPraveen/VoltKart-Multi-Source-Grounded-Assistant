"""tests/unit/test_variants.py - Verify variant generator functionality."""

from pathlib import Path

import pandas as pd

from tests.variants.make_variant import generate_variant, shift_date_str


def test_shift_date_str():
    assert shift_date_str("2025-01-15", 10) == "2025-01-25"
    assert shift_date_str("2025-01-15", -5) == "2025-01-10"
    assert shift_date_str("invalid", 10) == "invalid"


def test_generate_variant_minimal(tmp_path: Path):
    src = tmp_path / "src"
    src_tables = src / "tables"
    src_docs = src / "documents"
    src_tables.mkdir(parents=True)
    src_docs.mkdir(parents=True)

    # Mock stores.csv
    df_stores = pd.DataFrame([{"store_id": "S01", "store_name": "VoltKart Indiranagar"}])
    df_stores.to_csv(src_tables / "stores.csv", index=False)

    # Mock doc
    (src_docs / "VoltKart_Return_Policy_2025.txt").write_text("VoltKart Return Policy")

    out = tmp_path / "out"
    log = generate_variant(
        source_dir=src,
        output_dir=out,
        brand_name="ApexRetail",
        warranty_name="ApexCare",
        shift_days=0,
        price_scale=1.0,
    )

    assert (out / "tables" / "stores.csv").exists()
    assert len(log["tables_modified"]) == 1
    assert "stores.csv" in log["tables_modified"]
    out_stores = pd.read_csv(out / "tables" / "stores.csv")
    assert out_stores["store_name"].iloc[0] == "ApexRetail Indiranagar"

    # Verify doc rename & brand replacement
    assert (out / "documents" / "ApexRetail_Return_Policy_2025.txt").exists()
    doc_content = (out / "documents" / "ApexRetail_Return_Policy_2025.txt").read_text()
    assert "ApexRetail" in doc_content
    assert "VoltKart" not in doc_content
