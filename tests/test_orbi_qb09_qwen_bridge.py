from __future__ import annotations

import ast
import base64
from pathlib import Path

import pytest

from orbi_compat import OrbiRequest
from orbi_qwen_bridge import QwenRegistryInvoker, normalize_content_blocks
from orbi_qwen_bridge.factory import build_readonly_qwen_runtime

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


def test_normalize_text_block():
    assert normalize_content_blocks([{"type": "text", "text": "hello"}]) == [
        {"kind": "text", "text": "hello"}
    ]


def test_normalize_image_block():
    raw = b"fake-image-bytes"
    encoded = base64.b64encode(raw).decode("ascii")

    result = normalize_content_blocks(
        [{"type": "image", "data": encoded, "mimeType": "image/png"}]
    )

    assert result == [
        {
            "kind": "image",
            "mime_type": "image/png",
            "data_base64": encoded,
        }
    ]


def test_normalize_rejects_invalid_image_base64():
    with pytest.raises(ValueError):
        normalize_content_blocks(
            [{"type": "image", "data": "not base64 !", "mimeType": "image/png"}]
        )


def test_normalize_preserves_unknown_provider_block():
    result = normalize_content_blocks([{"type": "resource", "uri": "file:///tmp/a"}])

    assert result == [
        {
            "kind": "provider-block",
            "provider_type": "resource",
            "value": {"type": "resource", "uri": "file:///tmp/a"},
        }
    ]


def test_registry_rejects_unknown_capability():
    with pytest.raises(ValueError):
        QwenRegistryInvoker("does-not-exist")


def test_core_registry_exposes_media_info():
    bridge = QwenRegistryInvoker("core")

    assert bridge.version == "1.1.0"
    assert bridge.has_tool("media_info") is True


def test_readonly_factory_builds_core_runtime():
    runtime = build_readonly_qwen_runtime(CONTRACT, core=True, blender=False, mhs=False)

    assert "orbi.media.v1" in runtime.adapters
    assert "orbi.scene3d.v1" not in runtime.adapters
    assert "orbi.hardware.v1" not in runtime.adapters


def test_live_bridge_missing_file_becomes_normalized_failure():
    runtime = build_readonly_qwen_runtime(CONTRACT, core=True, blender=False, mhs=False)

    response = runtime.execute(
        OrbiRequest(
            interface="orbi.media.v1",
            operation="media_info",
            request_id="missing-media",
            input={"path": "/definitely/not/here/qb09.mp4"},
        )
    )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "PROVIDER_FAILURE"
    assert "file not found" in response.error.message.lower()


def test_orbi_compat_still_contains_no_qwen_imports():
    offenders = []
    root = ROOT / "src/orbi_compat"

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("qwen_mm_plugins"):
                        offenders.append((path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("qwen_mm_plugins"):
                    offenders.append((path, module))

    assert offenders == []


def test_qwen_provider_knowledge_is_confined_to_bridge_package():
    compat_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/orbi_compat").rglob("*.py")
    )
    bridge_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/orbi_qwen_bridge").rglob("*.py")
    )

    assert "qwen_mm_plugins_core" not in compat_text
    assert "qwen_mm_plugins_mhs" not in compat_text
    assert "qwen_mm_plugins_blender" not in compat_text

    assert "qwen_mm_plugins_core" in bridge_text
    assert "qwen_mm_plugins_mhs" in bridge_text
    assert "qwen_mm_plugins_blender" in bridge_text


def test_registry_normalizes_blender_style_text_error(monkeypatch):
    bridge = QwenRegistryInvoker("blender")

    monkeypatch.setattr(
        bridge.package,
        "get_handler",
        lambda name: (lambda payload: [{"type": "text", "text": "Error getting scene info: offline"}]),
    )

    with pytest.raises(Exception) as exc:
        bridge("get_scene_info", {})

    assert "Error getting scene info: offline" in str(exc.value)
