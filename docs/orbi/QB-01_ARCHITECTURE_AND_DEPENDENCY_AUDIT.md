# QB-01 — Architecture & Dependency Audit

Status: **PASS**

## Scope

Audit the Qwen-MM-Plugins baseline frozen in QB-00 before installing or integrating any capability into ORBI projects.

Baseline:
- Upstream commit: `7f7ca380f2a21c3bea7239c132213e14c1c9abaf`
- Distribution: `1.1.9`
- Capability count: 14
- ORBI branch: `integration/orbi-lab`

No ORBI production project is modified by this phase.

## Architecture summary

Qwen-MM-Plugins is a modular Agent Skills + MCP platform.

Each capability is independently packaged as:
- a Skill directory,
- an optional MCP server,
- an optional Python extra in `pyproject.toml`,
- harness-specific plugin manifests.

The base Python runtime requires Python >= 3.10 and uses:
- `mcp>=1,<2`
- `anyio>=4,<5`
- `docstring-parser>=0.18,<0.19`
- `pydantic>=2.11,<3`
- `pillow<12`
- `openai>=1,<2`

`uv` / `uvx` is the intended dependency/runtime mechanism and installs capability dependencies into isolated caches.

## Windows execution boundary

The upstream installation guide states that Windows is currently supported through **Ubuntu WSL2 only**.

For runtime installation/testing:
- use Ubuntu WSL2,
- clone into the WSL home filesystem (for example `~/code`),
- do not execute the validated Linux install flow from `/mnt/c`,
- native Windows has not been validated upstream.

Therefore ORBI will use two roles:

1. **Windows canonical working copy**
   - `C:\ORBI CODEX\orbi-qwen-mm-plugins-lab`
   - Git/source review, version control, documentation and coordination.

2. **WSL2 runtime laboratory**
   - dedicated clone inside the Linux filesystem,
   - installation, dependency verification and MCP execution,
   - disposable/test-oriented environment.

## Capability dependency matrix

| Capability | Local without cloud key | Main extra dependencies / services | ORBI audit result |
|---|---:|---|---|
| `core` | Yes | Python viz stack; ffmpeg for video; LibreOffice/TeX/Chromium only for relevant formats | **Priority A** |
| `mhs` | Yes | `msgpack`; external/local HTTP adapters; bundled mock adapter | **Priority A** |
| `video-spatio` geometry | Yes | numpy, scipy, matplotlib, opencv-headless | **Priority A** |
| `video-spatio` VLM helpers | No/optional | OpenAI-compatible VL endpoint; DashScope or compatible endpoint | Priority B |
| `blender` | Yes for MCP client, but needs application | Running Blender + bundled addon; socket host/port | Priority B |
| `freecad` | Yes for MCP client, but needs application | Running FreeCAD + addon; XML-RPC host/port | Priority C |
| `api` | Usually no | DashScope / compatible services; HTTP; optional SAM3/ASR endpoints | Priority C |
| `search` | No | Serper, Tavily, Exa or Serply credentials | Low priority for ORBI |
| `video-memory` | No for builds | DashScope + ffmpeg; numpy/requests | Later |
| `omni-memory` | No for builds | Omni model endpoint + ffmpeg | Later |
| `video-edit` | No | DashScope generation + ffmpeg + Node for workflows | Later |
| `omni-video2note` | No | DashScope + ffmpeg + PDF stack | Later |
| `omni-chatcut` | No | Omni/generation services + ffmpeg/ffprobe; optional dubbing service | Later |
| `omni-skill-creator` | No | DashScope/OpenAI-compatible services + ffmpeg; numpy, PyYAML; optional tesseract workflow support | **Priority B** |
| `edu-agent` | Mostly local workflow, content-specific | Node + ffmpeg + headless Chromium; currently Chinese education oriented | Low priority |

## Priority capability findings

### 1. core — first runtime target

`core` provides:
- image reading,
- video metadata and frame extraction,
- PDF/document visualization,
- CSV/XLSX visualization,
- code/text inspection,
- 3D model visualization,
- GIS and notebook handling,
- crop and bounding-box annotation.

Default native mode (`QWEN_MM_NATIVE_MODE=1`) does not require a model API key.

Important system dependencies are format-specific. We do not need LibreOffice, TeX, Chromium, Blender or every visualization dependency to prove the basic runtime.

**QB decision:** validate a minimal local subset first.

### 2. mhs — ORBI hardware architecture candidate

MHS exposes one fixed six-tool surface:

1. `mhs_discover`
2. `mhs_meta_info`
3. `mhs_read`
4. `mhs_write`
5. `mhs_health_check`
6. `mhs_reset`

It does not call a cloud API. Hardware-specific logic stays outside the plugin in HTTP adapters.

The bundled mock adapter simulates:
- a camera,
- hard/soft safety limits,
- a lamp requiring confirmation.

This is suitable for proving the architecture without controlling real hardware.

MHS explicitly supports:
- host-side safety limits,
- confirmation-required writes,
- health checks,
- emergency stop,
- read-only adapter declarations.

**QB decision:** second runtime target, mock adapter only. No ORBI physical device integration yet.

### 3. video-spatio — local geometry candidate

The geometry layer is stateless and model-free. The host model provides:
- object boxes,
- depth estimates,
- camera motion estimates.

The tools perform geometry on those inputs.

No GPU perception server is required.

Local geometry dependencies:
- `numpy<3`
- `scipy`
- `matplotlib`
- `opencv-python-headless`

Some helper tools such as VLM-backed orientation/grounding checks can optionally use an OpenAI-compatible endpoint.

Important limitation: visual depth values are estimates, not calibrated measurements.

**QB decision:** validate geometry locally after core and MHS; do not treat it as metrology.

### 4. omni-skill-creator — strategically valuable but cloud-dependent

This capability can turn demonstration video into a reusable Agent Skill and includes multimodal asset/provenance workflows.

It requires external model inference for its intended workflow and is therefore not part of the first offline validation.

**QB decision:** preserve as a high-value ORBI knowledge-capture candidate, but test only after the local foundation is certified.

### 5. blender — ORBI Creative Studio candidate

The Blender MCP component is a thin client to a running Blender instance with the bundled addon.

It communicates through:
- default host: `localhost`
- default port: `9876`

Upstream auto-download/autolaunch behavior is Linux-x86_64-specific. Other environments may require an existing Blender installation.

**QB decision:** defer Blender until the basic MCP runtime is certified. Do not modify ORBI Creative Studio during this phase.

## Recommended validation order

### QB-02
**Core Isolated Runtime Validation**

Goal:
- create the WSL2 runtime clone,
- verify Python / uv / uvx,
- install only `core`,
- test local image/file/media operations,
- no cloud keys.

### QB-03
**MHS Mock Hardware Validation**

Goal:
- install only `mhs`,
- run bundled mock adapter,
- test all six MHS operations,
- verify safety-limit and confirmation behavior,
- no real hardware.

### QB-04
**Video-Spatio Local Geometry Validation**

Goal:
- test geometry-only tools,
- no VLM endpoint required,
- establish confidence/limitations for ORBI use.

### QB-05
**Omni Skill Creator Evaluation**

Cloud-enabled controlled test only after the local stack is certified.

### QB-06
**Blender Integration Evaluation**

Standalone Blender laboratory before any connection to ORBI Creative Studio.

### QB-07
**ORBI Compatibility Layer Design**

Only after the upstream capabilities have been individually validated.

## Security and integration rules

- Never install all capabilities by default.
- Never place production ORBI credentials into the lab.
- Keep `QWEN_MM_NATIVE_MODE=1` during local-first tests.
- Do not connect MHS to real hardware during QB-03.
- Do not interpret video-spatio visual depth as calibrated field measurement.
- Keep Qwen `main` pristine.
- Every ORBI modification belongs on `integration/orbi-lab` or a dedicated feature branch.
- Existing ORBI repositories remain unchanged until QB-07 or an explicitly approved integration phase.

## QB-01 certification

The repository architecture and dependency boundaries are sufficiently understood to begin isolated runtime testing.

The lowest-risk/highest-value first stack is:

```text
Qwen-MM Runtime Lab
        |
        +-- core          (local multimodal file/media tools)
        |
        +-- mhs           (mock hardware only)
        |
        +-- video-spatio  (local geometry subset)
```

Cloud-dependent Omni/generation capabilities and application integrations are intentionally deferred.

**QB-01 result: PASS — ARCHITECTURE AUDITED, RUNTIME BOUNDARY DEFINED**
