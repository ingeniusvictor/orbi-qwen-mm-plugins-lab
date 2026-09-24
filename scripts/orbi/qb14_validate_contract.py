#!/usr/bin/env python3
"""Validate QB-14 ORBI Scene3D pilot integration contract invariants."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/orbi/qb14/scene3d_pilot_contract.v1.json"

REQUIRED_RENDERER_METHODS = {
    "getStatus",
    "sceneInfo",
    "objectInfo",
    "dryRunRecipe",
    "executeRecipe",
    "pendingRecoveries",
    "reconciliationHistory",
}
FORBIDDEN_RENDERER_METHODS = {
    "executePython",
    "executeBlenderCode",
    "retryExecution",
    "releaseReservation",
    "setLedgerPath",
    "setProvider",
    "reconcilePending",
}
INITIAL_RECIPES = {
    "orbi.blender.create_cube.v1",
    "orbi.blender.delete_object.v1",
}


def load_contract(path: Path = CONTRACT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(contract: dict) -> list[str]:
    checks: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)
        checks.append(message)

    require(
        contract.get("contract_version") == "orbi.scene3d-pilot/v1",
        "contract version is orbi.scene3d-pilot/v1",
    )

    deps = contract.get("dependencies", {})
    require(
        deps.get("qb12", {}).get("required_status") == "certified"
        and deps.get("qb13", {}).get("required_status") == "certified",
        "QB-12 and QB-13 certification are mandatory dependencies",
    )

    consumer = contract.get("consumer", {})
    require(
        consumer.get("repository") == "ingeniusvictor/orbi-creative-studio"
        and consumer.get("branch") == "integration/orbi-foundation",
        "consumer is the canonical Creative Studio integration branch",
    )
    require(
        bool(re.fullmatch(r"[0-9a-f]{40}", str(consumer.get("frozen_commit", "")))),
        "consumer snapshot is pinned to a full commit SHA",
    )

    gate = contract.get("feature_gate", {})
    require(
        gate.get("default") is False
        and gate.get("renderer_may_enable") is False
        and gate.get("production_default") is False,
        "Scene3D pilot is default-OFF and renderer cannot enable it",
    )

    deps_rule = contract.get("dependency_rule", {})
    require(
        all(
            deps_rule.get(name) is False
            for name in (
                "product_direct_qwen_imports",
                "renderer_direct_provider_access",
                "renderer_direct_filesystem_access",
                "renderer_direct_sqlite_access",
                "renderer_direct_python_access",
                "provider_specific_names_in_renderer_api",
            )
        ),
        "renderer/product remain provider-neutral and isolated from privileged resources",
    )

    renderer = contract.get("renderer_api", {})
    methods = {item.get("name") for item in renderer.get("methods", [])}
    require(
        methods == REQUIRED_RENDERER_METHODS,
        "renderer exposes exactly the approved Scene3D pilot methods",
    )
    require(
        FORBIDDEN_RENDERER_METHODS.issubset(set(renderer.get("forbidden_methods", []))),
        "dangerous provider/retry/reconciliation methods are explicitly forbidden",
    )

    main = contract.get("main_process", {})
    request_id = main.get("request_id", {})
    require(
        request_id.get("generated_by") == "electron-main"
        and request_id.get("renderer_supplied") is False,
        "Electron main exclusively owns execution request-id generation",
    )
    require(
        main.get("retries", {}).get("R2_EXECUTE_SANDBOXED") == "never-automatic",
        "R2 execution can never be retried automatically",
    )

    channels = list(contract.get("ipc_channels", {}).values())
    require(
        len(channels) == len(set(channels))
        and all(isinstance(ch, str) and ch.startswith("orbi-scene3d:") for ch in channels),
        "IPC channels are unique and Scene3D-namespaced",
    )

    recipes = contract.get("recipe_policy", {})
    require(
        set(recipes.get("initial_allowlist", [])) == INITIAL_RECIPES,
        "initial recipe allowlist is exactly the QB-10 certified pair",
    )
    require(
        recipes.get("arbitrary_python") is False
        and recipes.get("network_enabled_recipes") is False
        and recipes.get("filesystem_enabled_recipes") is False,
        "pilot recipes cannot expose Python, network, or filesystem authority",
    )
    require(
        recipes.get("destructive_recipe_product_confirmation", {}).get(
            "orbi.blender.delete_object.v1"
        )
        is True,
        "destructive delete recipe requires product-layer confirmation",
    )

    recovery = contract.get("recovery_policy", {})
    require(
        recovery.get("renderer_can_inspect_pending") is True
        and recovery.get("renderer_can_inspect_history") is True
        and recovery.get("renderer_can_reconcile") is False,
        "renderer recovery surface is inspection-only",
    )
    require(
        recovery.get("automatic_pending_resolution") is False
        and recovery.get("original_request_id_released_after_reconciliation") is False,
        "pending recovery is never automatic and historical request ids stay reserved",
    )

    transport = contract.get("transport", {})
    requirements = set(transport.get("requirements", []))
    require(
        {"local-only", "main-process-owned", "no-listening-public-interface"}.issubset(
            requirements
        ),
        "pilot transport is local-only, main-owned, and not publicly listening",
    )

    visible = set(contract.get("response_surface", {}).get("renderer_visible", []))
    hidden = set(contract.get("response_surface", {}).get("renderer_hidden", []))
    require(
        {"ok", "request_id", "data", "policy", "audit", "error"}.issubset(visible),
        "renderer receives normalized ORBI execution/recovery state",
    )
    require(
        {
            "sqlite_path",
            "python_path",
            "provider_raw_exception",
            "provider_secret",
            "generated_python_code",
            "qwen_package_name",
        }.issubset(hidden),
        "renderer never receives privileged implementation details",
    )

    pilot = contract.get("pilot_scope", {})
    require(
        pilot.get("default_off") is True
        and pilot.get("development_only") is True
        and pilot.get("production_cutover_authorized") is False,
        "pilot remains development-only with no production cutover authority",
    )
    require(
        pilot.get("compute_router_authority_changed") is False
        and pilot.get("mhs_actuation_enabled") is False,
        "pilot changes neither Compute Router authority nor MHS actuation",
    )

    return checks


def main() -> int:
    try:
        checks = validate(load_contract())
    except Exception as exc:
        print(f"QB-14 CONTRACT: FAIL — {exc}", file=sys.stderr)
        return 1

    print(f"QB-14 CONTRACT: PASS — {len(checks)} invariant(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
