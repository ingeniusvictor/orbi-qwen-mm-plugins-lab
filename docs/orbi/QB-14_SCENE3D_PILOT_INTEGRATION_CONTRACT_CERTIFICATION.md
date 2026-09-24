# QB-14 — Scene3D Pilot Integration Contract Certification

Status: **CERTIFIED**

## Certified candidate

Branch:

```text
feature/qb-14-scene3d-pilot-integration-contract
```

Implementation candidate:

```text
2827d39bfcf9eae0dd928b62e49decd3c4ad1a6b
```

## Certification evidence

### Contract validator

Observed locally on the certified candidate:

```text
QB-14 CONTRACT: PASS — 18 invariant(s)
```

### Full accumulated regression

Observed locally on the certified candidate:

```text
90 passed
```

The accumulated gate covers QB-08 through QB-14.

### Repository state

Verified on the same candidate:

```text
working tree clean
branch = feature/qb-14-scene3d-pilot-integration-contract
HEAD = 2827d39bfcf9eae0dd928b62e49decd3c4ad1a6b
```

## Certified contract invariants

QB-14 certifies that the Scene3D pilot contract:

- requires QB-12 and QB-13 certified dependencies,
- keeps the pilot default-OFF,
- prevents renderer-side enablement,
- keeps the product/renderer provider-neutral,
- exposes exactly the approved renderer API,
- forbids Python/provider/retry/release/reconciliation mutation methods,
- keeps request-id generation in Electron main,
- prohibits automatic R2 retries,
- constrains the initial recipe allowlist to the QB-10 certified pair,
- forbids arbitrary Python, network and filesystem authority,
- requires product confirmation for destructive delete,
- makes renderer recovery inspection-only,
- never auto-resolves pending executions,
- never releases historical request ids,
- requires local-only/main-owned/non-public transport,
- hides privileged implementation details from the renderer,
- keeps the pilot development-only,
- grants no production cutover authority,
- changes neither Compute Router authority nor MHS actuation.

## Safety invariant

QB-14 defines a product boundary, not a capability escalation.

The Scene3D renderer receives only normalized, provider-neutral surfaces. Privileged execution,
recovery mutation, raw provider internals, SQLite paths, Python paths, secrets, generated code,
and provider-specific implementation names remain outside renderer authority.

## Explicit limitations

QB-14 does not certify:

- a concrete transport implementation,
- process lifecycle supervision,
- sidecar framing,
- sidecar crash handling,
- cross-host launch behavior,
- end-to-end product execution,
- production enablement.

The local sidecar transport implementation is the scope of QB-15.

## Certification result

```text
QB-14 SCENE3D PILOT INTEGRATION CONTRACT: CERTIFIED
contract validator = PASS
regression = 90/90 PASS
```

**QB-14: CERTIFIED.**
