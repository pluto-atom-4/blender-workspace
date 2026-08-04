# Skills / Automations

Inventory of the generative scripts currently in
`blender-project/scripts/`. Each is a standalone Blender Python automation
run through the `run_blender_python` MCP tool.

## Tamiya pendulum

| Script | Purpose |
|---|---|
| `model_tamiya_pendulum.py` | Builds the base pendulum model and saves `tamiya_pendulum.blend`. |
| `model_tamiya_pendulum_precise.py` | Higher-fidelity rebuild from precise reference measurements; saves `tamiya_pendulum_precise.blend`. |
| `render_tamiya_pendulum.py` | Default-angle preview render of the base model. |
| `render_tamiya_pendulum_front.py` | Front-view render of the base model. |
| `render_tamiya_pendulum_side.py` | Side-view render of the base model. |
| `render_tamiya_pendulum_top.py` | Top-view render of the base model. |
| `render_tamiya_pendulum_precise.py` | Default-angle preview render of the precise model. |
| `render_tamiya_pendulum_precise_front.py` | Front-view render of the precise model. |
| `render_tamiya_pendulum_precise_side.py` | Side-view render of the precise model. |

Outputs land in `blender-project/renders/` as `<subject>_preview[_<angle>].png`
alongside the source `.blend` file.

## Armed inverted pendulum (issue #21)

Two-wheel-leg self-balancing robot with STS3032 hip servos, XL330
wheel-actuator servos, rigid-body physics, and a PID balance controller.
Full writeup: [PENDULUM.md](PENDULUM.md).

| Script | Purpose |
|---|---|
| `model_pendulum.py` | Builds the chassis stack, hip/leg/wheel-actuator rig, rigid bodies, hinge constraints, and motorized wheel hinges. Live-only save skip via `bpy.app.background`. |
| `control_pendulum_balance.py` | Strips the (non-functional, see [PENDULUM.md](PENDULUM.md)) rigid-body motor setup, runs the PID balance law as a plain Python sim, and bakes the result to keyframes. |
| `render_pendulum.py` | Rebuilds the rig headlessly, saves `pendulum.blend`, renders the default 3/4 preview. |
| `render_pendulum_front.py` | Front-view render (loads `pendulum.blend`). |
| `render_pendulum_side.py` | Side-view render (loads `pendulum.blend`). |
| `render_pendulum_top.py` | Top-view render (loads `pendulum.blend`). |

## Dual-wheel legged balancing robot (issue #23)

XGO-style dual-wheel legged balancing robot: CNC-mm-accurate chassis,
STS3032 hip/knee servos, a 4-bar leg linkage, and a driven wheel, built
with direct FK keyframes on the hip/knee joints (live bone IK constraints
didn't re-solve under this Blender build's live/headless evaluation).
Full writeup: [LEGGED_ROBOT.md](LEGGED_ROBOT.md).

| Script | Purpose |
|---|---|
| `model_dual_wheel_legged_robot.py` | Builds the base chassis, servo, 4-bar leg linkage, and wheel rig; FK-keyframes an exploded-view assembly (frames 1-120) and balance/crouch/jump/land animation (frames 121-250). Headless-only save via `bpy.app.background`. |
| `model_dual_wheel_legged_robot_precise.py` | Higher-fidelity `_precise` variant: sandwich CNC chassis stack and true parallelogram 4-bar leg linkage, refined against reference photos of the real hardware. Kept as a separate script rather than overwriting the base model. |

There are no separate `render_dual_wheel_legged_robot*.py` scripts for
this feature — both model scripts persist their own `.blend` under
`blender-project/renders/` directly when run headless.

## Physics simulation & LQR tuning (issue #28)

Trimmed Phase-1 slice of the Webots + LQR control pipeline proposed in issue
#28: exports the existing armed inverted pendulum geometry (issue #21) into
a Webots world, and a standalone LQR gain solver/tuning loop against a
linearized pendulum-on-cart model. No LangGraph, ESP32/PlatformIO firmware,
HIL bridge, CLI entry points, or dashboard yet -- see [WEBOTS.md](WEBOTS.md)
for what's deferred and why. Full writeup: [WEBOTS.md](WEBOTS.md).

| Script/module | Tool | Purpose |
|---|---|---|
| `scripts/export_pendulum_to_webots.py` | `run_blender_python` (headless) | Rebuilds the armed inverted pendulum rig via `model_pendulum.py` and exports it to `physics/worlds/meshes/pendulum.obj` for Webots (OBJ, not DAE -- this system's Blender build has no Collada exporter; see the script's docstring). |
| `physics/worlds/pendulum_world.wbt` | `webots` | Minimal Webots world wrapping `pendulum.obj`, with `Gyro`/`Accelerometer` nodes named `"gyro"`/`"accelerometer"` per `feat-idea.md`'s convention. |
| `orchestration/lqr_tuner.py` | `uv run --project blender-project/orchestration python lqr_tuner.py` | `solve_lqr_gain()` (Riccati-equation LQR solve), `run_webots_headless()` + `parse_telemetry()` (subprocess wrapper around `webots`, CSV/JSON telemetry parse), and `tune_lqr()` (plain Q/R iteration loop, no LangGraph). |
| `orchestration/tests/test_lqr_tuner.py` | `uv run --project blender-project/orchestration pytest` | Unit tests for `solve_lqr_gain()` against closed-form and `control.lqr()`-cross-checked systems. No Webots-dependent test. |

`blender-project/orchestration/` is its own isolated `uv` subproject
(`pyproject.toml`, own `uv.lock`), mirroring `blender-mcp/`'s pattern rather
than a monolithic root environment.

## Reference assets

- `blender-project/assets/hq720.jpg` — reference image used while modeling
  the Tamiya pendulum and the armed inverted pendulum (issue #21).

## Adding a new skill

1. Add `model_<subject>.py` to build and save the `.blend`.
2. Add one or more `render_<subject>[_<angle>].py` scripts to produce preview
   PNGs.
3. Update this table.
