# QB-07 — ORBI Compatibility Layer Design

Status: **DESIGN CANDIDATE — MACHINE-READABLE CONTRACT + POLICY INVARIANTS READY**

## Purpose

QB-07 defines the boundary between ORBI products and selectively adopted Qwen-MM-Plugins capabilities.

The central decision is:

> ORBI products MUST depend on ORBI-owned interfaces, not directly on Qwen-specific modules, tool names, environment variables, or provider response formats.

Qwen-MM-Plugins is therefore treated as one provider implementation behind an ORBI compatibility layer.

No existing ORBI production repository is modified in QB-07.

## Baseline

- Parent certification: QB-06
- Parent certified commit: `60cd9d40d2ecfaacf9343fa038773d63693d3e79`
- Frozen upstream baseline: `7f7ca380f2a21c3bea7239c132213e14c1c9abaf`
- Qwen-MM-Plugins distribution: `1.1.9`
- Branch: `feature/qb-07-orbi-compatibility-layer-design`

Individually certified inputs:

- `core` — local multimodal/media foundation
- `mhs` — mock hardware + safety gates
- `video-spatio` — local deterministic geometry subset
- `omni-skill-creator` — local authoring/provenance/validation pipeline
- `blender` — live local Blender MCP integration

## Canonical artifacts

QB-07 is intentionally machine-readable.

Canonical contract:

```text
docs/orbi/qb07/orbi_compatibility_contract.v1.json
```

Validator:

```text
scripts/orbi/qb07_validate_contract.py
```

Policy regression tests:

```text
tests/test_orbi_qb07_contract.py
```

The prose in this document explains the architecture, but the JSON contract is the source that future implementation phases should consume or mirror.

## Architectural rule

The intended dependency direction is:

```text
ORBI product
    |
    v
ORBI stable interface
    |
    v
ORBI policy gate
    |
    v
ORBI provider adapter
    |
    +---- Qwen-MM-Plugins
    |
    +---- future local/native provider
    |
    +---- future alternate MCP provider
```

The inverse direction is forbidden:

```text
ORBI product
    X----> qwen_mm_plugins_* direct import
    X----> raw Qwen tool-name dependency
    X----> Qwen-specific response schema
```

This isolates ORBI from upstream API churn and allows providers to be replaced without changing product call sites.

## Stable ORBI interfaces

### 1. `orbi.media.v1`

Initial provider:

```text
qwen-mm-plugins / core
```

Initial operations:

- `media_info`
- `read_image`
- `read_video`
- `visualize`

Default posture:

- local,
- read-only for source media,
- deterministic bounded artifact generation where applicable,
- no cloud key required for the certified path.

Candidate consumers:

- LUMIA
- ORBI Edge Mesh
- ORBI Creative Studio
- ORBI Dash
- ORBI PVMetrics
- ORBI Academy

### 2. `orbi.hardware.v1`

Initial provider:

```text
qwen-mm-plugins / mhs
```

Stable operations:

- `discover`
- `meta`
- `read`
- `health`
- `write`
- `reset`

The compatibility layer preserves the strong MHS safety semantics already proven in QB-03.

Mandatory ORBI rules:

- default mode is read-only,
- real hardware defaults to DENY,
- hard limits cannot be overridden,
- soft-limit overrides require confirmation,
- consequential writes require confirmation,
- write/reset require a separately certified adapter,
- unsupported reset/stop must surface explicitly,
- no fake success response.

The first compatibility implementation MUST NOT actuate:

- PV inverters,
- trackers,
- reclosers,
- protection relays,
- PLCs,
- plant controllers,
- BESS equipment.

Those targets require their own later certification phase.

### 3. `orbi.spatial.v1`

Initial provider:

```text
qwen-mm-plugins / video-spatio
```

Initial local operations:

- `build_scene`
- `camera_motion`
- `triangulate`
- `world_motion`
- `visualize_bev`

Mandatory semantic boundary:

> Visual/model-estimated geometry is not calibrated metrology.

Outputs derived from estimated depth or inferred camera parameters MUST preserve that qualification in metadata and UI.

Remote VLM helpers are disabled by default.

Candidate consumers:

- ORBI PVMetrics
- ORBI Academy
- future inspection/robotics prototypes

### 4. `orbi.skill-authoring.v1`

Initial provider:

```text
qwen-mm-plugins / omni-skill-creator
```

Initial operations:

- `inspect_media`
- `extract_assets`
- `author_skill`
- `validate_skill`
- optional `semantic_perception`

Mandatory knowledge-governance rules:

- generated skills begin as `source-grounded`,
- `execution-verified` requires real execution evidence,
- SHA-256 provenance is required,
- generated skills cannot self-grant tools or permissions,
- remote semantic perception is disabled by default,
- local authoring/validation remains usable without a remote Omni provider.

Candidate consumers:

- ORBI Academy
- LUMIA
- ORBI PVMetrics
- ORBI Creative Studio

### 5. `orbi.scene3d.v1`

Initial provider:

```text
qwen-mm-plugins / blender
```

Initial operations:

- `scene_info`
- `object_info`
- `viewport_screenshot`
- `execute_recipe`

The upstream provider exposes arbitrary Python execution inside Blender. That capability is useful in the lab, but it MUST NOT become the public ORBI API.

ORBI therefore exposes:

```text
execute_recipe(recipe_id, validated_parameters)
```

rather than:

```text
execute_python(arbitrary_string)
```

Implementation requirements:

- approved recipe registry,
- validated typed parameters,
- explicit filesystem scope,
- network denied by default,
- external asset providers denied by default,
- provider-specific raw Python kept behind the adapter boundary.

Candidate consumers:

- ORBI Creative Studio
- ORBI Dash
- ORBI Academy

## Risk model

QB-07 establishes five risk classes.

### `R0_READ_LOCAL`

Examples:

- inspect image,
- query Blender scene,
- discover mock devices,
- read device telemetry.

No external provider and no intended side effect.

### `R1_TRANSFORM_LOCAL`

Examples:

- extract frames,
- render a local visualization,
- calculate triangulation,
- build a skill artifact.

May create explicitly scoped artifacts but does not actuate external equipment.

### `R2_EXECUTE_SANDBOXED`

Examples:

- controlled Blender recipe execution.

Requires an execution boundary and a constrained operation registry.

### `R3_ACTUATE_CONFIRMED`

Examples:

- MHS write,
- MHS reset.

Requires explicit confirmation plus an independently certified hardware adapter.

### `R4_EXTERNAL_PROVIDER`

Examples:

- remote Omni semantic video perception.

Data leaves the local boundary and the provider must be configured explicitly.

External-provider operations default to disabled.

## Normalized request envelope

Future provider adapters should receive a provider-neutral request shaped conceptually as:

```json
{
  "interface": "orbi.scene3d.v1",
  "operation": "scene_info",
  "request_id": "...",
  "input": {}
}
```

Required request fields are encoded in the canonical JSON contract.

## Normalized response envelope

Provider-specific content must be normalized before returning to an ORBI product.

Conceptual shape:

```json
{
  "ok": true,
  "request_id": "...",
  "interface": "orbi.scene3d.v1",
  "operation": "scene_info",
  "provider": {
    "family": "qwen-mm-plugins",
    "capability": "blender",
    "version": "1.1.0"
  },
  "data": {},
  "provenance": {},
  "policy": {
    "risk_class": "R0_READ_LOCAL",
    "decision": "allow",
    "confirmation_required": false
  }
}
```

Errors must also be normalized:

```json
{
  "code": "...",
  "message": "...",
  "retryable": false
}
```

No ORBI consumer should need to parse a Qwen-specific exception string to decide application behavior.

## Retry semantics

Retries are risk-aware.

Read-only operations MAY be retried within bounded limits.

Transform operations MAY retry only when artifact creation is idempotent or scoped to a disposable target.

Actuation MUST NOT be blindly retried.

A timed-out hardware write is an unknown state until read-back/health verification proves otherwise.

## Project bindings

### LUMIA

Allowed initial interfaces:

- `orbi.media.v1`
- `orbi.skill-authoring.v1`
- `orbi.hardware.v1`

Hardware remains read-only at first.

### ORBI Edge Mesh

Allowed initial interfaces:

- `orbi.hardware.v1`
- `orbi.media.v1`

The first use case is node/device telemetry and observation, not actuation.

### ORBI Creative Studio

Allowed initial interfaces:

- `orbi.media.v1`
- `orbi.scene3d.v1`
- `orbi.skill-authoring.v1`

This is the strongest initial target for Blender-backed recipes.

### ORBI Dash

Allowed initial interfaces:

- `orbi.scene3d.v1`
- `orbi.media.v1`

Potential use: governed generation/refinement of 3D assets without giving game code direct access to Blender's Python executor.

### ORBI PVMetrics

Allowed initial interfaces:

- `orbi.spatial.v1`
- `orbi.skill-authoring.v1`
- `orbi.media.v1`

Initial scope is analysis and procedural knowledge.

No visual geometry output is certified as electrical/field metrology.

### ORBI Academy

Allowed initial interfaces:

- `orbi.media.v1`
- `orbi.skill-authoring.v1`
- `orbi.scene3d.v1`

Strong candidate for demonstration-to-skill and controlled 3D tutorial assets.

### ORBI Home Automation

Allowed initial interface:

- `orbi.hardware.v1`

Discovery and telemetry first. Device writes require a dedicated adapter certification.

## Security invariants encoded in tests

The QB-07 tests deliberately reject contract mutations that would:

1. allow real hardware by default,
2. expose arbitrary Blender Python as a public ORBI API,
3. enable remote external-provider perception by default,
4. bind a project to an unknown ORBI interface.

The validator additionally enforces:

- five required interfaces,
- unique interface ownership,
- known risk classes,
- confirmation for actuation,
- certified adapters for actuation,
- no override of MHS hard limits,
- no calibrated-metrology claim for visual geometry,
- no generated-skill tool grants,
- SHA-256 provenance requirement,
- approved Blender recipe registry.

## Provider-selection rule

Provider selection belongs in configuration or dependency injection, not product call sites.

Desired future pattern:

```python
client = OrbiMedia(provider="qwen-core")
result = client.media_info(path)
```

A product should not import `qwen_mm_plugins_core` directly.

A later provider could be introduced as:

```text
provider = "orbi-native"
provider = "qwen-core"
provider = "other-mcp"
```

without changing the public ORBI interface.

## What QB-07 intentionally does not implement

QB-07 does NOT:

- modify LUMIA,
- modify Edge Mesh,
- modify Creative Studio,
- modify ORBI Dash,
- modify PVMetrics,
- modify Academy,
- connect MHS to physical hardware,
- enable remote Omni semantic perception,
- expose arbitrary Blender Python to a production consumer.

Those changes belong after the compatibility contract itself is certified.

## Proposed next phase

### QB-08 — ORBI Compatibility Reference Implementation

Recommended scope:

1. implement provider-neutral request/response envelopes,
2. implement a read-only `orbi.media.v1` adapter,
3. implement a read-only `orbi.scene3d.v1` adapter,
4. implement an MHS read-only facade,
5. implement policy denial paths,
6. unit-test normalization and provider substitution,
7. keep all work inside this lab repository.

Only after a reference implementation passes should one ORBI product receive a pilot integration.

## Validation commands

From the repository root:

```bash
python scripts/orbi/qb07_validate_contract.py
python -m pytest tests/test_orbi_qb07_contract.py -q
```

Expected contract result:

```text
QB-07 CONTRACT: PASS
```

Expected policy test result:

```text
5 passed
```

## QB-07 design decision

The compatibility layer shall be **ORBI-owned, provider-neutral, policy-first and local-first**.

Qwen-MM-Plugins remains a valuable implementation provider, but it does not define ORBI's product-facing API.

**QB-07 status: DESIGN CANDIDATE — awaiting local validator/test execution before certification.**
