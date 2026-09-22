#!/usr/bin/env python3
"""QB-10 live governed Blender execution smoke.

Creates ORBI_QB10_Cube through an approved recipe, verifies it through the live read path,
then removes it through a second approved recipe. Arbitrary Python is never accepted from
the ORBI request surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat import OrbiRequest
from orbi_qwen_bridge import build_governed_blender_runtime

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"
NAME = "ORBI_QB10_Cube"


def request(runtime, operation, request_id, payload=None):
    return runtime.execute(
        OrbiRequest(
            interface="orbi.scene3d.v1",
            operation=operation,
            request_id=request_id,
            input=payload or {},
        )
    )


def main() -> int:
    runtime = build_governed_blender_runtime(CONTRACT)

    create_payload = {
        "recipe_id": "orbi.blender.create_cube.v1",
        "parameters": {
            "name": NAME,
            "size": 1.5,
            "location": [1.0, 0.0, 0.5],
        },
    }

    print("=== QB-10 PREEXISTING OBJECT GUARD ===")
    pre = request(
        runtime,
        "object_info",
        "qb10-precheck",
        {"object_name": NAME},
    )
    print(pre.to_dict())
    if pre.ok:
        raise AssertionError(
            f"{NAME} already exists before QB-10 smoke; refusing to modify or delete it"
        )
    if pre.error is None or "Object not found" not in pre.error.message:
        raise AssertionError(
            f"Blender precheck failed for an unexpected reason: "
            f"{pre.error.message if pre.error else 'unknown error'}"
        )

    print("=== QB-10 DRY RUN ===")
    dry = request(
        runtime,
        "execute_recipe",
        "qb10-dry-run",
        {**create_payload, "dry_run": True},
    )
    print(dry.to_dict())
    assert dry.ok is True
    assert dry.data["execution"] == "dry-run"
    assert dry.data["audit"]["provider_called"] is False
    assert dry.data["recipe"]["network_allowed"] is False
    assert dry.data["recipe"]["filesystem_scope"] == []

    print("\n=== QB-10 ARBITRARY CODE INJECTION DENIAL ===")
    denied = request(
        runtime,
        "execute_recipe",
        "qb10-injection-denied",
        {**create_payload, "code": "import os"},
    )
    print(denied.to_dict())
    assert denied.ok is False
    assert denied.error is not None
    assert denied.error.code == "POLICY_DENIED"

    created = False
    try:
        print("\n=== QB-10 GOVERNED CREATE ===")
        create = request(runtime, "execute_recipe", "qb10-create", create_payload)
        print(create.to_dict())
        created = create.ok
        assert create.ok is True
        assert create.data["execution"] == "executed"
        assert create.data["audit"]["provider_called"] is True

        print("\n=== QB-10 LIVE OBJECT VERIFY ===")
        obj = request(
            runtime,
            "object_info",
            "qb10-object-info",
            {"object_name": NAME},
        )
        print(obj.to_dict())
        assert obj.ok is True
        assert obj.data and obj.data[0]["kind"] == "text"
        assert NAME in obj.data[0]["text"]
        assert "MESH" in obj.data[0]["text"]

    finally:
        print("\n=== QB-10 GOVERNED CLEANUP ===")
        if created:
            cleanup = request(
                runtime,
                "execute_recipe",
                "qb10-delete",
                {
                    "recipe_id": "orbi.blender.delete_object.v1",
                    "parameters": {"name": NAME},
                },
            )
            print(cleanup.to_dict())
            assert cleanup.ok is True
        else:
            print("Cleanup skipped: QB-10 did not create the object.")

    print("\n=== QB-10 POST-CLEANUP OBJECT VERIFY ===")
    gone = request(
        runtime,
        "object_info",
        "qb10-object-gone",
        {"object_name": NAME},
    )
    print(gone.to_dict())
    assert gone.ok is False
    assert gone.error is not None
    assert "Object not found" in gone.error.message

    print("\nQB-10 LIVE GOVERNED BLENDER EXECUTION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
