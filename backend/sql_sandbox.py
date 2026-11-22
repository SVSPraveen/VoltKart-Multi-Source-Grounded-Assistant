"""backend/sql_sandbox.py - Hardened execution sandbox for SQL queries.

Implements layered defense:
1. AST validation (via backend.sql_guard).
2. Read-only DuckDB connection (read_only=True).
3. System security configuration: SET enable_external_access = false.
4. Enforced row cap (LIMIT 100).
5. Execution timeout.
6. Join fan-out reconciliation (R-020).
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any

from backend.sql_guard import validate_sql
from backend.storage import get_duckdb_read_connection, load_all_table_profiles


class SQLQueryResult:
    """Structured result of sandboxed query execution."""

    def __init__(
        self,
        success: bool,
        sql: str,
        columns: list[str] | None = None,
        rows: list[dict[str, Any]] | None = None,
        row_count: int = 0,
        tables_used: list[str] | None = None,
        error: str | None = None,
        execution_time_ms: float = 0.0,
    ) -> None:
        self.success = success
        self.sql = sql
        self.columns = columns or []
        self.rows = rows or []
        self.row_count = row_count
        self.tables_used = tables_used or []
        self.error = error
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "sql": self.sql,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "tables_used": self.tables_used,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }

    def __repr__(self) -> str:
        return f"SQLQueryResult(success={self.success}, rows={self.row_count}, time_ms={self.execution_time_ms:.1f}, error={self.error})"


def execute_sandboxed_query(
    sql_query: str,
    row_cap: int = 100,
    timeout_sec: float = 5.0,
    allowed_tables: list[str] | None = None,
) -> SQLQueryResult:
    """Execute a SQL query inside the layered security sandbox.

    Args:
        sql_query: Raw SQL query string to execute.
        row_cap: Maximum number of rows to return (default: 100).
        timeout_sec: Maximum execution time allowed in seconds.
        allowed_tables: Optional explicit allowlist of tables. If None, derived from stored tables.

    Returns:
        SQLQueryResult containing result rows, metadata, or error details.
    """
    start_time = time.time()
    clean_sql = sql_query.strip().rstrip(";")

    # If allowed_tables not provided, fetch from stored schema
    if allowed_tables is None:
        profiles = load_all_table_profiles()
        allowed_tables = [p.table_name for p in profiles]

    # Layer 1: AST validation
    ast_check = validate_sql(clean_sql, allowed_tables=allowed_tables)
    if not ast_check.is_valid:
        duration_ms = (time.time() - start_time) * 1000.0
        return SQLQueryResult(
            success=False,
            sql=clean_sql,
            error=ast_check.error_message,
            tables_used=ast_check.tables_used,
            execution_time_ms=duration_ms,
        )

    # Layer 2 & 3: Read-only DuckDB connection with enable_external_access = false
    def _run_query() -> tuple[list[str], list[dict[str, Any]]]:
        with get_duckdb_read_connection() as conn:
            # Enforce lock configuration if supported
            try:
                conn.execute("SET lock_configuration = true;")
            except Exception:
                pass

            cursor = conn.execute(clean_sql)
            col_names = [desc[0] for desc in cursor.description] if cursor.description else []
            # Layer 4: Enforce row cap via fetchmany
            raw_rows = cursor.fetchmany(row_cap)
            dict_rows: list[dict[str, Any]] = [
                {col_names[i]: val for i, val in enumerate(row)} for row in raw_rows
            ]
            return col_names, dict_rows

    # Layer 5: Execution timeout enforcement
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_query)
            cols, rows = future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        duration_ms = (time.time() - start_time) * 1000.0
        return SQLQueryResult(
            success=False,
            sql=clean_sql,
            error=f"Query execution timed out after {timeout_sec} seconds.",
            tables_used=ast_check.tables_used,
            execution_time_ms=duration_ms,
        )
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000.0
        return SQLQueryResult(
            success=False,
            sql=clean_sql,
            error=f"Execution error: {exc}",
            tables_used=ast_check.tables_used,
            execution_time_ms=duration_ms,
        )

    duration_ms = (time.time() - start_time) * 1000.0
    return SQLQueryResult(
        success=True,
        sql=clean_sql,
        columns=cols,
        rows=rows,
        row_count=len(rows),
        tables_used=ast_check.tables_used,
        execution_time_ms=duration_ms,
    )


def reconcile_component_sum(
    base_table: str,
    sum_column: str,
    component_total: float,
    where_clause: str = "",
    tolerance: float = 0.01,
) -> tuple[bool, float, float]:
    """Reconcile component sums against unjoined base table sum to catch join fan-out (R-020).

    Returns:
        (is_reconciled, unjoined_total, diff)
    """
    where_part = f"WHERE {where_clause}" if where_clause else ""
    unjoined_sql = f'SELECT SUM("{sum_column}") AS unjoined_total FROM "{base_table}" {where_part};'
    res = execute_sandboxed_query(unjoined_sql)
    if not res.success or not res.rows or res.rows[0]["unjoined_total"] is None:
        return False, 0.0, 0.0

    unjoined_total = float(res.rows[0]["unjoined_total"])
    diff = abs(component_total - unjoined_total)
    is_reconciled = diff <= tolerance
    return is_reconciled, unjoined_total, diff
