# QB-09 — Live Qwen Provider Bridge Certification

Status: **PASS — LIVE READ-ONLY QWEN PROVIDER BRIDGE CERTIFIED**

## Scope

QB-09 connects the certified ORBI-owned compatibility runtime to real local Qwen-MM-Plugins
capability registries while preserving the provider-neutral product boundary.

Parent certification:

- QB-08 certified commit: `ee31df8968a8f842529d4aca84e057f044dd0cf7`

Validated branch:

- `feature/qb-09-live-qwen-provider-bridge`

Validated candidate commit:

- `c4593aaa9d3ebf1cfbea0096c140f660ea512f20`

No ORBI production repository was modified.

## Certified architecture

```text
ORBI caller
    ↓
OrbiRequest
    ↓
PolicyEngine
    ↓
read-only ORBI adapter
    ↓
orbi_qwen_bridge
    ↓
real Qwen capability registry
    ↓
Core / MHS / Blender
```

The provider-neutral package `src/orbi_compat` remains free of direct
`qwen_mm_plugins_*` imports.

Provider-specific package knowledge is isolated inside:

```text
src/orbi_qwen_bridge
```

## Certified provider bridge

`QwenRegistryInvoker` was validated against the real capability registries for:

- `qwen_mm_plugins_core`
- `qwen_mm_plugins_mhs`
- `qwen_mm_plugins_blender`

The bridge uses each capability's real:

- `get_handler(name)`
- `list_tools()`
- `__version__`

and normalizes returned content into the ORBI response envelope.

## Content normalization

Certified provider content mappings include:

- text block → ORBI text block,
- image block → validated base64 ORBI image block,
- unknown provider block → preserved provider block.

Invalid image base64 is rejected.

Provider textual failure conventions such as:

```text
Error: ...
Error getting ...
Screenshot failed: ...
```

are normalized as provider failures rather than false-success responses.

## Unit/integration suite

Observed result:

```text
14 passed in 1.09s
```

The suite validated:

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
- Blender-style textual error → normalized provider failure,
- no direct Qwen imports in `orbi_compat`,
- Qwen provider package knowledge confined to `orbi_qwen_bridge`.

## Live Core bridge

Observed real provider registry:

```text
Provider package: qwen_mm_plugins_core
Provider version: 1.1.0
Tool count: 7
media_info present: True
```

A synthetic local WAV was generated and passed through:

```text
orbi.media.v1/media_info
    ↓
QwenCoreMediaAdapter
    ↓
QwenRegistryInvoker(core)
    ↓
real qwen_mm_plugins_core media_info handler
    ↓
ffprobe
```

Observed normalized response included:

- provider family: `qwen-mm-plugins`
- capability: `core`
- provider version: `1.1.0`
- policy class: `R0_READ_LOCAL`
- policy decision: `allow`
- WAV duration: approximately 0.25 s
- audio codec: `pcm_s16le`
- sample rate: `8000 Hz`
- channels: 1

Observed result:

```text
QB-09 LIVE CORE BRIDGE: PASS
```

## Live MHS bridge

The bundled official MHS mock adapter was started on an ephemeral localhost port.

A temporary MHS registry was used; the caller environment was restored afterward.

Validated through the ORBI compatibility layer:

- device discovery,
- health survey,
- mock camera image read,
- PNG normalization,
- 32×24 image response,
- MHS write denial.

No physical hardware was touched.

Observed result:

```text
QB-09 LIVE MHS READ-ONLY BRIDGE: PASS
```

## Live Blender bridge

The already-certified Blender 4.2.23 + bundled addon session remained reachable on:

```text
127.0.0.1:9876
```

Validated through the ORBI compatibility layer:

- real `scene_info` read,
- normalized provider response,
- `R0_READ_LOCAL` policy,
- Blender execution denial,
- second scene read to prove service stability.

The launch helper additionally confirmed:

```text
Blender MCP already listening on 127.0.0.1:9876 — nothing to do.
```

Observed result:

```text
QB-09 LIVE BLENDER READ-ONLY BRIDGE: PASS
```

## Read-only boundary remains enforced

QB-09 does NOT enable:

- MHS write,
- MHS reset,
- physical hardware actuation,
- arbitrary Blender Python,
- governed Blender recipes,
- remote Omni perception,
- production credentials,
- production ORBI integrations.

Provider composition therefore does not weaken the policy boundaries certified in QB-07/QB-08.

## Repository integrity

Validated candidate state before certification:

```text
branch: feature/qb-09-live-qwen-provider-bridge
HEAD: c4593aaa9d3ebf1cfbea0096c140f660ea512f20
working tree: clean
```

## Next phase

**QB-10 — Governed Capability Execution Layer**

Recommended scope:

- add an ORBI-approved recipe registry,
- implement controlled `execute_recipe` for Blender,
- typed recipe parameters,
- explicit filesystem scope,
- network denied by default,
- recipe provenance/versioning,
- dry-run/inspect mode,
- execution audit record,
- preserve MHS read-only boundary,
- no production repository integration.

**QB-09 result: PASS — LIVE READ-ONLY QWEN CORE, MHS, AND BLENDER PROVIDER BRIDGE CERTIFIED**
