# QB-13 — Durable Recovery & Reconciliation

Status: **IMPLEMENTATION CANDIDATE — LOCAL VALIDATION PENDING**

## Dependency status

QB-13 is built on top of the QB-12 implementation candidate:

- QB-12 candidate commit: `a05196d7302f3c2632dc5790673a97e338634d91`

QB-12 is not yet formally certified until its full 62-test regression gate is observed PASS.
QB-13 therefore remains dependent on QB-12 certification.

No ORBI production repository is modified.

## Purpose

QB-13 defines how ORBI handles a durable R2 execution left in `pending` after an unexpected process termination.

Central safety rule:

> An uncertain execution is never retried automatically and its original request id is never released.

Recovery is evidence-driven.

## Reconciliation model

Supported resolutions:

- `inconclusive`: evidence is persisted, reconciliation is non-final, and the execution remains pending.
- `applied`: read-back proves the intended effect exists; the execution becomes `reconciled-applied`.
- `not_applied`: read-back proves the intended effect does not exist; the execution becomes `reconciled-not-applied`.

In all three cases, the original request-id reservation remains intact. A later intentional execution requires a new request id.

## Durable reconciliation evidence

Implementation:

- `src/orbi_compat/recovery.py`
- `src/orbi_compat/sqlite_audit.py`

Each reconciliation record contains:

- reconciliation schema and sequence,
- original execution sequence,
- request id and request fingerprint,
- resolution,
- actor,
- structured evidence,
- SHA-256 of canonical evidence JSON,
- final/non-final flag,
- reservation-release flag,
- retry semantics.

Evidence must be deterministic non-empty JSON. Actor must be explicit and non-empty.

## Additive SQLite schema

QB-13 adds the `execution_reconciliation` table without changing the QB-12 execution-ledger schema version.

Compatibility remains:

    execution ledger schema = 1
    reconciliation schema   = 1

Existing QB-12 SQLite databases can therefore be opened and extended in place.

## Concurrency

Reconciliation uses `BEGIN IMMEDIATE`.

If two operators/processes concurrently attempt final reconciliation of the same pending execution, one final reconciliation wins and the other receives `ALREADY_RECONCILED`.

## Errors

- `PENDING_EXECUTION_NOT_FOUND`
- `ALREADY_RECONCILED`
- `RECONCILIATION_ERROR`

## Tests

New suite: `tests/test_orbi_qb13_reconciliation.py`

QB-13 adds 10 reconciliation tests covering additive schema, deterministic evidence hashing, invalid inputs, inconclusive evidence, later final resolution, permanent original-id reservation, persistence across restart, final immutability, missing-pending rejection, and concurrent final reconciliation.

QB-13 also adds an evidence-only operator utility:

- `scripts/orbi/qb13_recovery_tool.py`

The tool exposes only `pending`, `reconciliations`, and `reconcile`. It deliberately exposes no retry, release, execute, Blender, or provider command. Six dedicated tests verify its command surface, inline/file evidence handling, filtered history, and structured failure behavior.

Full regression target:

    QB-08: 13
    QB-09: 14
    QB-10: 13
    QB-11: 12
    QB-12: 10
    QB-13 reconciliation: 10
    QB-13 recovery tool:   6
    TOTAL: 78 passed

## Live Blender recovery smoke

Script: `scripts/orbi/qb13_live_reconciliation.py`

Case A simulates: durable reservation → Blender effect occurs → process crash before finalize → restart → live Blender read-back proves object exists → reconcile `applied` → same request id remains `REPLAY_DENIED`.

Case B simulates: durable reservation → no provider effect → process crash → restart → live Blender read-back proves object absent → reconcile `not_applied` → original id remains blocked → a new intentional request id may execute.

Required result:

    QB-13 LIVE DURABLE RECOVERY & RECONCILIATION: PASS

## Production boundary

QB-13 still does not authorize automatic retries of uncertain R2 operations, request-id release/reuse, automatic interpretation of provider state, arbitrary Blender Python, unregistered recipes, MHS actuation, distributed cross-host consensus, or production ORBI integration.

## Next recommended gate

After QB-12 and QB-13 are both certified:

**QB-14 — ORBI Scene3D Pilot Integration Contract**

Recommended scope: minimal consumer-facing `orbi.scene3d.v1` client, no Qwen imports in product repositories, durable-ledger configuration contract, recipe allowlist negotiation, read-only + governed execution modes, error/reconciliation surfacing, first controlled consumer ORBI Creative Studio, feature flag default OFF.

## Validation commands

    python -m pytest \
      tests/test_orbi_qb08_reference.py \
      tests/test_orbi_qb09_qwen_bridge.py \
      tests/test_orbi_qb10_governed_execution.py \
      tests/test_orbi_qb11_audit_replay.py \
      tests/test_orbi_qb12_durable_ledger.py \
      tests/test_orbi_qb13_reconciliation.py \
      tests/test_orbi_qb13_recovery_tool.py \
      -q

    python scripts/orbi/qb13_live_reconciliation.py

Then:

    git status
    git branch --show-current
    git rev-parse HEAD

QB-13 becomes certifiable only after QB-12 dependency is certified, 78/78 full regression tests pass, the live recovery/reconciliation smoke passes, and the working tree is clean.

**QB-13 status: IMPLEMENTATION CANDIDATE — awaiting dependency + local validation.**
