# QB-11 — Governed Execution Audit & Replay Safety Certification

Status: **PASS — SESSION-LOCAL EXECUTION AUDIT AND REPLAY SAFETY CERTIFIED**

## Scope

QB-11 protects governed R2 execution from accidental duplicate side effects caused by retries,
timeouts, or reuse of an execution request identifier.

Parent certification:

- QB-10 certified commit: `33fffbe5f1b1eaea53029450a16f218d91296671`

Validated branch:

- `feature/qb-11-governed-execution-audit-replay-safety`

Validated candidate commit:

- `f00368a5f5dc051a5d3cfe94443519f8a4499be7`

No ORBI production repository was modified.

## Certified execution audit

R2 responses may carry:

```text
audit.schema = orbi.execution-audit/v1
```

Certified receipt fields:

- monotonic session sequence,
- request id,
- deterministic SHA-256 request fingerprint,
- interface,
- operation,
- risk class,
- outcome,
- provider-called flag,
- provider identity/version,
- replay-reservation state,
- retry semantics,
- normalized error code.

## Certified request identity

The request fingerprint is deterministic SHA-256 over canonical JSON containing:

- interface,
- operation,
- input,
- confirm.

`request_id` is excluded from the fingerprint.

Equivalent operational payloads therefore retain the same fingerprint across request-id changes.

Non-deterministic/non-JSON R2 inputs are rejected before provider invocation.

## Certified replay reservation semantics

For real R2 execution, the request id is reserved before the provider call.

This protects the uncertain-outcome case:

```text
provider call
    ↓
timeout / connection loss
    ↓
side effect may have happened
    ↓
same request_id retry
    ↓
REPLAY_DENIED
```

Certified errors:

- exact same-id replay → `REPLAY_DENIED`
- same id + changed R2 payload → `REQUEST_ID_CONFLICT`

Both are non-retryable.

## Certified dry-run behavior

Dry-run execution:

- does not reserve the request id,
- does not call the provider,
- may be repeated,
- may reuse the same request id for the later real execution.

This preserves an inspect → execute workflow.

## Certified provider-failure behavior

If provider execution raises a timeout/connection failure after reservation:

- ORBI returns normalized provider unavailable/failure state,
- receipt records `provider_called=true`,
- the reservation remains active,
- same-id automatic retry is denied.

## Regression evidence

Combined QB-08 through QB-11 regression suite:

```text
.................................................... [100%]
52 passed in 0.99s
```

## Live Blender evidence

The live QB-11 sequence validated:

1. preexisting-object guard,
2. repeated dry-run with no provider call,
3. governed create + execution receipt,
4. exact replay → `REPLAY_DENIED`,
5. changed payload with same request id → `REQUEST_ID_CONFLICT`,
6. original object remained valid,
7. ownership-safe governed cleanup,
8. object absence after cleanup,
9. contiguous audit-ledger sequence.

Observed result:

```text
QB-11 LIVE AUDIT & REPLAY SAFETY: PASS
```

Repository integrity:

```text
branch: feature/qb-11-governed-execution-audit-replay-safety
HEAD: f00368a5f5dc051a5d3cfe94443519f8a4499be7
working tree: clean
```

## Explicit limitation

QB-11 replay protection is session-local/in-memory.

It does not survive process restart and is not yet sufficient for distributed or multi-process
production execution.

## Next phase

**QB-12 — Durable Execution Ledger & Restart Safety**

Recommended scope:

- SQLite-backed durable request reservations,
- transactional reservation before provider call,
- persistent execution receipts,
- process-restart replay protection,
- cross-runtime request-id conflict detection,
- durable unknown-outcome state,
- read-only audit inspection,
- no MHS actuation,
- no production project integration.

**QB-11 result: PASS — SESSION-LOCAL AUDIT, REQUEST FINGERPRINTING, AND REPLAY SAFETY CERTIFIED**
