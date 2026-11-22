"""tests/unit/test_sample_bundle_ingestion.py - End-to-end verification of sample bundle.

Verifies spec 7.1 and Phase 2 gate requirements:
- All 6 tables profiled with exact row counts, primary keys, and inferred/declared relationships.
- All 8 documents extracted with dates, sources, and grouped into exactly 4 version families.
- Data dictionary automatically included into schema card context without polluting documents list.
"""

from pathlib import Path

from backend.ingestion import (
    get_active_schema_card,
    ingest_files,
)
from backend.storage import reset_storage


def test_full_sample_bundle_ingestion():
    """Verify ingestion of the full sample bundle (6 tables, 8 documents, DATA_DICTIONARY.md)."""
    reset_storage()

    bundle_dir = Path("assignment/VoltKart_Sample_Bundle")
    if not bundle_dir.exists():
        return

    files: list[tuple[str, bytes]] = []

    # 1. 6 CSV tables
    for p in sorted((bundle_dir / "tables").glob("*.csv")):
        files.append((p.name, p.read_bytes()))

    # 2. 8 dated documents
    for p in sorted((bundle_dir / "documents").glob("*.*")):
        files.append((p.name, p.read_bytes()))

    # 3. Data Dictionary
    dict_file = bundle_dir / "DATA_DICTIONARY.md"
    if dict_file.exists():
        files.append((dict_file.name, dict_file.read_bytes()))

    summary = ingest_files(files)

    # Assert 0 errors
    assert len(summary.errors) == 0, f"Unexpected upload errors: {summary.errors}"

    # Assert 6 tables with expected rows
    assert len(summary.tables) == 6
    tbl_rows = {t.table_name: t.row_count for t in summary.tables}
    expected_rows = {
        "customers": 140,
        "order_items": 1329,
        "orders": 900,
        "products": 22,
        "returns": 64,
        "stores": 8,
    }
    assert tbl_rows == expected_rows

    # Assert primary keys
    tbl_pks = {t.table_name: t.primary_key for t in summary.tables}
    expected_pks = {
        "customers": "customer_id",
        "order_items": "order_item_id",
        "orders": "order_id",
        "products": "product_id",
        "returns": "return_id",
        "stores": "store_id",
    }
    assert tbl_pks == expected_pks

    # Assert declared/inferred relationships
    all_rels = [rel for t in summary.tables for rel in t.inferred_relationships]
    assert len(all_rels) >= 5
    assert any(
        r.from_table == "orders" and r.from_column == "customer_id" and r.to_table == "customers"
        for r in all_rels
    )
    assert any(
        r.from_table == "orders" and r.from_column == "store_id" and r.to_table == "stores"
        for r in all_rels
    )
    assert any(
        r.from_table == "order_items" and r.from_column == "order_id" and r.to_table == "orders"
        for r in all_rels
    )
    assert any(
        r.from_table == "order_items" and r.from_column == "product_id" and r.to_table == "products"
        for r in all_rels
    )
    assert any(
        r.from_table == "returns"
        and r.from_column == "order_item_id"
        and r.to_table == "order_items"
        for r in all_rels
    )

    # Assert exactly 8 documents
    assert len(summary.documents) == 8
    for doc in summary.documents:
        assert doc.doc_date is not None, f"Document {doc.file_name} missing date"
        assert doc.doc_date_source == "body", f"Expected body date for {doc.file_name}"
        assert doc.date_disagreement is False
        assert doc.chunk_count > 0

    # Assert exactly 4 version families
    assert len(summary.version_families) == 4
    expected_families = {
        "extended warranty terms",
        "job description machine learning engineer",
        "return refund policy",
        "store operations notice",
    }
    assert set(summary.version_families.keys()) == expected_families

    # Assert documentation loaded and included in schema card
    assert summary.documentation_loaded is True
    card = get_active_schema_card()
    assert "# Database Schema Card" in card
    assert "Business Definitions & Data Documentation" in card
