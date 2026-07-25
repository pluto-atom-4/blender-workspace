---
name: render-multi-angle
description: Render an existing Tamiya pendulum Blender model from the default, front, side, and top camera angles, producing the standard set of preview PNGs in blender-project/renders/.
---

Runs the existing `render_<subject>[_<angle>].py` scripts for a given
subject (see [SKILLS.md](../../../SKILLS.md) for the current inventory,
e.g. `tamiya_pendulum` / `tamiya_pendulum_precise`) via the
`run_blender_python` MCP tool, one angle at a time:

1. `render_<subject>.py` — default angle
2. `render_<subject>_front.py` — front view
3. `render_<subject>_side.py` — side view
4. `render_<subject>_top.py` — top view

If an angle script doesn't exist yet for the requested subject, write it
following the pattern of the existing scripts for that subject rather than
skipping the angle.

## Verification

After running, confirm all four PNGs exist in `blender-project/renders/`
following the `<subject>_preview[_<angle>].png` naming convention and are
non-trivial in size — a script exiting 0 doesn't guarantee the render
actually wrote a file.
