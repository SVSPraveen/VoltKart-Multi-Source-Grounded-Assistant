"""tests/unit/test_no_hardcode.py - Verify the no-hardcode scanner."""

from pathlib import Path

import pytest

from scripts.check_no_hardcode import scan_file


def test_scan_file_clean(tmp_path: Path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def calculate_total(items):\n    return sum(x.price for x in items)\n")
    violations = scan_file(clean_file)
    assert violations == []


@pytest.mark.parametrize(
    "bad_content, expected_match",
    [
        ("store_id = 'S04'", "Store ID S04"),
        ("name = 'VoltKart Connaught Place'", "voltkart"),
        ("if customer == 'Aarav Kulkarni': pass", "Aarav Kulkarni"),
        ("product = 'Nexora X12 Pro'", "Nexora X12 Pro"),
        ("doc = 'VoltKart_Return_Policy_2025.txt'", "voltkart"),
    ],
)
def test_scan_file_catches_violations(tmp_path: Path, bad_content: str, expected_match: str):
    dirty_file = tmp_path / "dirty.py"
    dirty_file.write_text(bad_content)
    violations = scan_file(dirty_file)
    assert len(violations) >= 1
    assert any(expected_match.lower() in v.lower() for v in violations)
