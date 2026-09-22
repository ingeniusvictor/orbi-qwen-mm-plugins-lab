from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/orbi/qb07_validate_contract.py"
CONTRACT_PATH = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"

spec = importlib.util.spec_from_file_location("qb07_validate_contract", VALIDATOR_PATH)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def adapter(doc, interface):
    return next(a for a in doc["adapters"] if a["interface"] == interface)


def test_qb07_contract_is_valid():
    assert validator.validate(load_contract()) == []


def test_qb07_rejects_real_hardware_default_allow():
    doc = deepcopy(load_contract())
    adapter(doc, "orbi.hardware.v1")["boundaries"]["real_hardware_default"] = "allow"
    errors = validator.validate(doc)
    assert any("real hardware must default deny" in e for e in errors)


def test_qb07_rejects_public_arbitrary_blender_python():
    doc = deepcopy(load_contract())
    adapter(doc, "orbi.scene3d.v1")["boundaries"]["arbitrary_python_public_api"] = True
    errors = validator.validate(doc)
    assert any("arbitrary Python must not be public API" in e for e in errors)


def test_qb07_rejects_external_provider_enabled_by_default():
    doc = deepcopy(load_contract())
    skill = adapter(doc, "orbi.skill-authoring.v1")
    op = next(o for o in skill["operations"] if o["name"] == "semantic_perception")
    op["default_enabled"] = True
    errors = validator.validate(doc)
    assert any("external provider must be disabled by default" in e for e in errors)


def test_qb07_rejects_unknown_project_interface():
    doc = deepcopy(load_contract())
    doc["project_bindings"][0]["interfaces"].append("orbi.unknown.v1")
    errors = validator.validate(doc)
    assert any("unknown interface orbi.unknown.v1" in e for e in errors)
