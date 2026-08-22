---
name: blender-scripts
description: Python model/render automation conventions for Blender scripts
applies_to: ["blender-project/scripts/**/*.py"]
---

# Blender Scripts Rules

Conventions for building models and rendering previews via the MCP tool layer.

## Script Structure

- **Always import bpy at the top** — these scripts only execute inside Blender's Python environment.
- Run scripts through the `run_blender_python` MCP tool (or `run_blender_python_live` for explicitly interactive tasks) — never invoke `blender` via shell, subprocess, or `os.system`.
- Verify output actually lands in `blender-project/renders/` before considering the script done — exit 0 doesn't guarantee the `.blend` or PNG exists.

## Naming Convention

Follow the two-category pattern from [DESIGN.md](../../../DESIGN.md#script-conventions):

### Model Scripts

- **`model_<subject>.py`** — builds the scene/mesh and saves a `.blend` file.
  - Example: `model_pendulum.py`, `model_dual_wheel_legged_robot.py`
  - Higher-fidelity variants use `model_<subject>_precise.py` — kept alongside the original, not replacing it.
  - Tip: use `bpy.app.background` to skip save under live sessions; headless always persists.

### Render Scripts

- **`render_<subject>.py`** — default-angle preview render of a subject's model.
- **`render_<subject>_<angle>.py`** — angle-specific render (front, side, top).
  - Example: `render_pendulum_front.py`, `render_tamiya_pendulum_top.py`
  - Outputs land in `blender-project/renders/` as `<subject>_preview[_<angle>].png`.

### File Organization

```
blender-project/scripts/
├── model_subject.py           # Build + save
├── model_subject_precise.py   # Higher-fidelity variant
├── render_subject.py          # Default angle
├── render_subject_front.py    # Front view
├── render_subject_side.py     # Side view
└── render_subject_top.py      # Top view
```

## Script Behavior

- Model scripts load a blank `.blend` (or load an existing one if iterating), build geometry/rigging/physics, and save to `blender-project/renders/<subject>.blend`.
- Render scripts load the corresponding `.blend` and output PNG(s) to `blender-project/renders/`.
- If a model or render doesn't yet exist for a requested subject, write it following the pattern of existing scripts for that subject.
- For multi-frame animation/simulation: bake keyframes to the armature/objects, don't rely on live physics simulation surviving the headless→file→headless round-trip.

## Documentation

Each script should have a module docstring explaining:
- What the script builds/renders (one sentence).
- Key design decisions or deferred scope (if any).
- Output file location and naming.

Example:
```python
"""
Model the armed inverted pendulum (issue #21): chassis stack, hip/leg/wheel actuators, rigid bodies.
Deferred: motor simulation (see PENDULUM.md).
Saves to blender-project/renders/pendulum.blend.
"""
```

## Workflow Integration

- Scripts are discovered and run via the `render-multi-angle` skill (see [SKILLS.md](../../../SKILLS.md)).
- New skills are documented in [SKILLS.md](../../../SKILLS.md) with script name, purpose, and section heading (e.g., "## Tamiya pendulum").
- Test that PNGs are non-trivial in size (not 0 bytes) and match the expected naming convention.
