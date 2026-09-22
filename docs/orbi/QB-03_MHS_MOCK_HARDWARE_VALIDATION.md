# QB-03 — MHS Mock Hardware Validation

Status: **PASS (runtime behavior validated; final local cleanup check pending)**

## Scope

Validate the Qwen-MM-Plugins `mhs` capability against the bundled mock adapter only.

No physical hardware was connected and no existing ORBI production repository was modified.

Baseline:

- Parent certification: QB-02
- Parent commit: `a026c5f7a164b2f3050a9a53d83aac0018f49e11`
- Validation branch: `feature/qb-03-mhs-mock-validation`
- MHS capability version: `1.1.0`

## Runtime architecture

The test exercised the real MHS host over MCP and the bundled HTTP + MessagePack mock adapter.

The configured mock adapter exposed:

- `mock/mock-camera`
- `mock/mock-lamp`

The MHS fixed tool surface was exercised end to end:

1. `mhs_discover`
2. `mhs_meta_info`
3. `mhs_read`
4. `mhs_write`
5. `mhs_health_check`
6. `mhs_reset`

## Discovery

`mhs_discover` returned both mock devices online.

### Camera

- device id: `mock/mock-camera`
- type: `camera`
- capabilities:
  - `frame`
  - `settings`
  - `temperature`

### Lamp

- device id: `mock/mock-lamp`
- type: `smart_light`
- capabilities:
  - `power`
  - `brightness`

## Metadata and declared safety

The mock camera metadata exposed:

- manufacturer: `Qwen-MM-Plugins`
- model: `MockCam-1`
- firmware: `0.1.0`

Declared limits:

| Parameter | Range | Type |
|---|---:|---|
| exposure | 1–100 ms | hard |
| gain | 0–32 dB recommended | soft |
| width | 8–512 px | hard |
| height | 8–512 px | hard |

The host surfaced the hard safety limits explicitly before writes.

## Read path

### Real image block from mock camera

A frame read was requested at 32 × 24.

Observed result:

```text
is_error: False
[IMAGE] mime=image/png base64_chars=2140
32x24 frame at exposure=40ms gain=0dB
```

This proves the adapter-to-host-to-MCP image path works end to end.

### Camera settings read

Initial values:

```text
exposure = 40
gain = 0
height = 64
width = 96
```

## Safe write and read-back

A permitted write set exposure to 75 ms.

Observed response:

```text
mock/mock-camera write 'settings': accepted
applied {'exposure': 75}
```

A subsequent read returned:

```text
exposure = 75
```

This proves that MHS was not merely returning canned acknowledgements; the simulated device state actually changed and could be read back.

## Hard safety limit enforcement

Attempt:

```text
exposure = 5000 ms
```

Result:

```text
Error: refused ... above the declared maximum 100 ms.
This is a hard safety limit ... and cannot be overridden.
```

The same request with:

```text
confirm = true
```

was also refused.

**Result:** PASS.

A hard safety limit cannot be bypassed by confirmation.

## Soft safety limit enforcement

Attempt:

```text
gain = 64 dB
```

Without confirmation:

```text
Error: refused ... above the declared maximum 32 dB.
This is a soft limit — pass confirm=true to proceed anyway
```

With `confirm=true`:

```text
mock/mock-camera write 'settings': accepted
applied {'gain': 64}
```

**Result:** PASS.

Soft limits require explicit confirmation before the host forwards the request.

## Consequential-write confirmation

The lamp declares `power` as requiring confirmation.

Without confirmation:

```text
Error: capability 'power' on mock/mock-lamp is marked as requiring confirmation.
```

With `confirm=true`:

```text
mock/mock-lamp write 'power': accepted
lamp on=True
```

**Result:** PASS.

The host blocks consequential writes unless explicitly confirmed.

## Health checks

A global health check reported both mock devices as online and healthy.

Camera:

```text
state: online
healthy: true
detail: simulated sensor responding
```

Lamp:

```text
state: online
healthy: true
detail: simulated lamp responding
```

**Result:** PASS.

## Reset and emergency stop

The mock camera accepted both:

- soft reset
- emergency stop

Observed:

```text
mock/mock-camera: soft reset completed. Device state: online.
mock/mock-camera: emergency stop completed. Device state: online.
```

The mock lamp intentionally does not implement reset.

Observed:

```text
Error: mock/mock-lamp does not implement reset (HTTP 405).
Reset is optional in MHS.
... this device cannot be stopped through the model.
```

This is the expected behavior and proves that unsupported emergency control is surfaced explicitly rather than falsely reported as successful.

## Safety conclusions

QB-03 demonstrated all three intended host-side safety classes:

```text
HARD LIMIT
unsafe request
    ↓
REFUSED
    ↓
confirm=true CANNOT override

SOFT LIMIT
out-of-recommended-range request
    ↓
without confirm → REFUSED
with confirm    → ACCEPTED

CONFIRMATION-REQUIRED ACTION
consequential write
    ↓
without confirm → REFUSED
with confirm    → ACCEPTED
```

The host performs these checks before a write is accepted by the adapter path.

## Boundary

This phase used only the bundled simulated devices.

Not authorized or validated by QB-03:

- physical cameras
- relays
- mobile devices
- ORBI Edge Mesh nodes
- photovoltaic plant equipment
- PLCs
- inverters
- trackers
- BESS equipment
- production home-automation devices

Any future real-hardware adapter must begin read-only, declare real limits from vendor documentation, expose consequential writes with confirmation, and pass adapter conformance checks before actuation.

## Standalone verifier note

The conversational runtime evidence captured here includes the complete MCP end-to-end behavior. The separate `qwen_mm_plugins_mhs.verify` console output was not included in the captured transcript, so this document does not claim an independently recorded verifier result.

That does not alter the observed end-to-end safety behavior above, but a future real-hardware adapter must pass the standalone verifier before registration.

## QB-03 certification

The bundled MHS mock architecture is functionally validated:

```text
MCP client
    ↓
Qwen MHS host
    ↓
host-side safety gate
    ↓
HTTP + MessagePack
    ↓
mock adapter
    ↓
simulated camera / lamp
```

**QB-03 runtime result: PASS — MHS MOCK HARDWARE AND SAFETY GATES VALIDATED**

Final local cleanup and Git integrity should be confirmed before merging this branch back into `integration/orbi-lab`.
