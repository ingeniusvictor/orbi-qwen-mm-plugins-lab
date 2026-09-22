#!/usr/bin/env python3
"""QB-12 live durable execution-ledger + restart-safety smoke."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat import OrbiRequest, SQLiteReplayLedger
from orbi_qwen_bridge import build_governed_blender_runtime

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"
NAME = "ORBI_QB12_Cube"


def call(runtime, operation, request_id, payload=None):
    return runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation=operation,
            request_id=request_id,
            input=payload or {},
        )
    )


def create_payload(*, location=None, dry_run=False):
    payload = {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": NAME,
            "size": 1.0,
            "location": location or [3.0, 0.0, 0.5],
        },
    }
    if dry_run:
        payload["dry_run"] = True
    return payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="qb12-ledger-") as td:
        db = Path(td) / "execution-ledger.sqlite3"

        print("=== QB-12 RUNTIME #1 ===")
        runtime1 = build_governed_blender_runtime(
            CONTRACT,
            durable_ledger_path=db,
        )

        pre = call(runtime1, "object_info", "qb12-precheck", {"object_name": NAME})
        print(pre.to_dict())
        if pre.ok:
            raise AssertionError(f"{NAME} already exists; refusing to touch it")
        if pre.error is None or "Object not found" not in pre.error.message:
            raise AssertionError(
                f"unexpected Blender precheck failure: "
                f"{pre.error.message if pre.error else 'unknown'}"
            )

        print("\n=== QB-12 DURABLE DRY RUN ===")
        dry = call(
            runtime1,
            "execute_recipe",
            "qb12-dry",
            create_payload(dry_run=True),
        )
        print(dry.to_dict())
        assert dry.ok is True
        assert dry.audit is not None
        assert dry.audit["outcome"] == "dry-run"
        assert dry.audit["replay_reserved"] is False

        create_attempted = False
        try:
            print("\n=== QB-12 GOVERNED CREATE / RUNTIME #1 ===")
            create_attempted = True
            created = call(
                runtime1,
                "execute_recipe",
                "qb12-create",
                create_payload(),
            )
            print(created.to_dict())
            assert created.ok is True
            assert created.audit is not None
            assert created.audit["outcome"] == "executed"
            assert created.audit["replay_reserved"] is True

            print("\n=== QB-12 SIMULATED PROCESS RESTART ===")
            del runtime1
            runtime2 = build_governed_blender_runtime(
                CONTRACT,
                durable_ledger_path=db,
            )

            print("\n=== QB-12 REPLAY AFTER RESTART ===")
            replay = call(
                runtime2,
                "execute_recipe",
                "qb12-create",
                create_payload(),
            )
            print(replay.to_dict())
            assert replay.ok is False
            assert replay.error is not None
            assert replay.error.code == "REPLAY_DENIED"
            assert replay.audit is not None
            assert replay.audit["provider_called"] is False

            print("\n=== QB-12 CONFLICT AFTER RESTART ===")
            conflict = call(
                runtime2,
                "execute_recipe",
                "qb12-create",
                create_payload(location=[8.0, 0.0, 0.5]),
            )
            print(conflict.to_dict())
            assert conflict.ok is False
            assert conflict.error is not None
            assert conflict.error.code == "REQUEST_ID_CONFLICT"
            assert conflict.audit is not None
            assert conflict.audit["provider_called"] is False

            print("\n=== QB-12 OBJECT STILL EXISTS ===")
            obj = call(
                runtime2,
                "object_info",
                "qb12-object-info",
                {"object_name": NAME},
            )
            print(obj.to_dict())
            assert obj.ok is True
            assert NAME in obj.data[0]["text"]
            assert "MESH" in obj.data[0]["text"]

        finally:
            print("\n=== QB-12 OWNERSHIP-SAFE DURABLE CLEANUP ===")
            runtime_cleanup = build_governed_blender_runtime(
                CONTRACT,
                durable_ledger_path=db,
            )
            if create_attempted:
                exists = call(
                    runtime_cleanup,
                    "object_info",
                    "qb12-cleanup-check",
                    {"object_name": NAME},
                )
                print(exists.to_dict())
                if exists.ok:
                    cleanup = call(
                        runtime_cleanup,
                        "execute_recipe",
                        "qb12-cleanup",
                        {
                            "recipe_id": "orbi.blender.delete_object.v1",
                            "parameters": {"name": NAME},
                        },
                    )
                    print(cleanup.to_dict())
                    assert cleanup.ok is True

        print("\n=== QB-12 SECOND RESTART / CLEANUP REPLAY GUARD ===")
        runtime3 = build_governed_blender_runtime(
            CONTRACT,
            durable_ledger_path=db,
        )
        cleanup_replay = call(
            runtime3,
            "execute_recipe",
            "qb12-cleanup",
            {
                "recipe_id": "orbi.blender.delete_object.v1",
                "parameters": {"name": NAME},
            },
        )
        print(cleanup_replay.to_dict())
        assert cleanup_replay.ok is False
        assert cleanup_replay.error is not None
        assert cleanup_replay.error.code == "REPLAY_DENIED"

        gone = call(
            runtime3,
            "object_info",
            "qb12-object-gone",
            {"object_name": NAME},
        )
        print(gone.to_dict())
        assert gone.ok is False
        assert gone.error is not None
        assert "Object not found" in gone.error.message

        print("\n=== QB-12 DURABLE LEDGER INSPECTION ===")
        ledger = SQLiteReplayLedger(db)
        print("DB:", db)
        print("Schema:", ledger.schema())
        print("Pending:", [r.to_dict() for r in ledger.pending_receipts()])
        receipts = ledger.receipts()
        for receipt in receipts:
            print(receipt.to_dict())

        assert db.is_file()
        assert ledger.schema() == "1"
        assert ledger.pending_receipts() == ()
        assert ledger.is_reserved("qb12-create") is True
        assert ledger.is_reserved("qb12-cleanup") is True

        sequences = [receipt.sequence for receipt in receipts]
        assert sequences == list(range(1, len(sequences) + 1))
        assert any(r.outcome == "executed" and r.request_id == "qb12-create" for r in receipts)
        assert any(r.outcome == "replay-denied" and r.request_id == "qb12-create" for r in receipts)
        assert any(r.error_code == "REQUEST_ID_CONFLICT" for r in receipts)

        print("\nQB-12 LIVE DURABLE LEDGER & RESTART SAFETY: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
