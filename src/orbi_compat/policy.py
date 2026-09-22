"""Risk-aware policy evaluator backed by the QB-07 compatibility contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .contracts import OrbiRequest
from .errors import PolicyDenied, UnsupportedOperation


class RiskClass(str, Enum):
    R0_READ_LOCAL = "R0_READ_LOCAL"
    R1_TRANSFORM_LOCAL = "R1_TRANSFORM_LOCAL"
    R2_EXECUTE_SANDBOXED = "R2_EXECUTE_SANDBOXED"
    R3_ACTUATE_CONFIRMED = "R3_ACTUATE_CONFIRMED"
    R4_EXTERNAL_PROVIDER = "R4_EXTERNAL_PROVIDER"


@dataclass(frozen=True)
class PolicyDecision:
    risk_class: RiskClass
    decision: str
    confirmation_required: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_class": self.risk_class.value,
            "decision": self.decision,
            "confirmation_required": self.confirmation_required,
            "reason": self.reason,
        }


class PolicyEngine:
    def __init__(self, contract: dict[str, Any]):
        self.contract = contract
        self._operations: dict[tuple[str, str], dict[str, Any]] = {}
        for adapter in contract.get("adapters", []):
            interface = adapter["interface"]
            for operation in adapter.get("operations", []):
                self._operations[(interface, operation["name"])] = operation

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def operation_spec(self, interface: str, operation: str) -> dict[str, Any]:
        try:
            return self._operations[(interface, operation)]
        except KeyError as exc:
            raise UnsupportedOperation(
                f"operation {interface}/{operation} is not present in the ORBI contract"
            ) from exc

    def evaluate(
        self,
        request: OrbiRequest,
        *,
        external_provider_enabled: bool = False,
        certified_adapter: bool = False,
    ) -> PolicyDecision:
        spec = self.operation_spec(request.interface, request.operation)
        risk = RiskClass(spec["risk_class"])
        confirmation_required = bool(spec.get("confirmation_required", False))

        if risk is RiskClass.R3_ACTUATE_CONFIRMED:
            if not certified_adapter:
                raise PolicyDenied(
                    f"{request.interface}/{request.operation} requires a certified hardware adapter"
                )
            if confirmation_required and not request.confirm:
                raise PolicyDenied(
                    f"{request.interface}/{request.operation} requires explicit confirmation"
                )

        if risk is RiskClass.R4_EXTERNAL_PROVIDER:
            if spec.get("default_enabled") is False and not external_provider_enabled:
                raise PolicyDenied(
                    f"{request.interface}/{request.operation} external provider is disabled by default"
                )

        return PolicyDecision(
            risk_class=risk,
            decision="allow",
            confirmation_required=confirmation_required,
        )
