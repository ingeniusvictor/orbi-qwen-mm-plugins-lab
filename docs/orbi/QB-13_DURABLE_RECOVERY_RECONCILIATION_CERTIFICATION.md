# QB-13 — Durable Recovery & Reconciliation Certification

Status: **CERTIFIED**

## Certified candidate

Branch:

```text
feature/qb-13-durable-recovery-reconciliation
```

Implementation candidate:

```text
19a07b3b043801acb65f5108d53023c497209cc0
```

## Certification evidence

### Full accumulated regression

Observed locally on the certified candidate:

```text
78 passed in 1.13s
```

The accumulated gate covers QB-08 through QB-13.

### Live durable recovery & reconciliation smoke

Observed locally on the same candidate:

```text
QB-13 LIVE DURABLE RECOVERY & RECONCILIATION: PASS
```

### Repository state

Verified on the same candidate:

```text
working tree clean
branch = feature/qb-13-durable-recovery-reconciliation
HEAD = 19a07b3b043801acb65f5108d53023c497209cc0
```

## Certified semantics

QB-13 certifies:

- durable discovery of pending/uncertain executions,
- explicit operator reconciliation outcomes:
  - `applied`,
  - `not_applied`,
  - `inconclusive`,
- deterministic reconciliation evidence,
- SHA-256 binding of reconciliation evidence,
- final reconciliation records for applied/not-applied outcomes,
- inconclusive outcomes remaining pending,
- original request ids remaining permanently reserved,
- no retry/release authority in the recovery inspection tool,
- applied effect detection through provider readback,
- not-applied detection through provider readback,
- intentional recovery requiring a fresh request id,
- replay denial after reconciliation.

## Safety invariant

Reconciliation is evidence-driven and fail-closed.

A pending execution is never converted into a retriable request merely because the process restarted.
An original request id is never released or reused after uncertainty or reconciliation.

## Explicit limitations

QB-13 does not certify:

- distributed consensus across hosts,
- remote shared-ledger arbitration,
- automatic external side-effect rollback,
- arbitrary provider-specific remediation,
- arbitrary Blender Python,
- MHS actuation,
- production product integration,
- automatic retry after reconciliation.

Scene3D product integration contract is the scope of QB-14.

## Certification result

```text
QB-13 DURABLE RECOVERY & RECONCILIATION: CERTIFIED
regression = 78/78 PASS
live reconciliation smoke = PASS
```

**QB-13: CERTIFIED.**
