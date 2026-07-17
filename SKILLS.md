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

## Reference assets

- `blender-project/assets/hq720.jpg` — reference image used while modeling
  the Tamiya pendulum.

## Adding a new skill

1. Add `model_<subject>.py` to build and save the `.blend`.
2. Add one or more `render_<subject>[_<angle>].py` scripts to produce preview
   PNGs.
3. Update this table.
