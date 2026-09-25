# QB-15 — Scene3D Local Sidecar Transport Certification

Status: **CERTIFIED**

## Certified candidate

Branch:

```text
feature/qb-15-scene3d-local-sidecar-transport
```

Implementation candidate:

```text
044a2059d63ecbc99a5bbd2562d7d82bafd91109
```

## Certification evidence

### Full accumulated regression

Observed on the certified candidate through the stacked preflight:

```text
expected_accumulated_tests = 107
offline_regression.passed = true
offline_regression.returncode = 0
```

The accumulated gate covers QB-08 through QB-15.

### QB-14 contract validation

Observed on the same candidate:

```text
QB-14 CONTRACT: PASS — 21 invariant(s)
```

### Stacked preflight

Observed on the same candidate:

```text
QB-12→QB-15 STACKED PREFLIGHT: PASS
preflight_passed = true
```

### Live process-level Scene3D sidecar smoke

Observed on the same candidate with Blender MCP available on localhost:

```text
QB-15 LIVE PROCESS SIDECAR: PASS
```

The live smoke exercised:

- local sidecar status,
- pre-existing object guard,
- dry-run recipe execution,
- governed object creation,
- provider-backed object readback,
- recovery inspection,
- reconciliation history inspection,
- governed cleanup,
- durable post-process ledger creation.

### Repository state

Verified on the same candidate:

```text
working tree clean
branch = feature/qb-15-scene3d-local-sidecar-transport
HEAD = 044a2059d63ecbc99a5bbd2562d7d82bafd91109
```

## Certified transport semantics

QB-15 certifies that the Scene3D pilot transport:

- is local-only and main-process owned,
- uses stdio JSONL framing,
- exposes no public listener,
- keeps the renderer/provider boundary provider-neutral,
- preserves Electron-main supplied request ids,
- allows only the approved Scene3D operation surface,
- exposes recovery and reconciliation as inspection-only from the sidecar,
- performs no automatic R2 retry,
- rejects privileged or smuggled execution fields,
- enforces bounded message size,
- drains oversized messages without corrupting the next frame,
- isolates provider stdout from the JSONL protocol stream,
- lazily creates the provider runtime,
- keeps the provider runtime singleton per sidecar process,
- preserves transport success separately from normalized application failure,
- records governed execution through the durable SQLite ledger.

## SQLite concurrency hardening

The QB-15 certification candidate also includes the post-QB-14 durable-ledger initialization hardening discovered during stacked preflight.

The certified behavior includes:

- `busy_timeout=10000` on connections,
- `synchronous=FULL`,
- persistent file-level WAL configuration,
- WAL negotiation during initialization,
- bounded retry only for transient SQLite `locked` initialization failures,
- fail-fast behavior for other operational errors,
- an 8-thread fresh-ledger concurrency regression.

The existing `BEGIN IMMEDIATE` reservation path and replay semantics remain unchanged.

## Safety invariant

QB-15 introduces transport, not new authority.

The sidecar does not expose arbitrary Python, provider selection, retry, request-id release, reconciliation mutation, filesystem authority, SQLite paths, or a public network listener to the renderer.

## Explicit limitations

QB-15 does not certify:

- production enablement,
- cross-host transport,
- distributed shared-ledger arbitration,
- automatic retry after uncertain execution,
- arbitrary Blender Python,
- arbitrary provider-specific commands,
- MHS actuation,
- the ORBI Creative Studio Electron product bridge.

The Creative Studio Electron Scene3D pilot bridge is the scope of QB-16.

## Certification result

```text
QB-15 SCENE3D LOCAL SIDECAR TRANSPORT: CERTIFIED
accumulated regression gate = PASS (107 expected tests)
QB-14 contract = PASS (21 invariants)
stacked preflight = PASS
live process sidecar smoke = PASS
candidate = 044a2059d63ecbc99a5bbd2562d7d82bafd91109
```

**QB-15: CERTIFIED.**
