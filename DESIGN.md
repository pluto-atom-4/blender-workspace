# Design

## Overview

The workspace splits into two concerns:

- **`blender-mcp/`** — a thin FastMCP server that is the only bridge between
  an agent and Blender. It has no Blender-specific logic beyond invoking the
  binary; all modeling/rendering logic lives in agent-authored scripts.
- **`blender-project/`** — the content produced and consumed by that bridge:
  scripts in, `.blend`/image files out.

This keeps the server generic and disposable — regenerating a model or
render is "write a script, run the tool," not "modify the server."

## Execution model

`run_blender_python` (`blender-mcp/blender_mcp.py`) takes a Python script as
a string and executes it via:

```
blender --background --python-expr <script>
```

Key properties:

- **Headless by default.** `--background` runs without a UI window, which is
  the common case (batch modeling/rendering). If a script needs to interact
  with a visible window (e.g. Wayland-specific preview tooling), the caller
  is responsible for passing the environment needed to attach to the running
  KDE Wayland session — the MCP process does not launch a UI on its own.
- **Environment passthrough.** The subprocess inherits the full parent
  environment (`os.environ.copy()`), so `WAYLAND_DISPLAY`,
  `XDG_RUNTIME_DIR`, etc. carry through without extra plumbing.
- **`import bpy` guaranteed.** The tool prepends `import bpy` if the script
  doesn't already import it, so agent-generated scripts can assume `bpy` is
  available.
- **Synchronous, blocking call.** `subprocess.run(..., check=True)` waits
  for Blender to exit and surfaces stdout on success or stderr (plus stdout)
  on failure. There is no streaming/progress channel — long-running renders
  block the tool call until completion.

## Script conventions

Scripts in `blender-project/scripts/` follow a naming pattern that separates
modeling from rendering, and rendering by camera angle:

- `model_<subject>.py` — builds the scene/mesh and saves a `.blend`.
- `render_<subject>.py` / `render_<subject>_<angle>.py` — loads or rebuilds
  the scene and renders a preview PNG from a specific viewpoint (`front`,
  `side`, `top`).

A `_precise` suffix marks a higher-fidelity variant of a model built from
more exact reference measurements, kept alongside the original rather than
replacing it, so both remain reproducible.

## Why FastMCP + subprocess instead of Blender's own Python API server

Blender's Python API (`bpy`) only runs inside a Blender process. Rather than
keeping a long-lived Blender instance with an RPC layer, each tool call
spawns a fresh `blender --background` process. This trades startup latency
per call for process isolation: a crashing or hung script can't take down a
shared Blender instance or leak state into the next script run.
