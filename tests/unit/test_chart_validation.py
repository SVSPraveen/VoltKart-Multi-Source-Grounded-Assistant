"""tests/unit/test_chart_validation.py - Unit tests for chart validation and rendering (B10, R-003).

Verifies:
1. Chart specs generated from query results pass strict validation.
2. Hand-edited or hallucinated numbers are deterministically rejected by validator.
3. Pie charts on negative or non-proportional data are rejected.
4. High-resolution PNG chart image rendering succeeds for bar, line, and pie charts.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from backend.charts import (
    ChartDataPoint,
    ChartSpec,
    ChartValidationError,
    create_grounded_chart_spec,
    render_chart_image,
    validate_chart_spec,
)


def test_valid_bar_chart_spec_validation():
    """Verify a valid grounded chart spec passes validation."""
    query_rows = [
        {"category": "Laptops", "revenue_inr": 11152212.55},
        {"category": "Smartphones", "revenue_inr": 10477358.05},
        {"category": "Televisions", "revenue_inr": 3211720.10},
    ]

    spec = create_grounded_chart_spec(
        query_result_rows=query_rows,
        chart_type="bar",
        title="2025 Category Revenue",
        x_column="category",
        y_column="revenue_inr",
        x_label="Category",
        y_label="Revenue (INR)",
    )

    assert spec.chart_type == "bar"
    assert len(spec.data_points) == 3
    assert validate_chart_spec(spec, query_rows) is True


def test_hand_edited_or_hallucinated_value_rejected():
    """Deterministic test: hand-edited or altered chart values are rejected by validator (B10)."""
    query_rows = [
        {"category": "Laptops", "revenue_inr": 11152212.55},
        {"category": "Smartphones", "revenue_inr": 10477358.05},
    ]

    spec = create_grounded_chart_spec(
        query_result_rows=query_rows,
        chart_type="bar",
        title="2025 Category Revenue",
        x_column="category",
        y_column="revenue_inr",
        x_label="Category",
        y_label="Revenue (INR)",
    )

    # Simulate an LLM or user hand-editing a number (e.g. inflating Laptops revenue)
    spec.data_points[0].y = 12000000.00

    with pytest.raises(ChartValidationError) as exc_info:
        validate_chart_spec(spec, query_rows)

    assert "Hallucinated or hand-edited chart value rejected" in str(exc_info.value)
    assert "Laptops" in str(exc_info.value)


def test_hallucinated_category_rejected():
    """Chart data points referencing categories not in query rows are rejected."""
    query_rows = [
        {"category": "Laptops", "revenue_inr": 11152212.55},
    ]

    spec = ChartSpec(
        chart_id="chart_fake",
        chart_type="bar",
        title="Fake Chart",
        x_label="Cat",
        y_label="Rev",
        x_column="category",
        y_column="revenue_inr",
        source_query_id="q1",
        data_points=[
            ChartDataPoint(row_id=99, x="FlyingCars", y=999999.0),
        ],
    )

    with pytest.raises(ChartValidationError) as exc_info:
        validate_chart_spec(spec, query_rows)

    assert "does not exist in executed query rows" in str(exc_info.value)


def test_pie_chart_parts_of_a_whole_constraint():
    """Pie charts are restricted to positive parts of a whole."""
    # Negative value rejected
    bad_rows = [
        {"category": "Audio", "net_profit": -500.0},
        {"category": "Video", "net_profit": 1500.0},
    ]
    with pytest.raises(ChartValidationError) as exc_info:
        create_grounded_chart_spec(
            query_result_rows=bad_rows,
            chart_type="pie",
            title="Profit Breakdown",
            x_column="category",
            y_column="net_profit",
            x_label="Category",
            y_label="Profit",
        )
    assert "Pie chart cannot contain negative value" in str(exc_info.value)


def test_pie_chart_percentage_sum_constraint():
    """Pie charts with percentage values must sum to 100% ± 0.5% (spec 7.8)."""
    # 1. Invalid percentage sum (e.g. 70% total != 100%)
    invalid_pct_rows = [
        {"tier": "Gold", "share_pct": 45.0},
        {"tier": "Silver", "share_pct": 25.0},
    ]
    with pytest.raises(ChartValidationError) as exc_info:
        create_grounded_chart_spec(
            query_result_rows=invalid_pct_rows,
            chart_type="pie",
            title="Tier Share Breakdown",
            x_column="tier",
            y_column="share_pct",
            x_label="Tier",
            y_label="Share Percentage",
        )
    assert "must sum to 100% ±0.5%" in str(exc_info.value)

    # 2. Valid percentage sum (e.g. 100% total)
    valid_pct_rows = [
        {"tier": "Gold", "share_pct": 60.0},
        {"tier": "Silver", "share_pct": 40.0},
    ]
    valid_spec = create_grounded_chart_spec(
        query_result_rows=valid_pct_rows,
        chart_type="pie",
        title="Tier Share Breakdown",
        x_column="tier",
        y_column="share_pct",
        x_label="Tier",
        y_label="Share Percentage",
    )
    assert validate_chart_spec(valid_spec, valid_pct_rows) is True


def test_render_chart_images_for_all_types():
    """Verify PNG rendering succeeds and creates valid image buffers for bar, line, pie."""
    sample_rows = [
        {"item": "Jan", "count": 16.0},
        {"item": "Feb", "count": 23.0},
        {"item": "Mar", "count": 19.0},
    ]

    for chart_t in ["bar", "line", "pie"]:
        spec = create_grounded_chart_spec(
            query_result_rows=sample_rows,
            chart_type=chart_t,
            title=f"Sample {chart_t.title()} Chart",
            x_column="item",
            y_column="count",
            x_label="Item",
            y_label="Count",
        )

        png_bytes = render_chart_image(spec)
        assert len(png_bytes) > 500
        assert png_bytes.startswith(b"\x89PNG")

        img = Image.open(io.BytesIO(png_bytes))
        assert img.width == 800
        assert img.height == 400
