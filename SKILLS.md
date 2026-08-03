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

## Reference assets

- `blender-project/assets/hq720.jpg` — reference image used while modeling
  the Tamiya pendulum and the armed inverted pendulum (issue #21).

## Adding a new skill

1. Add `model_<subject>.py` to build and save the `.blend`.
2. Add one or more `render_<subject>[_<angle>].py` scripts to produce preview
   PNGs.
3. Update this table.
