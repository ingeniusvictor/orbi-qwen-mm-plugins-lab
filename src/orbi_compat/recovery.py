"""Durable recovery and reconciliation primitives for uncertain R2 executions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

_ALLOWED_RESOLUTIONS = {"applied", "not_applied", "inconclusive"}


def normalize_reconciliation_input(
    *,
    resolution: str,
    evidence: dict[str, Any],
    actor: str,
) -> tuple[str, str, str, str]:
    if resolution not in _ALLOWED_RESOLUTIONS:
        raise ValueError(
            f"resolution must be one of: {', '.join(sorted(_ALLOWED_RESOLUTIONS))}"
        )
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor must be a non-empty string")
    if len(actor) > 128:
        raise ValueError("actor must be at most 128 characters")
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("evidence must be a non-empty dict")
    try:
        evidence_json = json.dumps(
            evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError("reconciliation evidence must be deterministic JSON data") from exc

    evidence_sha256 = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()
    return resolution, actor.strip(), evidence_json, evidence_sha256


@dataclass(frozen=True)
class ReconciliationRecord:
    schema: str
    reconciliation_sequence: int
    execution_sequence: int
    request_id: str
    request_fingerprint: str
    resolution: str
    actor: str
    evidence: dict[str, Any]
    evidence_sha256: str
    final: bool
    reservation_released: bool
    retry_semantics: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
