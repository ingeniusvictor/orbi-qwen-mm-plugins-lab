# QB-12 — Durable Execution Ledger & Restart Safety Certification

Status: **CERTIFIED**

## Certified candidate

Branch:

```text
feature/qb-12-durable-execution-ledger-restart-safety
```

Implementation candidate:

```text
a05196d7302f3c2632dc5790673a97e338634d91
```

## Certification evidence

### Full accumulated regression

Observed locally on the certified candidate:

```text
62 passed in 1.26s
```

The regression gate covers:

- QB-08 ORBI compatibility reference
- QB-09 live Qwen provider bridge
- QB-10 governed capability execution
- QB-11 audit and replay safety
- QB-12 durable SQLite execution ledger

### Live durable restart smoke

Previously observed on the same candidate:

```text
QB-12 LIVE DURABLE LEDGER & RESTART SAFETY: PASS
```

### Repository state

Previously verified on the same candidate:

```text
working tree clean
branch = feature/qb-12-durable-execution-ledger-restart-safety
HEAD = a05196d7302f3c2632dc5790673a97e338634d91
```

## Certified semantics

QB-12 certifies:

- SQLite-backed durable R2 request reservations,
- transactional reservation before provider invocation,
- WAL journal mode,
- `synchronous=FULL`,
- replay denial surviving process/runtime restart,
- request-id conflict detection surviving restart,
- persistent execution audit sequence,
- concurrent reservation serialization,
- dry-run remaining non-reserving,
- pending uncertain execution surviving restart,
- `provider_called = null` for a crash/uncertain pending state,
- timeout/unknown outcome remaining fail-closed and replay-protected.

## Safety invariant

A durable request reservation is never silently released because a process restarted or because
provider outcome became uncertain.

A request left in `pending` is treated as unknown, not automatically failed and not automatically
safe to retry.

## Explicit limitations

QB-12 does not certify:

- distributed consensus across multiple hosts,
- remote/shared database consensus,
- automatic reconciliation of pending outcomes,
- operator recovery workflow,
- release/reuse of historical request ids,
- arbitrary Blender Python,
- MHS actuation,
- physical hardware writes,
- production product integration.

Pending reconciliation/operator recovery is the scope of QB-13.

## Certification result

```text
QB-12 DURABLE EXECUTION LEDGER & RESTART SAFETY: CERTIFIED
regression = 62/62 PASS
live restart smoke = PASS
```

This certification freezes the QB-12 implementation candidate and permits the ORBI lab integration
branch to advance to the certification commit.

**QB-12: CERTIFIED.**
