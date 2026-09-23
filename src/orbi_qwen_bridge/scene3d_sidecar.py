"""Provider-neutral local stdio sidecar for ORBI Scene3D pilot integration."""

from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Callable

from orbi_compat import OrbiRequest, SQLiteReplayLedger

PROTOCOL = "orbi.scene3d-sidecar/v1"
MAX_MESSAGE_BYTES = 262_144

_ALLOWED_OPERATIONS = {
    "status",
    "scene_info",
    "object_info",
    "dry_run_recipe",
    "execute_recipe",
    "pending_recoveries",
    "reconciliation_history",
}

_EXECUTION_OPERATIONS = {"dry_run_recipe", "execute_recipe"}


class SidecarProtocolError(ValueError):
    code = "SIDECAR_PROTOCOL_ERROR"


class SidecarMessageTooLarge(SidecarProtocolError):
    code = "SIDECAR_MESSAGE_TOO_LARGE"


def allowed_operations() -> tuple[str, ...]:
    return tuple(sorted(_ALLOWED_OPERATIONS))


def _non_empty_string(value: Any, field: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SidecarProtocolError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise SidecarProtocolError(f"{field} must be at most {max_length} characters")
    return value


def decode_message(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        data = raw
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SidecarProtocolError("message must be UTF-8") from exc
    elif isinstance(raw, str):
        text = raw
        data = raw.encode("utf-8")
    else:
        raise TypeError("raw message must be str or bytes")

    if len(data) > MAX_MESSAGE_BYTES:
        raise SidecarMessageTooLarge(
            f"message exceeds {MAX_MESSAGE_BYTES} byte limit"
        )

    try:
        message = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SidecarProtocolError("message must be valid JSON") from exc

    if not isinstance(message, dict):
        raise SidecarProtocolError("message must decode to a JSON object")
    return message


def encode_message(message: dict[str, Any]) -> str:
    return json.dumps(
        message,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


class Scene3DPilotSidecar:
    """Process one provider-neutral Scene3D transport request at a time.

    Runtime creation is lazy so read-only ledger recovery inspection remains available even if
    Blender/provider startup is temporarily unavailable.
    """

    def __init__(
        self,
        *,
        ledger: SQLiteReplayLedger,
        runtime_factory: Callable[[], Any],
    ):
        self.ledger = ledger
        self._runtime_factory = runtime_factory
        self._runtime = None

    def _runtime_instance(self):
        if self._runtime is None:
            # stdout is reserved exclusively for JSONL protocol frames.
            # Any provider/runtime diagnostic print is redirected to stderr.
            with redirect_stdout(sys.stderr):
                self._runtime = self._runtime_factory()
        return self._runtime

    @staticmethod
    def _base_response(transport_id: str) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL,
            "id": transport_id,
        }

    def _validate(self, message: dict[str, Any]) -> tuple[str, str, str | None, dict[str, Any]]:
        if message.get("protocol") != PROTOCOL:
            raise SidecarProtocolError(f"protocol must be {PROTOCOL}")

        transport_id = _non_empty_string(message.get("id"), "id", max_length=128)
        operation = _non_empty_string(
            message.get("operation"), "operation", max_length=64
        )
        if operation not in _ALLOWED_OPERATIONS:
            raise SidecarProtocolError(f"unsupported sidecar operation: {operation}")

        payload = message.get("input", {})
        if not isinstance(payload, dict):
            raise SidecarProtocolError("input must be a JSON object")

        request_id = message.get("request_id")
        if operation not in {"status", "pending_recoveries", "reconciliation_history"}:
            request_id = _non_empty_string(
                request_id, "request_id", max_length=256
            )
        elif request_id is not None:
            request_id = _non_empty_string(
                request_id, "request_id", max_length=256
            )

        return transport_id, operation, request_id, payload

    def process(self, message: dict[str, Any]) -> dict[str, Any]:
        transport_id = str(message.get("id", ""))
        try:
            transport_id, operation, request_id, payload = self._validate(message)
            base = self._base_response(transport_id)

            if operation == "status":
                if payload:
                    raise SidecarProtocolError("status input must be empty")
                return {
                    **base,
                    "ok": True,
                    "result": {
                        "protocol": PROTOCOL,
                        "operations": list(allowed_operations()),
                        "transport": "stdio-jsonl",
                        "public_listener": False,
                        "automatic_r2_retry": False,
                        "reconciliation_mutation": False,
                        "ledger_schema": self.ledger.schema(),
                        "reconciliation_schema": self.ledger.reconciliation_schema(),
                    },
                }

            if operation == "pending_recoveries":
                if payload:
                    raise SidecarProtocolError("pending_recoveries input must be empty")
                return {
                    **base,
                    "ok": True,
                    "result": [item.to_dict() for item in self.ledger.pending_receipts()],
                }

            if operation == "reconciliation_history":
                unknown = set(payload) - {"request_id"}
                if unknown:
                    raise SidecarProtocolError(
                        f"unexpected reconciliation_history field(s): {', '.join(sorted(unknown))}"
                    )
                history_request_id = payload.get("request_id")
                if history_request_id is not None:
                    history_request_id = _non_empty_string(
                        history_request_id, "input.request_id", max_length=256
                    )
                return {
                    **base,
                    "ok": True,
                    "result": [
                        item.to_dict()
                        for item in self.ledger.reconciliations(history_request_id)
                    ],
                }

            runtime = self._runtime_instance()

            if operation == "scene_info":
                if payload:
                    raise SidecarProtocolError("scene_info input must be empty")
                request = OrbiRequest(
                    interface="orbi.scene3d.v1",
                    operation="scene_info",
                    request_id=request_id,
                    input={},
                )
            elif operation == "object_info":
                unknown = set(payload) - {"object_name"}
                if unknown:
                    raise SidecarProtocolError(
                        f"unexpected object_info field(s): {', '.join(sorted(unknown))}"
                    )
                object_name = _non_empty_string(
                    payload.get("object_name"), "input.object_name", max_length=128
                )
                request = OrbiRequest(
                    interface="orbi.scene3d.v1",
                    operation="object_info",
                    request_id=request_id,
                    input={"object_name": object_name},
                )
            elif operation in _EXECUTION_OPERATIONS:
                unknown = set(payload) - {"recipe_id", "parameters"}
                if unknown:
                    raise SidecarProtocolError(
                        f"unexpected {operation} field(s): {', '.join(sorted(unknown))}"
                    )
                recipe_id = _non_empty_string(
                    payload.get("recipe_id"), "input.recipe_id", max_length=128
                )
                parameters = payload.get("parameters", {})
                if not isinstance(parameters, dict):
                    raise SidecarProtocolError("input.parameters must be a JSON object")
                recipe_payload = {
                    "recipe_id": recipe_id,
                    "parameters": parameters,
                }
                if operation == "dry_run_recipe":
                    recipe_payload["dry_run"] = True
                request = OrbiRequest(
                    interface="orbi.scene3d.v1",
                    operation="execute_recipe",
                    request_id=request_id,
                    input=recipe_payload,
                )
            else:
                raise SidecarProtocolError(f"operation not implemented: {operation}")

            # stdout is reserved exclusively for JSONL protocol frames.
            with redirect_stdout(sys.stderr):
                response = runtime.execute(request)
            return {
                **base,
                "ok": True,
                "result": response.to_dict(),
            }
        except Exception as exc:
            return {
                "protocol": PROTOCOL,
                "id": transport_id,
                "ok": False,
                "error": {
                    "code": getattr(exc, "code", "SIDECAR_INTERNAL_ERROR"),
                    "message": str(exc),
                },
            }


def build_live_sidecar(
    *,
    contract_path: str | Path,
    ledger_path: str | Path,
) -> Scene3DPilotSidecar:
    """Build the real local Qwen/Blender-backed Scene3D sidecar."""
    from orbi_qwen_bridge.factory import build_governed_blender_runtime

    ledger = SQLiteReplayLedger(ledger_path)
    return Scene3DPilotSidecar(
        ledger=ledger,
        runtime_factory=lambda: build_governed_blender_runtime(
            contract_path,
            durable_ledger_path=ledger_path,
        ),
    )
