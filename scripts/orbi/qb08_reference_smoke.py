#!/usr/bin/env python3
"""Deterministic QB-08 smoke test for the ORBI compatibility reference runtime."""

from __future__ import annotations

from pathlib import Path

from orbi_compat import OrbiRequest, OrbiRuntime, PolicyEngine
from orbi_compat.adapters import (
    QwenBlenderReadOnlyAdapter,
    QwenCoreMediaAdapter,
    QwenMHSReadOnlyAdapter,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


class FakeInvoker:
    def __init__(self, label: str):
        self.label = label
        self.calls = []

    def __call__(self, tool, payload):
        self.calls.append((tool, payload))
        return {"fake_provider": self.label, "tool": tool, "payload": payload}


def main() -> int:
    policy = PolicyEngine.from_file(CONTRACT)
    media = FakeInvoker("core")
    scene = FakeInvoker("blender")
    hardware = FakeInvoker("mhs")

    runtime = OrbiRuntime(
        policy,
        [
            QwenCoreMediaAdapter(media),
            QwenBlenderReadOnlyAdapter(scene),
            QwenMHSReadOnlyAdapter(hardware),
        ],
    )

    print("=== QB-08 MEDIA READ ===")
    r = runtime.execute(
        OrbiRequest(
            interface="orbi.media.v1",
            operation="media_info",
            request_id="smoke-media",
            input={"path": "/tmp/example.mp4"},
        )
    )
    assert r.ok is True
    print(r.to_dict())

    print("\n=== QB-08 SCENE READ ===")
    r = runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="scene_info",
            request_id="smoke-scene",
        )
    )
    assert r.ok is True
    print(r.to_dict())

    print("\n=== QB-08 HARDWARE ACTUATION DENIAL ===")
    r = runtime.execute(
        OrbiRequest(
            interface="orbi.hardware.v1",
            operation="write",
            request_id="smoke-write",
            input={"device_id": "mock/device", "value": 1},
            confirm=True,
        )
    )
    assert r.ok is False
    assert r.error is not None and r.error.code == "POLICY_DENIED"
    assert hardware.calls == []
    print(r.to_dict())

    print("\n=== QB-08 BLENDER EXECUTION DENIAL ===")
    r = OrbiRuntime(
        policy,
        [QwenBlenderReadOnlyAdapter(scene)],
    ).execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation="execute_recipe",
            request_id="smoke-exec",
            input={"recipe_id": "not-enabled-yet"},
        )
    )
    assert r.ok is False
    assert r.error is not None and r.error.code == "POLICY_DENIED"
    print(r.to_dict())

    print("\nQB-08 REFERENCE SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
