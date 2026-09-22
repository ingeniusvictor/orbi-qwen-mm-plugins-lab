#!/usr/bin/env python3
"""QB-09 live Blender read-only bridge smoke.

Requires the already-certified Blender + bundled addon session on BLENDER_HOST/BLENDER_PORT
(default 127.0.0.1:9876).
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat import OrbiRequest
from orbi_qwen_bridge import build_readonly_qwen_runtime

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


def main() -> int:
    host = os.environ.get("BLENDER_HOST", "127.0.0.1")
    port = int(os.environ.get("BLENDER_PORT", "9876"))

    print("=== QB-09 BLENDER CONNECTIVITY ===")
    print(f"Target: {host}:{port}")

    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        raise SystemExit(
            f"Blender MCP is not reachable at {host}:{port}: {exc}. "
            "Start the certified Blender session before running this smoke."
        )

    runtime = build_readonly_qwen_runtime(
        CONTRACT,
        core=False,
        blender=True,
        mhs=False,
    )

    print("\n=== QB-09 ORBI SCENE READ ===")
    scene = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="scene_info",
            request_id="qb09-blender-scene",
        )
    )
    print(scene.to_dict())

    assert scene.ok is True
    assert scene.provider.capability == "blender"
    assert scene.policy["risk_class"] == "R0_READ_LOCAL"
    assert scene.data and scene.data[0]["kind"] == "text"
    scene_text = scene.data[0]["text"]
    assert "Error getting scene info" not in scene_text
    assert "objects" in scene_text.lower()

    print("\n=== QB-09 BLENDER EXECUTION DENIAL ===")
    denied = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="qb09-blender-exec-denied",
            input={"recipe_id": "qb09-not-enabled"},
        )
    )
    print(denied.to_dict())
    assert denied.ok is False
    assert denied.error is not None
    assert denied.error.code == "POLICY_DENIED"

    # Prove the live Blender service survives the ORBI read path and denial path.
    with socket.create_connection((host, port), timeout=3):
        pass

    print("\nQB-09 LIVE BLENDER READ-ONLY BRIDGE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
