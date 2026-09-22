#!/usr/bin/env python3
"""QB-09 live MHS bridge smoke using the bundled mock adapter only."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
REFS = ROOT / "src/capabilities/mhs/skill/references"
for path in (SRC, REFS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mock_adapter import build_server

from orbi_compat import OrbiRequest
from orbi_qwen_bridge import build_readonly_qwen_runtime

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


def main() -> int:
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    old_registry = os.environ.get("QWEN_MM_MHS_DEVICES")

    try:
        with tempfile.TemporaryDirectory(prefix="qb09-mhs-") as td:
            registry = Path(td) / "mhs-devices.json"
            registry.write_text(
                json.dumps(
                    {
                        "adapters": [
                            {
                                "name": "mock",
                                "url": f"http://{host}:{port}",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            os.environ["QWEN_MM_MHS_DEVICES"] = str(registry)

            runtime = build_readonly_qwen_runtime(
                CONTRACT,
                core=False,
                blender=False,
                mhs=True,
            )

            print("=== QB-09 MHS DISCOVER ===")
            discover = runtime.execute(
                OrbiRequest(
                    interface="orbi.hardware.v1",
                    operation="discover",
                    request_id="qb09-mhs-discover",
                )
            )
            print(discover.to_dict())
            assert discover.ok is True
            assert discover.data and discover.data[0]["kind"] == "text"
            report = json.loads(discover.data[0]["text"])
            ids = {device["device_id"] for device in report["devices"]}
            assert "mock/mock-camera" in ids
            assert "mock/mock-lamp" in ids

            print("\n=== QB-09 MHS HEALTH ===")
            health = runtime.execute(
                OrbiRequest(
                    interface="orbi.hardware.v1",
                    operation="health",
                    request_id="qb09-mhs-health",
                )
            )
            print(health.to_dict())
            assert health.ok is True
            health_report = json.loads(health.data[0]["text"])
            assert all(item.get("healthy") is True for item in health_report["devices"])

            print("\n=== QB-09 MHS READ IMAGE ===")
            frame = runtime.execute(
                OrbiRequest(
                    interface="orbi.hardware.v1",
                    operation="read",
                    request_id="qb09-mhs-frame",
                    input={
                        "device_id": "mock/mock-camera",
                        "capability": "frame",
                        "params": {"width": 32, "height": 24},
                    },
                )
            )
            print({
                "ok": frame.ok,
                "provider": frame.provider.to_dict(),
                "policy": frame.policy,
                "content_kinds": [item["kind"] for item in frame.data],
            })
            assert frame.ok is True
            assert any(item["kind"] == "image" and item["mime_type"] == "image/png" for item in frame.data)
            assert any(item["kind"] == "text" and "32x24 frame" in item["text"] for item in frame.data)

            print("\n=== QB-09 MHS WRITE DENIAL ===")
            denied = runtime.execute(
                OrbiRequest(
                    interface="orbi.hardware.v1",
                    operation="write",
                    request_id="qb09-mhs-write-denied",
                    input={"device_id": "mock/mock-lamp", "capability": "power", "params": {"on": True}},
                    confirm=True,
                )
            )
            print(denied.to_dict())
            assert denied.ok is False
            assert denied.error is not None
            assert denied.error.code == "POLICY_DENIED"

            print("\nQB-09 LIVE MHS READ-ONLY BRIDGE: PASS")
            return 0
    finally:
        if old_registry is None:
            os.environ.pop("QWEN_MM_MHS_DEVICES", None)
        else:
            os.environ["QWEN_MM_MHS_DEVICES"] = old_registry
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
