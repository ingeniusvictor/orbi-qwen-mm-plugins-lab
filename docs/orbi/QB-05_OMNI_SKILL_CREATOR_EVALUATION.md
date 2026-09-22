# QB-05 — Omni Skill Creator Evaluation

Status: **PASS (local authoring pipeline certified; remote AV perception explicitly deferred)**

## Scope

Evaluate the `omni-skill-creator` capability with a local-first policy.

QB-05 intentionally separates two layers:

1. the local authoring, media, validation and transport infrastructure;
2. remote audiovisual perception through `read_native_av`.

The first layer is certified by this phase. The second requires an external multimodal endpoint and is explicitly deferred rather than treated as an implicit dependency of the local result.

Baseline:

- Parent certification: QB-04
- Parent integration commit: `f3318189b37edc618bfaea2fd5fa7e5e6069773e`
- Validation branch: `feature/qb-05-omni-skill-creator-evaluation`
- Omni Skill Creator capability version: `1.0.1`
- No production ORBI repository modified
- No DashScope/OpenAI credential configured during local certification

## Runtime/system readiness

Observed:

```text
Omni Skill Creator version: 1.0.1

ffmpeg: PASS
tesseract: MISSING (optional)
DASHSCOPE_API_KEY: MISSING (intentional)
```

FFmpeg/ffprobe were already certified during QB-02 and are sufficient for the local media operations exercised here.

Tesseract is optional and was intentionally not installed merely to make the check fully green.

## Offline unit and transport tests

Executed:

```text
python -m pytest \
  tests/test_omni_skill_creator_tools.py \
  tests/test_omni_skill_creator_stream.py \
  -q
```

Observed:

```text
58 passed in 3.07s
```

The SSE/transport suite was also executed separately:

```text
python -m pytest tests/test_omni_skill_creator_stream.py -q
```

Observed:

```text
19 passed in 0.40s
```

These tests exercise the real local code paths with mocked/isolated external transport and no live provider dependency.

**Result: PASS.**

## Local end-to-end authoring fixture

A deterministic six-second synthetic MP4 was generated locally with:

- 320 × 240 test pattern
- 10 fps
- H.264 video
- AAC audio
- 440 Hz synthetic tone

The fixture was used to exercise the capability over MCP.

Validated local tools included:

- `get_video_metadata`
- `create_storyboard`
- `extract_clip`
- `extract_audio_clip`
- `validate_skill`

The generated Agent Skill contained:

- `SKILL.md`
- source provenance
- SHA-256 source fingerprint
- `.build/video_events.md`
- `.build/media_plan.md`
- generated storyboard
- video clip
- audio clip
- `asset_manifest.json`
- `evals/evals.json`

No remote model call was required.

## Positive structural validation

The synthetic skill was passed through `validate_skill`.

Required result:

```text
status: pass
errors: 0
```

The local pipeline completed successfully:

```text
QB-05 LOCAL AUTHORING PIPELINE: PASS
```

This proves that the capability can locally construct and validate a source-grounded Agent Skill artifact with real media assets and provenance.

## Security negative test

A copy of the valid synthetic skill was deliberately modified to add:

```yaml
allowed-tools: Bash
```

The validator rejected it.

Observed:

```text
=== SECURITY NEGATIVE TEST ===
status: fail
#5 Unexpected frontmatter key(s): allowed-tools.
#12 Forbidden frontmatter key(s): allowedtools.
```

This is the expected behavior.

The test proves that the validator does not silently permit a generated skill to self-grant tool access.

**Result: PASS.**

## Security and provenance properties demonstrated

QB-05 locally validated that generated skills can be checked for:

- frontmatter structure and naming,
- source type and source path,
- provenance/status fields,
- SHA-256 source identity,
- forbidden capability-granting metadata,
- local markdown link integrity,
- asset manifest consistency,
- asset file existence,
- asset naming conventions,
- source timestamps for video-derived assets,
- orphaned assets,
- media-plan/asset discipline,
- eval artifact presence.

The negative `allowed-tools` test demonstrates that security checks are active, not documentation-only.

## Remote audiovisual perception boundary

`read_native_av` is architecturally different from the local media/validation tools.

Its intended full perception path requires an external OpenAI-compatible Omni endpoint, typically configured through:

- `DASHSCOPE_BASE_URL`
- `DASHSCOPE_API_KEY`
- `QWEN_MM_API_OMNI_MODEL`

No credential was configured during QB-05 local certification.

The transport implementation itself was validated offline through the 19 passing SSE tests, including:

- content/reasoning streaming,
- usage accounting,
- transient retry behavior,
- terminal authentication/quota failures,
- partial-output handling,
- provider error classification,
- bounded retries.

Therefore QB-05 certifies the **local authoring architecture and provider transport behavior**, but does not claim that an external Omni provider produced a correct semantic event log from a real video.

That distinction is intentional.

## ORBI applicability

The local pipeline is strategically relevant to ORBI because it can support controlled conversion of demonstrations into reusable procedural knowledge.

Potential future mappings include:

- ORBI Academy: tutorial-to-skill conversion,
- L.U.M.I.A.: learning repeatable user workflows from demonstrations,
- ORBI PVMetrics: preserving operational/commissioning procedures as reusable skills,
- ORBI Creative Studio: capturing repeatable production workflows,
- ORBI Edge/field workflows: packaging visual procedures with provenance.

However, video-derived skills should remain `source-grounded` until their operational behavior is actually executed and verified.

## Repository integrity

Final local state before certification:

```text
On branch feature/qb-05-omni-skill-creator-evaluation
Your branch is up to date with 'origin/feature/qb-05-omni-skill-creator-evaluation'.

nothing to commit, working tree clean

HEAD:
f3318189b37edc618bfaea2fd5fa7e5e6069773e
```

All generated fixtures were kept under `/tmp` and removed after validation.

## QB-05 certification

Certified local path:

```text
synthetic teaching video
        ↓
ffprobe metadata
        ↓
storyboard / clip / audio extraction
        ↓
SKILL.md + provenance
        ↓
asset manifest + eval artifact
        ↓
validate_skill
        ├── valid skill → PASS
        └── forbidden tool grant → FAIL
```

Evidence:

- capability startup/version: PASS
- FFmpeg readiness: PASS
- optional OCR dependency intentionally deferred
- offline tool/transport suite: **58 passed**
- SSE suite: **19 passed**
- local media extraction: PASS
- positive Agent Skill validation: PASS
- security negative validation: PASS
- repository integrity: CLEAN
- live remote Omni semantic perception: DEFERRED

**QB-05 result: PASS — OMNI SKILL CREATOR LOCAL AUTHORING, VALIDATION, MEDIA, AND SECURITY PIPELINE CERTIFIED**

A future live-provider subphase may certify `read_native_av` semantic perception independently without changing this local result.
