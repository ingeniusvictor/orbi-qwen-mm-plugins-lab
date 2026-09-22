"""Read-only `orbi.scene3d.v1` facade for the certified Blender provider."""

from __future__ import annotations

from typing import Any

from orbi_compat.contracts import ProviderInfo
from orbi_compat.errors import PolicyDenied, UnsupportedOperation

from ._invoke import ToolInvoker, ensure_dict


class QwenBlenderReadOnlyAdapter:
    interface = "orbi.scene3d.v1"
    provider = ProviderInfo("qwen-mm-plugins", "blender", "1.1.0")

    _TOOLS = {
        "scene_info": "get_scene_info",
        "object_info": "get_object_info",
        "viewport_screenshot": "get_viewport_screenshot",
    }

    def __init__(self, invoke_tool: ToolInvoker):
        self._invoke_tool = invoke_tool

    def invoke(self, operation: str, payload: dict[str, Any]) -> Any:
        if operation == "execute_recipe":
            raise PolicyDenied(
                "execute_recipe is not implemented by the QB-08 read-only Blender reference adapter"
            )
        try:
            tool = self._TOOLS[operation]
        except KeyError as exc:
            raise UnsupportedOperation(f"{self.interface}/{operation} is unsupported") from exc
        return self._invoke_tool(tool, ensure_dict(payload))
