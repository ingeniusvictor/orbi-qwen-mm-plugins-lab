"""Composition helpers for provider-neutral ORBI runtimes backed by live Qwen registries."""

from __future__ import annotations

from pathlib import Path

from orbi_compat import OrbiRuntime, PolicyEngine, SQLiteReplayLedger
from orbi_compat.adapters import (
    QwenBlenderReadOnlyAdapter,
    QwenCoreMediaAdapter,
    QwenMHSReadOnlyAdapter,
)

from .blender_governed import QwenBlenderGovernedAdapter
from .registry import QwenRegistryInvoker


def build_readonly_qwen_runtime(
    contract_path: str | Path,
    *,
    core: bool = True,
    blender: bool = False,
    mhs: bool = False,
) -> OrbiRuntime:
    """Build a read-only ORBI runtime using real Qwen capability registries.

    Actuation remains unavailable because the QB-08 MHS and Blender adapters are read-only.
    """
    adapters = []

    if core:
        adapters.append(QwenCoreMediaAdapter(QwenRegistryInvoker("core")))
    if blender:
        adapters.append(QwenBlenderReadOnlyAdapter(QwenRegistryInvoker("blender")))
    if mhs:
        adapters.append(QwenMHSReadOnlyAdapter(QwenRegistryInvoker("mhs")))

    return OrbiRuntime(
        PolicyEngine.from_file(contract_path),
        adapters,
    )


def build_governed_blender_runtime(
    contract_path: str | Path,
    *,
    durable_ledger_path: str | Path | None = None,
) -> OrbiRuntime:
    """Build an ORBI runtime that enables only approved governed Blender recipes.

    When `durable_ledger_path` is provided, R2 replay reservations and audit receipts survive
    runtime/process restart through the QB-12 SQLite ledger. Without it, the certified QB-11
    session-local ledger remains the default.
    """
    ledger = (
        SQLiteReplayLedger(durable_ledger_path)
        if durable_ledger_path is not None
        else None
    )
    return OrbiRuntime(
        PolicyEngine.from_file(contract_path),
        [QwenBlenderGovernedAdapter(QwenRegistryInvoker("blender"))],
        sandboxed_execution_enabled=True,
        replay_ledger=ledger,
    )
