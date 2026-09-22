"""Deterministic execution audit and replay protection for governed ORBI operations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import OrbiRequest, ProviderInfo
from .errors import ReplayDenied, RequestIdConflict


def request_fingerprint(request: OrbiRequest) -> str:
    """Stable SHA-256 identity for a provider-neutral ORBI request payload."""
    payload = {
        "interface": request.interface,
        "operation": request.operation,
        "input": request.input,
        "confirm": request.confirm,
    }
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypeError("R2 request input must be deterministic JSON data") from exc
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ExecutionToken:
    sequence: int
    request_id: str
    request_fingerprint: str
    interface: str
    operation: str
    risk_class: str
    replay_reserved: bool


@dataclass(frozen=True)
class ExecutionReceipt:
    schema: str
    sequence: int
    request_id: str
    request_fingerprint: str
    interface: str
    operation: str
    risk_class: str
    outcome: str
    provider_called: bool
    provider: dict[str, str]
    replay_reserved: bool
    retry_semantics: str
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReplayLedger:
    """In-runtime replay guard for R2 execution.

    Real execution reserves request_id *before* the provider call. This is intentionally
    conservative: if the provider fails or times out, automatic retry with the same request_id
    remains denied because the external side effect may have occurred.
    """

    def __init__(self) -> None:
        self._sequence = 0
        self._reserved: dict[str, str] = {}
        self._receipts: list[ExecutionReceipt] = []

    def begin(self, request: OrbiRequest, risk_class: str, *, dry_run: bool) -> ExecutionToken:
        fingerprint = request_fingerprint(request)
        self._sequence += 1

        if not dry_run:
            previous = self._reserved.get(request.request_id)
            if previous is not None:
                if previous == fingerprint:
                    raise ReplayDenied(
                        f"request_id {request.request_id!r} already reserved for this R2 execution"
                    )
                raise RequestIdConflict(
                    f"request_id {request.request_id!r} was already used for a different R2 payload"
                )
            self._reserved[request.request_id] = fingerprint

        return ExecutionToken(
            sequence=self._sequence,
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            interface=request.interface,
            operation=request.operation,
            risk_class=risk_class,
            replay_reserved=not dry_run,
        )

    def finalize(
        self,
        token: ExecutionToken,
        provider: ProviderInfo,
        *,
        outcome: str,
        provider_called: bool,
        error_code: str | None = None,
    ) -> ExecutionReceipt:
        receipt = ExecutionReceipt(
            schema="orbi.execution-audit/v1",
            sequence=token.sequence,
            request_id=token.request_id,
            request_fingerprint=token.request_fingerprint,
            interface=token.interface,
            operation=token.operation,
            risk_class=token.risk_class,
            outcome=outcome,
            provider_called=provider_called,
            provider=provider.to_dict(),
            replay_reserved=token.replay_reserved,
            retry_semantics=(
                "new-request-id-required-after-execution-attempt"
                if token.replay_reserved
                else "dry-run-repeatable"
            ),
            error_code=error_code,
        )
        self._receipts.append(receipt)
        return receipt

    def record_denial(
        self,
        request: OrbiRequest,
        provider: ProviderInfo,
        risk_class: str,
        *,
        error_code: str,
    ) -> ExecutionReceipt:
        self._sequence += 1
        receipt = ExecutionReceipt(
            schema="orbi.execution-audit/v1",
            sequence=self._sequence,
            request_id=request.request_id,
            request_fingerprint=request_fingerprint(request),
            interface=request.interface,
            operation=request.operation,
            risk_class=risk_class,
            outcome="replay-denied",
            provider_called=False,
            provider=provider.to_dict(),
            replay_reserved=False,
            retry_semantics="new-request-id-required",
            error_code=error_code,
        )
        self._receipts.append(receipt)
        return receipt

    def receipts(self) -> tuple[ExecutionReceipt, ...]:
        return tuple(self._receipts)

    def is_reserved(self, request_id: str) -> bool:
        return request_id in self._reserved
