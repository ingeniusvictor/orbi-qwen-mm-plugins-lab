# QB-08 — ORBI Compatibility Reference Implementation

Status: **IMPLEMENTATION CANDIDATE — LOCAL VALIDATION PENDING**

## Purpose

QB-08 turns the QB-07 provider-neutral design into executable Python inside the laboratory repository.

No ORBI production repository is modified.

Parent certification:

- QB-07: `3c0e7aa08f87a53b16989bceb2638f7441b45ea4`

Branch:

- `feature/qb-08-orbi-compat-reference-implementation`

## Implemented package

```text
src/orbi_compat/
├── __init__.py
├── contracts.py
├── errors.py
├── policy.py
├── runtime.py
└── adapters/
    ├── __init__.py
    ├── base.py
    ├── _invoke.py
    ├── qwen_media.py
    ├── qwen_mhs_readonly.py
    └── qwen_scene3d_readonly.py
```

The package is included by setuptools as `orbi_compat*`.

## Reference envelopes

`OrbiRequest` defines the provider-neutral input envelope:

- interface
- operation
- request_id
- input
- confirm

`OrbiResponse` defines the normalized output envelope:

- ok
- request_id
- interface
- operation
- provider
- data
- provenance
- policy
- normalized error when applicable

Provider exceptions are normalized so ORBI consumers do not parse provider-specific error strings.

## Policy engine

`PolicyEngine` consumes the canonical QB-07 JSON contract.

It currently enforces:

- unknown operations rejected,
- R3 hardware actuation requires a certified adapter,
- R3 confirmation requirements,
- R4 external-provider operations disabled by default.

The provider adapter is not invoked when policy denies the request.

## Implemented provider facades

### Qwen Core media

ORBI interface:

```text
orbi.media.v1
```

Reference mappings:

- `media_info` → `media_info`
- `read_image` → `read_image`
- `read_video` → `read_video`
- `visualize` → `visualize`

The provider tool invoker is injected.

The ORBI module does not import a Qwen package directly.

### Qwen Blender read-only

ORBI interface:

```text
orbi.scene3d.v1
```

Mappings:

- `scene_info` → `get_scene_info`
- `object_info` → `get_object_info`
- `viewport_screenshot` → `get_viewport_screenshot`

`execute_recipe` is deliberately denied in the QB-08 reference adapter.

The future governed recipe executor needs its own registry and sandbox phase.

### Qwen MHS read-only

ORBI interface:

```text
orbi.hardware.v1
```

Mappings:

- `discover` → `mhs_discover`
- `meta` → `mhs_meta_info`
- `read` → `mhs_read`
- `health` → `mhs_health_check`

`write` and `reset` are deliberately denied by the reference adapter even when the caller supplies confirmation.

This creates defense in depth:

```text
ORBI policy gate
      ↓
read-only provider adapter
      ↓
provider
```

## Provider substitution

The runtime indexes adapters by ORBI interface, not provider name.

Therefore an alternate implementation can satisfy `orbi.media.v1` without changing an `OrbiRequest`.

The test suite includes an `orbi-native` fake media provider to prove provider substitution.

## Direct-import boundary

A source-level invariant test parses every Python module under:

```text
src/orbi_compat
```

and rejects direct imports beginning with:

```text
qwen_mm_plugins
```

Qwen-specific composition/imports, when introduced, must stay behind an explicit provider bridge rather than leak into product-facing modules.

## Deterministic validation

Reference suite:

```text
tests/test_orbi_qb08_reference.py
```

It verifies:

- request identity validation,
- media operation mapping,
- Blender execution denial,
- MHS write/reset denial,
- policy denial before provider invocation,
- external-provider default denial,
- retryable connection-error normalization,
- normalized successful response envelope,
- provider substitution,
- no direct Qwen imports,
- expected contract interfaces.

Deterministic smoke:

```text
scripts/orbi/qb08_reference_smoke.py
```

The smoke proves:

- allowed media read,
- allowed scene read,
- denied hardware actuation before provider invocation,
- denied Blender execution.

## Intentional boundary

QB-08 does not yet include:

- a live Qwen MCP composition bridge,
- a Blender governed recipe registry,
- real hardware adapters,
- any hardware writes,
- remote Omni provider enablement,
- production project integration,
- migration of existing ORBI APIs.

Those belong to later gates after the provider-neutral runtime itself passes.

## Local validation

Run:

```bash
python -m pytest tests/test_orbi_qb08_reference.py -q
python scripts/orbi/qb08_reference_smoke.py
```

Then verify:

```bash
git status
git branch --show-current
git rev-parse HEAD
```

QB-08 becomes certifiable only after both the test suite and deterministic smoke pass with a clean tree.

**QB-08 status: IMPLEMENTATION CANDIDATE — awaiting local validation.**
