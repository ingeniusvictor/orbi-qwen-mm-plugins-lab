#!/usr/bin/env python3
"""QB-06 live Blender verification.

Requires:
- a running Blender 4.2.x session with the bundled blender-mcp addon
- BLENDER_HOST/BLENDER_PORT reachable (defaults 127.0.0.1:9876)

Validates:
- MCP initialize
- get_scene_info
- get_object_info for ORBI_QB06_Cube
- viewport screenshot returned as MCP ImageContent
- PNG persistence to /tmp/qb06_mcp_viewport.png
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = "src/capabilities/blender/qwen_mm_plugins_blender"
OUT = Path("/tmp/qb06_mcp_viewport.png")


def text_blocks(result) -> list[str]:
    return [
        block.text
        for block in result.content
        if getattr(block, "type", "") == "text"
    ]


async def main() -> None:
    OUT.unlink(missing_ok=True)

    env = dict(os.environ)
    env.setdefault("BLENDER_HOST", "127.0.0.1")
    env.setdefault("BLENDER_PORT", "9876")

    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            info = getattr(init, "serverInfo", None) or getattr(init, "server_info", None)

            print("=== MCP INITIALIZED ===")
            if info:
                print("Server:", getattr(info, "name", "unknown"))
                print("Version:", getattr(info, "version", "unknown"))

            print("\n=== SCENE INFO ===")
            scene = await session.call_tool("get_scene_info", {})
            scene_text = "\n".join(text_blocks(scene))
            print(scene_text)
            if "ORBI_QB06_Cube" not in scene_text:
                raise AssertionError("ORBI_QB06_Cube missing from scene")

            print("\n=== OBJECT INFO ===")
            obj = await session.call_tool(
                "get_object_info",
                {"object_name": "ORBI_QB06_Cube"},
            )
            obj_text = "\n".join(text_blocks(obj))
            print(obj_text)
            if "ORBI_QB06_Cube" not in obj_text or "MESH" not in obj_text:
                raise AssertionError("Object info did not confirm ORBI_QB06_Cube as MESH")

            print("\n=== VIEWPORT SCREENSHOT ===")
            shot = await session.call_tool(
                "get_viewport_screenshot",
                {"max_size": 800},
            )

            for line in text_blocks(shot):
                print(line)

            images = [
                block
                for block in shot.content
                if getattr(block, "type", "") == "image"
            ]
            print("Image blocks:", len(images))
            if not images:
                raise AssertionError("No MCP image block returned")

            raw = base64.b64decode(images[0].data)
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise AssertionError("Returned image is not PNG")
            if len(raw) <= 1000:
                raise AssertionError(f"PNG unexpectedly small: {len(raw)} bytes")

            OUT.write_bytes(raw)

            print("PNG bytes:", len(raw))
            print("Saved:", OUT)
            print("\nQB-06 MCP VIEWPORT SCREENSHOT: PASS")


if __name__ == "__main__":
    asyncio.run(main())
