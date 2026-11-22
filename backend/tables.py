"""backend/tables.py - Tabular data loader, profiler, and schema card generator.

Loads relational CSV tables into DuckDB, profiles column statistics and types,
infers primary and foreign key relationships via value containment and name matching,
detects uploaded data dictionaries, and builds structured schema cards for SQL agents.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

import pandas as pd

from backend.models import (
    ColumnProfile,
    InferredRelationship,
    SchemaCard,
    TableProfile,
)
from backend.storage import get_duckdb_write_connection


def sniff_delimiter_and_encoding(raw_bytes: bytes) -> tuple[str, str]:
    """Sniff text encoding and CSV delimiter from raw bytes."""
    # Check BOMs first
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    elif raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        encoding = "utf-16"
    elif b"\x00" in raw_bytes[:4096]:
        # Contains null bytes -> check if UTF-16
        try:
            raw_bytes[:4096].decode("utf-16")
            encoding = "utf-16"
        except UnicodeDecodeError:
            try:
                raw_bytes[:4096].decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "utf-16"
    else:
        # Check standard encodings with strict decoding
        encoding = "utf-8"
        for enc in ("utf-8", "cp1252", "iso-8859-1"):
            try:
                raw_bytes.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue

    try:
        text_sample = raw_bytes[:8192].decode(encoding, errors="replace")
    except Exception:
        text_sample = raw_bytes[:8192].decode("utf-8", errors="replace")

    # Sniff delimiter
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(text_sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        # Fallback heuristic: count frequency of candidate delimiters in first 5 lines
        lines = [line for line in text_sample.splitlines() if line.strip()][:5]
        if lines:
            counts = {d: sum(line.count(d) for line in lines) for d in [",", ";", "\t", "|"]}
            delimiter = max(counts, key=counts.get) if max(counts.values()) > 0 else ","

    return encoding, delimiter


def load_csv_dataframe(file_path_or_bytes: Path | bytes, filename: str) -> pd.DataFrame:
    """Load a CSV into a pandas DataFrame with automatic delimiter/encoding detection."""
    if isinstance(file_path_or_bytes, bytes):
        raw_bytes = file_path_or_bytes
    else:
        raw_bytes = Path(file_path_or_bytes).read_bytes()

    if len(raw_bytes.strip()) == 0:
        raise ValueError(f"File {filename} is empty (0 bytes)")

    encoding, delimiter = sniff_delimiter_and_encoding(raw_bytes)
    df = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, sep=delimiter)

    # Clean column names (strip whitespace and special chars)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def sanitize_table_name(filename: str) -> str:
    """Derive a safe SQL table name from a file name."""
    stem = Path(filename).stem
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", stem).lower()
    if clean and clean[0].isdigit():
        clean = f"t_{clean}"
    return clean or "table"


def to_singular(name: str) -> str:
    """Derive singular form of a table or entity name for relationship matching."""
    name_lower = name.lower()
    if name_lower.endswith("ies"):
        return name_lower[:-3] + "y"
    if name_lower.endswith("ses"):
        return name_lower[:-2]
    if name_lower.endswith("s") and not name_lower.endswith("ss"):
        return name_lower[:-1]
    return name_lower


def profile_column(series: pd.Series, name: str) -> ColumnProfile:
    """Profile nulls, cardinality, min/max, and sample values of a column."""
    total = len(series)
    null_count = int(series.isna().sum())
    null_pct = round(null_count / total, 4) if total > 0 else 0.0

    valid = series.dropna()
    distinct_count = int(valid.nunique())

    # Format min and max safely (avoiding AttributeError on pandas Timestamps)
    min_val: Any = None
    max_val: Any = None
    if not valid.empty:
        try:
            raw_min = valid.min()
            raw_max = valid.max()
            min_val = (
                raw_min.item()
                if hasattr(raw_min, "item") and not isinstance(raw_min, pd.Timestamp)
                else str(raw_min)
            )
            max_val = (
                raw_max.item()
                if hasattr(raw_max, "item") and not isinstance(raw_max, pd.Timestamp)
                else str(raw_max)
            )
        except Exception:
            pass

    # Extract up to 5 diverse distinct non-null samples safely
    unique_vals = valid.unique()[:5]
    samples: list[Any] = []
    for v in unique_vals:
        if hasattr(v, "item") and not isinstance(v, pd.Timestamp):
            samples.append(v.item())
        else:
            samples.append(str(v))

    # Map pandas dtype to clean SQL type name
    dtype_str = str(series.dtype).lower()
    if "int" in dtype_str:
        sql_type = "INTEGER"
    elif "float" in dtype_str:
        sql_type = "DOUBLE"
    elif "bool" in dtype_str:
        sql_type = "BOOLEAN"
    elif "datetime" in dtype_str:
        sql_type = "TIMESTAMP"
    else:
        sql_type = "VARCHAR"

    return ColumnProfile(
        name=name,
        data_type=sql_type,
        null_count=null_count,
        null_pct=null_pct,
        distinct_count=distinct_count,
        min_value=min_val,
        max_value=max_val,
        sample_values=samples,
    )


def infer_primary_key(
    table_name: str, profiles: list[ColumnProfile], total_rows: int
) -> str | None:
    """Infer primary key column candidate based on uniqueness and naming conventions."""
    if total_rows == 0:
        return None

    # Priority 1: Column matching {table}_id or {singular}_id with 100% distinct values and 0 nulls
    singular = to_singular(table_name)
    for p in profiles:
        if p.null_count == 0 and p.distinct_count == total_rows:
            if p.name.lower() in (f"{table_name}_id", f"{singular}_id", "id"):
                return p.name

    # Priority 2: Any column ending in _id with 100% distinct values and 0 nulls
    for p in profiles:
        if p.null_count == 0 and p.distinct_count == total_rows and p.name.lower().endswith("_id"):
            return p.name

    # Priority 3: First column if it has 100% distinct values and 0 nulls
    if profiles and profiles[0].null_count == 0 and profiles[0].distinct_count == total_rows:
        return profiles[0].name

    return None


def parse_declared_schema_from_documentation(
    doc_text: str,
) -> tuple[dict[str, str], list[InferredRelationship]]:
    """Parse declared primary and foreign keys from uploaded data dictionary documentation.

    Adheres to spec 7.1: 'prefer keys declared in any uploaded documentation'.
    """
    declared_pks: dict[str, str] = {}
    declared_rels: list[InferredRelationship] = []

    for line in doc_text.splitlines():
        line_clean = line.strip()
        if not line_clean.startswith("|") or line_clean.startswith("|---"):
            continue
        cells = [c.strip() for c in line_clean.strip("|").split("|")]
        if len(cells) < 3:
            continue
        file_or_tbl = cells[0].lower()
        if "file" in file_or_tbl or "table" in file_or_tbl:
            continue
        tbl_name = sanitize_table_name(file_or_tbl.replace(".csv", "").strip())

        # Primary key in cell 1
        pk_val = cells[1].strip()
        if pk_val and not pk_val.lower().startswith("none"):
            declared_pks[tbl_name] = pk_val

        # Foreign keys in cell 2 (e.g. "order_id -> orders, product_id -> products")
        fk_val = cells[2].strip()
        if fk_val and "->" in fk_val:
            for part in fk_val.split(","):
                if "->" in part:
                    left, right = part.split("->", 1)
                    from_col = left.strip()
                    target = right.strip()
                    target_tbl = sanitize_table_name(target.replace(".csv", ""))
                    to_col = from_col
                    if "." in target:
                        t_parts = target.split(".", 1)
                        target_tbl = sanitize_table_name(t_parts[0])
                        to_col = t_parts[1].strip()
                    declared_rels.append(
                        InferredRelationship(
                            from_table=tbl_name,
                            from_column=from_col,
                            to_table=target_tbl,
                            to_column=to_col,
                            containment_ratio=1.0,
                            confidence=1.0,
                            status="declared",
                        )
                    )

    return declared_pks, declared_rels


def infer_foreign_keys(
    tables: dict[str, pd.DataFrame],
    primary_keys: dict[str, str | None],
    declared_relationships: list[InferredRelationship] | None = None,
) -> list[InferredRelationship]:
    """Infer foreign key relationships across loaded tables:

    Criteria:
    - Prefer declared relationships from uploaded documentation (spec 7.1).
    - Name match (colA == colB or colA == parent_table_id or colA == parent_singular_id)
    - Parent column is unique (distinct_count >= 0.99 of parent rows)
    - Value containment >= 0.98 (98%+ of child values exist in parent)
    """
    relationships: list[InferredRelationship] = []
    seen_pairs: set[tuple[str, str, str, str]] = set()

    # Priority 1: Add declared relationships
    if declared_relationships:
        for rel in declared_relationships:
            pair = (rel.from_table, rel.from_column, rel.to_table, rel.to_column)
            if pair not in seen_pairs:
                relationships.append(rel)
                seen_pairs.add(pair)

    # Priority 2: Infer remaining relationships via value containment
    for child_tbl, child_df in tables.items():
        if child_df.empty:
            continue
        for parent_tbl, parent_df in tables.items():
            if child_tbl == parent_tbl or parent_df.empty:
                continue

            parent_pk = primary_keys.get(parent_tbl)
            parent_singular = to_singular(parent_tbl)

            for child_col in child_df.columns:
                child_series = child_df[child_col].dropna()
                if child_series.empty:
                    continue
                # Normalize values to string representation for type-agnostic containment
                child_vals = {str(x).strip() for x in child_series}

                for parent_col in parent_df.columns:
                    parent_series = parent_df[parent_col].dropna()
                    if parent_series.empty:
                        continue

                    # Condition A: Uniqueness of parent column candidate
                    parent_is_unique = parent_col == parent_pk or parent_series.nunique() >= (
                        len(parent_df) * 0.99
                    )
                    if not parent_is_unique:
                        continue

                    # Condition B: Structural name match heuristic
                    child_lower = child_col.lower()
                    parent_lower = parent_col.lower()

                    name_match = (
                        child_lower == parent_lower
                        or child_lower == f"{parent_tbl}_id"
                        or child_lower == f"{parent_singular}_id"
                        or (child_lower.endswith("_id") and parent_lower == "id")
                    )
                    if not name_match:
                        continue

                    pair = (child_tbl, child_col, parent_tbl, parent_col)
                    if pair in seen_pairs:
                        continue

                    # Condition C: Value containment calculation
                    parent_vals = {str(x).strip() for x in parent_series}
                    contained_count = len(child_vals.intersection(parent_vals))
                    containment = contained_count / len(child_vals)

                    if containment >= 0.98:
                        confidence = (
                            1.0
                            if containment == 1.0 and child_lower == parent_lower
                            else round(containment, 4)
                        )
                        relationships.append(
                            InferredRelationship(
                                from_table=child_tbl,
                                from_column=child_col,
                                to_table=parent_tbl,
                                to_column=parent_col,
                                containment_ratio=round(containment, 4),
                                confidence=confidence,
                                status="inferred",
                            )
                        )
                        seen_pairs.add(pair)

    return relationships


def ingest_table(
    file_bytes: bytes,
    filename: str,
) -> tuple[str, pd.DataFrame, TableProfile]:
    """Ingest a CSV table into DuckDB and generate its column profile."""
    table_name = sanitize_table_name(filename)
    df = load_csv_dataframe(file_bytes, filename)

    # Ingest into persistent DuckDB with quoted table identifier for SQL reserved word safety
    with get_duckdb_write_connection() as conn:
        conn.register("temp_df", df)
        conn.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM temp_df;')
        conn.unregister("temp_df")

    profiles = [profile_column(df[col], col) for col in df.columns]
    pk = infer_primary_key(table_name, profiles, len(df))

    tbl_profile = TableProfile(
        table_name=table_name,
        row_count=len(df),
        column_count=len(df.columns),
        columns=profiles,
        primary_key=pk,
        inferred_relationships=[],
    )
    return table_name, df, tbl_profile


def is_data_documentation_text(
    text: str,
    known_tables: list[str] | None = None,
    known_columns: list[str] | None = None,
    filename: str = "",
) -> bool:
    """Check if an uploaded text/markdown file contains schema data dictionary documentation."""
    fname_lower = filename.lower()
    if "data_dictionary" in fname_lower or "datadictionary" in fname_lower:
        return True

    text_lower = text.lower()
    if "data dictionary" in text_lower and (
        "primary key" in text_lower or "foreign key" in text_lower
    ):
        return True

    if "## tables/" in text_lower or ("primary key" in text_lower and "foreign keys" in text_lower):
        return True

    tables = known_tables or []
    cols = known_columns or []
    table_hits = sum(1 for tbl in tables if tbl.lower() in text_lower)
    col_hits = sum(1 for col in cols if col.lower() in text_lower)
    return table_hits >= 2 or (table_hits >= 1 and col_hits >= 3)


def generate_schema_card(tables: list[TableProfile], doc_text: str | None = None) -> SchemaCard:
    """Generate a structured markdown schema card for the SQL planning agent."""
    lines: list[str] = ["# Database Schema Card", ""]

    for tbl in tables:
        lines.append(
            f"## Table: `{tbl.table_name}` ({tbl.row_count} rows, {tbl.column_count} columns)"
        )
        if tbl.primary_key:
            lines.append(f"- **Primary Key:** `{tbl.primary_key}`")
        if tbl.inferred_relationships:
            fk_strs = [
                f"`{r.from_column}` -> `{r.to_table}.{r.to_column}` ({r.status}, confidence: {r.confidence})"
                for r in tbl.inferred_relationships
            ]
            lines.append(f"- **Foreign Keys:** {', '.join(fk_strs)}")

        lines.append("- **Columns:**")
        for col in tbl.columns:
            sample_str = (
                f" [samples: {', '.join(map(str, col.sample_values[:3]))}]"
                if col.sample_values
                else ""
            )
            lines.append(
                f"  - `{col.name}` ({col.data_type}): {col.distinct_count} distinct, {col.null_count} nulls{sample_str}"
            )
        lines.append("")

    if doc_text:
        lines.append("## Business Definitions & Data Documentation")
        # Size cap data documentation text to avoid unbounded context expansion (spec 7.1)
        capped_doc = doc_text.strip()[:25000]
        lines.append(capped_doc)
        lines.append("")

    summary = "\n".join(lines)
    return SchemaCard(tables=tables, documentation_text=doc_text, markdown_summary=summary)
