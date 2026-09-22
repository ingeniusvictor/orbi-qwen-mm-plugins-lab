"""Read-oriented `orbi.media.v1` facade backed by injected Qwen core tools."""

from __future__ import annotations

from typing import Any

from orbi_compat.contracts import ProviderInfo
from orbi_compat.errors import UnsupportedOperation

from ._invoke import ToolInvoker, ensure_dict


class QwenCoreMediaAdapter:
    interface = "orbi.media.v1"
    provider = ProviderInfo("qwen-mm-plugins", "core", "1.1.0")

    _TOOLS = {
        "media_info": "media_info",
        "read_image": "read_image",
        "read_video": "read_video",
        "visualize": "visualize",
    }

    def __init__(self, invoke_tool: ToolInvoker):
        self._invoke_tool = invoke_tool

    def invoke(self, operation: str, payload: dict[str, Any]) -> Any:
        try:
            tool = self._TOOLS[operation]
        except KeyError as exc:
            raise UnsupportedOperation(f"{self.interface}/{operation} is unsupported") from exc
        return self._invoke_tool(tool, ensure_dict(payload))
