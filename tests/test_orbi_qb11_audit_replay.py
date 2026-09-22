from __future__ import annotations

from pathlib import Path

import pytest

from orbi_compat import OrbiRequest, OrbiRuntime, PolicyEngine, ProviderInfo, request_fingerprint
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


class ReadAdapter:
    interface = "orbi.media.v1"
    provider = ProviderInfo("fake", "media", "1")

    def __init__(self):
        self.calls = []

    def invoke(self, operation, payload):
        self.calls.append((operation, payload))
        return {"ok": True}


def policy():
    return PolicyEngine.from_file(CONTRACT)


def runtime(invoker=None):
    invoker = invoker or RecordingBlenderInvoker()
    return (
        OrbiRuntime(
            policy(),
            [QwenBlenderGovernedAdapter(invoker)],
            sandboxed_execution_enabled=True,
        ),
        invoker,
    )


def create_request(request_id="qb11-create", *, dry_run=False, location=None):
    payload = {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": "ORBI_QB11_Test",
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


def test_request_fingerprint_is_deterministic_across_dict_key_order():
    a = OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id="a",
        input={
            "recipe_id": "orbi.blender.create_cube.v1",
            "parameters": {"size": 1, "name": "Cube", "location": [0, 0, 0]},
        },
    )
    b = OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id="b",
        input={
            "parameters": {"location": [0, 0, 0], "name": "Cube", "size": 1},
            "recipe_id": "orbi.blender.create_cube.v1",
        },
    )

    assert request_fingerprint(a) == request_fingerprint(b)


def test_request_fingerprint_excludes_request_id_but_includes_payload():
    a = create_request("id-a")
    b = create_request("id-b")
    c = create_request("id-c", location=[1, 0, 0])

    assert request_fingerprint(a) == request_fingerprint(b)
    assert request_fingerprint(a) != request_fingerprint(c)


def test_r2_success_returns_execution_receipt():
    rt, invoker = runtime()

    response = rt.execute(create_request())

    assert response.ok is True
    assert response.audit is not None
    assert response.audit["schema"] == "orbi.execution-audit/v1"
    assert response.audit["outcome"] == "executed"
    assert response.audit["provider_called"] is True
    assert response.audit["replay_reserved"] is True
    assert response.audit["risk_class"] == "R2_EXECUTE_SANDBOXED"
    assert len(response.audit["request_fingerprint"]) == 64
    assert response.audit["retry_semantics"] == "new-request-id-required-after-execution-attempt"
    assert len(invoker.calls) == 1


def test_exact_r2_replay_is_denied_before_second_provider_call():
    rt, invoker = runtime()
    req = create_request("same-id")

    first = rt.execute(req)
    second = rt.execute(req)

    assert first.ok is True
    assert second.ok is False
    assert second.error is not None
    assert second.error.code == "REPLAY_DENIED"
    assert second.error.retryable is False
    assert second.audit is not None
    assert second.audit["outcome"] == "replay-denied"
    assert second.audit["provider_called"] is False
    assert second.audit["error_code"] == "REPLAY_DENIED"
    assert len(invoker.calls) == 1


def test_request_id_reuse_with_different_payload_is_conflict():
    rt, invoker = runtime()

    first = rt.execute(create_request("same-id", location=[0, 0, 0]))
    conflict = rt.execute(create_request("same-id", location=[5, 0, 0]))

    assert first.ok is True
    assert conflict.ok is False
    assert conflict.error is not None
    assert conflict.error.code == "REQUEST_ID_CONFLICT"
    assert conflict.audit is not None
    assert conflict.audit["provider_called"] is False
    assert conflict.audit["error_code"] == "REQUEST_ID_CONFLICT"
    assert len(invoker.calls) == 1


def test_dry_run_is_repeatable_and_not_reserved():
    rt, invoker = runtime()
    req = create_request("dry-id", dry_run=True)

    first = rt.execute(req)
    second = rt.execute(req)

    assert first.ok is True and second.ok is True
    assert first.audit is not None and second.audit is not None
    assert first.audit["outcome"] == "dry-run"
    assert second.audit["outcome"] == "dry-run"
    assert first.audit["provider_called"] is False
    assert second.audit["provider_called"] is False
    assert first.audit["replay_reserved"] is False
    assert second.audit["replay_reserved"] is False
    assert first.audit["retry_semantics"] == "dry-run-repeatable"
    assert invoker.calls == []


def test_dry_run_then_execution_may_reuse_request_id():
    rt, invoker = runtime()

    dry = rt.execute(create_request("inspect-then-run", dry_run=True))
    real = rt.execute(create_request("inspect-then-run", dry_run=False))

    assert dry.ok is True
    assert real.ok is True
    assert dry.audit is not None and dry.audit["replay_reserved"] is False
    assert real.audit is not None and real.audit["replay_reserved"] is True
    assert len(invoker.calls) == 1


def test_provider_timeout_reserves_request_id_and_blocks_automatic_retry():
    invoker = RecordingBlenderInvoker(exc=TimeoutError("provider timeout"))
    rt, _ = runtime(invoker)
    req = create_request("timeout-id")

    first = rt.execute(req)
    retry = rt.execute(req)

    assert first.ok is False
    assert first.error is not None
    assert first.error.code == "PROVIDER_UNAVAILABLE"
    assert first.error.retryable is True
    assert first.audit is not None
    assert first.audit["outcome"] == "provider-error"
    assert first.audit["provider_called"] is True
    assert first.audit["replay_reserved"] is True

    assert retry.ok is False
    assert retry.error is not None
    assert retry.error.code == "REPLAY_DENIED"
    assert retry.error.retryable is False
    assert len(invoker.calls) == 1


def test_invalid_recipe_is_reserved_but_records_provider_not_called():
    rt, invoker = runtime()

    req = OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id="invalid-recipe",
        input={"recipe_id": "not.approved", "parameters": {}},
    )
    response = rt.execute(req)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert response.audit is not None
    assert response.audit["outcome"] == "denied"
    assert response.audit["provider_called"] is False
    assert response.audit["replay_reserved"] is True
    assert invoker.calls == []


def test_r0_read_reuses_request_id_and_has_no_execution_audit():
    adapter = ReadAdapter()
    rt = OrbiRuntime(policy(), [adapter])
    req = OrbiRequest(
        interface="orbi.media.v1",
        operation="media_info",
        request_id="same-read-id",
        input={"path": "/tmp/a.wav"},
    )

    one = rt.execute(req)
    two = rt.execute(req)

    assert one.ok is True and two.ok is True
    assert one.audit is None and two.audit is None
    assert len(adapter.calls) == 2


def test_receipt_sequence_is_contiguous_across_success_and_replay_denial():
    rt, _ = runtime()

    one = rt.execute(create_request("seq-1", dry_run=True))
    two = rt.execute(create_request("seq-2"))
    three = rt.execute(create_request("seq-2"))

    assert one.audit is not None and one.audit["sequence"] == 1
    assert two.audit is not None and two.audit["sequence"] == 2
    assert three.audit is not None and three.audit["sequence"] == 3

    receipts = rt.replay_ledger.receipts()
    assert [r.sequence for r in receipts] == [1, 2, 3]


def test_non_json_r2_payload_is_rejected_before_provider_call():
    rt, invoker = runtime()

    req = OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id="non-json",
        input={
            "recipe_id": "orbi.blender.create_cube.v1",
            "parameters": {"name": "Cube", "size": 1, "location": {0, 1, 2}},
        },
    )
    response = rt.execute(req)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "PROVIDER_FAILURE"
    assert "deterministic JSON" in response.error.message
    assert invoker.calls == []
