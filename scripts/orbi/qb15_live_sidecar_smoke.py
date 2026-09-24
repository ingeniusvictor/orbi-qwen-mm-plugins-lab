#!/usr/bin/env python3
"""QB-15 live process-level Scene3D sidecar smoke."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = ROOT / "scripts/orbi/qb15_scene3d_sidecar.py"
NAME = "ORBI_QB15_Cube"
PROTOCOL = "orbi.scene3d-sidecar/v1"


def send(proc, operation, *, input=None, request_id=None):
    transport_id = str(uuid.uuid4())
    message = {
        "protocol": PROTOCOL,
        "id": transport_id,
        "operation": operation,
        "input": {} if input is None else input,
    }
    if request_id is not None:
        message["request_id"] = request_id

    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()

    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read()
        raise RuntimeError(f"sidecar closed unexpectedly: {stderr}")
    response = json.loads(line)
    assert response["id"] == transport_id
    return response


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="qb15-sidecar-") as td:
        ledger = Path(td) / "scene3d.sqlite3"
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SIDECAR),
                "--ledger",
                str(ledger),
            ],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        created = False
        try:
            print("=== QB-15 SIDECAR STATUS ===")
            status = send(proc, "status")
            print(status)
            assert status["ok"] is True
            assert status["result"]["transport"] == "stdio-jsonl"
            assert status["result"]["public_listener"] is False
            assert status["result"]["automatic_r2_retry"] is False

            print("\n=== QB-15 PREEXISTING OBJECT GUARD ===")
            pre = send(
                proc,
                "object_info",
                request_id=str(uuid.uuid4()),
                input={"object_name": NAME},
            )
            print(pre)
            assert pre["ok"] is True
            assert pre["result"]["ok"] is False
            assert "Object not found" in pre["result"]["error"]["message"]

            recipe = {
                "recipe_id": "orbi.blender.create_cube.v1",
                "parameters": {
                    "name": NAME,
                    "size": 1.0,
                    "location": [6.0, 0.0, 0.5],
                },
            }

            print("\n=== QB-15 PROCESS DRY RUN ===")
            dry = send(
                proc,
                "dry_run_recipe",
                request_id=str(uuid.uuid4()),
                input=recipe,
            )
            print(dry)
            assert dry["ok"] is True
            assert dry["result"]["ok"] is True
            assert dry["result"]["data"]["execution"] == "dry-run"
            assert dry["result"]["audit"]["provider_called"] is False

            print("\n=== QB-15 PROCESS GOVERNED CREATE ===")
            create_id = str(uuid.uuid4())
            create = send(
                proc,
                "execute_recipe",
                request_id=create_id,
                input=recipe,
            )
            print(create)
            assert create["ok"] is True
            assert create["result"]["ok"] is True
            assert create["result"]["request_id"] == create_id
            assert create["result"]["data"]["execution"] == "executed"
            assert create["result"]["audit"]["provider_called"] is True
            created = True

            print("\n=== QB-15 PROCESS OBJECT READ ===")
            obj = send(
                proc,
                "object_info",
                request_id=str(uuid.uuid4()),
                input={"object_name": NAME},
            )
            print(obj)
            assert obj["ok"] is True
            assert obj["result"]["ok"] is True
            assert NAME in obj["result"]["data"][0]["text"]
            assert "MESH" in obj["result"]["data"][0]["text"]

            print("\n=== QB-15 PROCESS RECOVERY INSPECTION ===")
            pending = send(proc, "pending_recoveries")
            history = send(proc, "reconciliation_history", input={})
            print(pending)
            print(history)
            assert pending["ok"] is True
            assert pending["result"] == []
            assert history["ok"] is True

        finally:
            if created:
                print("\n=== QB-15 PROCESS GOVERNED CLEANUP ===")
                cleanup = send(
                    proc,
                    "execute_recipe",
                    request_id=str(uuid.uuid4()),
                    input={
                        "recipe_id": "orbi.blender.delete_object.v1",
                        "parameters": {"name": NAME},
                    },
                )
                print(cleanup)
                assert cleanup["ok"] is True
                assert cleanup["result"]["ok"] is True

            if proc.stdin:
                proc.stdin.close()
            exit_code = proc.wait(timeout=10)
            stderr = proc.stderr.read()
            if stderr:
                print("SIDECAR STDERR:")
                print(stderr)
            assert exit_code == 0

        print("\n=== QB-15 POST-PROCESS LEDGER EXISTS ===")
        assert ledger.is_file()
        print("Ledger:", ledger)

        print("\nQB-15 LIVE PROCESS SIDECAR: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
