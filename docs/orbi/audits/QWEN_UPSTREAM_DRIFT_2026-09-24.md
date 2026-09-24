# Qwen-MM-Plugins Upstream Drift Audit — 2026-09-24

Status: **NO REBASE RECOMMENDED BEFORE QB-15 CERTIFICATION**

## Baseline

Frozen upstream baseline used by the ORBI lab:

```text
7f7ca380f2a21c3bea7239c132213e14c1c9abaf
```

Observed upstream `main`:

```text
07736672525443c7f8a3f6405eed37d2236f023f
```

Relationship:

```text
upstream main is 7 commits ahead
ORBI frozen baseline is 0 commits ahead
```

## What changed upstream

The seven post-baseline commits are concentrated in:

- README/community badges,
- installation documentation,
- non-interactive installer support,
- unified installer configuration/headless actions,
- OpenAI-compatible endpoint credential resolution,
- tests for those changes.

The only changed runtime source file relevant beyond installer/docs is:

```text
src/shared/api_openai.py
```

## Runtime change

Upstream now allows `DASHSCOPE_BASE_URL` and `DASHSCOPE_API_KEY` to act as a generic
same-origin OpenAI-compatible endpoint pair.

The key point is the same-origin restriction: a custom base URL configured through
`DASHSCOPE_BASE_URL` may reuse `DASHSCOPE_API_KEY`, while arbitrary unrelated hosts do not
receive that key automatically.

This is potentially useful for future cloud/provider routing, but it does not affect the current
local Scene3D pilot path.

## Certified/pending ORBI path impact

No direct upstream changes were observed in:

- Core capability implementation,
- Blender capability implementation,
- MHS capability implementation,
- video-spatio implementation,
- `orbi_compat`,
- `orbi_qwen_bridge`,
- Scene3D sidecar transport.

The QB-12 → QB-15 pending certification stack therefore does not need to move merely because of
this upstream drift.

## Decision

```text
KEEP_FROZEN_BASELINE
```

Do not rebase or cherry-pick upstream changes before QB-15 is sealed.

Reasons:

1. QB-12 → QB-15 is already under explicit frozen-SHA validation.
2. Moving upstream now would invalidate/reopen part of that evidence chain.
3. No direct changes touch the current local Blender/Scene3D path.
4. Installer improvements are useful but non-essential to current certification.
5. The OpenAI-compatible endpoint fix is cloud-facing and can be evaluated independently later.

## Recommended revisit point

Re-evaluate upstream `main` only after:

```text
QB-12 certified
QB-13 certified
QB-14 contract certified
QB-15 sidecar certified
```

At that point create a fresh selective-adoption audit rather than rebasing blindly.

Machine-readable record:

```text
docs/orbi/audits/QWEN_UPSTREAM_DRIFT_2026-09-24.json
```

**Decision: preserve baseline 7f7ca380... until QB-15 certification.**
