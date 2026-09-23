from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from orbi_compat import OrbiRequest, SQLiteReplayLedger

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/orbi/qb13_recovery_tool.py"
RISK = "R2_EXECUTE_SANDBOXED"


def load_tool():
    spec = importlib.util.spec_from_file_location("qb13_recovery_tool", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def pending_request(request_id="qb13-cli-pending"):
    return OrbiRequest(
        interface="orbi.scene3d.v1",
        operation="execute_recipe",
        request_id=request_id,
        input={
            "recipe_id": "orbi.blender.create_cube.v1",
            "parameters": {
                "name": "ORBI_QB13_CLI",
                "size": 1.0,
                "location": [0.0, 0.0, 0.0],
            },
        },
    )


def make_pending(db: Path, request_id="qb13-cli-pending"):
    ledger = SQLiteReplayLedger(db)
    ledger.begin(pending_request(request_id), RISK, dry_run=False)
    return ledger


def subcommand_names(parser: argparse.ArgumentParser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("subparser action not found")


def test_operator_tool_exposes_only_evidence_operations():
    tool = load_tool()
    parser = tool.build_parser()

    assert subcommand_names(parser) == {
        "pending",
        "reconciliations",
        "reconcile",
    }

    help_text = parser.format_help().lower()
    assert "retry" not in help_text
    assert "release" not in help_text
    assert "execute" not in help_text


def test_pending_command_outputs_pending_receipts(tmp_path, capsys):
    tool = load_tool()
    db = tmp_path / "ledger.sqlite3"
    make_pending(db)

    rc = tool.main(["--db", str(db), "pending"])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert len(out) == 1
    assert out[0]["request_id"] == "qb13-cli-pending"
    assert out[0]["outcome"] == "pending"
    assert out[0]["provider_called"] is None


def test_reconcile_with_inline_json_and_history_filter(tmp_path, capsys):
    tool = load_tool()
    db = tmp_path / "ledger.sqlite3"
    make_pending(db, "inline-id")

    rc = tool.main(
        [
            "--db",
            str(db),
            "reconcile",
            "--request-id",
            "inline-id",
            "--resolution",
            "applied",
            "--actor",
            "operator-inline",
            "--evidence-json",
            '{"source":"readback","exists":true}',
        ]
    )
    reconcile_out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert reconcile_out["request_id"] == "inline-id"
    assert reconcile_out["resolution"] == "applied"
    assert reconcile_out["final"] is True
    assert reconcile_out["reservation_released"] is False

    rc = tool.main(
        [
            "--db",
            str(db),
            "reconciliations",
            "--request-id",
            "inline-id",
        ]
    )
    history = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert len(history) == 1
    assert history[0]["actor"] == "operator-inline"
    assert history[0]["evidence"]["exists"] is True


def test_reconcile_accepts_evidence_file(tmp_path, capsys):
    tool = load_tool()
    db = tmp_path / "ledger.sqlite3"
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text(
        json.dumps(
            {
                "source": "blender-object-info",
                "object": "ORBI_QB13_CLI",
                "exists": False,
            }
        ),
        encoding="utf-8",
    )
    make_pending(db, "file-id")

    rc = tool.main(
        [
            "--db",
            str(db),
            "reconcile",
            "--request-id",
            "file-id",
            "--resolution",
            "not_applied",
            "--actor",
            "operator-file",
            "--evidence-file",
            str(evidence_file),
        ]
    )
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["resolution"] == "not_applied"
    assert out["evidence"]["exists"] is False
    assert SQLiteReplayLedger(db).is_reserved("file-id") is True


def test_missing_pending_returns_structured_nonzero_error(tmp_path, capsys):
    tool = load_tool()
    db = tmp_path / "ledger.sqlite3"

    rc = tool.main(
        [
            "--db",
            str(db),
            "reconcile",
            "--request-id",
            "missing-id",
            "--resolution",
            "applied",
            "--actor",
            "operator",
            "--evidence-json",
            '{"source":"readback","exists":true}',
        ]
    )
    captured = capsys.readouterr()
    err = json.loads(captured.err)

    assert rc == 2
    assert captured.out == ""
    assert err["ok"] is False
    assert err["error"]["code"] == "PENDING_EXECUTION_NOT_FOUND"


def test_non_object_evidence_returns_structured_error(tmp_path, capsys):
    tool = load_tool()
    db = tmp_path / "ledger.sqlite3"
    make_pending(db, "bad-evidence")

    rc = tool.main(
        [
            "--db",
            str(db),
            "reconcile",
            "--request-id",
            "bad-evidence",
            "--resolution",
            "applied",
            "--actor",
            "operator",
            "--evidence-json",
            '["not","an","object"]',
        ]
    )
    captured = capsys.readouterr()
    err = json.loads(captured.err)

    assert rc == 2
    assert err["ok"] is False
    assert "evidence" in err["error"]["message"].lower()
    assert SQLiteReplayLedger(db).pending_receipts()[0].outcome == "pending"
