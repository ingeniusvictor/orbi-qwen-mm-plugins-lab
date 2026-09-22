#!/usr/bin/env python3
"""Validate the QB-07 ORBI compatibility contract using only the Python stdlib."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"

REQUIRED_INTERFACES = {
    "orbi.media.v1",
    "orbi.hardware.v1",
    "orbi.spatial.v1",
    "orbi.skill-authoring.v1",
    "orbi.scene3d.v1",
}

VALID_RISKS = {
    "R0_READ_LOCAL",
    "R1_TRANSFORM_LOCAL",
    "R2_EXECUTE_SANDBOXED",
    "R3_ACTUATE_CONFIRMED",
    "R4_EXTERNAL_PROVIDER",
}


def validate(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if doc.get("contract_version") != "orbi.compatibility/v1":
        errors.append("unexpected contract_version")

    principles = doc.get("principles", {})
    required_true = (
        "orbi_owns_public_contracts",
        "local_first",
        "provider_swappable",
        "explicit_policy_before_side_effects",
    )
    for key in required_true:
        if principles.get(key) is not True:
            errors.append(f"principle must be true: {key}")

    if principles.get("direct_upstream_imports_outside_adapters") is not False:
        errors.append("direct upstream imports must be forbidden outside adapters")
    if principles.get("production_hardware_writes_in_lab") is not False:
        errors.append("production hardware writes must be forbidden in the lab")

    adapters = doc.get("adapters", [])
    interfaces = [a.get("interface") for a in adapters]

    if len(interfaces) != len(set(interfaces)):
        errors.append("adapter interfaces must be unique")

    missing = REQUIRED_INTERFACES - set(interfaces)
    if missing:
        errors.append(f"missing required interfaces: {sorted(missing)}")

    for adapter in adapters:
        interface = adapter.get("interface", "<unknown>")
        provider = adapter.get("provider", {})
        if provider.get("family") != "qwen-mm-plugins":
            errors.append(f"{interface}: unexpected provider family")

        for op in adapter.get("operations", []):
            risk = op.get("risk_class")
            if risk not in VALID_RISKS:
                errors.append(f"{interface}/{op.get('name')}: invalid risk class {risk!r}")
            if risk == "R3_ACTUATE_CONFIRMED":
                if op.get("confirmation_required") is not True:
                    errors.append(f"{interface}/{op.get('name')}: actuation must require confirmation")
                if op.get("certified_adapter_required") is not True:
                    errors.append(f"{interface}/{op.get('name')}: actuation must require a certified adapter")
            if risk == "R4_EXTERNAL_PROVIDER" and op.get("default_enabled") is not False:
                errors.append(f"{interface}/{op.get('name')}: external provider must be disabled by default")

    by_interface = {a["interface"]: a for a in adapters if "interface" in a}

    hardware = by_interface.get("orbi.hardware.v1", {})
    hb = hardware.get("boundaries", {})
    if hb.get("real_hardware_default") != "deny":
        errors.append("hardware: real hardware must default deny")
    if hb.get("hard_limits_overrideable") is not False:
        errors.append("hardware: hard limits must not be overrideable")

    spatial = by_interface.get("orbi.spatial.v1", {})
    sb = spatial.get("boundaries", {})
    if sb.get("calibrated_metrology") is not False:
        errors.append("spatial: visual geometry must not claim calibrated metrology")

    skills = by_interface.get("orbi.skill-authoring.v1", {})
    kb = skills.get("boundaries", {})
    if kb.get("generated_skill_can_grant_tools") is not False:
        errors.append("skill authoring: generated skills must not grant tools")
    if kb.get("provenance_sha256_required") is not True:
        errors.append("skill authoring: SHA-256 provenance is required")

    scene = by_interface.get("orbi.scene3d.v1", {})
    bb = scene.get("boundaries", {})
    if bb.get("arbitrary_python_public_api") is not False:
        errors.append("scene3d: arbitrary Python must not be public API")
    if bb.get("approved_recipe_registry_required") is not True:
        errors.append("scene3d: approved recipe registry is required")

    allowed_interfaces = set(interfaces)
    for binding in doc.get("project_bindings", []):
        for interface in binding.get("interfaces", []):
            if interface not in allowed_interfaces:
                errors.append(
                    f"project {binding.get('project')}: unknown interface {interface}"
                )

    return errors


def main() -> int:
    doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors = validate(doc)

    print("=== QB-07 ORBI COMPATIBILITY CONTRACT ===")
    print("Contract:", CONTRACT)
    print("Adapters:", len(doc.get("adapters", [])))
    print("Project bindings:", len(doc.get("project_bindings", [])))

    if errors:
        print("QB-07 CONTRACT: FAIL")
        for error in errors:
            print(" -", error)
        return 1

    print("Interfaces:")
    for adapter in doc["adapters"]:
        print(
            f" - {adapter['interface']} <- "
            f"{adapter['provider']['capability']} ({adapter['default_mode']})"
        )
    print("QB-07 CONTRACT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
