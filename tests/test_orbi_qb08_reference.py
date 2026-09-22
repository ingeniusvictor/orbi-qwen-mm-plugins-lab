from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from orbi_compat import OrbiRequest, OrbiRuntime, PolicyEngine, ProviderInfo
from orbi_compat.adapters import (
    QwenBlenderReadOnlyAdapter,
    QwenCoreMediaAdapter,
    QwenMHSReadOnlyAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


class RecordingInvoker:
    def __init__(self, result=None, exc: Exception | None = None):
        self.result = {} if result is None else result
        self.exc = exc
        self.calls = []

    def __call__(self, tool, payload):
        self.calls.append((tool, payload))
        if self.exc is not None:
            raise self.exc
        return self.result


def policy():
    return PolicyEngine.from_file(CONTRACT)


def test_request_rejects_empty_identity_fields():
    with pytest.raises(ValueError):
        OrbiRequest(interface="", operation="media_info", request_id="r1")


def test_media_adapter_maps_orbi_operation_without_qwen_import():
    invoke = RecordingInvoker({"duration": 3.0})
    adapter = QwenCoreMediaAdapter(invoke)

    result = adapter.invoke("media_info", {"path": "/tmp/a.mp4"})

    assert result == {"duration": 3.0}
    assert invoke.calls == [("media_info", {"path": "/tmp/a.mp4"})]


def test_blender_read_only_adapter_denies_execute_recipe():
    runtime = OrbiRuntime(
        policy(),
        [QwenBlenderReadOnlyAdapter(RecordingInvoker())],
    )
    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="scene-1",
            input={"recipe_id": "cube"},
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert response.policy["risk_class"] == "R2_EXECUTE_SANDBOXED"


@pytest.mark.parametrize("operation", ["write", "reset"])
def test_mhs_reference_adapter_denies_actuation(operation):
    runtime = OrbiRuntime(
        policy(),
        [QwenMHSReadOnlyAdapter(RecordingInvoker())],
        certified_adapters={"orbi.hardware.v1"},
    )
    response = runtime.execute(
        OrbiRequest(
            interface="orbi.hardware.v1",
            operation=operation,
            request_id=f"hw-{operation}",
            input={"device_id": "mock/device"},
            confirm=True,
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"


def test_policy_denies_uncertified_hardware_before_adapter_call():
    invoke = RecordingInvoker({"should": "not run"})
    runtime = OrbiRuntime(policy(), [QwenMHSReadOnlyAdapter(invoke)])

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.hardware.v1",
            operation="write",
            request_id="hw-write",
            input={"device_id": "mock/device", "value": 1},
            confirm=True,
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert invoke.calls == []


def test_external_provider_disabled_by_default():
    class ExternalAdapter:
        interface = "orbi.skill-authoring.v1"
        provider = ProviderInfo("qwen-mm-plugins", "omni-skill-creator", "1.0.1")

        def invoke(self, operation, payload):
            raise AssertionError("provider must not be called")

    runtime = OrbiRuntime(policy(), [ExternalAdapter()])
    response = runtime.execute(
        OrbiRequest(
            interface="orbi.skill-authoring.v1",
            operation="semantic_perception",
            request_id="skill-1",
            input={"path": "/tmp/demo.mp4"},
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert response.policy["risk_class"] == "R4_EXTERNAL_PROVIDER"


def test_provider_connection_error_normalizes_as_retryable():
    runtime = OrbiRuntime(
        policy(),
        [QwenCoreMediaAdapter(RecordingInvoker(exc=ConnectionError("offline")))],
    )
    response = runtime.execute(
        OrbiRequest(
            interface="orbi.media.v1",
            operation="media_info",
            request_id="media-1",
            input={"path": "/tmp/a.mp4"},
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "PROVIDER_UNAVAILABLE"
    assert response.error.retryable is True


def test_success_response_is_provider_neutral_envelope():
    runtime = OrbiRuntime(
        policy(),
        [QwenCoreMediaAdapter(RecordingInvoker({"width": 640, "height": 480}))],
    )
    response = runtime.execute(
        OrbiRequest(
            interface="orbi.media.v1",
            operation="media_info",
            request_id="media-ok",
            input={"path": "/tmp/image.png"},
        )
    ).to_dict()

    assert response["ok"] is True
    assert response["interface"] == "orbi.media.v1"
    assert response["operation"] == "media_info"
    assert response["provider"]["family"] == "qwen-mm-plugins"
    assert response["data"] == {"width": 640, "height": 480}
    assert response["policy"]["decision"] == "allow"
    assert response["policy"]["risk_class"] == "R0_READ_LOCAL"


def test_provider_can_be_substituted_without_changing_request_contract():
    class NativeMediaAdapter:
        interface = "orbi.media.v1"
        provider = ProviderInfo("orbi-native", "media", "0.1.0")

        def invoke(self, operation, payload):
            return {"provider": "native", "operation": operation, "path": payload["path"]}

    request = OrbiRequest(
        interface="orbi.media.v1",
        operation="media_info",
        request_id="swap-1",
        input={"path": "/tmp/a.mp4"},
    )

    response = OrbiRuntime(policy(), [NativeMediaAdapter()]).execute(request)

    assert response.ok is True
    assert response.provider.family == "orbi-native"
    assert response.data["operation"] == "media_info"


def test_orbi_compat_source_has_no_direct_qwen_imports():
    root = ROOT / "src/orbi_compat"
    offenders = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("qwen_mm_plugins"):
                        offenders.append((path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("qwen_mm_plugins"):
                    offenders.append((path, module))

    assert offenders == []


def test_contract_still_declares_expected_reference_interfaces():
    doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
    interfaces = {item["interface"] for item in doc["adapters"]}

    assert {
        "orbi.media.v1",
        "orbi.hardware.v1",
        "orbi.scene3d.v1",
    }.issubset(interfaces)
