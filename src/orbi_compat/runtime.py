"""Provider-neutral ORBI compatibility runtime."""

from __future__ import annotations

from typing import Any

from .audit import ExecutionToken, ReplayLedger
from .contracts import OrbiError, OrbiRequest, OrbiResponse, ProviderInfo
from .errors import UnsupportedOperation, normalize_exception
from .policy import PolicyEngine, RiskClass


class OrbiRuntime:
    def __init__(
        self,
        policy: PolicyEngine,
        adapters: list[Any],
        *,
        external_provider_enabled: bool = False,
        certified_adapters: set[str] | None = None,
        sandboxed_execution_enabled: bool = False,
        replay_ledger: ReplayLedger | None = None,
    ):
        self.policy = policy
        self.adapters = {adapter.interface: adapter for adapter in adapters}
        self.external_provider_enabled = external_provider_enabled
        self.certified_adapters = set(certified_adapters or ())
        self.sandboxed_execution_enabled = sandboxed_execution_enabled
        self.replay_ledger = (
            replay_ledger
            if replay_ledger is not None
            else (ReplayLedger() if sandboxed_execution_enabled else None)
        )

    def _adapter_for(self, interface: str):
        try:
            return self.adapters[interface]
        except KeyError as exc:
            raise UnsupportedOperation(f"no adapter registered for interface {interface}") from exc

    @staticmethod
    def _provider_called_from_data(data: Any, *, default: bool) -> bool:
        if isinstance(data, dict):
            audit = data.get("audit")
            if isinstance(audit, dict) and isinstance(audit.get("provider_called"), bool):
                return audit["provider_called"]
        return default

    def execute(self, request: OrbiRequest) -> OrbiResponse:
        adapter = self._adapter_for(request.interface)
        provider: ProviderInfo = adapter.provider
        token: ExecutionToken | None = None
        risk = "unknown"
        confirmation_required = False
        dry_run = False

        try:
            decision = self.policy.evaluate(
                request,
                external_provider_enabled=self.external_provider_enabled,
                certified_adapter=request.interface in self.certified_adapters,
                sandboxed_execution_enabled=self.sandboxed_execution_enabled,
            )
            risk = decision.risk_class.value
            confirmation_required = decision.confirmation_required

            if decision.risk_class is RiskClass.R2_EXECUTE_SANDBOXED:
                if self.replay_ledger is None:
                    raise RuntimeError("R2 execution requires replay protection")
                dry_run = request.input.get("dry_run") is True
                token = self.replay_ledger.begin(
                    request,
                    decision.risk_class.value,
                    dry_run=dry_run,
                )

            data = adapter.invoke(request.operation, request.input)

            audit = None
            if token is not None and self.replay_ledger is not None:
                provider_called = self._provider_called_from_data(
                    data,
                    default=not dry_run,
                )
                receipt = self.replay_ledger.finalize(
                    token,
                    provider,
                    outcome="dry-run" if dry_run else "executed",
                    provider_called=provider_called,
                )
                audit = receipt.to_dict()

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
                audit=audit,
            )
        except Exception as exc:
            code, message, retryable = normalize_exception(exc)

            if risk == "unknown":
                try:
                    spec = self.policy.operation_spec(request.interface, request.operation)
                    risk = spec["risk_class"]
                    confirmation_required = bool(spec.get("confirmation_required", False))
                except Exception:
                    pass

            audit = None
            if self.replay_ledger is not None and risk == RiskClass.R2_EXECUTE_SANDBOXED.value:
                if token is not None:
                    provider_called = False if code == "POLICY_DENIED" or dry_run else True
                    receipt = self.replay_ledger.finalize(
                        token,
                        provider,
                        outcome="denied" if code == "POLICY_DENIED" else "provider-error",
                        provider_called=provider_called,
                        error_code=code,
                    )
                    audit = receipt.to_dict()
                elif code in {"REPLAY_DENIED", "REQUEST_ID_CONFLICT"}:
                    audit = self.replay_ledger.record_denial(
                        request,
                        provider,
                        risk,
                        error_code=code,
                    ).to_dict()

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
                    "decision": "deny" if code in {
                        "POLICY_DENIED",
                        "REPLAY_DENIED",
                        "REQUEST_ID_CONFLICT",
                    } else "error",
                    "confirmation_required": confirmation_required,
                },
                error=OrbiError(code=code, message=message, retryable=retryable),
                audit=audit,
            )
