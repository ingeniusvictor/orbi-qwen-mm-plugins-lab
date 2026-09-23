#!/usr/bin/env python3
"""QB-20 offline validator for QB-19 Scene3D recovery handoff artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat.recovery_handoff import (
    EVIDENCE_TYPE,
    RecoveryHandoffError,
    load_recovery_handoff,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a QB-19 ORBI Scene3D recovery handoff and print a "
            "non-executing operator review plan."
        )
    )
    parser.add_argument("--file", required=True, help="Path to the exported recovery JSON.")
    parser.add_argument(
        "--sha256",
        help="Optional expected SHA-256 shown by Creative Studio after export.",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        handoff = load_recovery_handoff(
            args.file,
            expected_sha256=args.sha256,
        )
    except (RecoveryHandoffError, OSError) as exc:
        payload = {
            "ok": False,
            "error": {
                "code": getattr(exc, "code", exc.__class__.__name__.upper()),
                "message": str(exc),
            },
        }
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False), file=sys.stderr)
        return 2

    payload = {
        "ok": True,
        "evidence_type": EVIDENCE_TYPE,
        "operator_plan": handoff.operator_plan(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
