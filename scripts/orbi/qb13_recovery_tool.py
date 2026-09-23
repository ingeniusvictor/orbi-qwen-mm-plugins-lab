#!/usr/bin/env python3
"""QB-13 operator tool for durable execution recovery.

This utility is intentionally evidence-only. It can inspect pending executions, inspect
reconciliation history, and append an explicit reconciliation record. It cannot retry execution,
release request ids, or call Blender/provider tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat import SQLiteReplayLedger


def _json(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _read_evidence(args: argparse.Namespace) -> dict:
    if args.evidence_json is not None:
        value = json.loads(args.evidence_json)
    else:
        value = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("evidence must decode to a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and reconcile QB-13 durable R2 execution state."
    )
    parser.add_argument("--db", required=True, help="Path to the ORBI SQLite execution ledger.")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("pending", help="List pending/uncertain durable R2 executions.")

    history = sub.add_parser(
        "reconciliations",
        help="List reconciliation records, optionally for one request id.",
    )
    history.add_argument("--request-id")

    reconcile = sub.add_parser(
        "reconcile",
        help="Append evidence and reconcile one pending request.",
    )
    reconcile.add_argument("--request-id", required=True)
    reconcile.add_argument(
        "--resolution",
        required=True,
        choices=("applied", "not_applied", "inconclusive"),
    )
    reconcile.add_argument("--actor", required=True)

    source = reconcile.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--evidence-json",
        help="Evidence as a JSON object string.",
    )
    source.add_argument(
        "--evidence-file",
        help="Path to a UTF-8 JSON evidence file.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ledger = SQLiteReplayLedger(args.db)

    if args.command == "pending":
        _json([item.to_dict() for item in ledger.pending_receipts()])
        return 0

    if args.command == "reconciliations":
        _json([item.to_dict() for item in ledger.reconciliations(args.request_id)])
        return 0

    evidence = _read_evidence(args)
    record = ledger.reconcile_pending(
        args.request_id,
        resolution=args.resolution,
        evidence=evidence,
        actor=args.actor,
    )
    _json(record.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
