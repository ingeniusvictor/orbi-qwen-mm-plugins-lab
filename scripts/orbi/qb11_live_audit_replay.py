#!/usr/bin/env python3
"""QB-11 live governed execution audit + replay-safety smoke."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat import OrbiRequest
from orbi_qwen_bridge import build_governed_blender_runtime

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"
NAME = "ORBI_QB11_Cube"


def call(runtime, operation, request_id, payload=None):
    return runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation=operation,
            request_id=request_id,
            input=payload or {},
        )
    )


def create_payload(*, dry_run=False, location=None):
    payload = {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": NAME,
            "size": 1.25,
            "location": location or [2.0, 0.0, 0.5],
        },
    }
    if dry_run:
        payload["dry_run"] = True
    return payload


def main() -> int:
    runtime = build_governed_blender_runtime(CONTRACT)

    print("=== QB-11 PREEXISTING OBJECT GUARD ===")
    pre = call(runtime, "object_info", "qb11-precheck", {"object_name": NAME})
    print(pre.to_dict())
    if pre.ok:
        raise AssertionError(f"{NAME} already exists; refusing to touch it")
    if pre.error is None or "Object not found" not in pre.error.message:
        raise AssertionError(
            f"unexpected Blender precheck failure: "
            f"{pre.error.message if pre.error else 'unknown'}"
        )

    print("\n=== QB-11 REPEATABLE DRY RUN ===")
    dry1 = call(runtime, "execute_recipe", "qb11-dry", create_payload(dry_run=True))
    dry2 = call(runtime, "execute_recipe", "qb11-dry", create_payload(dry_run=True))
    print(dry1.to_dict())
    print(dry2.to_dict())
    assert dry1.ok is True and dry2.ok is True
    assert dry1.audit["outcome"] == "dry-run"
    assert dry2.audit["outcome"] == "dry-run"
    assert dry1.audit["replay_reserved"] is False
    assert dry2.audit["replay_reserved"] is False
    assert dry1.audit["provider_called"] is False
    assert dry2.audit["provider_called"] is False

    create_attempted = False
    try:
        print("\n=== QB-11 GOVERNED CREATE + RECEIPT ===")
        create_attempted = True
        create = call(runtime, "execute_recipe", "qb11-create", create_payload())
        print(create.to_dict())
        assert create.ok is True
        assert create.audit is not None
        assert create.audit["schema"] == "orbi.execution-audit/v1"
        assert create.audit["outcome"] == "executed"
        assert create.audit["provider_called"] is True
        assert create.audit["replay_reserved"] is True
        assert len(create.audit["request_fingerprint"]) == 64

        print("\n=== QB-11 EXACT REPLAY DENIAL ===")
        replay = call(runtime, "execute_recipe", "qb11-create", create_payload())
        print(replay.to_dict())
        assert replay.ok is False
        assert replay.error is not None
        assert replay.error.code == "REPLAY_DENIED"
        assert replay.error.retryable is False
        assert replay.audit is not None
        assert replay.audit["outcome"] == "replay-denied"
        assert replay.audit["provider_called"] is False

        print("\n=== QB-11 REQUEST-ID CONFLICT DENIAL ===")
        conflict = call(
            runtime,
            "execute_recipe",
            "qb11-create",
            create_payload(location=[9.0, 0.0, 0.5]),
        )
        print(conflict.to_dict())
        assert conflict.ok is False
        assert conflict.error is not None
        assert conflict.error.code == "REQUEST_ID_CONFLICT"
        assert conflict.audit is not None
        assert conflict.audit["provider_called"] is False

        print("\n=== QB-11 LIVE OBJECT VERIFY ===")
        obj = call(runtime, "object_info", "qb11-object-info", {"object_name": NAME})
        print(obj.to_dict())
        assert obj.ok is True
        assert NAME in obj.data[0]["text"]
        assert "MESH" in obj.data[0]["text"]

    finally:
        print("\n=== QB-11 OWNERSHIP-SAFE CLEANUP ===")
        if create_attempted:
            exists = call(
                runtime,
                "object_info",
                "qb11-cleanup-check",
                {"object_name": NAME},
            )
            print(exists.to_dict())
            if exists.ok:
                cleanup = call(
                    runtime,
                    "execute_recipe",
                    "qb11-cleanup",
                    {
                        "recipe_id": "orbi.blender.delete_object.v1",
                        "parameters": {"name": NAME},
                    },
                )
                print(cleanup.to_dict())
                assert cleanup.ok is True

    print("\n=== QB-11 POST-CLEANUP VERIFY ===")
    gone = call(runtime, "object_info", "qb11-object-gone", {"object_name": NAME})
    print(gone.to_dict())
    assert gone.ok is False
    assert gone.error is not None
    assert "Object not found" in gone.error.message

    print("\n=== QB-11 AUDIT LEDGER ===")
    receipts = runtime.replay_ledger.receipts()
    for receipt in receipts:
        print(receipt.to_dict())

    outcomes = [r.outcome for r in receipts]
    assert outcomes.count("dry-run") == 2
    assert "executed" in outcomes
    assert outcomes.count("replay-denied") >= 2

    sequences = [r.sequence for r in receipts]
    assert sequences == list(range(1, len(sequences) + 1))

    print("\nQB-11 LIVE AUDIT & REPLAY SAFETY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
