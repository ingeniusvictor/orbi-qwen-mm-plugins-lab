#!/usr/bin/env python3
"""Stacked QB-12→QB-15 preflight.

This is a convenience gate, NOT a substitute for phase-specific certification at each phase SHA.
It runs the full accumulated offline regression and the QB-14 machine-readable contract validator
from the current stacked branch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TESTS = [
    "tests/test_orbi_qb08_reference.py",
    "tests/test_orbi_qb09_qwen_bridge.py",
    "tests/test_orbi_qb10_governed_execution.py",
    "tests/test_orbi_qb11_audit_replay.py",
    "tests/test_orbi_qb12_durable_ledger.py",
    "tests/test_orbi_qb13_reconciliation.py",
    "tests/test_orbi_qb13_recovery_tool.py",
    "tests/test_orbi_qb14_scene3d_pilot_contract.py",
    "tests/test_orbi_qb15_scene3d_sidecar.py",
]

LIVE = [
    ("qb12", ROOT / "scripts/orbi/qb12_live_durable_restart.py"),
    ("qb13", ROOT / "scripts/orbi/qb13_live_reconciliation.py"),
    ("qb15", ROOT / "scripts/orbi/qb15_live_sidecar_smoke.py"),
]


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )


def git_value(*args: str) -> str:
    result = run(["git", *args], capture=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the stacked QB-12→QB-15 ORBI preflight."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also run the controlled QB-12/QB-13/QB-15 live Blender smokes.",
    )
    args = parser.parse_args()

    summary: dict[str, object] = {
        "schema": "orbi.qb12-qb15-preflight/v1",
        "scope": "stacked-current-branch-not-phase-certification",
        "branch": git_value("branch", "--show-current"),
        "head": git_value("rev-parse", "HEAD"),
        "working_tree_clean": not bool(git_value("status", "--porcelain")),
        "expected_accumulated_tests": 106,
        "gates": {},
    }

    print("=== QB-12→QB-15 STACKED OFFLINE REGRESSION ===")
    pytest_cmd = [sys.executable, "-m", "pytest", *TESTS, "-q"]
    tests = run(pytest_cmd)
    summary["gates"]["offline_regression"] = {
        "passed": tests.returncode == 0,
        "returncode": tests.returncode,
    }
    if tests.returncode != 0:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return tests.returncode

    print("\n=== QB-14 CONTRACT VALIDATION ===")
    contract = run([sys.executable, "scripts/orbi/qb14_validate_contract.py"])
    summary["gates"]["qb14_contract"] = {
        "passed": contract.returncode == 0,
        "returncode": contract.returncode,
    }
    if contract.returncode != 0:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return contract.returncode

    if args.live:
        for name, script in LIVE:
            print(f"\n=== {name.upper()} LIVE GATE ===")
            result = run([sys.executable, str(script)])
            summary["gates"][f"{name}_live"] = {
                "passed": result.returncode == 0,
                "returncode": result.returncode,
            }
            if result.returncode != 0:
                print(json.dumps(summary, indent=2, sort_keys=True))
                return result.returncode

    summary["preflight_passed"] = all(
        gate["passed"] for gate in summary["gates"].values()
    )
    summary["certification_note"] = (
        "PASS here proves the stacked current branch only; "
        "QB-12/QB-13 phase certification still requires their own frozen SHA evidence."
    )

    print("\n=== STACKED PREFLIGHT SUMMARY ===")
    print(json.dumps(summary, indent=2, sort_keys=True))

    if summary["preflight_passed"]:
        print("\nQB-12→QB-15 STACKED PREFLIGHT: PASS")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
