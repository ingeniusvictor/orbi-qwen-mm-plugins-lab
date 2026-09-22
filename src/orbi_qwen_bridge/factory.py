"""Composition helpers for provider-neutral ORBI runtimes backed by live Qwen registries."""

from __future__ import annotations

from pathlib import Path

from orbi_compat import OrbiRuntime, PolicyEngine
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


def build_governed_blender_runtime(contract_path: str | Path) -> OrbiRuntime:
    """Build an ORBI runtime that enables only approved QB-10 Blender recipes.

    The public operation remains `orbi.scene3d.v1/execute_recipe`; arbitrary Python is never
    accepted from the caller. MHS is not included and remains read-only in its separate factory.
    """
    return OrbiRuntime(
        PolicyEngine.from_file(contract_path),
        [QwenBlenderGovernedAdapter(QwenRegistryInvoker("blender"))],
        sandboxed_execution_enabled=True,
    )
