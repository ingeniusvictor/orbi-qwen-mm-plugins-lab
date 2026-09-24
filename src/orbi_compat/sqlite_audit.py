"""SQLite-backed durable execution ledger for governed ORBI R2 operations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .audit import ExecutionReceipt, ExecutionToken, request_fingerprint
from .contracts import OrbiRequest, ProviderInfo
from .errors import (
    AlreadyReconciled,
    PendingExecutionNotFound,
    ReplayDenied,
    RequestIdConflict,
)
from .recovery import ReconciliationRecord, normalize_reconciliation_input


_SCHEMA = """
CREATE TABLE IF NOT EXISTS orbi_schema (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    request_id TEXT PRIMARY KEY,
    request_fingerprint TEXT NOT NULL,
    interface TEXT NOT NULL,
    operation TEXT NOT NULL,
    risk_class TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_audit (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    interface TEXT NOT NULL,
    operation TEXT NOT NULL,
    risk_class TEXT NOT NULL,
    outcome TEXT NOT NULL,
    provider_called INTEGER,
    provider_family TEXT,
    provider_capability TEXT,
    provider_version TEXT,
    replay_reserved INTEGER NOT NULL,
    retry_semantics TEXT NOT NULL,
    error_code TEXT
);

CREATE TABLE IF NOT EXISTS execution_reconciliation (
    reconciliation_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_sequence INTEGER NOT NULL,
    request_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    resolution TEXT NOT NULL,
    actor TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL,
    final INTEGER NOT NULL,
    reservation_released INTEGER NOT NULL,
    retry_semantics TEXT NOT NULL
);
"""


class SQLiteReplayLedger:
    """Durable, process-restart-safe R2 replay ledger.

    Each non-dry-run request reservation and its initial pending audit row are committed atomically
    before provider execution. If the process terminates after `begin()`, a later process still
    sees both the request-id reservation and the pending/unknown execution attempt.
    """

    schema_version = "1"

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        # journal_mode=WAL is persistent at the database-file level. Do not renegotiate it on
        # every connection: two fresh ledger instances can otherwise race while both try to change
        # the journal mode before the busy handler can serialize normal writes.
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @staticmethod
    def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
        return "locked" in str(exc).lower()

    def _initialize(self) -> None:
        # Fresh processes/threads may construct the same ledger concurrently. WAL activation and
        # first-time schema creation are database-level operations, so retry only the transient
        # SQLITE_BUSY/locked case with a short bounded backoff. All other operational errors remain
        # fail-fast.
        attempts = 20
        for attempt in range(attempts):
            try:
                with self._connect() as conn:
                    mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
                    if mode is None or str(mode[0]).lower() != "wal":
                        raise RuntimeError(
                            f"ORBI execution ledger failed to enter WAL mode: "
                            f"{None if mode is None else mode[0]!r}"
                        )

                    conn.executescript(_SCHEMA)
                    conn.execute(
                        "INSERT OR IGNORE INTO orbi_schema(key, value) VALUES('schema_version', ?)",
                        (self.schema_version,),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO orbi_schema(key, value) "
                        "VALUES('reconciliation_schema_version', '1')"
                    )
                    row = conn.execute(
                        "SELECT value FROM orbi_schema WHERE key='schema_version'"
                    ).fetchone()
                    if row is None or row["value"] != self.schema_version:
                        raise RuntimeError(
                            f"unsupported ORBI execution ledger schema: "
                            f"{None if row is None else row['value']!r}"
                        )
                return
            except sqlite3.OperationalError as exc:
                if not self._is_locked_error(exc) or attempt == attempts - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))

    def begin(self, request: OrbiRequest, risk_class: str, *, dry_run: bool) -> ExecutionToken:
        fingerprint = request_fingerprint(request)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")

            if not dry_run:
                row = conn.execute(
                    "SELECT request_fingerprint FROM reservations WHERE request_id = ?",
                    (request.request_id,),
                ).fetchone()
                if row is not None:
                    conn.rollback()
                    if row["request_fingerprint"] == fingerprint:
                        raise ReplayDenied(
                            f"request_id {request.request_id!r} already reserved for this R2 execution"
                        )
                    raise RequestIdConflict(
                        f"request_id {request.request_id!r} was already used for a different R2 payload"
                    )

                conn.execute(
                    """
                    INSERT INTO reservations(
                        request_id, request_fingerprint, interface, operation, risk_class
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        request.request_id,
                        fingerprint,
                        request.interface,
                        request.operation,
                        risk_class,
                    ),
                )

            cursor = conn.execute(
                """
                INSERT INTO execution_audit(
                    request_id, request_fingerprint, interface, operation, risk_class,
                    outcome, provider_called, replay_reserved, retry_semantics
                ) VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
                """,
                (
                    request.request_id,
                    fingerprint,
                    request.interface,
                    request.operation,
                    risk_class,
                    0 if dry_run else 1,
                    "dry-run-repeatable" if dry_run else "new-request-id-required-after-execution-attempt",
                ),
            )
            sequence = int(cursor.lastrowid)
            conn.commit()
        finally:
            conn.close()

        return ExecutionToken(
            sequence=sequence,
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            interface=request.interface,
            operation=request.operation,
            risk_class=risk_class,
            replay_reserved=not dry_run,
        )

    def finalize(
        self,
        token: ExecutionToken,
        provider: ProviderInfo,
        *,
        outcome: str,
        provider_called: bool,
        error_code: str | None = None,
    ) -> ExecutionReceipt:
        retry_semantics = (
            "new-request-id-required-after-execution-attempt"
            if token.replay_reserved
            else "dry-run-repeatable"
        )
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE execution_audit
                SET outcome = ?,
                    provider_called = ?,
                    provider_family = ?,
                    provider_capability = ?,
                    provider_version = ?,
                    retry_semantics = ?,
                    error_code = ?
                WHERE sequence = ?
                  AND request_id = ?
                  AND request_fingerprint = ?
                """,
                (
                    outcome,
                    1 if provider_called else 0,
                    provider.family,
                    provider.capability,
                    provider.version,
                    retry_semantics,
                    error_code,
                    token.sequence,
                    token.request_id,
                    token.request_fingerprint,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"execution audit row {token.sequence} is missing or does not match its token"
                )

        return ExecutionReceipt(
            schema="orbi.execution-audit/v1",
            sequence=token.sequence,
            request_id=token.request_id,
            request_fingerprint=token.request_fingerprint,
            interface=token.interface,
            operation=token.operation,
            risk_class=token.risk_class,
            outcome=outcome,
            provider_called=provider_called,
            provider=provider.to_dict(),
            replay_reserved=token.replay_reserved,
            retry_semantics=retry_semantics,
            error_code=error_code,
        )

    def record_denial(
        self,
        request: OrbiRequest,
        provider: ProviderInfo,
        risk_class: str,
        *,
        error_code: str,
    ) -> ExecutionReceipt:
        fingerprint = request_fingerprint(request)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO execution_audit(
                    request_id, request_fingerprint, interface, operation, risk_class,
                    outcome, provider_called,
                    provider_family, provider_capability, provider_version,
                    replay_reserved, retry_semantics, error_code
                ) VALUES (?, ?, ?, ?, ?, 'replay-denied', 0, ?, ?, ?, 0,
                          'new-request-id-required', ?)
                """,
                (
                    request.request_id,
                    fingerprint,
                    request.interface,
                    request.operation,
                    risk_class,
                    provider.family,
                    provider.capability,
                    provider.version,
                    error_code,
                ),
            )
            sequence = int(cursor.lastrowid)

        return ExecutionReceipt(
            schema="orbi.execution-audit/v1",
            sequence=sequence,
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            interface=request.interface,
            operation=request.operation,
            risk_class=risk_class,
            outcome="replay-denied",
            provider_called=False,
            provider=provider.to_dict(),
            replay_reserved=False,
            retry_semantics="new-request-id-required",
            error_code=error_code,
        )

    def reconcile_pending(
        self,
        request_id: str,
        *,
        resolution: str,
        evidence: dict,
        actor: str,
    ) -> ReconciliationRecord:
        """Record evidence for an uncertain durable R2 execution.

        `inconclusive` records evidence but intentionally leaves the execution pending so a later
        read-back may resolve it. `applied` and `not_applied` are final for that execution row.

        The original request-id reservation is NEVER released. A later execution always requires a
        new request id, even when reconciliation concludes that the effect was not applied.
        """
        resolution, actor, evidence_json, evidence_sha256 = normalize_reconciliation_input(
            resolution=resolution,
            evidence=evidence,
            actor=actor,
        )
        final = resolution in {"applied", "not_applied"}
        retry_semantics = "original-request-id-remains-reserved;new-request-id-required"

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT sequence, request_id, request_fingerprint
                FROM execution_audit
                WHERE request_id = ?
                  AND replay_reserved = 1
                  AND outcome = 'pending'
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()

            if row is None:
                existing = conn.execute(
                    """
                    SELECT 1
                    FROM execution_reconciliation
                    WHERE request_id = ? AND final = 1
                    LIMIT 1
                    """,
                    (request_id,),
                ).fetchone()
                conn.rollback()
                if existing is not None:
                    raise AlreadyReconciled(
                        f"request_id {request_id!r} already has a final reconciliation"
                    )
                raise PendingExecutionNotFound(
                    f"request_id {request_id!r} has no pending durable R2 execution"
                )

            cursor = conn.execute(
                """
                INSERT INTO execution_reconciliation(
                    execution_sequence,
                    request_id,
                    request_fingerprint,
                    resolution,
                    actor,
                    evidence_json,
                    evidence_sha256,
                    final,
                    reservation_released,
                    retry_semantics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    int(row["sequence"]),
                    row["request_id"],
                    row["request_fingerprint"],
                    resolution,
                    actor,
                    evidence_json,
                    evidence_sha256,
                    1 if final else 0,
                    retry_semantics,
                ),
            )
            reconciliation_sequence = int(cursor.lastrowid)

            if final:
                update = conn.execute(
                    """
                    UPDATE execution_audit
                    SET outcome = ?,
                        retry_semantics = ?
                    WHERE sequence = ?
                      AND outcome = 'pending'
                    """,
                    (
                        f"reconciled-{resolution.replace('_', '-')}",
                        retry_semantics,
                        int(row["sequence"]),
                    ),
                )
                if update.rowcount != 1:
                    raise RuntimeError(
                        f"pending execution row {int(row['sequence'])} changed during reconciliation"
                    )

            conn.commit()
        finally:
            conn.close()

        import json

        return ReconciliationRecord(
            schema="orbi.execution-reconciliation/v1",
            reconciliation_sequence=reconciliation_sequence,
            execution_sequence=int(row["sequence"]),
            request_id=row["request_id"],
            request_fingerprint=row["request_fingerprint"],
            resolution=resolution,
            actor=actor,
            evidence=json.loads(evidence_json),
            evidence_sha256=evidence_sha256,
            final=final,
            reservation_released=False,
            retry_semantics=retry_semantics,
        )

    def reconciliations(self, request_id: str | None = None) -> tuple[ReconciliationRecord, ...]:
        import json

        with self._connect() as conn:
            if request_id is None:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM execution_reconciliation
                    ORDER BY reconciliation_sequence
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM execution_reconciliation
                    WHERE request_id = ?
                    ORDER BY reconciliation_sequence
                    """,
                    (request_id,),
                ).fetchall()

        return tuple(
            ReconciliationRecord(
                schema="orbi.execution-reconciliation/v1",
                reconciliation_sequence=int(row["reconciliation_sequence"]),
                execution_sequence=int(row["execution_sequence"]),
                request_id=row["request_id"],
                request_fingerprint=row["request_fingerprint"],
                resolution=row["resolution"],
                actor=row["actor"],
                evidence=json.loads(row["evidence_json"]),
                evidence_sha256=row["evidence_sha256"],
                final=bool(row["final"]),
                reservation_released=bool(row["reservation_released"]),
                retry_semantics=row["retry_semantics"],
            )
            for row in rows
        )

    def reconciliation_schema(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM orbi_schema WHERE key='reconciliation_schema_version'"
            ).fetchone()
        return row["value"]

    def receipts(self) -> tuple[ExecutionReceipt, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_audit ORDER BY sequence"
            ).fetchall()
        return tuple(self._row_to_receipt(row) for row in rows)

    def pending_receipts(self) -> tuple[ExecutionReceipt, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_audit WHERE outcome='pending' ORDER BY sequence"
            ).fetchall()
        return tuple(self._row_to_receipt(row) for row in rows)

    def is_reserved(self, request_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM reservations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return row is not None

    def schema(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM orbi_schema WHERE key='schema_version'"
            ).fetchone()
        return row["value"]

    @staticmethod
    def _row_to_receipt(row: sqlite3.Row) -> ExecutionReceipt:
        return ExecutionReceipt(
            schema="orbi.execution-audit/v1",
            sequence=int(row["sequence"]),
            request_id=row["request_id"],
            request_fingerprint=row["request_fingerprint"],
            interface=row["interface"],
            operation=row["operation"],
            risk_class=row["risk_class"],
            outcome=row["outcome"],
            provider_called=(
                None if row["provider_called"] is None else bool(row["provider_called"])
            ),
            provider={
                "family": row["provider_family"] or "",
                "capability": row["provider_capability"] or "",
                "version": row["provider_version"] or "",
            },
            replay_reserved=bool(row["replay_reserved"]),
            retry_semantics=row["retry_semantics"],
            error_code=row["error_code"],
        )
