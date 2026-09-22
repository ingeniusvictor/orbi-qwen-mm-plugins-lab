# QB-09 — Live Qwen Provider Bridge

Status: **IMPLEMENTATION CANDIDATE — LOCAL LIVE VALIDATION PENDING**

## Purpose

QB-09 connects the certified provider-neutral ORBI compatibility runtime to the real local
Qwen-MM-Plugins capability registries while preserving the ORBI-owned API boundary.

Parent certification:

- QB-08 certified commit: `ee31df8968a8f842529d4aca84e057f044dd0cf7`

Branch:

- `feature/qb-09-live-qwen-provider-bridge`

No ORBI production repository is modified.

## Architecture

```text
ORBI caller
    ↓
orbi_compat OrbiRequest
    ↓
PolicyEngine
    ↓
read-only ORBI adapter
    ↓
orbi_qwen_bridge
    ↓
real Qwen capability get_handler()/list_tools()
    ↓
local provider implementation
```

The provider-specific package names live only in:

```text
src/orbi_qwen_bridge/
```

The provider-neutral package:

```text
src/orbi_compat/
```

continues to contain no direct `qwen_mm_plugins_*` imports.

## Live provider registry bridge

`QwenRegistryInvoker` dynamically composes a capability package and validates that it exposes:

- `get_handler(name)`
- `list_tools()`
- `__version__`

Supported QB-09 capabilities:

- `core`
- `mhs`
- `blender`

The registry bridge invokes the real Qwen handler directly and normalizes content into ORBI-friendly
blocks.

## Content normalization

Raw Qwen content:

```json
{"type": "text", "text": "..."}
```

becomes:

```json
{"kind": "text", "text": "..."}
```

Raw images become:

```json
{
  "kind": "image",
  "mime_type": "image/png",
  "data_base64": "..."
}
```

Image base64 is validated before crossing the provider boundary.

Unknown block types are preserved as provider blocks rather than silently dropped.

## Error normalization

Some Qwen handlers communicate expected failures as textual content blocks rather than Python
exceptions.

QB-09 recognizes the selected provider error conventions, including:

- `Error: ...`
- `Error getting ...`
- `Screenshot failed: ...`

and raises a provider failure at the bridge boundary.

The ORBI runtime then returns:

```text
ok = false
error.code = PROVIDER_FAILURE
```

This prevents false-success envelopes.

## Read-only composition factory

`build_readonly_qwen_runtime(...)` can compose any combination of:

- Qwen Core → `orbi.media.v1`
- Qwen Blender → `orbi.scene3d.v1`
- Qwen MHS → `orbi.hardware.v1`

The existing QB-08 adapters remain read-only:

- MHS `write` and `reset`: denied
- Blender `execute_recipe`: denied

Therefore provider composition does not weaken QB-07/QB-08 policy.

## Deterministic/unit validation

Suite:

```text
tests/test_orbi_qb09_qwen_bridge.py
```

It validates:

- text normalization,
- image normalization,
- invalid image rejection,
- unknown provider-block preservation,
- unsupported capability rejection,
- live Core registry discovery,
- live MHS registry discovery,
- live Blender registry discovery,
- read-only runtime factory,
- all-three-capability composition,
- missing Core file → normalized provider failure,
- Blender-style text error → normalized provider failure,
- no direct Qwen imports in `orbi_compat`,
- Qwen package knowledge confined to `orbi_qwen_bridge`.

Expected result:

```text
14 passed
```

## Live Core smoke

Script:

```text
scripts/orbi/qb09_live_core_bridge.py
```

It generates a small WAV with Python stdlib and performs:

```text
OrbiRequest(orbi.media.v1/media_info)
    ↓
QwenCoreMediaAdapter
    ↓
QwenRegistryInvoker(core)
    ↓
real qwen_mm_plugins_core media_info handler
    ↓
ffprobe
    ↓
normalized OrbiResponse
```

No cloud key is required.

Required result:

```text
QB-09 LIVE CORE BRIDGE: PASS
```

## Live MHS smoke

Script:

```text
scripts/orbi/qb09_live_mhs_bridge.py
```

The script:

1. starts the bundled official MHS mock adapter on an ephemeral localhost port,
2. creates a temporary `QWEN_MM_MHS_DEVICES` registry,
3. calls ORBI `discover`,
4. calls ORBI `health`,
5. reads a real 32×24 PNG frame through MHS,
6. verifies the ORBI image normalization,
7. verifies ORBI `write` is denied,
8. restores the caller environment,
9. shuts the mock server down.

No physical hardware is touched.

Required result:

```text
QB-09 LIVE MHS READ-ONLY BRIDGE: PASS
```

## Live Blender smoke

Script:

```text
scripts/orbi/qb09_live_blender_bridge.py
```

Requires the already-certified Blender + bundled addon session.

The script:

1. composes the real Blender Qwen registry,
2. performs `orbi.scene3d.v1/scene_info`,
3. verifies the returned live scene,
4. verifies `execute_recipe` remains denied,
5. performs a second live scene read to prove stability.

Required result:

```text
QB-09 LIVE BLENDER READ-ONLY BRIDGE: PASS
```

## Production boundary

QB-09 still does not authorize:

- physical hardware writes,
- MHS reset,
- arbitrary Blender Python from ORBI,
- governed Blender recipes,
- cloud Omni perception,
- production credentials,
- production ORBI project integration.

## Validation commands

From repository root:

```bash
python -m pytest tests/test_orbi_qb09_qwen_bridge.py -q
python scripts/orbi/qb09_live_core_bridge.py
python scripts/orbi/qb09_live_mhs_bridge.py
python scripts/orbi/qb09_live_blender_bridge.py
```

Then verify:

```bash
git status
git branch --show-current
git rev-parse HEAD
```

QB-09 becomes certifiable after:

- 14/14 bridge tests pass,
- Core live smoke passes,
- MHS mock live smoke passes,
- Blender live read-only smoke passes,
- working tree is clean.

**QB-09 status: IMPLEMENTATION CANDIDATE — awaiting local live validation.**
