#!/usr/bin/env python3
"""scripts/runner.py - Cross-platform task runner and verification harness.

Supports subcommands: verify, test, golden, lint, format, no-hardcode, clean.
For `verify`, executes the verification pipeline, prints a formatted summary table
to stdout, and writes a detailed markdown report to reports/verify-<timestamp>.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple


class StepResult(NamedTuple):
    name: str
    command: str
    status: str  # "PASS", "FAIL", "SKIP"
    exit_code: int
    duration_sec: float
    output: str


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_venv_python() -> str:
    """Resolve the python executable inside .venv, or fallback to sys.executable."""
    root = get_project_root()
    if os.name == "nt":
        venv_py = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = root / ".venv" / "bin" / "python"

    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, float, str]:
    """Execute a command, capturing stdout, stderr, and execution duration."""
    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or get_project_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.time() - start_time
        return proc.returncode, duration, proc.stdout
    except Exception as exc:
        duration = time.time() - start_time
        return 1, duration, f"Execution failed: {exc}"


def get_git_info() -> str:
    """Retrieve git branch and short commit hash if available."""
    try:
        code, _, out = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        branch = out.strip() if code == 0 else "unknown"
        code, _, out = run_command(["git", "rev-parse", "--short", "HEAD"])
        commit = out.strip() if code == 0 else "uncommitted"
        return f"{branch}@{commit}"
    except Exception:
        return "unknown"


def print_summary_table(results: list[StepResult]) -> None:
    """Print an ASCII summary table of the verification steps to stdout."""
    col_check = 15
    col_cmd = 42
    col_status = 10
    col_dur = 10

    border = f"+{'-' * col_check}+{'-' * col_cmd}+{'-' * col_status}+{'-' * col_dur}+"
    header = (
        f"| {'Check':<{col_check - 2}} "
        f"| {'Command':<{col_cmd - 2}} "
        f"| {'Status':<{col_status - 2}} "
        f"| {'Duration':<{col_dur - 2}} |"
    )

    print("\n" + border)
    print(header)
    print(border)
    for res in results:
        cmd_disp = (
            res.command if len(res.command) <= col_cmd - 2 else res.command[: col_cmd - 5] + "..."
        )
        row = (
            f"| {res.name:<{col_check - 2}} "
            f"| {cmd_disp:<{col_cmd - 2}} "
            f"| {res.status:<{col_status - 2}} "
            f"| {res.duration_sec:6.2f}s   |"
        )
        print(row)
    print(border + "\n")


def write_verification_report(results: list[StepResult], report_dir: Path) -> Path:
    """Write reports/verify-<timestamp>.md containing full logs and summary table."""
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    report_file = report_dir / f"verify-{timestamp}.md"

    git_info = get_git_info()
    lines = [
        f"# Verification Report — {timestamp}",
        "",
        f"- **Timestamp (UTC):** {timestamp}",
        f"- **Git Reference:** `{git_info}`",
        f"- **Python Interpreter:** `{get_venv_python()}`",
        "",
        "## Summary",
        "",
        "| Check | Command | Status | Duration |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for res in results:
        lines.append(
            f"| `{res.name}` | `{res.command}` | **{res.status}** | {res.duration_sec:.2f}s |"
        )

    lines.extend(["", "## Detailed Execution Logs", ""])
    for res in results:
        lines.extend(
            [
                f"### {res.name} (`{res.status}`)",
                f"- Command: `{res.command}`",
                f"- Exit Code: `{res.exit_code}`",
                f"- Duration: `{res.duration_sec:.2f}s`",
                "",
                "```text",
                res.output.strip() if res.output.strip() else "(no output)",
                "```",
                "",
            ]
        )

    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file


def run_verify(allow_red_golden: bool = False) -> int:
    """Run full verification pipeline."""
    root = get_project_root()
    py = get_venv_python()

    steps = [
        ("lint", [py, "-m", "ruff", "check", "."]),
        ("format", [py, "-m", "ruff", "format", "--check", "."]),
        ("no-hardcode", [py, str(root / "scripts" / "check_no_hardcode.py")]),
        ("unit", [py, "-m", "pytest", "tests/unit"]),
        ("golden", [py, "-m", "pytest", "tests/golden"]),
    ]

    results: list[StepResult] = []
    has_fatal_failure = False

    for name, cmd in steps:
        cmd_str = " ".join(
            Path(c).name if c.endswith(".py") or c.endswith(".exe") else c for c in cmd
        )
        exit_code, duration, output = run_command(cmd, cwd=root)

        if exit_code == 0:
            status = "PASS"
        else:
            if name == "golden" and allow_red_golden:
                status = "FAIL (RED)"
            else:
                status = "FAIL"
                has_fatal_failure = True

        results.append(
            StepResult(
                name=name,
                command=cmd_str,
                status=status,
                exit_code=exit_code,
                duration_sec=duration,
                output=output,
            )
        )

    # Always print summary table
    print_summary_table(results)

    # Always write report markdown
    report_file = write_verification_report(results, root / "reports")
    print(f"Verification report written to: {report_file.relative_to(root)}")

    if has_fatal_failure:
        print("\n[RESULT] Verification encountered failures.")
        return 1

    print("\n[RESULT] All verification checks passed.")
    return 0


def clean_project() -> int:
    """Clean transient caches and build artifacts."""
    root = get_project_root()
    patterns = ["__pycache__", ".pytest_cache", ".ruff_cache", "*.egg-info", "dist", "build"]
    removed_count = 0
    for p in root.rglob("*"):
        if any(p.match(pat) for pat in patterns):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                removed_count += 1
    print(f"Cleaned {removed_count} cache/build directories.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="VoltKart Project Runner")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # verify
    verify_parser = subparsers.add_parser("verify", help="Run full verification suite")
    verify_parser.add_argument(
        "--red-baseline",
        action="store_true",
        help="Allow golden suite to fail as expected red baseline (Phase 1)",
    )

    # test
    subparsers.add_parser("test", help="Run unit tests")

    # golden
    subparsers.add_parser("golden", help="Run golden evaluation tests")

    # lint
    subparsers.add_parser("lint", help="Run Ruff linter")

    # format
    fmt_parser = subparsers.add_parser("format", help="Run Ruff formatter")
    fmt_parser.add_argument("--check", action="store_true", help="Only check formatting")

    # no-hardcode
    subparsers.add_parser("no-hardcode", help="Check for hardcoded sample strings")

    # clean
    subparsers.add_parser("clean", help="Remove test/lint caches")

    # stubs for later phases
    subparsers.add_parser("eval", help="Live golden evals (Phase 3+)")
    subparsers.add_parser("e2e", help="Browser E2E tests (Phase 5+)")
    subparsers.add_parser("fresh-clone-test", help="Fresh clone test (Phase 8)")

    args = parser.parse_args()
    py = get_venv_python()
    root = get_project_root()

    if args.subcommand == "verify":
        return run_verify(allow_red_golden=args.red_baseline)
    elif args.subcommand == "test":
        code, _, out = run_command([py, "-m", "pytest", "tests/unit"], cwd=root)
        print(out)
        return code
    elif args.subcommand == "golden":
        code, _, out = run_command([py, "-m", "pytest", "tests/golden"], cwd=root)
        print(out)
        return code
    elif args.subcommand == "lint":
        code, _, out = run_command([py, "-m", "ruff", "check", "."], cwd=root)
        print(out)
        return code
    elif args.subcommand == "format":
        cmd = [py, "-m", "ruff", "format"]
        if getattr(args, "check", False):
            cmd.append("--check")
        cmd.append(".")
        code, _, out = run_command(cmd, cwd=root)
        print(out)
        return code
    elif args.subcommand == "no-hardcode":
        code, _, out = run_command([py, str(root / "scripts" / "check_no_hardcode.py")], cwd=root)
        print(out)
        return code
    elif args.subcommand == "clean":
        return clean_project()
    elif args.subcommand in ("eval", "e2e", "fresh-clone-test"):
        print(f"Target '{args.subcommand}' will be configured in subsequent phases.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
