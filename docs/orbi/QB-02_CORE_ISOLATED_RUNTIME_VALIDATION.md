# QB-02 — Core Isolated Runtime Validation

Status: **PASS**

## Scope

Validate the Qwen-MM-Plugins `core` capability in an isolated Ubuntu WSL2 runtime without cloud credentials and without modifying any existing ORBI production repository.

Baseline entering this phase:

- ORBI repository: `ingeniusvictor/orbi-qwen-mm-plugins-lab`
- ORBI branch: `integration/orbi-lab`
- Pre-certification HEAD: `edadac560a790fd617435df573a726a20b9fe806`
- Upstream frozen baseline: `7f7ca380f2a21c3bea7239c132213e14c1c9abaf`
- Distribution baseline: `1.1.9`
- Core capability version: `1.1.0`

No ORBI production project was modified.

## Runtime host

QB-02 used the upstream-supported Windows execution boundary:

- Windows host with WSL2
- Ubuntu `26.04.1 LTS (Resolute Raccoon)`
- WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`
- Linux-native checkout: `/home/ingvmlp/code/orbi-qwen-mm-plugins-lab`
- Runtime checkout was not executed from `/mnt/c`

The Ubuntu system Python was `3.14.4`. Rather than forcing that interpreter, ORBI created an isolated `uv`-managed CPython environment using:

- CPython `3.13.15`
- virtual environment: `.venv`

This preserved the Ubuntu system Python and kept the Qwen runtime on a conservative supported interpreter line.

## Installation strategy

The upstream local-development path was used instead of `bash install.sh local`.

Only the `core` Python extra was installed into the isolated virtual environment.

The full marketplace/plugin installer was intentionally not used, avoiding absolute-path manifest rewrites during this validation.

## Core startup validation

Direct source execution succeeded:

```text
python src/capabilities/core/qwen_mm_plugins_core --version
1.1.0
```

The MCP server also initialized successfully through the official Python MCP client flow:

```text
ClientSession.initialize()
session.list_tools()
session.call_tool(...)
```

A raw `tools/list` request before initialization was rejected by the server as expected. The corrected initialized-client flow succeeded.

## System dependencies

Initial `--check-system` correctly reported that `ffmpeg/ffprobe` were missing for video/audio operations.

ORBI then installed Ubuntu's FFmpeg package:

- `ffmpeg 8.0.1-3ubuntu2`
- `ffprobe 8.0.1-3ubuntu2`

After installation:

```text
✓ read_video / media_info (video & audio) [core]
```

The following optional visualization dependencies remain intentionally deferred:

- Blender
- LibreOffice
- TeX / pdflatex
- Playwright Chromium

These are format-specific and were not required to certify the local core media path.

No `DASHSCOPE_API_KEY` was configured. This was intentional.

## Real local image test

A synthetic local image was generated and passed through the running MCP server with `read_image`.

Input:

- local temporary file
- 320 × 200 RGB image
- left half red
- right half blue
- no network or cloud dependency

MCP result:

```text
is_error: False
Image: /tmp/orbi-qb02-core-test.png | 200x320 → 416x640 (HxW)
Block 1: text
Block 2: image
image mime: image/jpeg
image base64 chars: 8380
```

This proves that the core server can:

- receive an MCP tool call,
- open a local image,
- apply model-oriented dynamic resizing,
- return a text summary,
- return an actual image content block.

The optimized output format is not required to preserve the source container format.

## Real local video test

A deterministic local MP4 fixture was generated with FFmpeg:

- duration: 3 seconds
- resolution: 160 × 120
- native rate: 10 fps
- H.264 / yuv420p
- 30 frames
- no audio

### media_info

The MCP `media_info` call succeeded:

```text
is_error: False
Container: mov,mp4,m4a,3gp,3g2,mj2
Duration: 3.00s
Video: h264 (High)
Resolution: 160x120
Frame rate: 10.00 fps
Frames: 30
Audio: none
```

### read_video

The MCP `read_video` call succeeded with:

- requested sampling: 1 fps
- maximum frames: 3
- budget: small

Observed result:

```text
is_error: False
Source: 3.0s | 160x120 (WxH) | 10.0 fps native
Sampled: 3 frames @ 1.0 fps | 0.0s–2.9s | 320x256 (WxH) per frame

Image block 1: 16320 base64 chars
Image block 2: 15680 base64 chars
Image block 3: 16500 base64 chars

TOTAL IMAGE BLOCKS: 3
```

This validates actual local frame extraction and MCP image-block delivery through the core streaming stdio server.

## Repository integrity

Before the certification commit, the WSL checkout remained clean:

```text
On branch integration/orbi-lab
Your branch is up to date with 'origin/integration/orbi-lab'.

nothing to commit, working tree clean
```

Pre-certification HEAD remained:

```text
edadac560a790fd617435df573a726a20b9fe806
```

The runtime experiment therefore introduced no path-specific installer edits, generated fixtures, or source changes into Git.

## Deferred items

QB-02 does not certify:

- Blender-backed 3D rendering
- LibreOffice document rendering
- LaTeX rendering
- HTML screenshots through Playwright Chromium
- cloud captioning or DashScope-backed behavior
- any other Qwen-MM capability

Those remain outside this phase.

## Security boundary

During QB-02:

- no production ORBI credential was added,
- no DashScope key was configured,
- no real hardware was connected,
- no existing ORBI repository was modified,
- the Windows canonical source copy and WSL runtime laboratory remained separate.

## QB-02 certification

The isolated WSL2 runtime has proven the complete local core path:

```text
Ubuntu WSL2
    ↓
uv-managed CPython 3.13
    ↓
isolated .venv
    ↓
Qwen-MM-Plugins core 1.1.0
    ↓
MCP initialize
    ↓
local image read
    ↓
FFmpeg / ffprobe
    ↓
local media metadata
    ↓
local video frame extraction
```

**QB-02 result: PASS — CORE ISOLATED RUNTIME VALIDATED**

Next controlled phase:

**QB-03 — MHS Mock Hardware Validation**

QB-03 must use the bundled mock adapter only. No physical ORBI device is authorized during that phase.
