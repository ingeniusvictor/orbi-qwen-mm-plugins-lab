#!/usr/bin/env python3
"""QB-13 live durable recovery/reconciliation smoke.

Simulates the hardest uncertain-outcome case:
1) durable reservation is committed,
2) Blender side effect happens,
3) process "crashes" before audit finalization,
4) a new runtime reads back Blender state,
5) the pending execution is reconciled as applied,
6) the original request id remains permanently replay-protected.
"""

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
from orbi_qwen_bridge.blender_governed import QwenBlenderGovernedAdapter
from orbi_qwen_bridge.registry import QwenRegistryInvoker

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"
RISK = "R2_EXECUTE_SANDBOXED"
APPLIED_NAME = "ORBI_QB13_Applied"
NOT_APPLIED_NAME = "ORBI_QB13_NotApplied"


def call(runtime, operation, request_id, payload=None):
    return runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation=operation,
            request_id=request_id,
            input=payload or {},
        )
    )


def create_payload(name, location):
    return {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": name,
            "size": 1.0,
            "location": location,
        },
    }


def create_request(request_id, name, location):
    return OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id=request_id,
        input=create_payload(name, location),
    )


def assert_absent(runtime, name, request_id):
    result = call(runtime, "object_info", request_id, {"object_name": name})
    print(result.to_dict())
    assert result.ok is False
    assert result.error is not None
    assert "Object not found" in result.error.message


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="qb13-reconcile-") as td:
        db = Path(td) / "execution-ledger.sqlite3"

        print("=== QB-13 PREEXISTING OBJECT GUARDS ===")
        guard_runtime = build_governed_blender_runtime(CONTRACT, durable_ledger_path=db)
        assert_absent(guard_runtime, APPLIED_NAME, "qb13-pre-applied")
        assert_absent(guard_runtime, NOT_APPLIED_NAME, "qb13-pre-not-applied")

        applied_request = create_request(
            "qb13-crash-applied",
            APPLIED_NAME,
            [4.0, 0.0, 0.5],
        )

        print("\n=== QB-13 COMMIT DURABLE RESERVATION ===")
        ledger1 = SQLiteReplayLedger(db)
        token = ledger1.begin(applied_request, RISK, dry_run=False)
        print({
            "sequence": token.sequence,
            "request_id": token.request_id,
            "fingerprint": token.request_fingerprint,
            "reserved": token.replay_reserved,
        })
        assert ledger1.is_reserved(applied_request.request_id) is True
        assert len(ledger1.pending_receipts()) == 1

        print("\n=== QB-13 SIMULATE PROVIDER EFFECT BEFORE CRASH ===")
        direct_adapter = QwenBlenderGovernedAdapter(QwenRegistryInvoker("blender"))
        provider_result = direct_adapter.invoke("execute_recipe", applied_request.input)
        print(provider_result)
        assert provider_result["execution"] == "executed"
        assert provider_result["audit"]["provider_called"] is True

        print("\n=== QB-13 SIMULATED CRASH: NO FINALIZE ===")
        del direct_adapter
        del ledger1

        print("\n=== QB-13 RESTART + PENDING INSPECTION ===")
        ledger2 = SQLiteReplayLedger(db)
        pending = ledger2.pending_receipts()
        for item in pending:
            print(item.to_dict())
        assert len(pending) == 1
        assert pending[0].request_id == "qb13-crash-applied"
        assert pending[0].outcome == "pending"
        assert pending[0].provider_called is None

        runtime2 = build_governed_blender_runtime(CONTRACT, durable_ledger_path=db)

        print("\n=== QB-13 LIVE READ-BACK PROVES EFFECT APPLIED ===")
        observed = call(
            runtime2,
            "object_info",
            "qb13-readback-applied",
            {"object_name": APPLIED_NAME},
        )
        print(observed.to_dict())
        assert observed.ok is True
        assert APPLIED_NAME in observed.data[0]["text"]
        assert "MESH" in observed.data[0]["text"]

        print("\n=== QB-13 FINAL RECONCILIATION: APPLIED ===")
        applied_reconciliation = ledger2.reconcile_pending(
            "qb13-crash-applied",
            resolution="applied",
            evidence={
                "source": "blender-object-info",
                "object_name": APPLIED_NAME,
                "exists": True,
                "type": "MESH",
            },
            actor="qb13-live-smoke",
        )
        print(applied_reconciliation.to_dict())
        assert applied_reconciliation.final is True
        assert applied_reconciliation.reservation_released is False
        assert ledger2.pending_receipts() == ()

        print("\n=== QB-13 ORIGINAL ID STAYS REPLAY-PROTECTED ===")
        replay = runtime2.execute(applied_request)
        print(replay.to_dict())
        assert replay.ok is False
        assert replay.error is not None
        assert replay.error.code == "REPLAY_DENIED"

        print("\n=== QB-13 CLEANUP APPLIED OBJECT WITH NEW ID ===")
        cleanup = call(
            runtime2,
            "execute_recipe",
            "qb13-cleanup-applied",
            {
                "recipe_id": "orbi.blender.delete_object.v1",
                "parameters": {"name": APPLIED_NAME},
            },
        )
        print(cleanup.to_dict())
        assert cleanup.ok is True
        assert_absent(runtime2, APPLIED_NAME, "qb13-applied-gone")

        print("\n=== QB-13 SECOND CRASH CASE: EFFECT NOT APPLIED ===")
        not_applied_request = create_request(
            "qb13-crash-not-applied",
            NOT_APPLIED_NAME,
            [5.0, 0.0, 0.5],
        )
        ledger3 = SQLiteReplayLedger(db)
        token2 = ledger3.begin(not_applied_request, RISK, dry_run=False)
        print({
            "sequence": token2.sequence,
            "request_id": token2.request_id,
            "reserved": token2.replay_reserved,
        })
        del ledger3

        print("\n=== QB-13 RESTART + READ-BACK PROVES ABSENCE ===")
        runtime3 = build_governed_blender_runtime(CONTRACT, durable_ledger_path=db)
        assert_absent(runtime3, NOT_APPLIED_NAME, "qb13-readback-not-applied")

        ledger4 = SQLiteReplayLedger(db)
        not_applied_reconciliation = ledger4.reconcile_pending(
            "qb13-crash-not-applied",
            resolution="not_applied",
            evidence={
                "source": "blender-object-info",
                "object_name": NOT_APPLIED_NAME,
                "exists": False,
            },
            actor="qb13-live-smoke",
        )
        print(not_applied_reconciliation.to_dict())
        assert not_applied_reconciliation.final is True
        assert not_applied_reconciliation.reservation_released is False

        print("\n=== QB-13 NOT-APPLIED STILL REQUIRES NEW REQUEST ID ===")
        denied = runtime3.execute(not_applied_request)
        print(denied.to_dict())
        assert denied.ok is False
        assert denied.error is not None
        assert denied.error.code == "REPLAY_DENIED"

        print("\n=== QB-13 NEW ID MAY EXECUTE INTENTIONALLY ===")
        intentional = call(
            runtime3,
            "execute_recipe",
            "qb13-new-intent",
            create_payload(NOT_APPLIED_NAME, [5.0, 0.0, 0.5]),
        )
        print(intentional.to_dict())
        assert intentional.ok is True

        cleanup2 = call(
            runtime3,
            "execute_recipe",
            "qb13-cleanup-not-applied",
            {
                "recipe_id": "orbi.blender.delete_object.v1",
                "parameters": {"name": NOT_APPLIED_NAME},
            },
        )
        print(cleanup2.to_dict())
        assert cleanup2.ok is True
        assert_absent(runtime3, NOT_APPLIED_NAME, "qb13-not-applied-gone")

        print("\n=== QB-13 DURABLE RECONCILIATION INSPECTION ===")
        final_ledger = SQLiteReplayLedger(db)
        assert final_ledger.reconciliation_schema() == "1"
        assert final_ledger.pending_receipts() == ()

        reconciliations = final_ledger.reconciliations()
        for item in reconciliations:
            print(item.to_dict())

        by_request = {item.request_id: item for item in reconciliations if item.final}
        assert by_request["qb13-crash-applied"].resolution == "applied"
        assert by_request["qb13-crash-not-applied"].resolution == "not_applied"
        assert all(item.reservation_released is False for item in reconciliations)

        assert final_ledger.is_reserved("qb13-crash-applied") is True
        assert final_ledger.is_reserved("qb13-crash-not-applied") is True

        print("\nQB-13 LIVE DURABLE RECOVERY & RECONCILIATION: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
