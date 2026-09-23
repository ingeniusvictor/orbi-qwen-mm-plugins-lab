# QB-14 — ORBI Scene3D Pilot Integration Contract

Status: **DESIGN CANDIDATE — MACHINE-READABLE CONTRACT READY**

## Purpose

QB-14 defines the first product-consumer boundary for the certified ORBI Scene3D capability stack.

It does **not** modify ORBI Creative Studio.

The goal is to make the eventual pilot:

- provider-neutral,
- default-OFF,
- Electron-main-owned,
- renderer-safe,
- durable-ledger-aware,
- recovery-aware,
- reversible,
- independent from Qwen package names.

## Dependency gate

QB-14 requires formal certification of:

- QB-12 — Durable Execution Ledger & Restart Safety
- QB-13 — Durable Recovery & Reconciliation

The design may be reviewed before those certifications, but product implementation must not begin
until both dependency gates are PASS.

## Frozen Creative Studio consumer snapshot

Repository:

```text
ingeniusvictor/orbi-creative-studio
```

Branch:

```text
integration/orbi-foundation
```

Frozen observed commit:

```text
b0c63b33f51e7d81322b47eb3312b6e76a266c68
```

Observed desktop architecture:

```text
renderer
    ↓
contextBridge / preload
    ↓
Electron main
    ↓
trusted internal bridge/core
```

Observed security posture relevant to the pilot:

- `contextIsolation: true`
- `nodeIntegration: false`
- trusted IPC sender checks via `assertTrustedSender`
- existing narrow preload bridges such as `orbiComputeRouter` and `orbiBenchmark`
- privileged filesystem/provider operations kept in Electron main.

QB-14 deliberately follows this existing pattern instead of inventing a second security model.

## Canonical contract

Machine-readable source:

```text
docs/orbi/qb14/scene3d_pilot_contract.v1.json
```

Validator:

```text
scripts/orbi/qb14_validate_contract.py
```

Regression tests:

```text
tests/test_orbi_qb14_scene3d_pilot_contract.py
```

## Target dependency direction

Allowed:

```text
Creative Studio renderer
        ↓
window.orbiScene3D
        ↓
preload
        ↓
Electron main Scene3D bridge
        ↓
provider-neutral ORBI Scene3D transport
        ↓
orbi.scene3d.v1
        ↓
ORBI policy / ledger / recovery
        ↓
Qwen Blender provider
        ↓
Blender
```

Forbidden:

```text
renderer → qwen_mm_plugins_*
renderer → Python
renderer → SQLite
renderer → execute_blender_code
renderer → ledger path
renderer → provider configuration
renderer → reconciliation mutation
```

Creative Studio therefore depends on ORBI semantics, not Qwen implementation details.

## Feature flag

Pilot feature:

```text
ORBI_SCENE3D_PILOT_ENABLED
```

Rules:

- default: OFF
- production default: OFF
- renderer cannot enable it
- Electron main owns the resolved state
- disabled pilot must not start a Scene3D provider transport.

## Proposed renderer API

Global:

```text
window.orbiScene3D
```

Approved methods:

### Read-only

```text
getStatus()
sceneInfo()
objectInfo(...)
pendingRecoveries()
reconciliationHistory(...)
```

### Governed execution

```text
dryRunRecipe(...)
executeRecipe(...)
```

Explicitly forbidden renderer methods include:

```text
executePython
executeBlenderCode
retryExecution
releaseReservation
setLedgerPath
setProvider
reconcilePending
```

The renderer can display uncertain/pending executions but cannot resolve them.

## Proposed IPC channels

```text
orbi-scene3d:status
orbi-scene3d:scene-info
orbi-scene3d:object-info
orbi-scene3d:dry-run-recipe
orbi-scene3d:execute-recipe
orbi-scene3d:pending-recoveries
orbi-scene3d:reconciliation-history
```

Every handler must:

1. run in Electron main,
2. validate the trusted sender,
3. reject malformed payloads,
4. return normalized ORBI responses only.

## Request-id ownership

The renderer does not create execution request ids.

Electron main owns request-id generation.

This keeps replay identity out of untrusted UI code and prevents accidental manual reuse.

For R2 execution:

```text
renderer intent
    ↓
Electron main generates request_id
    ↓
ORBI durable reservation
    ↓
provider execution
```

## Retry behavior

### R0 reads

Bounded retry may be allowed.

Examples:

- scene info
- object info
- recovery inspection

### R2 execution

Automatic retry is forbidden.

Examples:

- create cube
- delete object

If execution becomes uncertain, the renderer receives the normalized error/audit state and the
request remains recoverable through QB-13.

## Initial recipe allowlist

Exactly:

```text
orbi.blender.create_cube.v1
orbi.blender.delete_object.v1
```

The pilot does not allow:

- arbitrary Python,
- filesystem recipes,
- network recipes,
- external Blender asset providers.

The product layer must require explicit user confirmation before the destructive
`delete_object` recipe is sent.

## Recovery surface

Renderer may inspect:

- pending executions,
- reconciliation history.

Renderer may **not**:

- mark pending state applied/not-applied,
- release reservations,
- retry an uncertain execution.

Initial reconciliation remains an operator function through:

```text
scripts/orbi/qb13_recovery_tool.py
```

This is intentional for the first pilot.

## Main-process ownership

Electron main owns:

- feature flag,
- trusted-sender checks,
- request-id generation,
- transport configuration,
- durable ledger location,
- timeout rules,
- retry rules,
- recipe allowlist.

The renderer must not be able to select or mutate any of those.

## Transport boundary

QB-14 does not yet choose the concrete Python/Node transport implementation.

The product-facing contract requires the transport to be:

- local-only,
- owned by Electron main,
- non-public/listening,
- bounded in message size,
- provider-neutral,
- normalized to ORBI envelopes,
- free of provider credentials in renderer.

A concrete stdio/sidecar implementation belongs to the next implementation gate.

## Renderer-visible response

Allowed normalized fields include:

```text
ok
request_id
interface
operation
data
policy
audit
error
```

Implementation details that must remain hidden include:

```text
sqlite_path
python_path
provider_raw_exception
provider_secret
generated_python_code
qwen_package_name
```

## Compute Router isolation

The Scene3D pilot is not a Compute Router cutover.

QB-14 does not:

- change current generation routing,
- promote a local inference backend,
- change benchmark authority,
- alter hardware-pilot evidence authority.

Scene3D is a separate capability boundary.

## MHS isolation

The pilot enables no MHS actuation.

```text
mhs_actuation_enabled = false
```

Nothing in QB-14 grants writes to:

- PV inverters,
- trackers,
- BESS,
- PLCs,
- reclosers,
- plant controllers,
- other physical hardware.

## Validation

Run:

```bash
python scripts/orbi/qb14_validate_contract.py
python -m pytest tests/test_orbi_qb14_scene3d_pilot_contract.py -q
```

Expected contract result:

```text
QB-14 CONTRACT: PASS
```

Expected QB-14 unit result:

```text
12 passed
```

For a full pre-pilot regression, after QB-12 and QB-13 are certified:

```bash
python -m pytest \
  tests/test_orbi_qb08_reference.py \
  tests/test_orbi_qb09_qwen_bridge.py \
  tests/test_orbi_qb10_governed_execution.py \
  tests/test_orbi_qb11_audit_replay.py \
  tests/test_orbi_qb12_durable_ledger.py \
  tests/test_orbi_qb13_reconciliation.py \
  tests/test_orbi_qb13_recovery_tool.py \
  tests/test_orbi_qb14_scene3d_pilot_contract.py \
  -q
```

Expected combined count:

```text
90 passed
```

## Proposed next phase

**QB-15 — Scene3D Local Sidecar Transport Reference Implementation**

Recommended scope:

- provider-neutral local transport,
- JSONL or equivalent bounded message framing,
- no public listening socket,
- status/read/dry-run/execute/recovery-read operations,
- Electron-main-compatible request shape,
- no Creative Studio modification yet,
- transport failure/timeout semantics,
- no automatic R2 retry.

Only after QB-15 is certified should a small feature-flagged branch be created in Creative Studio.

**QB-14 status: DESIGN CANDIDATE — awaiting dependency certification + local contract validation.**
