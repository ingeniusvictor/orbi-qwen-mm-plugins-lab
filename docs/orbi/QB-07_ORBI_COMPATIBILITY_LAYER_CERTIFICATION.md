# QB-07 — ORBI Compatibility Layer Design Certification

Status: **PASS — ORBI-OWNED COMPATIBILITY CONTRACT CERTIFIED**

## Scope

QB-07 defines and validates the provider-neutral compatibility boundary that ORBI products will use before any production integration.

Parent certification:

- QB-06 certified commit: `60cd9d40d2ecfaacf9343fa038773d63693d3e79`

Validated branch:

- `feature/qb-07-orbi-compatibility-layer-design`

Validated candidate commit:

- `7c4d3b78a86fd29436547139d55edd173716fd04`

No existing ORBI production repository was modified.

## Certified artifacts

- `docs/orbi/qb07/orbi_compatibility_contract.v1.json`
- `scripts/orbi/qb07_validate_contract.py`
- `tests/test_orbi_qb07_contract.py`
- `docs/orbi/QB-07_ORBI_COMPATIBILITY_LAYER_DESIGN.md`

## Certified interfaces

QB-07 establishes five ORBI-owned public interfaces:

1. `orbi.media.v1`
2. `orbi.hardware.v1`
3. `orbi.spatial.v1`
4. `orbi.skill-authoring.v1`
5. `orbi.scene3d.v1`

Qwen-MM-Plugins is treated as an implementation provider behind these interfaces.

Direct Qwen-specific dependencies from ORBI product call sites are forbidden by design.

## Certified policy invariants

The contract and tests enforce:

- ORBI owns product-facing contracts.
- Provider selection is swappable/configurable.
- Local-first operation is preferred.
- Real hardware defaults to deny.
- MHS hard limits are not overrideable.
- Actuation requires explicit confirmation and a certified adapter.
- External-provider operations are disabled by default.
- Visual spatial geometry is not calibrated metrology.
- Generated skills cannot grant themselves tools/permissions.
- Skill provenance requires SHA-256 source identity.
- Arbitrary Blender Python is not a public ORBI API.
- Blender execution must be mediated by an approved recipe registry.
- Unknown project/interface bindings are rejected.

## Risk classes

The compatibility contract defines:

- `R0_READ_LOCAL`
- `R1_TRANSFORM_LOCAL`
- `R2_EXECUTE_SANDBOXED`
- `R3_ACTUATE_CONFIRMED`
- `R4_EXTERNAL_PROVIDER`

These classes drive policy decisions, retries, confirmations, and provider boundaries.

## Local validation evidence

Observed policy suite result:

```text
5 passed in 0.70s
```

The suite includes a positive validation of the canonical contract and negative mutation tests for:

- real-hardware default allow,
- public arbitrary Blender Python,
- external-provider default enablement,
- unknown project interfaces.

Repository integrity at validation:

```text
On branch feature/qb-07-orbi-compatibility-layer-design
nothing to commit, working tree clean
HEAD:
7c4d3b78a86fd29436547139d55edd173716fd04
```

## Architectural decision

The certified dependency direction is:

```text
ORBI product
    ↓
ORBI public interface
    ↓
ORBI policy gate
    ↓
ORBI provider adapter
    ↓
Qwen-MM-Plugins or another provider
```

The following dependency is intentionally prohibited:

```text
ORBI product → qwen_mm_plugins_* direct integration
```

## Production boundary

QB-07 certifies design and invariants only.

It does not authorize:

- real hardware actuation,
- production MHS adapters,
- direct Blender arbitrary-code access from ORBI products,
- cloud semantic perception by default,
- changes to LUMIA,
- changes to ORBI Edge Mesh,
- changes to ORBI Creative Studio,
- changes to ORBI Dash,
- changes to ORBI PVMetrics,
- changes to ORBI Academy,
- changes to ORBI Home Automation.

## Next phase

**QB-08 — ORBI Compatibility Reference Implementation**

Initial scope:

- provider-neutral request/response envelopes,
- central policy evaluator,
- read-only media adapter,
- read-only Blender/scene adapter,
- read-only MHS facade,
- provider-error normalization,
- denial-path tests,
- all implementation confined to this lab repository.

**QB-07 result: PASS — ORBI COMPATIBILITY CONTRACT AND POLICY INVARIANTS CERTIFIED**
