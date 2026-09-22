# QB-06 — Blender Integration Evaluation

Status: **PASS — LIVE BLENDER INTEGRATION CERTIFIED**

## Scope

Evaluate the `blender` capability as a thin MCP client against a real Blender runtime, preserving a local-first test boundary and avoiding unnecessary cloud-provider dependencies.

Baseline:

- Parent certification: QB-05
- Parent integration commit: `f16528c9b04426eaf6f8d7acbc8d8be62cebd2d0`
- Validation branch: `feature/qb-06-blender-integration-evaluation`
- Blender capability version: `1.1.0`
- Qwen-MM-Plugins distribution: `1.1.9`
- Blender runtime: `4.2.23`
- Environment: Ubuntu under WSLg
- No production ORBI repository modified

## Phase A — client/protocol validation

The upstream Blender test suite was executed before provisioning a live Blender instance.

Initial result:

```text
10 passed in 7.12s
```

The suite validated:

- full advertised Blender MCP tool surface,
- schema/handler availability,
- graceful degradation with no Blender listener,
- stdio MCP initialize/list/call flow,
- persistent connection behavior,
- concurrent socket serialization,
- URL validation,
- stdout protection for MCP framing.

## Host shared-library preflight hardening

The official rootless Blender 4.2.23 Linux build downloaded successfully, but initially failed before GUI startup:

```text
error while loading shared libraries: libSM.so.6:
cannot open shared object file: No such file or directory
```

This exposed a launcher diagnostic gap: the launcher waited for the MCP port and reported a timeout even though Blender could never start.

QB-06 added an ELF shared-library preflight using `ldd`, allowing missing host libraries to fail immediately with an actionable diagnostic.

Relevant commits include:

- `4d255e1` — fail fast on missing host shared libraries
- `90060bf` — regression coverage for unresolved shared libraries

After installing the required host package, Blender 4.2.23 became launchable.

## WSLg Wayland instability and X11 fallback

With both WSLg display paths present:

```text
DISPLAY=:0
WAYLAND_DISPLAY=wayland-0
```

Blender 4.2.23 repeatedly terminated when allowed to auto-select the Wayland path.

A controlled A/B runtime test established:

```text
default / Wayland-auto path: Blender terminated
forced X11 through WSLg:      PASS — alive after observation interval
```

This isolated the failure below Qwen-MM-Plugins, MCP, and the bundled addon.

QB-06 therefore added a narrowly scoped GUI-environment hardening:

- only on Linux,
- only when WSL/WSLg is detected,
- only when both X11 and Wayland variables are present,
- clear `WAYLAND_DISPLAY` for the Blender child process,
- preserve `DISPLAY`,
- leave ordinary non-WSL Linux Wayland environments untouched.

Relevant commits:

- `ece26dc` — force X11 for WSLg GUI launches
- `f24ba13` — regression coverage for WSLg X11 fallback and non-WSL preservation

After hardening, the Blender regression suite reached:

```text
13 passed
```

## Live Blender session

The hardened launcher successfully started the real pinned Blender runtime:

```text
Blender 4.2.23
Blender MCP ready on 127.0.0.1:9876
```

A real live session then validated:

- TCP connectivity,
- `get_scene_info`,
- `execute_blender_code`,
- real scene mutation,
- object creation,
- post-mutation scene verification,
- persistent Blender process after tool execution.

The test object:

```text
ORBI_QB06_Cube
```

was created inside Blender and subsequently found in the live scene.

Observed result:

```text
QB-06 WSLg X11 LIVE SESSION: PASS
BLENDER MCP STILL ALIVE: PASS
```

## Viewport screenshot validation

The Blender addon was first tested directly to separate Blender/OpenGL capture behavior from MCP content conversion.

Direct result:

```text
QB-06 DIRECT VIEWPORT SCREENSHOT: PASS
```

A dedicated live MCP verifier was then added:

```text
scripts/orbi/qb06_live_blender_verify.py
```

Relevant commit:

- `493e90a` — dedicated QB-06 live Blender verifier

The verifier exercised:

1. MCP initialize,
2. `get_scene_info`,
3. `get_object_info` for `ORBI_QB06_Cube`,
4. `get_viewport_screenshot`,
5. MCP `ImageContent`,
6. PNG decode and persistence.

Final observed evidence:

```text
=== VIEWPORT SCREENSHOT ===
Image blocks: 1
PNG bytes: 246770
Saved: /tmp/qb06_mcp_viewport.png

QB-06 MCP VIEWPORT SCREENSHOT: PASS
```

File validation:

```text
PNG image data, 800 x 450, 8-bit/color RGBA, non-interlaced
241K
```

The Blender process remained alive after the live scene operations and screenshot capture.

## Security / dependency boundary

No DashScope key is required for the locally validated Blender operations.

QB-06 validates the local Blender/MCP path only:

```text
Qwen Blender MCP client
        ↓
local TCP 127.0.0.1:9876
        ↓
Blender 4.2.23
        ↓
bundled blender-mcp addon
        ↓
scene query / Python execution / viewport capture
```

Cloud asset providers such as Hyper3D, Sketchfab credentials, or Hunyuan services are outside this certification and were not required to prove the core ORBI-relevant Blender control path.

## ORBI applicability

The validated local Blender bridge is a strong candidate for selective ORBI use in:

- ORBI Creative Studio — controlled scene/model generation and refinement,
- ORBI Dash — repeatable 3D asset and scene workflows,
- ORBI Academy — procedural demonstrations and visual learning assets.

The recommended ORBI architecture is not to bind production components directly to Qwen-specific APIs. QB-07 will define an ORBI-owned compatibility/adapter layer so Blender is exposed through stable ORBI contracts and can remain provider-swappable.

## Repository integrity

Final validated feature state before certification:

```text
branch: feature/qb-06-blender-integration-evaluation
working tree: clean
validated head before certification:
493e90a9422bdbf9aa8118f1e2076c0cb97902c5
```

## Certification summary

Validated:

- Blender capability 1.1.0: PASS
- MCP client/protocol surface: PASS
- host-library preflight: PASS
- shared-library diagnostic hardening: PASS
- WSLg Wayland failure isolation: PASS
- automatic WSLg → X11 fallback: PASS
- Blender 4.2.23 real runtime: PASS
- live TCP/MCP session: PASS
- scene query: PASS
- arbitrary Blender Python execution: PASS
- real scene mutation: PASS
- object verification: PASS
- direct viewport capture: PASS
- MCP image-block viewport capture: PASS
- Blender process stability after live operations: PASS
- repository integrity: PASS

**QB-06 result: PASS — LIVE BLENDER INTEGRATION CERTIFIED**
