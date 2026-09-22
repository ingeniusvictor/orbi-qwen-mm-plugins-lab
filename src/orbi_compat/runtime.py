"""Provider-neutral ORBI compatibility runtime."""

from __future__ import annotations

from typing import Any

from .contracts import OrbiError, OrbiRequest, OrbiResponse, ProviderInfo
from .errors import UnsupportedOperation, normalize_exception
from .policy import PolicyEngine


class OrbiRuntime:
    def __init__(
        self,
        policy: PolicyEngine,
        adapters: list[Any],
        *,
        external_provider_enabled: bool = False,
        certified_adapters: set[str] | None = None,
        sandboxed_execution_enabled: bool = False,
    ):
        self.policy = policy
        self.adapters = {adapter.interface: adapter for adapter in adapters}
        self.external_provider_enabled = external_provider_enabled
        self.certified_adapters = set(certified_adapters or ())
        self.sandboxed_execution_enabled = sandboxed_execution_enabled

    def _adapter_for(self, interface: str):
        try:
            return self.adapters[interface]
        except KeyError as exc:
            raise UnsupportedOperation(f"no adapter registered for interface {interface}") from exc

    def execute(self, request: OrbiRequest) -> OrbiResponse:
        adapter = self._adapter_for(request.interface)
        provider: ProviderInfo = adapter.provider

        try:
            decision = self.policy.evaluate(
                request,
                external_provider_enabled=self.external_provider_enabled,
                certified_adapter=request.interface in self.certified_adapters,
                sandboxed_execution_enabled=self.sandboxed_execution_enabled,
            )
            data = adapter.invoke(request.operation, request.input)
            return OrbiResponse(
                ok=True,
                request_id=request.request_id,
                interface=request.interface,
                operation=request.operation,
                provider=provider,
                data=data,
                provenance={
                    "provider": provider.family,
                    "provider_version": provider.version,
                    "source_mode": "adapter",
                },
                policy=decision.to_dict(),
            )
        except Exception as exc:
            code, message, retryable = normalize_exception(exc)
            risk = "unknown"
            confirmation_required = False
            try:
                spec = self.policy.operation_spec(request.interface, request.operation)
                risk = spec["risk_class"]
                confirmation_required = bool(spec.get("confirmation_required", False))
            except Exception:
                pass

            return OrbiResponse(
                ok=False,
                request_id=request.request_id,
                interface=request.interface,
                operation=request.operation,
                provider=provider,
                data=None,
                provenance={
                    "provider": provider.family,
                    "provider_version": provider.version,
                    "source_mode": "adapter",
                },
                policy={
                    "risk_class": risk,
                    "decision": "deny" if code == "POLICY_DENIED" else "error",
                    "confirmation_required": confirmation_required,
                },
                error=OrbiError(code=code, message=message, retryable=retryable),
            )
