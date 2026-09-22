"""Read-only `orbi.hardware.v1` facade for the certified Qwen MHS provider."""

from __future__ import annotations

from typing import Any

from orbi_compat.contracts import ProviderInfo
from orbi_compat.errors import PolicyDenied, UnsupportedOperation

from ._invoke import ToolInvoker, ensure_dict


class QwenMHSReadOnlyAdapter:
    interface = "orbi.hardware.v1"
    provider = ProviderInfo("qwen-mm-plugins", "mhs", "1.1.0")

    _TOOLS = {
        "discover": "mhs_discover",
        "meta": "mhs_meta_info",
        "read": "mhs_read",
        "health": "mhs_health_check",
    }

    def __init__(self, invoke_tool: ToolInvoker):
        self._invoke_tool = invoke_tool

    def invoke(self, operation: str, payload: dict[str, Any]) -> Any:
        if operation in {"write", "reset"}:
            raise PolicyDenied(
                f"{operation} is disabled by the QB-08 read-only MHS reference adapter"
            )
        try:
            tool = self._TOOLS[operation]
        except KeyError as exc:
            raise UnsupportedOperation(f"{self.interface}/{operation} is unsupported") from exc
        return self._invoke_tool(tool, ensure_dict(payload))
