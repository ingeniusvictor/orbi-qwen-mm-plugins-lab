"""Live Qwen-MM-Plugins composition bridge for ORBI compatibility adapters (QB-09)."""

from .registry import QwenRegistryInvoker, normalize_content_blocks

__all__ = ["QwenRegistryInvoker", "normalize_content_blocks"]
