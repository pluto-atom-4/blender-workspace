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
| `control_pendulum_balance.py` | Installs a `frame_change_pre` PID handler that balances the chassis by driving the wheel-hinge motors. |
| `render_pendulum.py` | Rebuilds the rig headlessly, saves `pendulum.blend`, renders the default 3/4 preview. |
| `render_pendulum_front.py` | Front-view render (loads `pendulum.blend`). |
| `render_pendulum_side.py` | Side-view render (loads `pendulum.blend`). |
| `render_pendulum_top.py` | Top-view render (loads `pendulum.blend`). |

## Reference assets

- `blender-project/assets/hq720.jpg` — reference image used while modeling
  the Tamiya pendulum and the armed inverted pendulum (issue #21).

## Adding a new skill

1. Add `model_<subject>.py` to build and save the `.blend`.
2. Add one or more `render_<subject>[_<angle>].py` scripts to produce preview
   PNGs.
3. Update this table.
