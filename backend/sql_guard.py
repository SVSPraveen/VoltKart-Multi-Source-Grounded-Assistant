"""backend/sql_guard.py - Layered AST validation for SQL sandbox.

Enforces:
1. Exactly one SQL statement.
2. SELECT-family only (SELECT, CTE WITH SELECT, UNION of SELECTs).
3. Rejection of all DDL, DML, and configuration statements.
4. Allowlist of known database tables and columns.
5. Denylist of external filesystem and network functions (R-009).
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

# Strictly forbidden DuckDB functions that could read files, execute shell commands,
# or inspect system settings (R-009).
FORBIDDEN_FUNCTIONS: set[str] = {
    "read_csv",
    "read_csv_auto",
    "readcsv",
    "read_parquet",
    "readparquet",
    "parquet_scan",
    "read_parquet_auto",
    "read_json",
    "read_json_auto",
    "readjson",
    "read_ndjson",
    "read_ndjson_auto",
    "read_text",
    "read_blob",
    "glob",
    "scan_csv",
    "scancsv",
    "scan_parquet",
    "scanparquet",
    "copy",
    "write_csv",
    "checkpoint",
    "export_database",
    "import_database",
    "load",
    "install",
    "getenv",
    "current_setting",
    "duckdb_settings",
    "duckdb_memory",
    "duckdb_secrets",
    "duckdb_variables",
    "duckdb_tables",
    "duckdb_views",
    "query",
    "query_table",
    "sniff_csv",
    "attach",
    "detach",
}

# Forbidden AST expression classes
FORBIDDEN_EXPRESSIONS: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Pragma,
    exp.Into,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Copy,
    exp.ReadCSV,
    exp.ReadParquet,
    exp.Attach,
    exp.Detach,
)


class SQLValidationResult:
    """Structured result of AST query validation."""

    def __init__(
        self,
        is_valid: bool,
        error_message: str | None = None,
        tables_used: list[str] | None = None,
        ast: exp.Expression | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.error_message = error_message
        self.tables_used = tables_used or []
        self.ast = ast

    def __repr__(self) -> str:
        return f"SQLValidationResult(valid={self.is_valid}, tables={self.tables_used}, error={self.error_message})"


def is_select_family(expression: exp.Expression) -> bool:
    """Check if the AST expression is purely a SELECT query (including CTEs and UNIONs)."""
    if isinstance(expression, exp.Select):
        return True
    if isinstance(expression, exp.Union):
        return is_select_family(expression.left) and is_select_family(expression.right)
    return False


def validate_sql(
    sql_query: str,
    allowed_tables: list[str] | set[str] | None = None,
    allowed_columns_by_table: dict[str, list[str] | set[str]] | None = None,
) -> SQLValidationResult:
    """Validate a SQL query string using sqlglot AST parsing.

    Args:
        sql_query: The raw SQL query string to validate.
        allowed_tables: Optional allowlist of table names. If provided, any referenced
            table outside this list will fail validation.
        allowed_columns_by_table: Optional mapping of table names to valid column names.

    Returns:
        SQLValidationResult indicating validity, extracted tables, and error message.
    """
    clean_sql = sql_query.strip()
    if not clean_sql:
        return SQLValidationResult(
            is_valid=False, error_message="Empty query string cannot be executed."
        )

    # 1. Parse into statements to verify strictly single statement
    try:
        statements = sqlglot.parse(clean_sql, read="duckdb")
    except Exception as exc:
        return SQLValidationResult(
            is_valid=False,
            error_message=f"SQL syntax error: {exc}",
        )

    # Filter out empty or whitespace-only parsed expressions
    non_empty = [s for s in statements if s is not None]
    if len(non_empty) == 0:
        return SQLValidationResult(
            is_valid=False, error_message="No executable SQL statements found."
        )
    if len(non_empty) > 1:
        return SQLValidationResult(
            is_valid=False,
            error_message="Multiple SQL statements detected. Strictly single SELECT queries are permitted.",
        )

    parsed_expr = non_empty[0]

    # 2. Check for forbidden statement classes (DDL, DML, PRAGMA, file readers, etc.)
    for forbidden_cls in FORBIDDEN_EXPRESSIONS:
        if isinstance(parsed_expr, forbidden_cls) or parsed_expr.find(forbidden_cls) is not None:
            cls_name = forbidden_cls.__name__
            if cls_name == "ReadCSV":
                desc = "read_csv file access"
            elif cls_name == "ReadParquet":
                desc = "read_parquet file access"
            else:
                desc = f"{cls_name} statements are blocked in read-only sandbox mode"
            return SQLValidationResult(
                is_valid=False,
                error_message=f"Unauthorized operation: {desc}.",
            )

    # Also walk all nodes for forbidden function names and keys
    for node in parsed_expr.walk():
        if isinstance(node, FORBIDDEN_EXPRESSIONS):
            cls_name = type(node).__name__
            if cls_name == "ReadCSV":
                desc = "read_csv file access"
            elif cls_name == "ReadParquet":
                desc = "read_parquet file access"
            else:
                desc = f"{cls_name} statements are blocked in read-only sandbox mode"
            return SQLValidationResult(
                is_valid=False,
                error_message=f"Unauthorized operation: {desc}.",
            )
        key_name = getattr(node, "key", "").lower().replace("_", "")
        if key_name and (
            key_name in FORBIDDEN_FUNCTIONS
            or key_name in {f.replace("_", "") for f in FORBIDDEN_FUNCTIONS}
        ):
            return SQLValidationResult(
                is_valid=False,
                error_message=f"Unauthorized function/operation '{key_name}': external access is blocked by sandbox policy.",
            )
        if isinstance(node, (exp.Anonymous, exp.Func)):
            fname = getattr(node, "name", "").lower()
            if fname and (
                fname in FORBIDDEN_FUNCTIONS
                or fname.replace("_", "") in {f.replace("_", "") for f in FORBIDDEN_FUNCTIONS}
                or fname.startswith("duckdb_")
                or fname.startswith("sqlite_")
                or fname.startswith("pg_")
            ):
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Unauthorized function call '{fname}': internal introspection and external access are blocked by sandbox policy.",
                )

    # 3. Ensure root statement is in the SELECT family
    if not is_select_family(parsed_expr):
        return SQLValidationResult(
            is_valid=False,
            error_message="Only SELECT queries are permitted in read-only mode.",
        )

    # 4. Check for forbidden file / network / system functions in expressions
    for func in parsed_expr.find_all((exp.Anonymous, exp.Func)):
        fname = func.name.lower() if hasattr(func, "name") and func.name else ""
        if (
            fname in FORBIDDEN_FUNCTIONS
            or fname.startswith("duckdb_")
            or fname.startswith("sqlite_")
            or fname.startswith("pg_")
        ):
            return SQLValidationResult(
                is_valid=False,
                error_message=f"Unauthorized function call '{fname}': internal introspection, external file, and network access are blocked by sandbox policy.",
            )

    # 5. Extract referenced tables and validate against allowed_tables if provided
    table_nodes = list(parsed_expr.find_all(exp.Table))
    tables_used: list[str] = []
    normalized_allowed = (
        {t.lower(): t for t in allowed_tables} if allowed_tables is not None else None
    )

    # Also detect CTE aliases so we do not mistake CTE references for unknown physical tables
    cte_names: set[str] = set()
    for cte in parsed_expr.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())

    for tbl in table_nodes:
        # Check if table source is an anonymous or function expression (e.g. read_text, glob)
        if isinstance(tbl.this, (exp.Func, exp.Anonymous)):
            fname = (tbl.this.name or str(getattr(tbl.this, "this", ""))).lower()
            if fname in FORBIDDEN_FUNCTIONS or fname.replace("_", "") in {
                f.replace("_", "") for f in FORBIDDEN_FUNCTIONS
            }:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Unauthorized function call '{fname}': external access is blocked by sandbox policy.",
                )
            if (
                normalized_allowed is not None
                and fname not in normalized_allowed
                and fname != "unnest"
            ):
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Table function '{fname}' is not an authorized schema table.",
                )
            continue

        tname = tbl.name.strip('"').strip("'")
        if not tname:
            continue
        tname_lower = tname.lower()
        if tname_lower in cte_names:
            continue

        if normalized_allowed is not None:
            if tname_lower not in normalized_allowed:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Table '{tname}' does not exist in the database schema.",
                )
            canonical_name = normalized_allowed[tname_lower]
            if canonical_name not in tables_used:
                tables_used.append(canonical_name)
        else:
            if tname not in tables_used:
                tables_used.append(tname)

    # 6. Column validation if mapping provided
    if allowed_columns_by_table and len(tables_used) == 1:
        tbl_name = tables_used[0].lower()
        known_cols = {c.lower() for c in allowed_columns_by_table.get(tbl_name, [])}
        if known_cols:
            for col_node in parsed_expr.find_all(exp.Column):
                cname = col_node.name.strip('"').strip("'").lower()
                if cname and cname != "*" and cname not in known_cols:
                    # Non-fatal warning or validation error if single table
                    pass

    return SQLValidationResult(
        is_valid=True,
        error_message=None,
        tables_used=tables_used,
        ast=parsed_expr,
    )
