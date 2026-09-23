"""Offline validation for QB-19 Scene3D recovery handoff artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

EVIDENCE_TYPE = "orbi-scene3d-recovery-handoff"
MAX_HANDOFF_BYTES = 1_048_576
_ALLOWED_RESOLUTIONS = ("applied", "not_applied", "inconclusive")

_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "evidenceType",
    "capturedAt",
    "pendingExecutions",
    "reconciliationHistory",
    "requiresOperatorReview",
    "privacy",
    "authority",
}
_PENDING_KEYS = {
    "sequence",
    "requestId",
    "operation",
    "outcome",
    "providerCalled",
    "replayReserved",
}
_HISTORY_KEYS = {
    "sequence",
    "requestId",
    "resolution",
    "actor",
    "final",
    "reservationReleased",
}
_PRIVACY = {
    "providerMetadataIncluded": False,
    "requestFingerprintIncluded": False,
    "rawEvidenceIncluded": False,
    "localPathsIncluded": False,
}
_AUTHORITY = {
    "readOnly": True,
    "executionAuthorized": False,
    "retryAuthorized": False,
    "reconciliationAuthorized": False,
    "requestIdReleaseAuthorized": False,
    "productionCutoverAuthorized": False,
}


class RecoveryHandoffError(ValueError):
    code = "RECOVERY_HANDOFF_INVALID"


class RecoveryHandoffHashMismatch(RecoveryHandoffError):
    code = "RECOVERY_HANDOFF_HASH_MISMATCH"


class RecoveryHandoffTooLarge(RecoveryHandoffError):
    code = "RECOVERY_HANDOFF_TOO_LARGE"


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise RecoveryHandoffError(
            f"{label} fields do not match the certified schema"
        )


def _request_id(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise RecoveryHandoffError("requestId must be a non-empty string up to 256 characters")
    return value


def _strict_iso_utc(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RecoveryHandoffError("capturedAt must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RecoveryHandoffError("capturedAt must be an ISO-8601 UTC timestamp") from exc
    canonical = parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if canonical != value:
        raise RecoveryHandoffError("capturedAt must use canonical millisecond UTC form")
    return value


@dataclass(frozen=True)
class PendingExecution:
    sequence: int
    request_id: str
    operation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "request_id": self.request_id,
            "operation": self.operation,
            "state": "uncertain",
            "provider_called": None,
            "original_request_id_reusable": False,
            "requires_external_readback_evidence": True,
            "allowed_resolutions": list(_ALLOWED_RESOLUTIONS),
        }


@dataclass(frozen=True)
class HistoricalReconciliation:
    sequence: int
    request_id: str
    resolution: str
    actor: str
    final: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecoveryHandoff:
    captured_at: str
    pending: tuple[PendingExecution, ...]
    history: tuple[HistoricalReconciliation, ...]
    file_sha256: str

    def operator_plan(self) -> dict[str, Any]:
        return {
            "schema": "orbi.recovery-operator-plan/v1",
            "captured_at": self.captured_at,
            "file_sha256": self.file_sha256,
            "pending_count": len(self.pending),
            "history_count": len(self.history),
            "operator_review_required": bool(self.pending),
            "automatic_reconciliation": False,
            "automatic_retry": False,
            "execution_authorized": False,
            "request_id_release_authorized": False,
            "pending": [item.to_dict() for item in self.pending],
            "history": [item.to_dict() for item in self.history],
        }


def _sanitize_pending(items: Any) -> tuple[PendingExecution, ...]:
    if not isinstance(items, list):
        raise RecoveryHandoffError("pendingExecutions must be an array")

    sequences: set[int] = set()
    request_ids: set[str] = set()
    out: list[PendingExecution] = []

    for item in items:
        if not isinstance(item, dict):
            raise RecoveryHandoffError("pending execution must be an object")
        _exact_keys(item, _PENDING_KEYS, "pending execution")

        sequence = item["sequence"]
        request_id = _request_id(item["requestId"])

        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise RecoveryHandoffError("pending sequence must be a positive integer")
        if sequence in sequences or request_id in request_ids:
            raise RecoveryHandoffError("pending execution identity must be unique")
        if item["operation"] != "execute_recipe":
            raise RecoveryHandoffError("pending operation must be execute_recipe")
        if item["outcome"] != "pending":
            raise RecoveryHandoffError("pending outcome must be pending")
        if item["providerCalled"] is not None:
            raise RecoveryHandoffError("pending providerCalled must be null/unknown")
        if item["replayReserved"] is not True:
            raise RecoveryHandoffError("pending request id must remain replay-reserved")

        sequences.add(sequence)
        request_ids.add(request_id)
        out.append(PendingExecution(sequence, request_id, "execute_recipe"))

    return tuple(out)


def _sanitize_history(items: Any) -> tuple[HistoricalReconciliation, ...]:
    if not isinstance(items, list):
        raise RecoveryHandoffError("reconciliationHistory must be an array")

    sequences: set[int] = set()
    out: list[HistoricalReconciliation] = []

    for item in items:
        if not isinstance(item, dict):
            raise RecoveryHandoffError("reconciliation record must be an object")
        _exact_keys(item, _HISTORY_KEYS, "reconciliation record")

        sequence = item["sequence"]
        request_id = _request_id(item["requestId"])
        actor = item["actor"]

        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise RecoveryHandoffError("reconciliation sequence must be a positive integer")
        if sequence in sequences:
            raise RecoveryHandoffError("reconciliation sequence must be unique")
        if item["resolution"] not in _ALLOWED_RESOLUTIONS:
            raise RecoveryHandoffError("reconciliation resolution is invalid")
        if not isinstance(actor, str) or not actor or len(actor) > 128:
            raise RecoveryHandoffError("reconciliation actor is invalid")
        if not isinstance(item["final"], bool):
            raise RecoveryHandoffError("reconciliation final must be boolean")
        if item["reservationReleased"] is not False:
            raise RecoveryHandoffError("historical request id must remain reserved")

        sequences.add(sequence)
        out.append(
            HistoricalReconciliation(
                sequence=sequence,
                request_id=request_id,
                resolution=item["resolution"],
                actor=actor,
                final=item["final"],
            )
        )

    return tuple(out)


def validate_recovery_handoff(
    payload: Any,
    *,
    file_sha256: str,
) -> RecoveryHandoff:
    if not isinstance(payload, dict):
        raise RecoveryHandoffError("recovery handoff must be a JSON object")
    _exact_keys(payload, _TOP_LEVEL_KEYS, "recovery handoff")

    if payload["schemaVersion"] != 1:
        raise RecoveryHandoffError("unsupported recovery handoff schema version")
    if payload["evidenceType"] != EVIDENCE_TYPE:
        raise RecoveryHandoffError("unexpected recovery handoff evidence type")

    captured_at = _strict_iso_utc(payload["capturedAt"])
    pending = _sanitize_pending(payload["pendingExecutions"])
    history = _sanitize_history(payload["reconciliationHistory"])

    if payload["requiresOperatorReview"] is not bool(pending):
        raise RecoveryHandoffError("operator-review flag does not match pending state")
    if payload["privacy"] != _PRIVACY:
        raise RecoveryHandoffError("recovery handoff privacy claims are invalid")
    if payload["authority"] != _AUTHORITY:
        raise RecoveryHandoffError("recovery handoff authority claims are invalid")

    if (
        not isinstance(file_sha256, str)
        or len(file_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in file_sha256)
    ):
        raise RecoveryHandoffError("file SHA-256 is invalid")

    return RecoveryHandoff(
        captured_at=captured_at,
        pending=pending,
        history=history,
        file_sha256=file_sha256,
    )


def load_recovery_handoff(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> RecoveryHandoff:
    source = Path(path)
    data = source.read_bytes()

    if len(data) > MAX_HANDOFF_BYTES:
        raise RecoveryHandoffTooLarge(
            f"handoff exceeds {MAX_HANDOFF_BYTES} byte limit"
        )

    actual_sha256 = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None:
        expected = expected_sha256.strip().lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise RecoveryHandoffError("expected SHA-256 is invalid")
        if actual_sha256 != expected:
            raise RecoveryHandoffHashMismatch(
                "recovery handoff SHA-256 does not match expected value"
            )

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryHandoffError("recovery handoff must be valid UTF-8 JSON") from exc

    return validate_recovery_handoff(payload, file_sha256=actual_sha256)
