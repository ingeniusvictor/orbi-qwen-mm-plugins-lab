"""Governed Blender adapter for ORBI scene3d execution (QB-10)."""

from __future__ import annotations

from typing import Any

from orbi_compat.contracts import ProviderInfo
from orbi_compat.errors import PolicyDenied, UnsupportedOperation

from .blender_recipes import compile_recipe
from .registry import QwenRegistryInvoker


class QwenBlenderGovernedAdapter:
    interface = "orbi.scene3d.v1"
    provider = ProviderInfo("qwen-mm-plugins", "blender", "1.1.0")

    _READ_TOOLS = {
        "scene_info": "get_scene_info",
        "object_info": "get_object_info",
        "viewport_screenshot": "get_viewport_screenshot",
    }

    def __init__(self, invoker: QwenRegistryInvoker):
        if invoker.capability != "blender":
            raise ValueError("QwenBlenderGovernedAdapter requires the blender capability")
        self._invoker = invoker

    def invoke(self, operation: str, payload: dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            raise TypeError("scene3d payload must be a dict")

        if operation in self._READ_TOOLS:
            return self._invoker(self._READ_TOOLS[operation], payload)

        if operation != "execute_recipe":
            raise UnsupportedOperation(f"{self.interface}/{operation} is unsupported")

        allowed = {"recipe_id", "parameters", "dry_run"}
        unknown = set(payload) - allowed
        if unknown:
            raise PolicyDenied(f"unexpected execute_recipe field(s): {', '.join(sorted(unknown))}")

        recipe_id = payload.get("recipe_id")
        if not isinstance(recipe_id, str) or not recipe_id:
            raise PolicyDenied("execute_recipe requires a non-empty recipe_id")

        dry_run = payload.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise PolicyDenied("dry_run must be boolean")

        try:
            compiled = compile_recipe(recipe_id, payload.get("parameters"))
        except (LookupError, TypeError, ValueError) as exc:
            raise PolicyDenied(str(exc)) from exc

        plan = compiled.public_plan()

        if dry_run:
            return {
                "execution": "dry-run",
                "recipe": plan,
                "audit": {
                    "provider_tool": "execute_blender_code",
                    "provider_called": False,
                },
            }

        result = self._invoker(
            "execute_blender_code",
            {"code": compiled.code},
        )
        return {
            "execution": "executed",
            "recipe": plan,
            "provider_result": result,
            "audit": {
                "provider_tool": "execute_blender_code",
                "provider_called": True,
            },
        }
