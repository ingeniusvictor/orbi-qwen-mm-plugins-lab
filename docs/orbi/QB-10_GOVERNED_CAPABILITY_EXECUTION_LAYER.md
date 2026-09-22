# QB-10 — Governed Capability Execution Layer

Status: **IMPLEMENTATION CANDIDATE — LOCAL VALIDATION PENDING**

## Purpose

QB-10 introduces the first controlled side-effecting operation through the ORBI compatibility
boundary without exposing arbitrary provider execution.

Parent certification:

- QB-09 certified commit: `17f50588c7c14cbebad6d72993e9787dc1aa999a`

Branch:

- `feature/qb-10-governed-capability-execution-layer`

No ORBI production repository is modified.

## Security decision

The public ORBI operation remains:

```text
orbi.scene3d.v1 / execute_recipe
```

The caller does **not** provide Python source.

The caller may provide only:

- `recipe_id`
- `parameters`
- optional `dry_run`

Any unexpected field, including `code`, is denied.

The only component that may compile Python is the ORBI-owned approved recipe registry.

## R2 policy gate

QB-10 hardens `R2_EXECUTE_SANDBOXED`.

Previously, the QB-07 contract classified `execute_recipe` as R2, while the QB-08 read-only
adapter denied it.

QB-10 adds an explicit runtime gate:

```text
sandboxed_execution_enabled = false   (default)
```

Therefore an R2 request is denied by `PolicyEngine` before reaching any adapter unless the
composition root explicitly enables governed execution.

The normal QB-09 read-only runtime remains unchanged.

Only:

```text
build_governed_blender_runtime(...)
```

enables the R2 gate.

## Approved recipe registry

Provider-specific Blender recipes are isolated in:

```text
src/orbi_qwen_bridge/blender_recipes.py
```

Initial approved recipes:

### `orbi.blender.create_cube.v1`

Parameters:

- `name`: restricted to `[A-Za-z0-9_.-]{1,64}`
- `size`: numeric, 0.01–1000
- `location`: three numeric coordinates, each -10000–10000

Safety behavior:

- no caller Python,
- no network,
- no filesystem,
- no overwrite of an existing object,
- deterministic static recipe compiler,
- SHA-256 code identity,
- controlled stdout result.

If an object with the requested name already exists, the recipe fails rather than deleting or
overwriting it.

### `orbi.blender.delete_object.v1`

Parameters:

- `name`: restricted to `[A-Za-z0-9_.-]{1,64}`

Safety behavior:

- explicit destructive recipe,
- name-scoped only,
- no network,
- no filesystem,
- SHA-256 code identity,
- controlled stdout result.

## Compiled recipe evidence

Every compiled recipe carries:

- recipe id,
- recipe version,
- normalized parameters,
- SHA-256 of the exact provider code,
- declared filesystem scope,
- network permission.

Initial recipes declare:

```text
filesystem_scope = []
network_allowed = false
```

The raw generated Python is intentionally not part of the public ORBI request API.

## Dry run

`dry_run=true` validates and compiles the approved recipe but does not invoke Blender.

The returned plan includes:

- normalized parameters,
- recipe version,
- code SHA-256,
- filesystem scope,
- network policy,
- audit flag `provider_called=false`.

This provides an inspection gate before side effects.

## Governed Blender adapter

Provider bridge:

```text
src/orbi_qwen_bridge/blender_governed.py
```

The adapter preserves read-only operations:

- `scene_info`
- `object_info`
- `viewport_screenshot`

and adds only:

- `execute_recipe`

The adapter maps an approved compiled recipe internally to:

```text
execute_blender_code
```

A caller cannot select that provider tool directly.

## Defense in depth

Execution path:

```text
OrbiRequest
    ↓
PolicyEngine R2 gate
    ↓
QwenBlenderGovernedAdapter
    ↓
approved recipe id
    ↓
typed/ranged parameter validation
    ↓
static recipe compiler
    ↓
SHA-256 / scope metadata
    ↓
execute_blender_code
```

Denial paths include:

- R2 disabled by default,
- unknown recipe id,
- unexpected payload fields,
- caller-supplied `code`,
- invalid object names,
- out-of-range numeric parameters,
- wrong parameter types.

## Hardware boundary

QB-10 does not relax MHS restrictions.

The governed Blender runtime contains only:

```text
orbi.scene3d.v1
```

It does not register:

```text
orbi.hardware.v1
```

MHS write/reset remain disabled.

## Static/governance tests

Suite:

```text
tests/test_orbi_qb10_governed_execution.py
```

It validates:

- R2 denied by default before adapter call,
- exact approved recipe set,
- parameter normalization,
- SHA-256 code identity,
- no filesystem scope,
- network denied,
- recipe Python imports only `bpy`,
- no dynamic `open/exec/eval/__import__`,
- unknown recipe denial,
- caller code-injection denial,
- malicious-name denial,
- range enforcement,
- dry-run provider isolation,
- actual governed provider-tool mapping,
- governed deletion,
- read operations remain available,
- governed runtime contains no hardware adapter.

Expected result:

```text
13 passed
```

## Live Blender smoke

Script:

```text
scripts/orbi/qb10_live_governed_blender.py
```

The live sequence is:

1. verify `ORBI_QB10_Cube` does not already exist,
2. dry-run create recipe,
3. verify arbitrary `code` field is denied,
4. execute governed create recipe,
5. read the object through `object_info`,
6. verify it is a Blender `MESH`,
7. execute governed delete recipe,
8. verify the object is gone.

The cleanup is ownership-safe:

- if the smoke did not create the object, it does not delete it.

Required result:

```text
QB-10 LIVE GOVERNED BLENDER EXECUTION: PASS
```

## Regression requirement

Because QB-10 changes the central policy/runtime, the QB-08 and QB-09 suites must continue to pass.

Combined expected regression count:

```text
QB-08: 13
QB-09: 14
QB-10: 13
TOTAL: 40 passed
```

## Production boundary

QB-10 still does not authorize:

- arbitrary Blender Python from product callers,
- unregistered recipes,
- network-enabled Blender recipes,
- filesystem-writing Blender recipes,
- MHS actuation,
- physical hardware integration,
- production credentials,
- production ORBI repository changes.

## Validation commands

From repository root:

```bash
python -m pytest \
  tests/test_orbi_qb08_reference.py \
  tests/test_orbi_qb09_qwen_bridge.py \
  tests/test_orbi_qb10_governed_execution.py \
  -q

python scripts/orbi/qb10_live_governed_blender.py
```

Then:

```bash
git status
git branch --show-current
git rev-parse HEAD
```

QB-10 becomes certifiable after:

- 40/40 compatibility/regression tests pass,
- live governed Blender smoke passes,
- working tree is clean.

**QB-10 status: IMPLEMENTATION CANDIDATE — awaiting local validation.**
