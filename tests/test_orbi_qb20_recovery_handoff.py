from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from orbi_compat.recovery_handoff import (
    MAX_HANDOFF_BYTES,
    RecoveryHandoffError,
    RecoveryHandoffHashMismatch,
    RecoveryHandoffTooLarge,
    load_recovery_handoff,
    validate_recovery_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/orbi/qb20_validate_recovery_handoff.py"


def valid_payload(**overrides):
    payload = {
        "schemaVersion": 1,
        "evidenceType": "orbi-scene3d-recovery-handoff",
        "capturedAt": "2026-09-23T05:10:00.000Z",
        "pendingExecutions": [
            {
                "sequence": 5,
                "requestId": "pending-request-1",
                "operation": "execute_recipe",
                "outcome": "pending",
                "providerCalled": None,
                "replayReserved": True,
            }
        ],
        "reconciliationHistory": [
            {
                "sequence": 2,
                "requestId": "historical-request-1",
                "resolution": "inconclusive",
                "actor": "operator",
                "final": False,
                "reservationReleased": False,
            }
        ],
        "requiresOperatorReview": True,
        "privacy": {
            "providerMetadataIncluded": False,
            "requestFingerprintIncluded": False,
            "rawEvidenceIncluded": False,
            "localPathsIncluded": False,
        },
        "authority": {
            "readOnly": True,
            "executionAuthorized": False,
            "retryAuthorized": False,
            "reconciliationAuthorized": False,
            "requestIdReleaseAuthorized": False,
            "productionCutoverAuthorized": False,
        },
    }
    payload.update(overrides)
    return payload


def serialize(payload):
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_handoff(tmp_path: Path, payload=None):
    data = serialize(payload or valid_payload())
    path = tmp_path / "recovery.json"
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def load_cli():
    spec = importlib.util.spec_from_file_location("qb20_validate_recovery_handoff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_qb20_valid_handoff_builds_non_executing_operator_plan():
    handoff = validate_recovery_handoff(
        valid_payload(),
        file_sha256="a" * 64,
    )
    plan = handoff.operator_plan()

    assert plan["schema"] == "orbi.recovery-operator-plan/v1"
    assert plan["pending_count"] == 1
    assert plan["history_count"] == 1
    assert plan["operator_review_required"] is True
    assert plan["automatic_reconciliation"] is False
    assert plan["automatic_retry"] is False
    assert plan["execution_authorized"] is False
    assert plan["request_id_release_authorized"] is False

    pending = plan["pending"][0]
    assert pending["request_id"] == "pending-request-1"
    assert pending["state"] == "uncertain"
    assert pending["provider_called"] is None
    assert pending["original_request_id_reusable"] is False
    assert pending["requires_external_readback_evidence"] is True
    assert pending["allowed_resolutions"] == [
        "applied",
        "not_applied",
        "inconclusive",
    ]


def test_qb20_plan_contains_no_shell_command_or_database_mutation():
    plan = validate_recovery_handoff(
        valid_payload(),
        file_sha256="a" * 64,
    ).operator_plan()

    serialized = json.dumps(plan)
    for forbidden in [
        "subprocess",
        "shell",
        "--db",
        "sqlite",
        "execute_blender_code",
        "qwen",
        "retryExecution",
        "reconcile_pending(",
    ]:
        assert forbidden not in serialized


def test_qb20_load_verifies_exact_export_sha256(tmp_path):
    path, sha256 = write_handoff(tmp_path)

    handoff = load_recovery_handoff(path, expected_sha256=sha256)

    assert handoff.file_sha256 == sha256
    assert handoff.captured_at == "2026-09-23T05:10:00.000Z"


def test_qb20_hash_mismatch_is_explicit(tmp_path):
    path, _ = write_handoff(tmp_path)

    with pytest.raises(RecoveryHandoffHashMismatch):
        load_recovery_handoff(path, expected_sha256="0" * 64)


def test_qb20_rejects_noncanonical_or_nonhex_hash():
    with pytest.raises(RecoveryHandoffError):
        validate_recovery_handoff(valid_payload(), file_sha256="g" * 64)

    with pytest.raises(RecoveryHandoffError):
        validate_recovery_handoff(valid_payload(), file_sha256="a" * 63)


def test_qb20_requires_exact_top_level_schema():
    forged = valid_payload()
    forged["provider"] = "qwen"

    with pytest.raises(RecoveryHandoffError, match="certified schema"):
        validate_recovery_handoff(forged, file_sha256="a" * 64)


def test_qb20_rejects_privacy_or_authority_escalation():
    privacy = valid_payload()
    privacy["privacy"] = {
        **privacy["privacy"],
        "rawEvidenceIncluded": True,
    }
    with pytest.raises(RecoveryHandoffError, match="privacy"):
        validate_recovery_handoff(privacy, file_sha256="a" * 64)

    authority = valid_payload()
    authority["authority"] = {
        **authority["authority"],
        "reconciliationAuthorized": True,
    }
    with pytest.raises(RecoveryHandoffError, match="authority"):
        validate_recovery_handoff(authority, file_sha256="a" * 64)


def test_qb20_rejects_invalid_pending_semantics_and_duplicates():
    for pending in [
        [
            {
                "sequence": 1,
                "requestId": "id-1",
                "operation": "execute_recipe",
                "outcome": "executed",
                "providerCalled": None,
                "replayReserved": True,
            }
        ],
        [
            {
                "sequence": 1,
                "requestId": "id-1",
                "operation": "execute_recipe",
                "outcome": "pending",
                "providerCalled": True,
                "replayReserved": True,
            }
        ],
        [
            {
                "sequence": 1,
                "requestId": "id-1",
                "operation": "scene_info",
                "outcome": "pending",
                "providerCalled": None,
                "replayReserved": True,
            }
        ],
        [
            {
                "sequence": 1,
                "requestId": "id-1",
                "operation": "execute_recipe",
                "outcome": "pending",
                "providerCalled": None,
                "replayReserved": True,
            },
            {
                "sequence": 2,
                "requestId": "id-1",
                "operation": "execute_recipe",
                "outcome": "pending",
                "providerCalled": None,
                "replayReserved": True,
            },
        ],
    ]:
        payload = valid_payload(pendingExecutions=pending)
        with pytest.raises(RecoveryHandoffError):
            validate_recovery_handoff(payload, file_sha256="a" * 64)


def test_qb20_rejects_invalid_reconciliation_semantics():
    base = valid_payload()["reconciliationHistory"][0]

    for history in [
        [{**base, "resolution": "retry"}],
        [{**base, "reservationReleased": True}],
        [{**base, "actor": ""}],
        [base, {**base, "requestId": "another"}],
    ]:
        payload = valid_payload(reconciliationHistory=history)
        with pytest.raises(RecoveryHandoffError):
            validate_recovery_handoff(payload, file_sha256="a" * 64)


def test_qb20_requires_operator_review_flag_to_match_pending_state():
    with pytest.raises(RecoveryHandoffError, match="operator-review"):
        validate_recovery_handoff(
            valid_payload(requiresOperatorReview=False),
            file_sha256="a" * 64,
        )

    empty = valid_payload(
        pendingExecutions=[],
        requiresOperatorReview=False,
    )
    handoff = validate_recovery_handoff(empty, file_sha256="a" * 64)
    assert handoff.operator_plan()["operator_review_required"] is False


def test_qb20_rejects_noncanonical_capture_timestamp():
    with pytest.raises(RecoveryHandoffError, match="capturedAt"):
        validate_recovery_handoff(
            valid_payload(capturedAt="2026-09-23T05:10:00Z"),
            file_sha256="a" * 64,
        )


def test_qb20_enforces_one_mebibyte_file_bound(tmp_path):
    path = tmp_path / "too-large.json"
    path.write_bytes(b"x" * (MAX_HANDOFF_BYTES + 1))

    with pytest.raises(RecoveryHandoffTooLarge):
        load_recovery_handoff(path)


def test_qb20_cli_returns_structured_plan_without_executing_any_action(tmp_path, capsys):
    cli = load_cli()
    path, sha256 = write_handoff(tmp_path)

    rc = cli.main(["--file", str(path), "--sha256", sha256])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert output["ok"] is True
    assert output["evidence_type"] == "orbi-scene3d-recovery-handoff"
    assert output["operator_plan"]["automatic_retry"] is False
    assert output["operator_plan"]["automatic_reconciliation"] is False
    assert output["operator_plan"]["execution_authorized"] is False


def test_qb20_cli_hash_failure_is_structured_and_nonzero(tmp_path, capsys):
    cli = load_cli()
    path, _ = write_handoff(tmp_path)

    rc = cli.main(["--file", str(path), "--sha256", "0" * 64])
    captured = capsys.readouterr()
    error = json.loads(captured.err)

    assert rc == 2
    assert captured.out == ""
    assert error["ok"] is False
    assert error["error"]["code"] == "RECOVERY_HANDOFF_HASH_MISMATCH"


def test_qb20_cli_surface_has_no_db_resolution_or_execution_arguments():
    source = SCRIPT.read_text(encoding="utf-8")

    for forbidden in [
        "--db",
        "--resolution",
        "--actor",
        "subprocess",
        "execute_recipe",
        "reconcile_pending",
        "SQLiteReplayLedger",
        "QwenRegistryInvoker",
    ]:
        assert forbidden not in source
