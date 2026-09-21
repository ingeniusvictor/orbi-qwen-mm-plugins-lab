# QB-00 — Upstream Acquisition & Baseline Certification

Status: **FROZEN**

## Purpose

Establish the immutable starting point for ORBI evaluation of Qwen-MM-Plugins before any ORBI-specific adaptation or integration.

## Repository topology

- Upstream: `QwenLM/Qwen-MM-Plugins`
- ORBI fork: `ingeniusvictor/orbi-qwen-mm-plugins-lab`
- Upstream default branch: `main`
- ORBI integration branch: `integration/orbi-lab`

## Certified upstream baseline

- Baseline date: 2026-09-20
- Upstream commit: `7f7ca380f2a21c3bea7239c132213e14c1c9abaf`
- Upstream commit title: `Merge pull request #67 from QwenLM/feat/add_video_spatio`
- Distribution version at baseline: `1.1.9`
- Capability count at baseline: `14`

### Capabilities present at baseline

1. `core`
2. `api`
3. `search`
4. `video-memory`
5. `omni-memory`
6. `video-edit`
7. `blender`
8. `freecad`
9. `edu-agent`
10. `omni-video2note`
11. `omni-chatcut`
12. `omni-skill-creator`
13. `mhs`
14. `video-spatio`

## ORBI change policy

- `main` remains an upstream-tracking branch and must not receive ORBI feature changes.
- ORBI experiments begin on `integration/orbi-lab`.
- Existing ORBI projects are not modified during QB-00.
- No production integration with L.U.M.I.A., ORBI Creative Studio, ORBI Edge Mesh, ORBI PVMetrics, or ORBI News is authorized by this baseline.
- Every future ORBI adaptation must be traceable to a dedicated QB phase and commit.

## Initial evaluation order

1. QB-01 — Architecture & dependency audit
2. QB-02 — Core isolated validation
3. QB-03 — MHS mock-hardware validation
4. QB-04 — Omni Skill Creator evaluation
5. QB-05 — Video Spatio evaluation
6. QB-06 — Blender integration evaluation
7. QB-07 — ORBI compatibility layer design

## Certification

The ORBI fork was created from the upstream commit listed above with no ORBI source modifications.

This document is the first ORBI-only change and marks the beginning of controlled experimentation.

**QB-00 result: PASS — UPSTREAM BASELINE ACQUIRED AND FROZEN**
