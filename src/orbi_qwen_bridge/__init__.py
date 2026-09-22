"""Live Qwen-MM-Plugins composition bridge for ORBI compatibility adapters."""

from .blender_recipes import CompiledRecipe, compile_recipe, recipe_ids
from .factory import build_governed_blender_runtime, build_readonly_qwen_runtime
from .registry import QwenRegistryInvoker, normalize_content_blocks

__all__ = [
    "CompiledRecipe",
    "QwenRegistryInvoker",
    "normalize_content_blocks",
    "compile_recipe",
    "recipe_ids",
    "build_readonly_qwen_runtime",
    "build_governed_blender_runtime",
]
