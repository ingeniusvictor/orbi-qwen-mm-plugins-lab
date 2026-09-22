"""Adapter protocol used by the provider-neutral ORBI runtime."""

from __future__ import annotations

from typing import Any, Protocol

from orbi_compat.contracts import ProviderInfo


class Adapter(Protocol):
    interface: str
    provider: ProviderInfo

    def invoke(self, operation: str, payload: dict[str, Any]) -> Any:
        ...
