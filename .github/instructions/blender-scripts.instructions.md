---
applyTo: "blender-project/scripts/**/*.py"
---

- Always `import bpy` at the top; these scripts only make sense inside
  Blender's Python.
- Run scripts through the `run_blender_python` MCP tool (or
  `run_blender_python_live` for an explicitly live-session task) — never
  invoke `blender` via a raw shell command, subprocess, or `os.system`.
- Follow the naming convention: `model_<subject>.py` builds and saves a
  `.blend`; `render_<subject>[_<angle>].py` renders a preview PNG; a
  `_precise` suffix marks a higher-fidelity variant.
- Confirm output actually landed in `blender-project/renders/` before
  considering the script done.
