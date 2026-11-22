"""tests/unit/test_sql_sandbox.py - Tests for sandboxed SQL execution and reconciliation."""

from __future__ import annotations

from backend.sql_sandbox import execute_sandboxed_query, reconcile_component_sum
from backend.storage import get_duckdb_read_connection


def test_sandboxed_query_execution():
    res = execute_sandboxed_query("SELECT 1 AS num, 'test' AS str_col;")
    assert res.success
    assert res.row_count == 1
    assert res.rows[0]["num"] == 1
    assert res.rows[0]["str_col"] == "test"
    assert res.execution_time_ms >= 0


def test_sandboxed_row_cap():
    # Generate 200 rows, should cap at 100
    res = execute_sandboxed_query("SELECT unnest(range(200)) AS num;", row_cap=100)
    assert res.success
    assert res.row_count == 100


def test_sandboxed_drop_table_rejection():
    res = execute_sandboxed_query("DROP TABLE orders;")
    assert not res.success
    assert res.error is not None
    # Verify orders table still exists
    with get_duckdb_read_connection() as conn:
        tables = [t[0] for t in conn.execute("SHOW TABLES;").fetchall()]
        assert "orders" in tables


def test_sandboxed_read_csv_rejection():
    res = execute_sandboxed_query("SELECT * FROM read_csv('/etc/passwd');")
    assert not res.success
    assert res.error is not None
    assert "read_csv" in res.error.lower() or "unauthorized" in res.error.lower()


def test_reconcile_component_sum():
    # In sample data, returns table has refund_amount_inr
    with get_duckdb_read_connection() as conn:
        tables = [t[0] for t in conn.execute("SHOW TABLES;").fetchall()]
    if "returns" in tables:
        # Sum of refunds
        res = execute_sandboxed_query('SELECT SUM("refund_amount_inr") AS total FROM "returns";')
        assert res.success
        total = float(res.rows[0]["total"])
        is_rec, unjoined, diff = reconcile_component_sum("returns", "refund_amount_inr", total)
        assert is_rec
        assert diff == 0.0


def test_deliberate_fan_out_query_fails_reconciliation():
    """Verify join fan-out inflation is detected by reconciliation check (R-020)."""
    with get_duckdb_read_connection() as conn:
        tables = [t[0] for t in conn.execute("SHOW TABLES;").fetchall()]
    if "returns" in tables:
        # Deliberately fanned-out / inflated component sum
        inflated_component_total = 2500000.0
        is_rec, unjoined, diff = reconcile_component_sum(
            "returns", "refund_amount_inr", inflated_component_total
        )
        assert not is_rec
        assert diff > 1000.0
