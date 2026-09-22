#!/usr/bin/env python3
"""QB-09 live Core bridge smoke: ORBI -> adapter -> live Qwen registry -> ffprobe."""

from __future__ import annotations

import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orbi_compat import OrbiRequest
from orbi_qwen_bridge import QwenRegistryInvoker, build_readonly_qwen_runtime

CONTRACT = ROOT / "docs/orbi/qb07/orbi_compatibility_contract.v1.json"


def write_test_wav(path: Path, *, seconds: float = 0.25, rate: int = 8000) -> None:
    samples = int(seconds * rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for n in range(samples):
            value = int(8000 * math.sin(2 * math.pi * 440 * n / rate))
            wav.writeframesraw(struct.pack("<h", value))


def main() -> int:
    bridge = QwenRegistryInvoker("core")

    print("=== QB-09 LIVE CORE REGISTRY ===")
    print("Provider package:", bridge.package_name)
    print("Provider version:", bridge.version)
    print("Tool count:", len(bridge.tool_names()))
    print("media_info present:", bridge.has_tool("media_info"))
    assert bridge.has_tool("media_info")

    runtime = build_readonly_qwen_runtime(
        CONTRACT,
        core=True,
        blender=False,
        mhs=False,
    )

    with tempfile.TemporaryDirectory(prefix="qb09-core-") as td:
        wav_path = Path(td) / "tone.wav"
        write_test_wav(wav_path)

        print("\n=== QB-09 ORBI REQUEST ===")
        print("Path:", wav_path)

        response = runtime.execute(
            OrbiRequest(
                interface="orbi.media.v1",
                operation="media_info",
                request_id="qb09-core-live",
                input={"path": str(wav_path)},
            )
        )

        print("\n=== QB-09 ORBI RESPONSE ===")
        print(response.to_dict())

        assert response.ok is True
        assert response.provider.family == "qwen-mm-plugins"
        assert response.provider.capability == "core"
        assert response.policy["risk_class"] == "R0_READ_LOCAL"
        assert response.policy["decision"] == "allow"
        assert isinstance(response.data, list)
        assert response.data
        assert response.data[0]["kind"] == "text"

        text = response.data[0]["text"]
        assert "Media:" in text
        assert "Audio stream" in text
        assert "8000 Hz" in text

    print("\nQB-09 LIVE CORE BRIDGE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
