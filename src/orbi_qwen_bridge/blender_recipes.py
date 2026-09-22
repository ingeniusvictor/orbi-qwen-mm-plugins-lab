"""Approved Blender recipes for QB-10 governed execution.

Only code compiled from validated, typed parameters may reach execute_blender_code.
No recipe in this registry performs network or filesystem access.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


@dataclass(frozen=True)
class CompiledRecipe:
    recipe_id: str
    version: str
    parameters: dict[str, Any]
    code: str
    code_sha256: str
    filesystem_scope: tuple[str, ...]
    network_allowed: bool

    def public_plan(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "version": self.version,
            "parameters": self.parameters,
            "code_sha256": self.code_sha256,
            "filesystem_scope": list(self.filesystem_scope),
            "network_allowed": self.network_allowed,
        }


def _name(value: Any) -> str:
    if not isinstance(value, str) or not _NAME_RE.fullmatch(value):
        raise ValueError("name must match [A-Za-z0-9_.-]{1,64}")
    return value


def _number(name: str, value: Any, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    value = float(value)
    if not low <= value <= high:
        raise ValueError(f"{name} must be within [{low}, {high}]")
    return value


def _vec3(name: str, value: Any, low: float, high: float) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise TypeError(f"{name} must be a 3-element list/tuple")
    return tuple(_number(f"{name}[{i}]", item, low, high) for i, item in enumerate(value))


def _compile(recipe_id: str, version: str, params: dict[str, Any], code: str) -> CompiledRecipe:
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return CompiledRecipe(
        recipe_id=recipe_id,
        version=version,
        parameters=params,
        code=code,
        code_sha256=digest,
        filesystem_scope=(),
        network_allowed=False,
    )


def compile_create_cube(parameters: dict[str, Any]) -> CompiledRecipe:
    allowed = {"name", "size", "location"}
    unknown = set(parameters) - allowed
    if unknown:
        raise ValueError(f"unknown parameter(s): {', '.join(sorted(unknown))}")

    name = _name(parameters.get("name", "ORBI_Cube"))
    size = _number("size", parameters.get("size", 2.0), 0.01, 1000.0)
    location = _vec3("location", parameters.get("location", [0.0, 0.0, 0.0]), -10000.0, 10000.0)

    normalized = {"name": name, "size": size, "location": list(location)}

    code = (
        "import bpy\n"
        f"name = {name!r}\n"
        f"size = {size!r}\n"
        f"location = {tuple(location)!r}\n"
        "existing = bpy.data.objects.get(name)\n"
        "if existing is not None:\n"
        "    bpy.data.objects.remove(existing, do_unlink=True)\n"
        "bpy.ops.mesh.primitive_cube_add(size=size, location=location)\n"
        "obj = bpy.context.active_object\n"
        "obj.name = name\n"
        "result = {'name': obj.name, 'type': obj.type, 'location': list(obj.location), "
        "'dimensions': list(obj.dimensions)}\n"
    )
    return _compile("orbi.blender.create_cube.v1", "1.0.0", normalized, code)


def compile_delete_object(parameters: dict[str, Any]) -> CompiledRecipe:
    allowed = {"name"}
    unknown = set(parameters) - allowed
    if unknown:
        raise ValueError(f"unknown parameter(s): {', '.join(sorted(unknown))}")

    name = _name(parameters.get("name"))
    normalized = {"name": name}

    code = (
        "import bpy\n"
        f"name = {name!r}\n"
        "obj = bpy.data.objects.get(name)\n"
        "deleted = obj is not None\n"
        "if obj is not None:\n"
        "    bpy.data.objects.remove(obj, do_unlink=True)\n"
        "result = {'name': name, 'deleted': deleted}\n"
    )
    return _compile("orbi.blender.delete_object.v1", "1.0.0", normalized, code)


_COMPILERS: dict[str, Callable[[dict[str, Any]], CompiledRecipe]] = {
    "orbi.blender.create_cube.v1": compile_create_cube,
    "orbi.blender.delete_object.v1": compile_delete_object,
}


def recipe_ids() -> tuple[str, ...]:
    return tuple(sorted(_COMPILERS))


def compile_recipe(recipe_id: str, parameters: dict[str, Any] | None = None) -> CompiledRecipe:
    if recipe_id not in _COMPILERS:
        raise LookupError(
            f"recipe {recipe_id!r} is not approved. Available: {', '.join(recipe_ids())}"
        )
    params = {} if parameters is None else parameters
    if not isinstance(params, dict):
        raise TypeError("parameters must be a dict")
    return _COMPILERS[recipe_id](params)
