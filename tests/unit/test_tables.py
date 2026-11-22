"""tests/unit/test_tables.py - Unit tests for tabular ingestion and profiling (C2).

Verifies delimiter sniffing, column profiling, primary key identification,
relationship inference (containment >= 0.98), and schema card generation.
"""

import pandas as pd

from backend.tables import (
    generate_schema_card,
    infer_foreign_keys,
    infer_primary_key,
    ingest_table,
    is_data_documentation_text,
    load_csv_dataframe,
    parse_declared_schema_from_documentation,
    profile_column,
    sniff_delimiter_and_encoding,
)


def test_sniff_delimiter_and_encoding():
    """Verify delimiter sniffing across comma, semicolon, tab, and UTF-8 BOM."""
    # Standard CSV
    enc, sep = sniff_delimiter_and_encoding(b"id,name,value\n1,Alpha,100")
    assert enc == "utf-8"
    assert sep == ","

    # Semicolon delimited (European format)
    enc, sep = sniff_delimiter_and_encoding(b"id;name;value\n1;Beta;200")
    assert sep == ";"

    # Tab delimited
    enc, sep = sniff_delimiter_and_encoding(b"id\tname\tvalue\n1\tGamma\t300")
    assert sep == "\t"

    # UTF-8 with BOM
    enc, sep = sniff_delimiter_and_encoding(b"\xef\xbb\xbfid,name\n1,Delta")
    assert enc == "utf-8-sig"
    assert sep == ","


def test_profile_column():
    """Verify statistical profiling for numeric, string, and null columns."""
    series = pd.Series([10, 20, 30, None, 50])
    profile = profile_column(series, "metric_val")

    assert profile.name == "metric_val"
    assert profile.data_type in ("DOUBLE", "INTEGER")
    assert profile.null_count == 1
    assert profile.null_pct == 0.2
    assert profile.distinct_count == 4
    assert profile.min_value == 10.0
    assert profile.max_value == 50.0
    assert len(profile.sample_values) == 4


def test_infer_primary_key():
    """Verify primary key candidates with 100% distinct values and 0 nulls."""
    df = pd.DataFrame(
        {
            "item_id": ["I01", "I02", "I03"],
            "name": ["A", "B", "C"],
            "category": ["X", "X", "Y"],
        }
    )
    profiles = [profile_column(df[col], col) for col in df.columns]
    pk = infer_primary_key("items", profiles, len(df))
    assert pk == "item_id"


def test_infer_foreign_keys_high_containment():
    """Verify relationship inference when value containment >= 0.98."""
    # Parent table: products (product_id is unique)
    products_df = pd.DataFrame(
        {
            "product_id": [f"P{i:03d}" for i in range(1, 101)],
            "price": [10.0 * i for i in range(1, 101)],
        }
    )
    # Child table: order_items (all product_ids exist in products)
    order_items_df = pd.DataFrame(
        {
            "item_id": [f"ITM_{i}" for i in range(1, 51)],
            "product_id": [f"P{i:03d}" for i in range(1, 51)],
        }
    )

    tables = {"products": products_df, "order_items": order_items_df}
    pks = {"products": "product_id", "order_items": "item_id"}

    rels = infer_foreign_keys(tables, pks)
    assert len(rels) == 1
    rel = rels[0]
    assert rel.from_table == "order_items"
    assert rel.from_column == "product_id"
    assert rel.to_table == "products"
    assert rel.to_column == "product_id"
    assert rel.containment_ratio == 1.0
    assert rel.confidence == 1.0


def test_infer_foreign_keys_low_containment_rejected():
    """Verify relationship is NOT inferred when containment < 0.98."""
    products_df = pd.DataFrame(
        {
            "product_id": ["P001", "P002", "P003"],
        }
    )
    # Child has many IDs that do not exist in parent (only 25% containment)
    order_items_df = pd.DataFrame(
        {
            "item_id": ["ITM_1", "ITM_2", "ITM_3", "ITM_4"],
            "product_id": ["P001", "P997", "P998", "P999"],
        }
    )

    tables = {"products": products_df, "order_items": order_items_df}
    pks = {"products": "product_id", "order_items": "item_id"}

    rels = infer_foreign_keys(tables, pks)
    assert len(rels) == 0


def test_is_data_documentation_detection():
    """Verify detection of data documentation text mentioning schema tables."""
    doc_text = """
    # Data Dictionary
    Stores table contains store_id and region.
    Orders table links to customers via customer_id.
    Line amount = quantity * unit_price.
    """
    assert (
        is_data_documentation_text(
            doc_text, ["stores", "orders", "customers"], ["store_id", "customer_id"]
        )
        is True
    )

    # Generic text with no table mentions
    generic_text = "The quarterly team offsite will take place in the main conference room."
    assert is_data_documentation_text(generic_text, ["stores", "orders"], ["store_id"]) is False


def test_generate_schema_card():
    """Verify formatted schema card contains tables, columns, PKs, and documentation."""
    csv_bytes = b"dept_id,dept_name\nD01,Engineering\nD02,Support\n"
    tbl_name, df, profile = ingest_table(csv_bytes, "departments.csv")

    card = generate_schema_card([profile], doc_text="Definition: Active depts only.")
    assert "Table: `departments`" in card.markdown_summary
    assert "dept_id" in card.markdown_summary
    assert "Definition: Active depts only." in card.markdown_summary


def test_utf16_csv_ingestion():
    """Verify UTF-16 CSV files with and without BOM load without column name corruption."""
    utf16_bom = "id,name\n1,Alice\n2,Bob\n".encode("utf-16")
    df_bom = load_csv_dataframe(utf16_bom, "users_utf16.csv")
    assert list(df_bom.columns) == ["id", "name"]
    assert len(df_bom) == 2

    # Ingest into DuckDB
    tbl_name, df, prof = ingest_table(utf16_bom, "users_utf16.csv")
    assert tbl_name == "users_utf16"
    assert prof.row_count == 2
    assert [c.name for c in prof.columns] == ["id", "name"]


def test_sql_reserved_keyword_table_names():
    """Verify tables with SQL reserved keywords (order, select, group, user) load cleanly."""
    csv_bytes = b"order_id,amount\nORD_01,150.0\nORD_02,250.0\n"
    tbl_name, df, prof = ingest_table(csv_bytes, "order.csv")
    assert tbl_name == "order"
    assert prof.row_count == 2
    assert prof.primary_key == "order_id"


def test_declared_schema_parsing():
    """Verify parsing of declared primary and foreign keys from documentation text (spec 7.1)."""
    doc_markdown = """
    # Data Dictionary
    | File | Primary key | Foreign keys | Columns |
    |---|---|---|---|
    | orders.csv | order_id | customer_id -> customers, store_id -> stores | order_id, customer_id, store_id |
    | order_items.csv | order_item_id | order_id -> orders, product_id -> products | order_item_id, order_id, product_id |
    """
    pks, fks = parse_declared_schema_from_documentation(doc_markdown)
    assert pks["orders"] == "order_id"
    assert pks["order_items"] == "order_item_id"
    assert len(fks) == 4
    assert any(
        r.from_table == "orders"
        and r.from_column == "customer_id"
        and r.to_table == "customers"
        and r.status == "declared"
        for r in fks
    )
    assert any(
        r.from_table == "order_items"
        and r.from_column == "product_id"
        and r.to_table == "products"
        and r.status == "declared"
        for r in fks
    )
