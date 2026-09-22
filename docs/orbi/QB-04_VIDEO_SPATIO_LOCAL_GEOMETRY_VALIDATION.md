# QB-04 — Video-Spatio Local Geometry Validation

Status: **PASS**

## Scope

Validate the local/model-free geometry path of the Qwen-MM-Plugins `video-spatio` capability in the ORBI WSL2 laboratory.

This phase intentionally excludes remote VLM inference and does not configure DashScope, OpenAI, or any other cloud model endpoint.

Baseline:

- Parent certification: QB-03
- Parent integration commit: `806c81a492269b8dd5b240e3f3939f67cccd66fa`
- Validation branch: `feature/qb-04-video-spatio-local-geometry`
- Video-Spatio capability version: `1.0.0`
- Python runtime: isolated ORBI `.venv` on WSL2

No existing ORBI production repository was modified.

## Runtime boundary

The capability reports no system-tool dependency for its model-free path.

The validated geometry workflow is driven by host-supplied observations:

- image/frame paths,
- grounded object boxes,
- estimated object depths,
- estimated camera motion.

The capability performs geometry over those inputs. It does not independently measure depth, infer calibrated camera motion, or provide metrology.

The following VLM-backed tools were intentionally excluded from the offline certification:

- `orient_facing`
- `verify_grounding`

## MCP surface

The server initialized successfully over MCP:

```text
Server: qwen_mm_plugins_video_spatio
Version: 1.0.0
```

The server advertised the expected 19-tool surface:

1. `assess_coverage`
2. `assess_reachable`
3. `build_scene`
4. `calibrate_scale`
5. `camera_motion`
6. `count_objects`
7. `match_entities`
8. `mobile_manip`
9. `motion`
10. `object_world_motion`
11. `orient_facing`
12. `plan_exploration`
13. `render_scene_views`
14. `scene_map`
15. `select_keyframes`
16. `triangulate`
17. `verify_grounding`
18. `view_reason`
19. `visualize_bev`

## Deterministic synthetic geometry

QB-04 used two generated 1600 × 1200 RGB frames and a known synthetic scene.

Ground truth:

- camera 0 position: `[0, 0]`
- camera 1 position: `[2, 0]`
- camera movement: 2 m right
- yaw: 0°
- target: stationary `chair`
- target world position: approximately `[0, -5.495]` m
- view from camera 0: 0° bearing
- view from camera 1: approximately -20° bearing

No remote perception was used. The object boxes, depths, and camera motion were supplied deterministically.

## build_scene

`build_scene` succeeded:

```text
is_error: False
Built scene: 2 frame(s), 2 instance(s), 1600x1200, FOV=60°, cameras=camera_motions.
```

The generated scene contained:

- schema: `video-spatio/scene@1`
- focal length: approximately `1385.640646`
- principal point: `[800, 600]`
- camera 0 position: `[0.0, 0.0]`
- camera 1 position: `[2.0, 0.0]`
- camera 1 movement vector: `[2.0, 0.0]`

**Result: PASS.**

## camera_motion

Observed:

```json
{
  "translation_m": {
    "right": 2.0,
    "forward": 0.0,
    "distance": 2.0
  },
  "rotation_deg": {
    "yaw": 0.0,
    "pitch": 0.0
  },
  "dominant_translation": "right",
  "dominant_rotation": "none"
}
```

The result exactly matched the synthetic ground truth.

**Result: PASS.**

## triangulate

Observed:

```json
{
  "label": "chair",
  "world_xz": [-0.0, -5.495],
  "depth_from_a": 5.495,
  "depth_from_b": 5.8476,
  "baseline_m": 2.0,
  "triangulation_angle_deg": 20.0,
  "reliable": true
}
```

The recovered position matches the known synthetic geometry within the expected rounding tolerance.

The 2 m baseline and 20° triangulation angle were classified as reliable.

**Result: PASS.**

## object_world_motion

The camera moved 2 m while the target remained stationary.

Initial observed geometry correctly returned:

```json
{
  "pos_a": [0.0, -5.495],
  "pos_b": [0.0, -5.495],
  "displacement_m": 0.0,
  "move_vec": [0.0, -0.0],
  "is_moving": false,
  "camera_moved_m": 2.0
}
```

This proves the world-motion calculation removed camera ego-motion correctly.

### Semantic inconsistency discovered during QB-04

Although displacement was zero and `is_moving` was false, the upstream implementation still computed an 8-way direction from `atan2(0, 0)`, producing a spurious direction label.

The geometry was correct; the output semantics were inconsistent.

### ORBI lab hardening patch

The QB-04 branch changes stationary results to:

```json
{
  "displacement_m": 0.0,
  "direction": "stationary",
  "is_moving": false
}
```

Patch commit:

```text
ca85ce16bf6f381021c9a77452f597b6da062f1d
fix(video-spatio): report stationary world motion consistently
```

Regression-test commit:

```text
56e9418ddc73fd531dc58703a499843fe8ee42cd
test(video-spatio): cover stationary world-motion direction
```

This is an ORBI laboratory hardening change. The upstream-tracking `main` branch remains pristine.

## visualize_bev

The scene rendered successfully through `visualize_bev`.

Observed:

```text
is_error: False
BEV rendered — camera 0.
max |camera pitch|=0°
BEV image 1: 49576 base64 chars
TOTAL BEV IMAGES: 1
```

This proves the local scene-to-BEV rendering path produces an actual PNG image block over MCP.

**Result: PASS.**

## Stationary regression verification

After the ORBI hardening patch, the dedicated stationary regression completed successfully:

```text
QB-04 STATIONARY REGRESSION: PASS
```

The regression verifies:

- `displacement_m == 0.0`
- `is_moving is False`
- `direction == "stationary"`

## Full Video-Spatio test suite

The complete capability test file was executed after the patch:

```text
python -m pytest tests/test_video_spatio.py -q
................................................. [100%]
49 passed in 20.22s
```

**Result: 49 PASS / 0 FAIL.**

This confirms the stationary-direction hardening did not regress the existing Video-Spatio contract.

## Repository integrity

Final local state:

```text
On branch feature/qb-04-video-spatio-local-geometry
Your branch is up to date with 'origin/feature/qb-04-video-spatio-local-geometry'.

nothing to commit, working tree clean

HEAD:
56e9418ddc73fd531dc58703a499843fe8ee42cd
```

## Important limitations for ORBI

QB-04 validates geometry math, not independent perception accuracy.

For future ORBI use:

- bounding boxes remain only as accurate as the perception source,
- `depth_m` is an estimate unless supplied by calibrated sensing,
- camera motion is an estimate unless supplied by a trusted pose source,
- BEV is derived from those same estimates and is not independent evidence,
- visual depth must not be presented as calibrated field measurement,
- triangulation requires a real baseline and suitable ray geometry,
- large pitch and uncertain correspondence reduce reliability.

For photovoltaic inspection, robotics, and maintenance use, Video-Spatio should therefore be treated as a reasoning/scene-geometry layer rather than a metrology instrument.

## QB-04 certification

The local Video-Spatio geometry path is validated:

```text
host-supplied boxes/depth/motion
        ↓
build_scene
        ↓
common world frame
        ├── camera_motion
        ├── triangulate
        ├── object_world_motion
        └── visualize_bev
```

Evidence:

- MCP initialization: PASS
- 19-tool surface: PASS
- scene construction: PASS
- camera motion ground truth: PASS
- reliable triangulation: PASS
- camera ego-motion removal: PASS
- BEV rendering: PASS
- stationary semantic regression: PASS
- full Video-Spatio suite: **49 passed**
- repository integrity: CLEAN

**QB-04 result: PASS — VIDEO-SPATIO LOCAL GEOMETRY VALIDATED AND STATIONARY-MOTION OUTPUT HARDENED**
