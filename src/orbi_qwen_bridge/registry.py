"""Dynamic bridge from ORBI adapters to real Qwen-MM-Plugins capability registries.

This package is intentionally separate from `orbi_compat`. Product-facing ORBI code depends on
`orbi_compat`; only the composition layer knows the provider package names.
"""

from __future__ import annotations

import base64
import importlib
from dataclasses import dataclass
from typing import Any


_CAPABILITY_PACKAGES = {
    "core": "qwen_mm_plugins_core",
    "mhs": "qwen_mm_plugins_mhs",
    "blender": "qwen_mm_plugins_blender",
}


def normalize_content_blocks(blocks: Any) -> list[dict[str, Any]]:
    """Normalize raw Qwen handler blocks into a stable ORBI-friendly content list."""
    if not isinstance(blocks, list):
        raise TypeError("Qwen tool handler must return a list of content blocks")

    normalized: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise TypeError(f"content block #{index} must be a dict")

        kind = block.get("type")
        if kind == "text":
            normalized.append(
                {
                    "kind": "text",
                    "text": str(block.get("text", "")),
                }
            )
            continue

        if kind == "image":
            data = block.get("data")
            if not isinstance(data, str):
                raise TypeError(f"image content block #{index} must contain base64 string data")
            # Validate provider output without decoding/re-encoding the payload.
            try:
                base64.b64decode(data, validate=True)
            except Exception as exc:
                raise ValueError(f"image content block #{index} contains invalid base64") from exc
            normalized.append(
                {
                    "kind": "image",
                    "mime_type": str(block.get("mimeType", "image/jpeg")),
                    "data_base64": data,
                }
            )
            continue

        normalized.append(
            {
                "kind": "provider-block",
                "provider_type": str(kind or "unknown"),
                "value": block,
            }
        )

    return normalized


@dataclass
class QwenRegistryInvoker:
    """Callable tool invoker backed by one real Qwen capability package registry."""

    capability: str

    def __post_init__(self) -> None:
        try:
            self.package_name = _CAPABILITY_PACKAGES[self.capability]
        except KeyError as exc:
            raise ValueError(f"unsupported Qwen capability: {self.capability}") from exc

        self.package = importlib.import_module(self.package_name)

        if not callable(getattr(self.package, "get_handler", None)):
            raise RuntimeError(f"{self.package_name} does not expose get_handler()")
        if not callable(getattr(self.package, "list_tools", None)):
            raise RuntimeError(f"{self.package_name} does not expose list_tools()")

    @property
    def version(self) -> str:
        return str(getattr(self.package, "__version__", "unknown"))

    def tool_names(self) -> tuple[str, ...]:
        return tuple(item["name"] for item in self.package.list_tools())

    def has_tool(self, name: str) -> bool:
        return name in self.tool_names()

    def __call__(self, tool: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        handler = self.package.get_handler(tool)
        if handler is None:
            raise LookupError(f"{self.package_name} has no tool named {tool!r}")
        if not isinstance(payload, dict):
            raise TypeError("Qwen tool payload must be a dict")

        raw = handler(payload)
        return normalize_content_blocks(raw)
