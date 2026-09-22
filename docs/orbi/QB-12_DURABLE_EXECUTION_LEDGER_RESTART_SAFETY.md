# QB-12 — Durable Execution Ledger & Restart Safety

Status: **IMPLEMENTATION CANDIDATE — LOCAL VALIDATION PENDING**

## Purpose

QB-12 extends the QB-11 governed-execution replay guard from session-local memory to a durable,
transactional SQLite ledger.

Parent certification:

- QB-11 certified commit: `c5aa043e9999eb70c8d46fe1f4390fdd6c62a002`

Branch:

- `feature/qb-12-durable-execution-ledger-restart-safety`

No ORBI production repository is modified.

## Durable ledger

Implementation:

```text
src/orbi_compat/sqlite_audit.py
```

The ledger uses Python stdlib `sqlite3` and enables:

- SQLite WAL journaling,
- `synchronous=FULL`,
- bounded busy timeout,
- transactional `BEGIN IMMEDIATE` reservation.

No new external database dependency is introduced.

## Atomic pre-provider reservation

For a real R2 execution:

```text
BEGIN IMMEDIATE
    ↓
check request_id
    ↓
insert reservation
    ↓
insert audit row outcome=pending
    ↓
COMMIT
    ↓
provider call
```

The reservation and initial audit evidence therefore become durable before the provider invocation.

If the process terminates after this commit, a new process still sees:

- the request-id reservation,
- the request fingerprint,
- the pending execution attempt.

## Pending / unknown outcome

A durable pending row uses:

```text
outcome = pending
provider_called = null
```

`provider_called=null` intentionally means **unknown**.

After an unexpected process termination, ORBI must not claim the provider was or was not called.

The request id remains reserved until an explicit future recovery/reconciliation policy exists.

## Restart replay safety

A second runtime using the same database rejects an already-reserved id:

Exact same payload:

```text
REPLAY_DENIED
```

Same id with changed R2 payload:

```text
REQUEST_ID_CONFLICT
```

The second runtime does not call Blender.

## Durable receipts

Finalized execution receipts persist:

- sequence,
- request id,
- request fingerprint,
- interface,
- operation,
- risk class,
- outcome,
- provider-called state,
- provider family/capability/version,
- replay-reserved state,
- retry semantics,
- normalized error code.

Sequences are SQLite AUTOINCREMENT values and remain monotonic across runtime instances.

## Dry run

Dry-run records may be persisted for audit, but they do not reserve the request id.

Therefore:

- repeated dry-run remains allowed,
- process restart does not turn a dry-run into a reservation,
- the same id may later be used for real execution.

## Factory integration

`build_governed_blender_runtime(...)` now supports:

```python
durable_ledger_path=<path>
```

When omitted:

- QB-11 in-memory replay protection remains the default.

When provided:

- QB-12 SQLite durability is enabled.

This keeps existing certified behavior backward compatible.

## Concurrency behavior

QB-12 uses SQLite transaction serialization plus a unique `request_id` reservation key.

The test suite verifies that two concurrent ledger instances attempting the same real R2 request
produce exactly:

- one successful reservation,
- one replay denial.

## Unit/regression suite

New suite:

```text
tests/test_orbi_qb12_durable_ledger.py
```

QB-12 adds 10 tests covering:

- database/schema initialization,
- reservation persistence across ledger instances,
- changed-payload conflict after restart,
- durable pending/unknown outcome,
- receipt/provider identity persistence,
- dry-run non-reservation across restart,
- replay blocking across new runtimes,
- timeout/unknown-outcome protection across restart,
- concurrent single-owner reservation,
- monotonic durable sequence and denial receipts.

Full regression target:

```text
QB-08: 13
QB-09: 14
QB-10: 13
QB-11: 12
QB-12: 10
TOTAL: 62 passed
```

## Live Blender restart smoke

Script:

```text
scripts/orbi/qb12_live_durable_restart.py
```

Sequence:

1. create a temporary durable SQLite ledger,
2. verify `ORBI_QB12_Cube` did not preexist,
3. persist a dry-run,
4. execute governed create with runtime #1,
5. destroy runtime #1,
6. create runtime #2 over the same SQLite file,
7. exact replay → `REPLAY_DENIED`,
8. changed payload same id → `REQUEST_ID_CONFLICT`,
9. verify original Blender object still exists,
10. governed cleanup with a new request id,
11. create runtime #3 over the same SQLite file,
12. replay cleanup → `REPLAY_DENIED`,
13. verify object is absent,
14. inspect durable receipts and reserved ids,
15. verify no pending rows remain after normal completion.

Required result:

```text
QB-12 LIVE DURABLE LEDGER & RESTART SAFETY: PASS
```

## Explicit limitation

QB-12 protects against process/runtime restart and competing processes sharing the same SQLite file.

It does not yet provide:

- a distributed ledger shared across different hosts,
- remote database consensus,
- automatic reconciliation of old `pending` attempts,
- operator approval workflow for uncertain outcomes.

Those remain future gates before distributed production execution.

## Production boundary

QB-12 still does not authorize:

- arbitrary Blender Python,
- unregistered recipes,
- network/filesystem-enabled Blender recipes,
- MHS actuation,
- physical hardware write integration,
- production ORBI repository integration.

## Validation commands

```bash
python -m pytest \
  tests/test_orbi_qb08_reference.py \
  tests/test_orbi_qb09_qwen_bridge.py \
  tests/test_orbi_qb10_governed_execution.py \
  tests/test_orbi_qb11_audit_replay.py \
  tests/test_orbi_qb12_durable_ledger.py \
  -q

python scripts/orbi/qb12_live_durable_restart.py
```

Then:

```bash
git status
git branch --show-current
git rev-parse HEAD
```

QB-12 becomes certifiable after:

- 62/62 regression tests pass,
- live durable restart smoke passes,
- working tree is clean.

**QB-12 status: IMPLEMENTATION CANDIDATE — awaiting local validation.**
