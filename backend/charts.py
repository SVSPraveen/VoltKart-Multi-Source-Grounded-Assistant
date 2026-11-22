"""backend/charts.py - Analytical chart generation, row-grounded validation, and rendering.

Implements B10 (Spec Section 7.8):
1. Structured ChartSpec model (bar, line, pie).
2. Strict row-level numeric grounding: Chart values reference stored query rows and must
   match executed query results within 0.001. Hand-edited or hallucinated values are rejected.
3. "Pie only for parts of a whole" semantic check.
4. Pure-Python/PIL rendering for high-resolution embedded images in ReportLab PDF export.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field


class ChartValidationError(ValueError):
    """Raised when a chart specification fails grounding or structural validation."""

    pass


class ChartDataPoint(BaseModel):
    """A single data point in a chart linked to a query result row."""

    row_id: str | int
    x: str
    y: float


class ChartSpec(BaseModel):
    """Analytical chart specification grounded in executed database query rows."""

    chart_id: str
    chart_type: str  # "bar", "line", "pie"
    title: str
    x_label: str
    y_label: str
    x_column: str
    y_column: str
    source_query_id: str
    data_points: list[ChartDataPoint] = Field(default_factory=list)


def validate_chart_spec(
    chart_spec: ChartSpec | dict[str, Any],
    query_result_rows: list[dict[str, Any]],
) -> bool:
    """Validate that every chart value is grounded in actual executed query rows (B10, R-003).

    Rejects:
    - Hand-edited, altered, or hallucinated values not in the database result rows.
    - Unsupported chart types.
    - Pie charts applied to non-proportional or negative data.
    - Missing or orphaned row references.
    """
    if isinstance(chart_spec, dict):
        spec = ChartSpec(**chart_spec)
    else:
        spec = chart_spec

    # 1. Valid chart types
    valid_types = {"bar", "line", "pie"}
    if spec.chart_type not in valid_types:
        raise ChartValidationError(
            f"Unsupported chart_type '{spec.chart_type}'. Must be one of {valid_types}."
        )

    # 2. Must have data points
    if not spec.data_points:
        raise ChartValidationError("Chart specification contains no data points.")

    # 3. Pie chart constraint: parts of a whole only
    if spec.chart_type == "pie":
        total_y = sum(p.y for p in spec.data_points)
        if total_y <= 0:
            raise ChartValidationError(
                "Pie chart values must sum to a positive total representing parts of a whole."
            )
        for p in spec.data_points:
            if p.y < 0:
                raise ChartValidationError(
                    f"Pie chart cannot contain negative value: {p.y} for '{p.x}'."
                )

        # Enforce 100% ± 0.5% if data points represent percentage shares (spec 7.8)
        y_col_lower = (spec.y_column + " " + spec.y_label).lower()
        if any(term in y_col_lower for term in ["pct", "percent", "share"]):
            if abs(total_y - 100.0) > 0.5:
                raise ChartValidationError(
                    f"Pie chart percentage values must sum to 100% ±0.5%, got {total_y:.2f}%."
                )

    # 4. Strict row grounding against executed query rows
    if not query_result_rows:
        raise ChartValidationError(
            "Cannot validate chart: executed query returned zero result rows."
        )

    # Map query rows by row index and by x-column value for deterministic verification
    row_map_by_idx: dict[int, dict[str, Any]] = {i: row for i, row in enumerate(query_result_rows)}
    row_map_by_x: dict[str, dict[str, Any]] = {
        str(row.get(spec.x_column, "")).strip(): row for row in query_result_rows
    }

    for p in spec.data_points:
        matched_row: dict[str, Any] | None = None

        # Try matching by row_id if integer or index-based
        if isinstance(p.row_id, int) and p.row_id in row_map_by_idx:
            matched_row = row_map_by_idx[p.row_id]
        elif isinstance(p.row_id, str) and p.row_id.isdigit() and int(p.row_id) in row_map_by_idx:
            matched_row = row_map_by_idx[int(p.row_id)]
        elif p.x.strip() in row_map_by_x:
            matched_row = row_map_by_x[p.x.strip()]

        if not matched_row:
            raise ChartValidationError(
                f"Data point '{p.x}' (row_id={p.row_id}) does not exist in executed query rows."
            )

        # Check numeric match against actual query row
        actual_val_raw = matched_row.get(spec.y_column)
        if actual_val_raw is None:
            raise ChartValidationError(
                f"Column '{spec.y_column}' not found in query result row for '{p.x}'."
            )

        try:
            actual_y = float(actual_val_raw)
        except (ValueError, TypeError) as err:
            raise ChartValidationError(
                f"Query result value for column '{spec.y_column}' is not numeric: {actual_val_raw}"
            ) from err

        # Deterministic 0.001 tolerance check against hand-edited or hallucinated numbers
        if abs(p.y - actual_y) > 0.001:
            raise ChartValidationError(
                f"Hallucinated or hand-edited chart value rejected for '{p.x}': "
                f"spec provided {p.y}, but database ground truth is {actual_y}."
            )

    return True


def create_grounded_chart_spec(
    query_result_rows: list[dict[str, Any]],
    chart_type: str,
    title: str,
    x_column: str,
    y_column: str,
    x_label: str,
    y_label: str,
    source_query_id: str | None = None,
) -> ChartSpec:
    """Construct a ChartSpec strictly populated from executed query rows and verified."""
    qid = source_query_id or f"qry_{uuid.uuid4().hex[:8]}"
    points: list[ChartDataPoint] = []

    for idx, row in enumerate(query_result_rows):
        x_val = str(row.get(x_column, ""))
        y_raw = row.get(y_column, 0)
        y_val = float(y_raw) if y_raw is not None else 0.0
        points.append(ChartDataPoint(row_id=idx, x=x_val, y=y_val))

    spec = ChartSpec(
        chart_id=f"chart_{uuid.uuid4().hex[:8]}",
        chart_type=chart_type,
        title=title,
        x_label=x_label,
        y_label=y_label,
        x_column=x_column,
        y_column=y_column,
        source_query_id=qid,
        data_points=points,
    )

    # Validate immediately
    validate_chart_spec(spec, query_result_rows)
    return spec


def render_chart_image(
    chart_spec: ChartSpec | dict[str, Any],
    width: int = 800,
    height: int = 400,
) -> bytes:
    """Render a crisp, publication-grade PNG chart image using Pillow (DESIGN.md tokens)."""
    if isinstance(chart_spec, dict):
        spec = ChartSpec(**chart_spec)
    else:
        spec = chart_spec

    # Palette tokens
    bg_color = (253, 252, 247)  # #FDFCF7 warm paper
    ink_color = (17, 24, 39)  # #111827 deep ink
    muted_ink = (107, 114, 128)  # #6B7280 secondary text
    border_color = (229, 226, 217)  # #E5E2D9 hairline rules
    teal_primary = (15, 118, 110)  # #0F766E
    volt_accent = (212, 232, 21)  # #D4E815 volt accent

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try loading a readable TrueType font or fallback to default
    try:
        from backend.export_pdf import BOLD_FONT_PATH, REGULAR_FONT_PATH

        title_font = ImageFont.truetype(str(BOLD_FONT_PATH), 18)
        label_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 12)
        small_font = ImageFont.truetype(str(REGULAR_FONT_PATH), 10)
    except Exception:
        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Draw Title
    draw.text((40, 20), spec.title, fill=ink_color, font=title_font)

    # Chart Area Coordinates
    left = 120
    top = 70
    right = width - 40
    bottom = height - 70

    points = spec.data_points

    if spec.chart_type == "bar":
        # Draw Bar Chart
        if points:
            max_val = max(p.y for p in points) if points else 1.0
            if max_val <= 0:
                max_val = 1.0

            # Y-axis and X-axis rules
            draw.line([(left, top), (left, bottom)], fill=border_color, width=1)
            draw.line([(left, bottom), (right, bottom)], fill=border_color, width=1)

            # Draw Y-axis gridlines and labels (4 ticks)
            for step in range(5):
                tick_y = bottom - (step / 4.0) * (bottom - top)
                tick_val = (step / 4.0) * max_val
                val_str = f"{tick_val:,.0f}" if tick_val >= 100 else f"{tick_val:,.1f}"
                draw.line([(left - 5, tick_y), (right, tick_y)], fill=(243, 244, 246), width=1)
                draw.text((left - 80, tick_y - 6), val_str, fill=muted_ink, font=small_font)

            bar_count = len(points)
            slot_width = (right - left) / max(bar_count, 1)
            bar_width = max(slot_width * 0.6, 8)

            for i, p in enumerate(points):
                bar_h = (p.y / max_val) * (bottom - top)
                bx0 = left + i * slot_width + (slot_width - bar_width) / 2
                by0 = bottom - bar_h
                bx1 = bx0 + bar_width
                by1 = bottom

                # Bar fill (teal)
                draw.rectangle([bx0, by0, bx1, by1], fill=teal_primary, outline=border_color)

                # Value label above bar
                v_str = f"{p.y:,.0f}" if p.y >= 1000 else f"{p.y:,.2f}"
                draw.text((bx0 - 5, by0 - 15), v_str, fill=ink_color, font=small_font)

                # X label below bar (truncated if long)
                x_str = p.x if len(p.x) <= 12 else p.x[:10] + ".."
                draw.text((bx0, bottom + 8), x_str, fill=ink_color, font=small_font)

            # Axis labels
            draw.text((left - 80, top - 25), spec.y_label, fill=muted_ink, font=small_font)
            draw.text(
                ((left + right) / 2 - 30, bottom + 35),
                spec.x_label,
                fill=muted_ink,
                font=label_font,
            )

    elif spec.chart_type == "line":
        # Draw Line Chart
        if points:
            max_val = max(p.y for p in points) if points else 1.0
            min_val = min(p.y for p in points) if points else 0.0
            range_val = max(max_val - min_val, 1.0)

            # Axes
            draw.line([(left, top), (left, bottom)], fill=border_color, width=1)
            draw.line([(left, bottom), (right, bottom)], fill=border_color, width=1)

            # Y-axis ticks
            for step in range(5):
                tick_y = bottom - (step / 4.0) * (bottom - top)
                tick_val = min_val + (step / 4.0) * range_val
                val_str = f"{tick_val:,.0f}" if tick_val >= 100 else f"{tick_val:,.1f}"
                draw.line([(left - 5, tick_y), (right, tick_y)], fill=(243, 244, 246), width=1)
                draw.text((left - 80, tick_y - 6), val_str, fill=muted_ink, font=small_font)

            slot_width = (right - left) / max(len(points) - 1, 1)
            coord_points: list[tuple[float, float]] = []

            for i, p in enumerate(points):
                px = left + i * slot_width
                py = bottom - ((p.y - min_val) / range_val) * (bottom - top)
                coord_points.append((px, py))

                # X label
                x_str = p.x if len(p.x) <= 8 else p.x[-5:]
                draw.text((px - 10, bottom + 8), x_str, fill=ink_color, font=small_font)
                # Value label
                draw.text(
                    (px - 8, py - 16),
                    str(int(p.y) if p.y.is_integer() else p.y),
                    fill=ink_color,
                    font=small_font,
                )

            # Draw connecting lines
            for i in range(len(coord_points) - 1):
                draw.line([coord_points[i], coord_points[i + 1]], fill=teal_primary, width=3)

            # Draw point markers
            for px, py in coord_points:
                draw.ellipse(
                    [px - 4, py - 4, px + 4, py + 4],
                    fill=volt_accent,
                    outline=teal_primary,
                    width=2,
                )

            # Axis labels
            draw.text((left - 80, top - 25), spec.y_label, fill=muted_ink, font=small_font)
            draw.text(
                ((left + right) / 2 - 30, bottom + 35),
                spec.x_label,
                fill=muted_ink,
                font=label_font,
            )

    elif spec.chart_type == "pie":
        # Draw Pie Chart
        total = sum(p.y for p in points) if points else 1.0
        cx = left + 140
        cy = (top + bottom) / 2
        radius = min(bottom - top, right - left) / 2.2

        slice_colors = [
            teal_primary,
            (45, 212, 191),
            (212, 232, 21),
            (245, 158, 11),
            (99, 102, 241),
            (236, 72, 153),
            (14, 165, 233),
        ]

        start_angle = 0.0
        legend_x = cx + radius + 40
        legend_y = top + 20

        for i, p in enumerate(points):
            frac = p.y / total
            angle = frac * 360.0
            c = slice_colors[i % len(slice_colors)]

            # Draw pie slice
            draw.pieslice(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                start=start_angle,
                end=start_angle + angle,
                fill=c,
                outline=border_color,
            )
            start_angle += angle

            # Legend
            if legend_y < height - 30:
                draw.rectangle([legend_x, legend_y, legend_x + 14, legend_y + 14], fill=c)
                pct_str = f"{p.x}: {p.y:,.2f} ({frac * 100:.1f}%)"
                draw.text((legend_x + 22, legend_y), pct_str, fill=ink_color, font=small_font)
                legend_y += 24

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
