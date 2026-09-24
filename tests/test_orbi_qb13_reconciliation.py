from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orbi_compat import OrbiRequest, ProviderInfo, SQLiteReplayLedger
from orbi_compat.errors import AlreadyReconciled, PendingExecutionNotFound, ReplayDenied
from orbi_compat.recovery import normalize_reconciliation_input

RISK = "R2_EXECUTE_SANDBOXED"


def request(request_id="qb13-pending", *, name="ORBI_QB13_Test"):
    return OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id=request_id,
        input={
            "recipe_id": "orbi.blender.create_cube.v1",
            "parameters": {
                "name": name,
                "size": 1.0,
                "location": [0.0, 0.0, 0.0],
            },
        },
    )


def make_pending(db: Path, request_id="qb13-pending"):
    ledger = SQLiteReplayLedger(db)
    token = ledger.begin(request(request_id), RISK, dry_run=False)
    return ledger, token


def test_reconciliation_schema_is_additive_and_qb12_schema_remains_v1(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger = SQLiteReplayLedger(db)

    assert ledger.schema() == "1"
    assert ledger.reconciliation_schema() == "1"
    assert ledger.reconciliations() == ()


def test_reconciliation_input_is_deterministic():
    a = normalize_reconciliation_input(
        resolution="applied",
        evidence={"b": 2, "a": 1},
        actor="operator-1",
    )
    b = normalize_reconciliation_input(
        resolution="applied",
        evidence={"a": 1, "b": 2},
        actor="operator-1",
    )

    assert a[0] == "applied"
    assert a[1] == "operator-1"
    assert a[2] == b[2]
    assert a[3] == b[3]
    assert len(a[3]) == 64


def test_reconciliation_input_rejects_invalid_values():
    with pytest.raises(ValueError):
        normalize_reconciliation_input(
            resolution="retry",
            evidence={"source": "readback"},
            actor="operator",
        )

    with pytest.raises(ValueError):
        normalize_reconciliation_input(
            resolution="applied",
            evidence={},
            actor="operator",
        )

    with pytest.raises(ValueError):
        normalize_reconciliation_input(
            resolution="applied",
            evidence={"source": "readback"},
            actor="",
        )


def test_inconclusive_evidence_keeps_execution_pending(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger, token = make_pending(db, "inconclusive-id")

    record = ledger.reconcile_pending(
        "inconclusive-id",
        resolution="inconclusive",
        evidence={"source": "operator", "observation": "cannot reach Blender"},
        actor="operator-a",
    )

    assert record.execution_sequence == token.sequence
    assert record.final is False
    assert record.reservation_released is False
    assert len(ledger.pending_receipts()) == 1
    assert ledger.pending_receipts()[0].outcome == "pending"
    assert ledger.is_reserved("inconclusive-id") is True


def test_inconclusive_can_later_be_resolved_applied(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger, token = make_pending(db, "later-applied")

    first = ledger.reconcile_pending(
        "later-applied",
        resolution="inconclusive",
        evidence={"source": "readback", "result": "temporary-unavailable"},
        actor="operator-a",
    )
    final = SQLiteReplayLedger(db).reconcile_pending(
        "later-applied",
        resolution="applied",
        evidence={"source": "blender-object-info", "object": "ORBI_QB13_Test", "exists": True},
        actor="operator-b",
    )

    assert first.final is False
    assert final.final is True
    assert final.execution_sequence == token.sequence
    assert SQLiteReplayLedger(db).pending_receipts() == ()
    receipts = SQLiteReplayLedger(db).receipts()
    assert receipts[0].outcome == "reconciled-applied"

    recs = SQLiteReplayLedger(db).reconciliations("later-applied")
    assert [r.resolution for r in recs] == ["inconclusive", "applied"]
    assert [r.final for r in recs] == [False, True]


def test_not_applied_resolution_never_releases_original_request_id(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger, _ = make_pending(db, "not-applied-id")

    record = ledger.reconcile_pending(
        "not-applied-id",
        resolution="not_applied",
        evidence={"source": "blender-object-info", "object": "ORBI_QB13_Test", "exists": False},
        actor="operator",
    )

    assert record.final is True
    assert record.reservation_released is False
    assert ledger.is_reserved("not-applied-id") is True
    assert ledger.pending_receipts() == ()
    assert ledger.receipts()[0].outcome == "reconciled-not-applied"

    with pytest.raises(ReplayDenied):
        SQLiteReplayLedger(db).begin(
            request("not-applied-id"),
            RISK,
            dry_run=False,
        )


def test_applied_resolution_persists_evidence_across_restart(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger, token = make_pending(db, "applied-id")

    record = ledger.reconcile_pending(
        "applied-id",
        resolution="applied",
        evidence={
            "source": "blender-object-info",
            "object": "ORBI_QB13_Test",
            "type": "MESH",
            "exists": True,
        },
        actor="qb13-test",
    )

    restarted = SQLiteReplayLedger(db)
    recs = restarted.reconciliations("applied-id")

    assert len(recs) == 1
    assert recs[0] == record
    assert recs[0].execution_sequence == token.sequence
    assert recs[0].evidence["type"] == "MESH"
    assert len(recs[0].evidence_sha256) == 64
    assert restarted.receipts()[0].outcome == "reconciled-applied"


def test_final_reconciliation_cannot_be_rewritten(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger, _ = make_pending(db, "final-id")

    ledger.reconcile_pending(
        "final-id",
        resolution="applied",
        evidence={"source": "readback", "exists": True},
        actor="operator-a",
    )

    with pytest.raises(AlreadyReconciled):
        SQLiteReplayLedger(db).reconcile_pending(
            "final-id",
            resolution="not_applied",
            evidence={"source": "second-opinion", "exists": False},
            actor="operator-b",
        )


def test_unknown_request_has_no_pending_execution(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger = SQLiteReplayLedger(db)

    with pytest.raises(PendingExecutionNotFound):
        ledger.reconcile_pending(
            "missing-id",
            resolution="applied",
            evidence={"source": "readback", "exists": True},
            actor="operator",
        )


def test_concurrent_final_reconciliation_allows_only_one_final_owner(tmp_path):
    db = tmp_path / "audit.sqlite3"
    make_pending(db, "race-final")
    barrier = threading.Barrier(2)
    results = []
    lock = threading.Lock()

    def worker(resolution):
        ledger = SQLiteReplayLedger(db)
        barrier.wait()
        try:
            result = ledger.reconcile_pending(
                "race-final",
                resolution=resolution,
                evidence={"source": "concurrent-readback", "resolution": resolution},
                actor=f"operator-{resolution}",
            )
            outcome = ("resolved", result.resolution)
        except AlreadyReconciled:
            outcome = ("already-reconciled", resolution)
        with lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=worker, args=("applied",)),
        threading.Thread(target=worker, args=("not_applied",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(item[0] for item in results) == ["already-reconciled", "resolved"]
    recs = SQLiteReplayLedger(db).reconciliations("race-final")
    assert len([r for r in recs if r.final]) == 1
    assert SQLiteReplayLedger(db).pending_receipts() == ()
