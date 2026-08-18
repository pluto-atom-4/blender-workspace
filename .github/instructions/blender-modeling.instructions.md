---
applyTo: "blender-project/scripts/model_*.py"
description: "Conventions for Blender model_*.py build scripts"
---

# Modeling scripts

- Name the file `model_<subject>.py` and have it build **and persist** one
  `.blend`. A `model_` script that only builds in memory leaves nothing for
  the `render_*` scripts to load, so the render step silently rebuilds
  divergent geometry.
- Guard the save on `bpy.app.background`. Under `run_blender_python_live`
  the user's open scene is the working file — an unguarded
  `bpy.ops.wm.save_as_mainfile()` overwrites what they have open. Pattern:
  save when `bpy.app.background` is true, otherwise print a skip notice.
- Put a higher-fidelity rebuild in a **new** `model_<subject>_precise.py`
  rather than editing the base script. Both variants must stay
  independently reproducible; overwriting the base one destroys the
  lower-fidelity reference the earlier renders were made from.
- Import shared mesh/animation primitives from `_model_common.py` when
  working on the dual-wheel-legged-robot pair. The same `kf_loc` fcurve
  filtering bug had to be found twice in duplicated code (issue #23
  review) — that's why the module exists. Don't import it from unrelated
  scripts; it isn't a general-purpose library.
- Remove orphaned data-blocks explicitly after deleting an object.
  `bpy.data.objects.remove()` leaves the mesh and material behind; check
  `.users == 0` and remove those too, or repeated live runs leak
  `bpy.data` entries until the session bloats (issue #10).
- Re-read `bpy.data.objects` before assuming a name still exists. In a live
  session the user may have renamed or deleted objects since your last
  call, and a stale snapshot turns into a `KeyError` mid-build.
- Keep 1 Blender unit == 1 mm conversions in one place (`mm()` /
  `MM` in `_model_common.py`). Inlined magic numbers are how a CNC-accurate
  chassis drifts out of spec between the base and `_precise` variants.
