from __future__ import annotations

import ast
from pathlib import Path

from orbi_compat import OrbiRequest, OrbiRuntime, PolicyEngine, ProviderInfo
from orbi_qwen_bridge.blender_governed import QwenBlenderGovernedAdapter
from orbi_qwen_bridge.blender_recipes import compile_recipe, recipe_ids

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


class FakeBlenderInvoker:
    capability = "blender"

    def __init__(self):
        self.calls = []

    def __call__(self, tool, payload):
        self.calls.append((tool, payload))
        return [{"kind": "text", "text": "provider ok"}]


class PermissiveSceneAdapter:
    interface = "orbi.scene3d.v1"
    provider = ProviderInfo("fake", "scene3d", "0")

    def __init__(self):
        self.calls = []

    def invoke(self, operation, payload):
        self.calls.append((operation, payload))
        return {"ok": True}


def policy():
    return PolicyEngine.from_file(CONTRACT)


def governed_runtime(invoker=None):
    invoker = invoker or FakeBlenderInvoker()
    return (
        OrbiRuntime(
            policy(),
            [QwenBlenderGovernedAdapter(invoker)],
            sandboxed_execution_enabled=True,
        ),
        invoker,
    )


def execute_payload(**overrides):
    payload = {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": "ORBI_QB10_Test",
            "size": 2.0,
            "location": [1.0, 2.0, 3.0],
        },
    }
    payload.update(overrides)
    return payload


def test_r2_execution_is_denied_by_default_before_adapter_call():
    adapter = PermissiveSceneAdapter()
    runtime = OrbiRuntime(policy(), [adapter])

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="r2-denied",
            input=execute_payload(),
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert "sandboxed execution is disabled" in response.error.message
    assert adapter.calls == []


def test_recipe_registry_contains_only_initial_approved_recipes():
    assert recipe_ids() == (
        "orbi.blender.create_cube.v1",
        "orbi.blender.delete_object.v1",
    )


def test_create_cube_recipe_normalizes_parameters_and_hashes_code():
    recipe = compile_recipe(
        "orbi.blender.create_cube.v1",
        {"name": "Cube_01", "size": 2, "location": [1, 2, 3]},
    )

    assert recipe.parameters == {
        "name": "Cube_01",
        "size": 2.0,
        "location": [1.0, 2.0, 3.0],
    }
    assert len(recipe.code_sha256) == 64
    assert recipe.filesystem_scope == ()
    assert recipe.network_allowed is False


def test_recipe_code_imports_only_bpy_and_has_no_dynamic_code_or_file_open():
    for recipe_id, params in (
        (
            "orbi.blender.create_cube.v1",
            {"name": "SafeCube", "size": 1, "location": [0, 0, 0]},
        ),
        ("orbi.blender.delete_object.v1", {"name": "SafeCube"}),
    ):
        recipe = compile_recipe(recipe_id, params)
        tree = ast.parse(recipe.code)

        imports = set()
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)

        assert imports == {"bpy"}
        assert not {"open", "exec", "eval", "__import__"}.intersection(calls)


def test_unknown_recipe_is_policy_denied_without_provider_call():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="unknown-recipe",
            input={"recipe_id": "attacker.python", "parameters": {}},
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert invoker.calls == []


def test_unexpected_code_field_is_denied_without_provider_call():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="code-injection",
            input=execute_payload(code="import os; os.system('echo nope')"),
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert invoker.calls == []


def test_malicious_object_name_is_denied_without_provider_call():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="name-injection",
            input=execute_payload(
                parameters={
                    "name": "x'; import os; #",
                    "size": 1,
                    "location": [0, 0, 0],
                }
            ),
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert invoker.calls == []


def test_out_of_range_size_is_denied():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="bad-size",
            input=execute_payload(
                parameters={
                    "name": "Cube",
                    "size": 999999,
                    "location": [0, 0, 0],
                }
            ),
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "POLICY_DENIED"
    assert invoker.calls == []


def test_dry_run_returns_plan_without_calling_provider():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="dry-run",
            input=execute_payload(dry_run=True),
        )
    )

    assert response.ok is True
    assert response.policy["risk_class"] == "R2_EXECUTE_SANDBOXED"
    assert response.data["execution"] == "dry-run"
    assert response.data["recipe"]["network_allowed"] is False
    assert response.data["recipe"]["filesystem_scope"] == []
    assert response.data["audit"]["provider_called"] is False
    assert invoker.calls == []


def test_governed_execution_calls_only_execute_blender_code_with_compiled_code():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="execute",
            input=execute_payload(),
        )
    )

    assert response.ok is True
    assert response.data["execution"] == "executed"
    assert response.data["audit"]["provider_called"] is True
    assert len(invoker.calls) == 1

    tool, payload = invoker.calls[0]
    assert tool == "execute_blender_code"
    assert set(payload) == {"code"}
    assert "ORBI_QB10_Test" in payload["code"]
    assert "import bpy" in payload["code"]


def test_delete_recipe_is_governed_and_executes_through_same_tool():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="delete",
            input={
                "recipe_id": "orbi.blender.delete_object.v1",
                "parameters": {"name": "ORBI_QB10_Test"},
            },
        )
    )

    assert response.ok is True
    assert invoker.calls[0][0] == "execute_blender_code"
    assert "ORBI_QB10_Test" in invoker.calls[0][1]["code"]


def test_read_operation_remains_available_in_governed_adapter():
    runtime, invoker = governed_runtime()

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="scene_info",
            request_id="read-scene",
        )
    )

    assert response.ok is True
    assert invoker.calls == [("get_scene_info", {})]
