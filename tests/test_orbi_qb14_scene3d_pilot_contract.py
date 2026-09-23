from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/orbi/qb14/scene3d_pilot_contract.v1.json"
VALIDATOR = ROOT / "scripts/orbi/qb14_validate_contract.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("qb14_validate_contract", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_canonical_qb14_contract_passes_all_invariants():
    validator = load_validator()
    checks = validator.validate(contract())

    assert len(checks) >= 18


def test_feature_flag_cannot_default_on():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["feature_gate"]["default"] = True

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_renderer_cannot_gain_provider_or_python_authority():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["dependency_rule"]["renderer_direct_python_access"] = True

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_renderer_cannot_gain_reconciliation_mutation():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["recovery_policy"]["renderer_can_reconcile"] = True

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_r2_cannot_gain_automatic_retry():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["main_process"]["retries"]["R2_EXECUTE_SANDBOXED"] = "bounded-allowed"

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_request_id_generation_cannot_move_to_renderer():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["main_process"]["request_id"]["renderer_supplied"] = True

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_recipe_allowlist_cannot_expand_without_contract_update():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["recipe_policy"]["initial_allowlist"].append(
        "orbi.blender.arbitrary_python.v1"
    )

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_transport_cannot_become_public_listener():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["transport"]["requirements"].remove("no-listening-public-interface")

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_compute_router_and_mhs_authority_cannot_expand():
    validator = load_validator()

    compute_mutation = copy.deepcopy(contract())
    compute_mutation["pilot_scope"]["compute_router_authority_changed"] = True
    with pytest.raises(AssertionError):
        validator.validate(compute_mutation)

    mhs_mutation = copy.deepcopy(contract())
    mhs_mutation["pilot_scope"]["mhs_actuation_enabled"] = True
    with pytest.raises(AssertionError):
        validator.validate(mhs_mutation)


def test_dangerous_renderer_method_cannot_replace_approved_surface():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["renderer_api"]["methods"].append(
        {"name": "executeBlenderCode", "risk": "R2_EXECUTE_SANDBOXED"}
    )

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_sensitive_implementation_fields_must_remain_hidden():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["response_surface"]["renderer_hidden"].remove("sqlite_path")

    with pytest.raises(AssertionError):
        validator.validate(mutated)


def test_consumer_snapshot_must_be_full_commit_sha():
    validator = load_validator()
    mutated = copy.deepcopy(contract())
    mutated["consumer"]["frozen_commit"] = "b0c63b3"

    with pytest.raises(AssertionError):
        validator.validate(mutated)
