# QB-08 — ORBI Compatibility Reference Implementation Certification

Status: **PASS — PROVIDER-NEUTRAL REFERENCE RUNTIME CERTIFIED**

## Scope

QB-08 turns the QB-07 compatibility contract into executable Python inside the ORBI Qwen-MM-Plugins laboratory.

Parent certification:

- QB-07 certified commit: `3c0e7aa08f87a53b16989bceb2638f7441b45ea4`

Validated branch:

- `feature/qb-08-orbi-compat-reference-implementation`

Validated candidate commit:

- `c6e3e52aa2ff973949d9f2b6f6dd86a451ea0867`

No ORBI production repository was modified.

## Certified implementation

Package:

```text
src/orbi_compat/
```

Certified components:

- provider-neutral `OrbiRequest`
- normalized `OrbiResponse`
- normalized error model
- contract-backed `PolicyEngine`
- `OrbiRuntime`
- Qwen Core media facade
- read-only Qwen MHS facade
- read-only Qwen Blender facade
- provider-invoker injection boundary

The package is included by setuptools as `orbi_compat*`.

## Certified architectural properties

QB-08 proves:

- ORBI product-facing modules do not directly import `qwen_mm_plugins_*`.
- Provider-specific tool invocation is injected behind the adapter boundary.
- Allowed reads pass through the policy/runtime envelope.
- MHS write/reset remain denied by the reference adapter.
- Uncertified hardware actuation is denied before provider invocation.
- Blender arbitrary execution is not exposed by the read-only reference adapter.
- External-provider semantic perception remains disabled by default.
- Provider connection failures normalize to a retryable ORBI error.
- A non-Qwen `orbi-native` implementation can replace the media provider without changing `OrbiRequest`.
- Direct script execution bootstraps `src/` without relying on ambient `PYTHONPATH`.

## Local validation evidence

Reference suite:

```text
............. [100%]
13 passed in 0.10s
```

Deterministic smoke:

```text
QB-08 REFERENCE SMOKE: PASS
```

Repository integrity:

```text
On branch feature/qb-08-orbi-compat-reference-implementation
nothing to commit, working tree clean
HEAD:
c6e3e52aa2ff973949d9f2b6f6dd86a451ea0867
```

## Security boundary

The certified implementation remains intentionally conservative.

Not enabled:

- physical hardware actuation,
- MHS write/reset,
- arbitrary Blender Python,
- remote Omni providers,
- production credentials,
- production ORBI repository integration.

## Next phase

**QB-09 — Live Qwen Provider Bridge**

Scope:

- compose real Qwen capability packages behind the ORBI adapter invoker boundary,
- validate live local Core operations,
- validate live Blender read path through `orbi.scene3d.v1`,
- validate MHS read path against the mock adapter,
- normalize real provider content blocks,
- prove ORBI call sites remain provider-neutral,
- keep writes/actuation disabled.

**QB-08 result: PASS — PROVIDER-NEUTRAL REFERENCE RUNTIME AND POLICY BOUNDARY CERTIFIED**
