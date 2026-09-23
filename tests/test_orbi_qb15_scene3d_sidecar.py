from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

from orbi_compat import OrbiRequest, SQLiteReplayLedger
from orbi_qwen_bridge.scene3d_sidecar import (
    MAX_MESSAGE_BYTES,
    PROTOCOL,
    Scene3DPilotSidecar,
    SidecarMessageTooLarge,
    allowed_operations,
    decode_message,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/orbi/qb15_scene3d_sidecar.py"
RISK = "R2_EXECUTE_SANDBOXED"


class FakeResponse:
    def __init__(self, request: OrbiRequest, *, ok=True):
        self.request = request
        self.ok = ok

    def to_dict(self):
        out = {
            "ok": self.ok,
            "request_id": self.request.request_id,
            "interface": self.request.interface,
            "operation": self.request.operation,
            "data": {"echo": self.request.input} if self.ok else None,
            "policy": {"risk_class": "R2_EXECUTE_SANDBOXED"},
            "audit": None,
        }
        if not self.ok:
            out["error"] = {
                "code": "PROVIDER_FAILURE",
                "message": "fake failure",
                "retryable": False,
            }
        return out


class FakeRuntime:
    def __init__(self, *, response_ok=True, exc=None):
        self.requests = []
        self.response_ok = response_ok
        self.exc = exc

    def execute(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return FakeResponse(request, ok=self.response_ok)


class CountingFactory:
    def __init__(self, runtime):
        self.runtime = runtime
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.runtime


def load_script():
    spec = importlib.util.spec_from_file_location("qb15_scene3d_sidecar", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def msg(operation, *, transport_id="t1", request_id=None, input=None):
    out = {
        "protocol": PROTOCOL,
        "id": transport_id,
        "operation": operation,
        "input": {} if input is None else input,
    }
    if request_id is not None:
        out["request_id"] = request_id
    return out


def sidecar(tmp_path, *, runtime=None):
    runtime = runtime or FakeRuntime()
    factory = CountingFactory(runtime)
    ledger = SQLiteReplayLedger(tmp_path / "ledger.sqlite3")
    return Scene3DPilotSidecar(ledger=ledger, runtime_factory=factory), ledger, runtime, factory


def test_operation_surface_has_no_privileged_mutation_commands():
    assert set(allowed_operations()) == {
        "status",
        "scene_info",
        "object_info",
        "dry_run_recipe",
        "execute_recipe",
        "pending_recoveries",
        "reconciliation_history",
    }
    assert not {
        "reconcile",
        "retry",
        "release_reservation",
        "execute_python",
        "execute_blender_code",
    }.intersection(allowed_operations())


def test_decode_message_enforces_byte_limit():
    oversized = b'{"x":"' + (b"a" * MAX_MESSAGE_BYTES) + b'"}'

    with pytest.raises(SidecarMessageTooLarge):
        decode_message(oversized)


def test_status_is_local_and_does_not_start_provider_runtime(tmp_path):
    sc, _, _, factory = sidecar(tmp_path)

    response = sc.process(msg("status"))

    assert response["ok"] is True
    assert response["result"]["transport"] == "stdio-jsonl"
    assert response["result"]["public_listener"] is False
    assert response["result"]["automatic_r2_retry"] is False
    assert response["result"]["reconciliation_mutation"] is False
    assert factory.calls == 0


def test_pending_recovery_inspection_does_not_start_provider_runtime(tmp_path):
    sc, ledger, _, factory = sidecar(tmp_path)
    request = OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id="pending-id",
        input={
            "recipe_id": "orbi.blender.create_cube.v1",
            "parameters": {"name": "Cube", "size": 1, "location": [0, 0, 0]},
        },
    )
    ledger.begin(request, RISK, dry_run=False)

    response = sc.process(msg("pending_recoveries"))

    assert response["ok"] is True
    assert response["result"][0]["request_id"] == "pending-id"
    assert response["result"][0]["provider_called"] is None
    assert factory.calls == 0


def test_reconciliation_history_is_read_only_and_lazy(tmp_path):
    sc, ledger, _, factory = sidecar(tmp_path)
    request = OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id="history-id",
        input={
            "recipe_id": "orbi.blender.create_cube.v1",
            "parameters": {"name": "Cube", "size": 1, "location": [0, 0, 0]},
        },
    )
    ledger.begin(request, RISK, dry_run=False)
    ledger.reconcile_pending(
        "history-id",
        resolution="not_applied",
        evidence={"source": "readback", "exists": False},
        actor="tester",
    )

    response = sc.process(
        msg("reconciliation_history", input={"request_id": "history-id"})
    )

    assert response["ok"] is True
    assert len(response["result"]) == 1
    assert response["result"][0]["resolution"] == "not_applied"
    assert factory.calls == 0


def test_scene_info_maps_to_provider_neutral_orbi_request(tmp_path):
    sc, _, runtime, factory = sidecar(tmp_path)

    response = sc.process(msg("scene_info", request_id="read-1"))

    assert response["ok"] is True
    assert factory.calls == 1
    req = runtime.requests[0]
    assert req.interface == "orbi.scene3d.v1"
    assert req.operation == "scene_info"
    assert req.request_id == "read-1"
    assert req.input == {}


def test_object_info_validates_exact_payload(tmp_path):
    sc, _, runtime, _ = sidecar(tmp_path)

    ok = sc.process(
        msg("object_info", request_id="obj-1", input={"object_name": "Cube"})
    )
    denied = sc.process(
        msg(
            "object_info",
            request_id="obj-2",
            input={"object_name": "Cube", "provider": "qwen"},
        )
    )

    assert ok["ok"] is True
    assert runtime.requests[0].input == {"object_name": "Cube"}
    assert denied["ok"] is False
    assert denied["error"]["code"] == "SIDECAR_PROTOCOL_ERROR"
    assert len(runtime.requests) == 1


def test_dry_run_recipe_forces_dry_run_server_side(tmp_path):
    sc, _, runtime, _ = sidecar(tmp_path)

    response = sc.process(
        msg(
            "dry_run_recipe",
            request_id="dry-1",
            input={
                "recipe_id": "orbi.blender.create_cube.v1",
                "parameters": {"name": "Cube", "size": 1, "location": [0, 0, 0]},
            },
        )
    )

    assert response["ok"] is True
    req = runtime.requests[0]
    assert req.operation == "execute_recipe"
    assert req.input["dry_run"] is True


def test_execution_input_cannot_smuggle_dry_run_code_or_provider(tmp_path):
    sc, _, runtime, _ = sidecar(tmp_path)

    for field, value in (
        ("dry_run", True),
        ("code", "import os"),
        ("provider", "qwen"),
    ):
        response = sc.process(
            msg(
                "execute_recipe",
                transport_id=f"t-{field}",
                request_id=f"req-{field}",
                input={
                    "recipe_id": "orbi.blender.create_cube.v1",
                    "parameters": {},
                    field: value,
                },
            )
        )
        assert response["ok"] is False
        assert response["error"]["code"] == "SIDECAR_PROTOCOL_ERROR"

    assert runtime.requests == []


def test_execute_recipe_uses_main_supplied_request_id_unchanged(tmp_path):
    sc, _, runtime, _ = sidecar(tmp_path)

    response = sc.process(
        msg(
            "execute_recipe",
            request_id="electron-main-generated-id",
            input={
                "recipe_id": "orbi.blender.create_cube.v1",
                "parameters": {"name": "Cube", "size": 1, "location": [0, 0, 0]},
            },
        )
    )

    assert response["ok"] is True
    req = runtime.requests[0]
    assert req.request_id == "electron-main-generated-id"
    assert "dry_run" not in req.input


def test_transport_success_preserves_orbi_application_failure(tmp_path):
    runtime = FakeRuntime(response_ok=False)
    sc, _, runtime, _ = sidecar(tmp_path, runtime=runtime)

    response = sc.process(
        msg(
            "execute_recipe",
            request_id="r2-failure",
            input={
                "recipe_id": "orbi.blender.create_cube.v1",
                "parameters": {},
            },
        )
    )

    assert response["ok"] is True
    assert response["result"]["ok"] is False
    assert response["result"]["error"]["code"] == "PROVIDER_FAILURE"


def test_sidecar_does_not_retry_runtime_exception(tmp_path):
    runtime = FakeRuntime(exc=TimeoutError("provider timeout"))
    sc, _, runtime, _ = sidecar(tmp_path, runtime=runtime)

    response = sc.process(
        msg(
            "execute_recipe",
            request_id="timeout-id",
            input={
                "recipe_id": "orbi.blender.create_cube.v1",
                "parameters": {},
            },
        )
    )

    assert response["ok"] is False
    assert len(runtime.requests) == 1


def test_runtime_factory_is_lazy_and_singleton_per_sidecar(tmp_path):
    sc, _, runtime, factory = sidecar(tmp_path)

    sc.process(msg("scene_info", request_id="read-a"))
    sc.process(msg("scene_info", request_id="read-b"))

    assert factory.calls == 1
    assert len(runtime.requests) == 2


def test_stdio_continues_after_invalid_json_line(tmp_path):
    script = load_script()
    sc, _, _, factory = sidecar(tmp_path)

    valid = json.dumps(msg("status")).encode("utf-8")
    stdin = io.BytesIO(b"not-json\n" + valid + b"\n")
    stdout = io.StringIO()

    rc = script.run_stdio(sc, stdin=stdin, stdout=stdout)
    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]

    assert rc == 0
    assert lines[0]["ok"] is False
    assert lines[1]["ok"] is True
    assert lines[1]["result"]["transport"] == "stdio-jsonl"
    assert factory.calls == 0


def test_stdio_drains_oversized_line_and_processes_next_message(tmp_path):
    script = load_script()
    sc, _, _, _ = sidecar(tmp_path)

    oversized = b"x" * (MAX_MESSAGE_BYTES + 1000) + b"\n"
    valid = json.dumps(msg("status", transport_id="after-large")).encode("utf-8") + b"\n"
    stdin = io.BytesIO(oversized + valid)
    stdout = io.StringIO()

    rc = script.run_stdio(sc, stdin=stdin, stdout=stdout)
    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]

    assert rc == 0
    assert lines[0]["ok"] is False
    assert lines[0]["error"]["code"] == "SIDECAR_MESSAGE_TOO_LARGE"
    assert lines[1]["ok"] is True
    assert lines[1]["id"] == "after-large"
