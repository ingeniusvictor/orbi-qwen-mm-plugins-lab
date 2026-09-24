#!/usr/bin/env python3
"""QB-15 local ORBI Scene3D stdio JSONL sidecar."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_qwen_bridge.scene3d_sidecar import (
    MAX_MESSAGE_BYTES,
    PROTOCOL,
    SidecarMessageTooLarge,
    build_live_sidecar,
    decode_message,
    encode_message,
)

DEFAULT_CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local stdio JSONL transport for ORBI Scene3D pilot."
    )
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT),
        help="Path to the certified ORBI compatibility contract.",
    )
    parser.add_argument(
        "--ledger",
        required=True,
        help="Path to the durable ORBI SQLite execution ledger.",
    )
    return parser


def _transport_error(exc: Exception) -> dict:
    return {
        "protocol": PROTOCOL,
        "id": "",
        "ok": False,
        "error": {
            "code": getattr(exc, "code", "SIDECAR_PROTOCOL_ERROR"),
            "message": str(exc),
        },
    }


def _readline_limited(stream) -> bytes:
    raw = stream.readline(MAX_MESSAGE_BYTES + 2)
    if raw == b"":
        return raw

    body = raw.rstrip(b"\r\n")
    if len(body) <= MAX_MESSAGE_BYTES and raw.endswith((b"\n", b"\r")):
        return body

    if len(body) <= MAX_MESSAGE_BYTES and len(raw) <= MAX_MESSAGE_BYTES + 2:
        return body

    # Drain the rest of an oversized line without buffering it in memory.
    if not raw.endswith(b"\n"):
        while True:
            chunk = stream.readline(MAX_MESSAGE_BYTES + 2)
            if chunk == b"" or chunk.endswith(b"\n"):
                break

    raise SidecarMessageTooLarge(
        f"message exceeds {MAX_MESSAGE_BYTES} byte limit"
    )


def run_stdio(sidecar, *, stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout

    while True:
        try:
            raw = _readline_limited(stdin)
        except Exception as exc:
            stdout.write(encode_message(_transport_error(exc)) + "\n")
            stdout.flush()
            continue

        if raw == b"":
            return 0
        if not raw.strip():
            continue

        try:
            message = decode_message(raw)
            response = sidecar.process(message)
        except Exception as exc:
            response = _transport_error(exc)

        stdout.write(encode_message(response) + "\n")
        stdout.flush()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    sidecar = build_live_sidecar(
        contract_path=Path(args.contract),
        ledger_path=Path(args.ledger),
    )
    return run_stdio(sidecar)


if __name__ == "__main__":
    raise SystemExit(main())
