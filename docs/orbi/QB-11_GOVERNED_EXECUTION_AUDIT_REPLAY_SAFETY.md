# QB-11 — Governed Execution Audit & Replay Safety

Status: **IMPLEMENTATION CANDIDATE — LOCAL VALIDATION PENDING**

## Purpose

QB-11 protects governed R2 execution from accidental duplicate side effects caused by retries,
timeouts, or reuse of an execution request identifier.

Parent certification:

- QB-10 certified commit: `33fffbe5f1b1eaea53029450a16f218d91296671`

Branch:

- `feature/qb-11-governed-execution-audit-replay-safety`

No ORBI production repository is modified.

## Execution receipt

R2 responses now optionally carry:

```text
audit.schema = orbi.execution-audit/v1
```

Receipt fields include:

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
- normalized error code when applicable.

R0/R1 reads and transformations do not receive R2 execution receipts.

## Request fingerprint

The fingerprint is SHA-256 over canonical JSON containing:

- interface,
- operation,
- input,
- confirm.

`request_id` is intentionally excluded.

This means two requests with identical operational meaning have the same payload fingerprint even
when their request ids differ.

Only deterministic JSON payloads are accepted for R2 fingerprinting.

## Replay reservation

For a real R2 execution:

```text
policy allow
    ↓
request fingerprint
    ↓
request_id reservation
    ↓
provider call
```

Reservation occurs **before** calling the provider.

This is critical for uncertain outcomes:

```text
provider called
    ↓
timeout / connection loss
    ↓
we do NOT know whether side effect happened
    ↓
same request_id retry is DENIED
```

The caller must inspect state and, if a new action is truly intended, issue a new request id.

## Replay errors

Exact retry:

```text
REPLAY_DENIED
```

Same request id with a different R2 payload:

```text
REQUEST_ID_CONFLICT
```

Both are non-retryable ORBI errors.

## Dry-run behavior

Dry-run requests are not replay-reserved.

Therefore:

- dry-run may be repeated,
- multiple dry-run receipts may exist,
- provider is not called,
- the same request id may later be used for the corresponding real execution.

This supports an inspect → execute workflow.

## Conservative validation behavior

If an actual R2 request reserves its id and is then rejected by the governed adapter before provider
execution, the id remains reserved.

This prevents silently changing an execution payload under the same id after a failed validation.

The receipt records:

```text
provider_called = false
outcome = denied
```

## Provider failure semantics

If a real R2 provider call raises a timeout/connection failure:

- response is normalized as provider failure/unavailable,
- receipt records `provider_called=true`,
- replay reservation remains active,
- automatic same-id retry is denied.

This is intentionally more conservative than read-only retry behavior.

## Session boundary

QB-11 replay protection is **in-runtime/session-local**.

It does not yet persist a replay ledger across process restart.

That limitation is explicit and will need a durable store before distributed/multi-process production
use.

## Unit/regression suite

New suite:

```text
tests/test_orbi_qb11_audit_replay.py
```

QB-11 adds 12 tests covering:

- deterministic request fingerprinting,
- request-id-independent payload identity,
- execution receipts,
- exact replay denial,
- request-id conflict denial,
- repeatable dry-run,
- dry-run → real execution using the same id,
- timeout/unknown-outcome replay protection,
- invalid recipe reservation semantics,
- R0 reads unaffected,
- contiguous receipt sequence,
- rejection of nondeterministic/non-JSON R2 payloads.

Full regression target:

```text
QB-08: 13
QB-09: 14
QB-10: 13
QB-11: 12
TOTAL: 52 passed
```

## Live Blender smoke

Script:

```text
scripts/orbi/qb11_live_audit_replay.py
```

Live sequence:

1. ensure `ORBI_QB11_Cube` did not preexist,
2. repeat the same dry-run twice,
3. execute governed create and capture receipt,
4. repeat exact same execution request id → `REPLAY_DENIED`,
5. reuse same request id with changed location → `REQUEST_ID_CONFLICT`,
6. verify the original object still exists,
7. ownership-safe cleanup with a new request id,
8. verify object absence,
9. inspect contiguous audit receipts.

Required result:

```text
QB-11 LIVE AUDIT & REPLAY SAFETY: PASS
```

## Production boundary

QB-11 still does not authorize:

- distributed/multi-process replay protection,
- persistent execution ledger,
- arbitrary Blender Python,
- unregistered Blender recipes,
- network/filesystem-enabled recipes,
- MHS actuation,
- production project integration.

## Validation commands

```bash
python -m pytest \
  tests/test_orbi_qb08_reference.py \
  tests/test_orbi_qb09_qwen_bridge.py \
  tests/test_orbi_qb10_governed_execution.py \
  tests/test_orbi_qb11_audit_replay.py \
  -q

python scripts/orbi/qb11_live_audit_replay.py
```

Then:

```bash
git status
git branch --show-current
git rev-parse HEAD
```

QB-11 becomes certifiable after:

- 52/52 regression tests pass,
- live audit/replay smoke passes,
- working tree is clean.

**QB-11 status: IMPLEMENTATION CANDIDATE — awaiting local validation.**
