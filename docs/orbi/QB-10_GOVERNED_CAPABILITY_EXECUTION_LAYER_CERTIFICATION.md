# QB-10 — Governed Capability Execution Layer Certification

Status: **PASS — GOVERNED BLENDER EXECUTION CERTIFIED**

## Scope

QB-10 introduces controlled side effects through the ORBI compatibility boundary without exposing
arbitrary provider execution.

Parent certification:

- QB-09 certified commit: `17f50588c7c14cbebad6d72993e9787dc1aa999a`

Validated branch:

- `feature/qb-10-governed-capability-execution-layer`

Validated candidate commit:

- `0610da9ccf6c4aa90bf7b8696164ed37961ec2d8`

No ORBI production repository was modified.

## Certified policy behavior

`R2_EXECUTE_SANDBOXED` is denied by default.

Governed execution must be enabled explicitly by the composition root through:

```text
sandboxed_execution_enabled = true
```

The regular QB-09 read-only runtime remains unaffected.

## Certified public execution API

The caller may invoke only:

```text
orbi.scene3d.v1 / execute_recipe
```

Accepted public fields:

- `recipe_id`
- `parameters`
- optional `dry_run`

Caller-provided Python source is not accepted.

Unexpected fields such as `code` are policy-denied before provider execution.

## Certified recipe registry

Initial approved recipes:

- `orbi.blender.create_cube.v1`
- `orbi.blender.delete_object.v1`

Recipe properties certified:

- typed/ranged parameters,
- restricted object-name grammar,
- deterministic static compilation,
- SHA-256 of generated provider code,
- no network access,
- no filesystem scope,
- no dynamic `open`, `exec`, `eval`, or `__import__` inside compiled recipes,
- provider code imports only `bpy`,
- create recipe refuses to overwrite a preexisting named object,
- controlled stdout result.

## Dry-run behavior

`dry_run=true` validates and compiles the recipe but does not call Blender.

The dry-run plan returns:

- recipe id,
- recipe version,
- normalized parameters,
- code SHA-256,
- filesystem scope,
- network policy,
- `provider_called=false`.

## Hardware isolation

The governed Blender runtime registers only:

```text
orbi.scene3d.v1
```

It does not register:

```text
orbi.hardware.v1
```

MHS remains read-only and unchanged.

## Regression evidence

Combined compatibility/regression suite:

```text
........................................ [100%]
40 passed in 1.89s
```

Coverage includes:

- QB-08 provider-neutral runtime,
- QB-09 live Qwen bridge semantics,
- QB-10 governed-execution policy and recipe invariants.

## Live Blender evidence

The live governed sequence validated:

1. preexisting-object guard,
2. dry-run with no provider call,
3. caller-code injection denial,
4. governed cube creation,
5. live object verification,
6. MESH type verification,
7. governed cleanup,
8. post-cleanup object absence.

Observed result:

```text
QB-10 LIVE GOVERNED BLENDER EXECUTION: PASS
```

Repository integrity at validation:

```text
branch: feature/qb-10-governed-capability-execution-layer
HEAD: 0610da9ccf6c4aa90bf7b8696164ed37961ec2d8
working tree: clean
```

## Production boundary

QB-10 does not authorize:

- arbitrary Blender Python from product callers,
- unregistered recipes,
- network-enabled recipes,
- filesystem-writing recipes,
- MHS actuation,
- physical hardware integration,
- production credentials,
- production ORBI repository integration.

## Next phase

**QB-11 — Governed Execution Audit & Replay Safety**

Recommended scope:

- execution receipts,
- deterministic request fingerprints,
- in-runtime replay protection,
- explicit retry semantics for R2 execution,
- dry-run receipts,
- provider-call audit evidence,
- duplicate-request denial,
- no change to MHS read-only boundary,
- no production repository integration.

**QB-10 result: PASS — GOVERNED BLENDER EXECUTION, POLICY GATING, AND RECIPE CONTROLS CERTIFIED**
