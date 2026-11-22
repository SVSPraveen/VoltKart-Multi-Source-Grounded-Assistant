"""tests/unit/test_sql_guard.py - Unit tests for AST SQL validation and sandbox guards."""

from __future__ import annotations

from backend.sql_guard import validate_sql


def test_valid_select_query():
    sql = "SELECT order_id, order_status FROM orders WHERE order_status = 'Delivered' LIMIT 10;"
    result = validate_sql(sql, allowed_tables=["orders"])
    assert result.is_valid
    assert result.tables_used == ["orders"]
    assert result.error_message is None


def test_valid_join_query():
    sql = """
    SELECT o.order_id, oi.unit_price_inr, s.store_name
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN stores s ON o.store_id = s.store_id
    WHERE o.order_status = 'Delivered';
    """
    result = validate_sql(sql, allowed_tables=["orders", "order_items", "stores"])
    assert result.is_valid
    assert sorted(result.tables_used) == ["order_items", "orders", "stores"]


def test_valid_cte_query():
    sql = """
    WITH delivered_rev AS (
        SELECT store_id, SUM(unit_price_inr) as rev
        FROM orders
        GROUP BY store_id
    )
    SELECT * FROM delivered_rev ORDER BY rev DESC;
    """
    result = validate_sql(sql, allowed_tables=["orders"])
    assert result.is_valid
    assert result.tables_used == ["orders"]


def test_reject_drop_table():
    sql = "DROP TABLE orders;"
    result = validate_sql(sql, allowed_tables=["orders"])
    assert not result.is_valid
    assert (
        "blocked in read-only sandbox mode" in result.error_message
        or "DROP" in result.error_message.upper()
    )


def test_reject_insert():
    sql = "INSERT INTO orders (order_id) VALUES ('O99999');"
    result = validate_sql(sql, allowed_tables=["orders"])
    assert not result.is_valid
    assert "blocked in read-only sandbox mode" in result.error_message


def test_reject_delete():
    sql = "DELETE FROM orders WHERE order_id = 'O00001';"
    result = validate_sql(sql, allowed_tables=["orders"])
    assert not result.is_valid
    assert "blocked in read-only sandbox mode" in result.error_message


def test_reject_multiple_statements():
    sql = "SELECT * FROM orders; DROP TABLE orders;"
    result = validate_sql(sql, allowed_tables=["orders"])
    assert not result.is_valid
    assert "Multiple SQL statements detected" in result.error_message


def test_reject_forbidden_read_csv():
    sql = "SELECT * FROM read_csv('/etc/passwd');"
    result = validate_sql(sql, allowed_tables=["orders"])
    assert not result.is_valid
    assert "read_csv" in result.error_message


def test_reject_unknown_table():
    sql = "SELECT * FROM super_secret_credentials;"
    result = validate_sql(sql, allowed_tables=["orders", "customers"])
    assert not result.is_valid
    assert "super_secret_credentials" in result.error_message
