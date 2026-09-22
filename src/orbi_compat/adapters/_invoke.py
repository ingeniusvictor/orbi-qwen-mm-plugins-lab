"""Helpers for injected Qwen tool invocation.

The adapter modules intentionally do not import qwen_mm_plugins_* packages. A provider bridge is
injected by the composition root, keeping Qwen-specific imports behind the adapter boundary.
"""

from __future__ import annotations

from typing import Any, Callable

ToolInvoker = Callable[[str, dict[str, Any]], Any]


def ensure_dict(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise TypeError("adapter payload must be a dict")
    return payload
