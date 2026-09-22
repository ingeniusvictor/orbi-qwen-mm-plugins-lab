from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orbi_compat import OrbiRequest, OrbiRuntime, PolicyEngine, ProviderInfo, SQLiteReplayLedger
from orbi_compat.errors import ReplayDenied, RequestIdConflict
from orbi_qwen_bridge.blender_governed import QwenBlenderGovernedAdapter

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


class RecordingBlenderInvoker:
    capability = "blender"

    def __init__(self, exc: Exception | None = None):
        self.calls = []
        self.exc = exc

    def __call__(self, tool, payload):
        self.calls.append((tool, payload))
        if self.exc is not None:
            raise self.exc
        return [{"kind": "text", "text": "provider ok"}]


def policy():
    return PolicyEngine.from_file(CONTRACT)


def create_request(request_id="qb12-create", *, location=None, dry_run=False):
    payload = {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": "ORBI_QB12_Test",
            "size": 1.0,
            "location": location or [0.0, 0.0, 0.0],
        },
    }
    if dry_run:
        payload["dry_run"] = True
    return OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id=request_id,
        input=payload,
    )


def durable_runtime(db_path: Path, invoker=None):
    invoker = invoker or RecordingBlenderInvoker()
    return (
        OrbiRuntime(
            policy(),
            [QwenBlenderGovernedAdapter(invoker)],
            sandboxed_execution_enabled=True,
            replay_ledger=SQLiteReplayLedger(db_path),
        ),
        invoker,
    )


def test_sqlite_ledger_initializes_schema_and_database(tmp_path):
    db = tmp_path / "audit.sqlite3"
    ledger = SQLiteReplayLedger(db)

    assert db.is_file()
    assert ledger.schema() == "1"
    assert ledger.receipts() == ()
    assert ledger.pending_receipts() == ()


def test_reservation_survives_new_ledger_instance(tmp_path):
    db = tmp_path / "audit.sqlite3"
    req = create_request("persist-id")

    first = SQLiteReplayLedger(db)
    token = first.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=False)

    second = SQLiteReplayLedger(db)

    assert token.replay_reserved is True
    assert second.is_reserved("persist-id") is True
    with pytest.raises(ReplayDenied):
        second.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=False)


def test_changed_payload_conflicts_across_restart(tmp_path):
    db = tmp_path / "audit.sqlite3"

    first = SQLiteReplayLedger(db)
    first.begin(
        create_request("conflict-id", location=[0, 0, 0]),
        "R2_EXECUTE_SANDBOXED",
        dry_run=False,
    )

    second = SQLiteReplayLedger(db)
    with pytest.raises(RequestIdConflict):
        second.begin(
            create_request("conflict-id", location=[5, 0, 0]),
            "R2_EXECUTE_SANDBOXED",
            dry_run=False,
        )


def test_pending_unknown_outcome_survives_restart(tmp_path):
    db = tmp_path / "audit.sqlite3"

    first = SQLiteReplayLedger(db)
    token = first.begin(
        create_request("pending-id"),
        "R2_EXECUTE_SANDBOXED",
        dry_run=False,
    )

    second = SQLiteReplayLedger(db)
    pending = second.pending_receipts()

    assert len(pending) == 1
    assert pending[0].sequence == token.sequence
    assert pending[0].request_id == "pending-id"
    assert pending[0].outcome == "pending"
    assert pending[0].provider_called is False
    assert pending[0].replay_reserved is True


def test_finalize_persists_receipt_and_provider_identity(tmp_path):
    db = tmp_path / "audit.sqlite3"
    provider = ProviderInfo("qwen-mm-plugins", "blender", "1.1.0")

    first = SQLiteReplayLedger(db)
    token = first.begin(
        create_request("finalized-id"),
        "R2_EXECUTE_SANDBOXED",
        dry_run=False,
    )
    first.finalize(
        token,
        provider,
        outcome="executed",
        provider_called=True,
    )

    second = SQLiteReplayLedger(db)
    receipts = second.receipts()

    assert len(receipts) == 1
    assert receipts[0].outcome == "executed"
    assert receipts[0].provider_called is True
    assert receipts[0].provider == provider.to_dict()
    assert second.pending_receipts() == ()


def test_dry_run_does_not_reserve_request_id_across_restart(tmp_path):
    db = tmp_path / "audit.sqlite3"
    req = create_request("dry-id", dry_run=True)
    provider = ProviderInfo("qwen-mm-plugins", "blender", "1.1.0")

    first = SQLiteReplayLedger(db)
    token = first.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=True)
    first.finalize(token, provider, outcome="dry-run", provider_called=False)

    second = SQLiteReplayLedger(db)

    assert second.is_reserved("dry-id") is False
    token2 = second.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=True)
    assert token2.sequence > token.sequence


def test_second_runtime_blocks_replay_without_second_provider_call(tmp_path):
    db = tmp_path / "audit.sqlite3"
    req = create_request("runtime-replay")

    rt1, invoker1 = durable_runtime(db)
    first = rt1.execute(req)

    rt2, invoker2 = durable_runtime(db)
    replay = rt2.execute(req)

    assert first.ok is True
    assert replay.ok is False
    assert replay.error is not None
    assert replay.error.code == "REPLAY_DENIED"
    assert len(invoker1.calls) == 1
    assert invoker2.calls == []


def test_timeout_unknown_outcome_blocks_retry_after_restart(tmp_path):
    db = tmp_path / "audit.sqlite3"
    req = create_request("timeout-restart")

    rt1, invoker1 = durable_runtime(
        db,
        RecordingBlenderInvoker(exc=TimeoutError("provider timeout")),
    )
    failed = rt1.execute(req)

    rt2, invoker2 = durable_runtime(db)
    retry = rt2.execute(req)

    assert failed.ok is False
    assert failed.error is not None
    assert failed.error.code == "PROVIDER_UNAVAILABLE"
    assert failed.audit is not None
    assert failed.audit["provider_called"] is True

    assert retry.ok is False
    assert retry.error is not None
    assert retry.error.code == "REPLAY_DENIED"
    assert len(invoker1.calls) == 1
    assert invoker2.calls == []


def test_concurrent_reservation_allows_only_one_owner(tmp_path):
    db = tmp_path / "audit.sqlite3"
    req = create_request("race-id")
    barrier = threading.Barrier(2)
    results = []
    lock = threading.Lock()

    def worker():
        ledger = SQLiteReplayLedger(db)
        barrier.wait()
        try:
            token = ledger.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=False)
            result = ("reserved", token.sequence)
        except ReplayDenied:
            result = ("replay-denied", None)
        with lock:
            results.append(result)

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(item[0] for item in results) == ["replay-denied", "reserved"]
    assert SQLiteReplayLedger(db).is_reserved("race-id") is True


def test_sequences_and_denials_remain_monotonic_across_instances(tmp_path):
    db = tmp_path / "audit.sqlite3"
    provider = ProviderInfo("qwen-mm-plugins", "blender", "1.1.0")
    req = create_request("sequence-id")

    first = SQLiteReplayLedger(db)
    token = first.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=False)
    first.finalize(token, provider, outcome="executed", provider_called=True)

    second = SQLiteReplayLedger(db)
    with pytest.raises(ReplayDenied):
        second.begin(req, "R2_EXECUTE_SANDBOXED", dry_run=False)
    denial = second.record_denial(
        req,
        provider,
        "R2_EXECUTE_SANDBOXED",
        error_code="REPLAY_DENIED",
    )

    third = SQLiteReplayLedger(db)
    receipts = third.receipts()

    assert [receipt.sequence for receipt in receipts] == [1, 2]
    assert denial.sequence == 2
    assert receipts[1].outcome == "replay-denied"
