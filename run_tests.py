#!/usr/bin/env python3
"""
Test runner for the d.onl project.

Usage:
    python run_tests.py          # run all tests
    python run_tests.py -k auth  # run tests matching 'auth'

Outputs:
    logs/test_results.txt    – full pytest output
    logs/coverage_report.txt – coverage summary
    stdout                   – quick pass/fail summary
"""

import os
import sys
import subprocess
import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
TEST_RESULTS = os.path.join(LOG_DIR, "test_results.txt")
COVERAGE_REPORT = os.path.join(LOG_DIR, "coverage_report.txt")

# Ensure the logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)


def run_tests(extra_args: list[str] | None = None) -> int:
    """Run pytest with coverage and return the exit code."""

    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        f"--cov=app",
        "--cov-report=term-missing",
        "--asyncio-mode=auto",
    ]

    # Forward any extra CLI arguments (e.g. -k, -x)
    if extra_args:
        cmd.extend(extra_args)

    print(f"[run_tests] Running: {' '.join(cmd)}")
    print(f"[run_tests] Started at {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print("-" * 70)

    # Capture full output
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    full_output = result.stdout + "\n" + result.stderr

    # ---- Write test results ----
    with open(TEST_RESULTS, "w", encoding="utf-8") as f:
        f.write(f"d.onl Test Results — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write("=" * 70 + "\n\n")
        f.write(full_output)

    # ---- Extract & write coverage report ----
    coverage_lines: list[str] = []
    capture = False
    for line in full_output.splitlines():
        if line.startswith("---------- coverage:") or line.startswith("Name"):
            capture = True
        if capture:
            coverage_lines.append(line)

    with open(COVERAGE_REPORT, "w", encoding="utf-8") as f:
        f.write(f"d.onl Coverage Report — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write("=" * 70 + "\n\n")
        if coverage_lines:
            f.write("\n".join(coverage_lines) + "\n")
        else:
            f.write("(no coverage data captured)\n")

    # ---- Print summary ----
    print(full_output)
    print("-" * 70)

    if result.returncode == 0:
        print("\n[run_tests] OK ALL TESTS PASSED")
    else:
        print(f"\n[run_tests] FAILED (exit code {result.returncode})")

    print(f"[run_tests] Full results  -> {TEST_RESULTS}")
    print(f"[run_tests] Coverage      -> {COVERAGE_REPORT}")

    return result.returncode


if __name__ == "__main__":
    extra = sys.argv[1:] if len(sys.argv) > 1 else None
    sys.exit(run_tests(extra))
