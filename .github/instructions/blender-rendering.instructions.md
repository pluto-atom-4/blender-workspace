---
applyTo: "blender-project/scripts/render_*.py"
description: "Conventions for Blender render_*.py preview scripts"
---

# Rendering scripts

- Name the file `render_<subject>.py` for the default 3/4 view and
  `render_<subject>_<angle>.py` (`front`, `side`, `top`) for a fixed
  viewpoint. Angle-in-the-body-only scripts can't be discovered by the
  `render-multi-angle` skill, which selects scripts by filename.
- Write the PNG to `blender-project/renders/` as
  `<subject>_preview[_<angle>].png`. A different stem or directory means the
  render silently doesn't replace the preview referenced from SKILLS.md and
  the writeup docs.
- Mirror the model's `_precise` suffix in the render name
  (`render_<subject>_precise_side.py` →
  `<subject>_precise_preview_side.png`). Sharing one output path between the
  base and precise variants makes the two overwrite each other, so the
  comparison the `_precise` variant exists for becomes impossible.
- Either load the saved `.blend` or rebuild via the matching `model_`
  script — never re-derive geometry inline. Divergent inline geometry
  produces previews that don't match the model anyone else renders.
- Assert the output file exists and is non-trivial in size after rendering.
  Blender exits 0 on a render that wrote nothing (bad output path, missing
  camera, unwritable directory) — exit 0 is not evidence the PNG is there.
- Set the camera, resolution, and engine explicitly in the script. Inheriting
  whatever the `.blend` happened to save makes previews change between runs
  for reasons no diff can explain.
- Run these through the `run_blender_python` MCP tool. Rendering inside the
  user's open GUI session ties up their Blender and mutates their scene's
  render settings.
