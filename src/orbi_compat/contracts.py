"""Provider-neutral request/response envelopes for ORBI compatibility adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderInfo:
    family: str
    capability: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrbiRequest:
    interface: str
    operation: str
    request_id: str
    input: dict[str, Any] = field(default_factory=dict)
    confirm: bool = False

    def __post_init__(self) -> None:
        for name in ("interface", "operation", "request_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.input, dict):
            raise TypeError("input must be a dict")


@dataclass(frozen=True)
class OrbiError:
    code: str
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrbiResponse:
    ok: bool
    request_id: str
    interface: str
    operation: str
    provider: ProviderInfo
    data: Any
    provenance: dict[str, Any]
    policy: dict[str, Any]
    error: OrbiError | None = None
    audit: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {
            "ok": self.ok,
            "request_id": self.request_id,
            "interface": self.interface,
            "operation": self.operation,
            "provider": self.provider.to_dict(),
            "data": self.data,
            "provenance": dict(self.provenance),
            "policy": dict(self.policy),
        }
        if self.error is not None:
            out["error"] = self.error.to_dict()
        if self.audit is not None:
            out["audit"] = dict(self.audit)
        return out
