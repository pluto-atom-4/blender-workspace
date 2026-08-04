# Webots Physics Export & LQR Tuning (issue #28, Phase 1)

Trimmed Phase-1 slice of the Control & Physics Simulation + HIL pipeline
proposed in issue #28. Scope follows the architect-plan comment on that
issue (see the issue's comment history): Blender-to-Webots geometry export
plus a standalone LQR gain solver, nothing else. Explicitly **deferred**
to later PRs: LangGraph state-machine orchestration, the `langchain-openai`
"designer agent" node, PlatformIO/ESP32 firmware (Phase 3), the
hardware-in-the-loop bridge, CLI entry points, and the Dash dashboard (Phase
4). None of those are installed, wired up, or referenced by this PR.

## What this builds on

Reuses the armed inverted pendulum rig from issue #21
(`blender-project/scripts/model_pendulum.py`, full writeup in
[PENDULUM.md](PENDULUM.md)) rather than re-deriving geometry or dimensions.
All physical dimensions referenced below (chassis size, leg length, wheel
radius, Z-stack heights) come from that script's own computed constants,
converted from millimeters (the model's native units) to meters (Webots'
native units).

## Pipeline

```
model_pendulum.py (issue #21 rig)
        |
        v  (export_pendulum_to_webots.py, headless bpy)
physics/worlds/meshes/pendulum.obj + .mtl
        |
        v  (referenced by a Mesh node)
physics/worlds/pendulum_world.wbt  (Webots R2025a world)
        |
        v  (orchestration/lqr_tuner.py, subprocess)
LQR gain solve (scipy) -> Webots headless run -> telemetry parse -> iterate
```

## Blender -> Webots export

`blender-project/scripts/export_pendulum_to_webots.py` reuses
`model_pendulum.py` (via the same `exec(open(...).read())` pattern
`render_pendulum.py` already uses) to rebuild the full rig, then exports
every mesh object except `Ground_Plane` (the world file supplies its own
floor) to `blender-project/physics/worlds/meshes/pendulum.obj`.

**Format note:** the original plan (and issue #28's own pre-installation
notes) called for `bpy.ops.wm.collada_export` (`.dae`). This repo's system
Blender package (Debian's `blender` `4.3.2+dfsg-2`) does not ship a Collada
exporter -- `bpy.ops.wm.collada_export` raises `"operator ... could not be
found"` in this environment; `bpy.ops.wm` only exposes `obj_export`/
`ply_export`/`stl_export`, and `bpy.ops.export_scene` only `fbx`/`gltf`.
Webots' `Mesh` node accepts OBJ directly (confirmed against
`/usr/local/webots/resources/nodes/Mesh.wrl`: `"URL of a 3D file such as
DAE, STL, OBJ or FBX format"`), so the script exports OBJ instead --
functionally equivalent for this purpose, just a different container
format. `global_scale=0.001` in the `obj_export` call converts the model's
millimeter-scale coordinates to Webots' meters; the exporter's default
`forward_axis='NEGATIVE_Z'`/`up_axis='Y'` already matches Webots' Y-up
convention, so no extra rotation is applied in the world file.

The export only actually runs when `bpy.app.background` is true (same
guard `model_pendulum.py` itself uses for `save_as_mainfile`), so running
this script against a live GUI session by mistake is a no-op rather than a
silent overwrite.

## Webots world file

`blender-project/physics/worlds/pendulum_world.wbt` is a minimal but real,
loadable Webots R2025a world:

- `WorldInfo` + `Viewpoint` + `TexturedBackground`/`TexturedBackgroundLight`
  (via `EXTERNPROTO`) + `RectangleArena` floor.
- A single `Robot` node (`DEF ARMED_INVERTED_PENDULUM`) whose `Shape` wraps
  a `Mesh` node pointing at `meshes/pendulum.obj`.
- `Gyro` and `Accelerometer` child nodes, named exactly `"gyro"` and
  `"accelerometer"` per `feat-idea.md`'s sensor-naming convention.
- A coarse placeholder `boundingObject` (a box sized to the chassis plate
  footprint, `CHASSIS_WIDTH x CHASSIS_DEPTH x CHASSIS_THICKNESS` from
  `model_pendulum.py`, converted mm -> m) and a `Physics` node with
  `mass 0.15` (matching the chassis's own placeholder rigid-body mass in
  `model_pendulum.py` -- like that script, not sourced from a real BOM).
- `controller "<none>"` -- there is no Webots controller in this repo yet.
  See "What isn't validated end-to-end" below.

**Validated, not just written:** this world file was actually loaded with
the real `webots` R2025a binary in this environment
(`webots --batch --mode=fast --minimize --no-rendering pendulum_world.wbt`)
and loads cleanly (exit 0, no errors or warnings) once `pendulum.obj`
exists. Before the mesh existed, the same command surfaced a clear "Unable
to find resource" warning rather than crashing -- confirming the `Mesh`
node and file reference are both syntactically and semantically correct,
not just plausible-looking VRML97.

## LQR gain solver

`blender-project/orchestration/lqr_tuner.py`:

- **`solve_lqr_gain(A, B, Q, R)`** -- solves the continuous-time algebraic
  Riccati equation via `scipy.linalg.solve_continuous_are` and returns the
  optimal state-feedback gain `K` (`u = -Kx`), the Riccati solution `S`, and
  the closed-loop eigenvalues of `A - B@K`. Unit-tested against a
  closed-form scalar solution and cross-checked against the `control`
  package's own `control.lqr()` in
  `orchestration/tests/test_lqr_tuner.py`.
- **`pendulum_state_space()`** -- a linearized cart-pole approximation of
  the armed inverted pendulum (state `[cart_pos, cart_vel, tilt_angle,
  tilt_rate]`), parameterized by `PendulumParams`. This collapses the real
  two-leg, independently-hinged rig into the textbook single
  inverted-pendulum-on-a-cart model for a first LQR pass -- not a literal
  multi-body match. Mass figures mirror `model_pendulum.py`'s own
  placeholder rigid-body masses; pendulum length mirrors the model's
  `CHASSIS_Z_CENTER`.
- **`run_webots_headless(world_path, duration_s, telemetry_path, ...)`** --
  launches `webots --batch --mode=fast --minimize --stdout --stderr
  --no-rendering <world>` via `subprocess.Popen`, enforcing `duration_s`
  externally (`communicate(timeout=...)`, escalating `terminate()` ->
  `kill()`), then parses telemetry via `parse_telemetry()`.
- **`parse_telemetry(path)`** -- reads a CSV (or `.json` list-of-records)
  telemetry file with columns
  `time,gyro_x,gyro_y,gyro_z,accel_x,accel_y,accel_z,tilt_rad` into a
  pandas `DataFrame`. CSV was chosen over JSON as the primary format so a
  future controller can append one row per timestep without holding the
  whole run in memory.
- **`tune_lqr(A, B, Q0, R0, ...)`** -- a plain iteration loop (explicitly
  not a LangGraph state machine): solve the LQR gain, check the
  closed-loop stability margin (`-max(real(eigenvalues))`), and if it
  hasn't cleared `stability_margin` yet, scale up the tilt-angle cost term
  in `Q` and retry, up to `max_iterations`. Optionally (`run_webots=True`)
  also attempts a headless Webots run + telemetry parse per iteration, but
  convergence is gated on the analytic eigenvalues, not on telemetry (see
  below for why).

### What isn't validated end-to-end

`pendulum_world.wbt`'s `Robot` node has `controller "<none>"` -- there is
no Webots controller script in this repo (Python or otherwise) that reads
the `gyro`/`accelerometer` sensors and writes a telemetry file, and the
exported mesh is a single static `Shape` with no `HingeJoint`s (the real
rig's hip/wheel joints from `model_pendulum.py` aren't reproduced as
Webots joints). Writing that controller -- and a properly articulated
multi-body Webots robot matching the hinge-jointed rig -- is follow-up
work, not part of this trimmed Phase 1 PR.

Concretely, in this environment:

- `run_webots_headless()` **was** exercised end-to-end against the real
  `webots` binary and the real `pendulum_world.wbt` (confirmed by wall-clock
  timing: a `duration_s=5.0` call took ~5.7s, consistent with Webots
  actually running for the requested duration before being terminated).
- `parse_telemetry()` correctly reports "no telemetry file" in that case,
  since nothing produces one yet -- this is the expected result today, not
  a bug.
- `tune_lqr()`'s stability/convergence check is therefore based entirely on
  the analytic closed-loop eigenvalues of the linearized model, which is a
  legitimate, always-available control-theory stability check independent
  of whether Webots telemetry exists.

## Orchestration subproject

`blender-project/orchestration/` is an isolated `uv` subproject (own
`pyproject.toml`, own `uv.lock`), mirroring `blender-mcp/`'s pattern rather
than adding a monolithic root `pyproject.toml` -- keeps this PR's
dependency footprint (`numpy`, `scipy`, `control`, `pandas`, plus a `test`
group with `pytest`) isolated from `blender-mcp/`'s FastMCP server
dependencies. `requires-python = ">=3.12"`, matching the sibling
subproject. `uv sync --project blender-project/orchestration` (or `cd`
into it and `uv sync`) resolves cleanly.

## Running

```bash
# Export the mesh (via the blender-local-agent MCP tool, or directly):
blender --background --python-expr "exec(open('blender-project/scripts/export_pendulum_to_webots.py').read())"

# Validate the world loads (no controller, so it just idles until killed):
webots --batch --mode=fast --minimize --no-rendering blender-project/physics/worlds/pendulum_world.wbt

# LQR solver + tuning loop demo:
cd blender-project/orchestration
uv run python lqr_tuner.py

# Tests:
uv run --extra test pytest
```

## Known limitations / next steps

- No Webots controller yet -- `pendulum_world.wbt`'s `controller` is
  `"<none>"`. A follow-up PR needs a Python controller reading
  `gyro`/`accelerometer` and applying the LQR gain as wheel-drive torque,
  which in turn needs the exported model to have actual `HingeJoint`s
  (today it's one static mesh).
- `pendulum_state_space()`'s cart-pole model is a deliberate
  simplification of the real two-leg rig -- good enough for a first LQR
  pass, not a substitute for full multi-body dynamics.
- Mass/length parameters are placeholders (same caveat `PENDULUM.md` gives
  for `model_pendulum.py`'s rigid-body masses) -- not sourced from a real
  BOM.
- `pendulum_world.wbt`'s `boundingObject` is a coarse box around the
  chassis plate only, not a full hull of the legs/wheels -- fine for a
  first loadable world, not for contact-accurate simulation.
- LangGraph orchestration, `langchain-openai`, PlatformIO/ESP32 firmware,
  HIL, CLI entry points, and the Dash dashboard are all deferred -- see the
  architect-plan comment on issue #28 for the full phase breakdown.
