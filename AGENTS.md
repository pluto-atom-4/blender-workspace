# Agent Operating Guide

Instructions for AI agents (Claude Code or otherwise) working in this
repository. See also [CLAUDE.md](CLAUDE.md) for the canonical Claude Code
project instructions — this file restates the same rules in
tool-agnostic form.

## Project layout

- `blender-mcp/` — the local FastMCP server that exposes Blender to agents.
  Treat it as infrastructure: change it only when the tool interface itself
  needs to change, not to work around a one-off script issue.
- `blender-project/scripts/` — generative Python automations. This is where
  day-to-day modeling/rendering work happens.
- `blender-project/renders/` — pipeline output (`.blend` files, preview
  PNGs). Treat existing files here as build artifacts: regenerate via
  scripts rather than hand-editing.

## Workflow

1. Write or iterate a script in `blender-project/scripts/`. Every script
   must `import bpy` to touch Blender data blocks.
2. Execute it via the `blender-local-agent` MCP tool
   (`run_blender_python`), not by shelling out to `blender` directly —
   the tool guarantees the right environment (Wayland display variables,
   `bpy` import) is in place.
3. Verify output landed in `blender-project/renders/` before reporting a
   task complete; a script that exits 0 without producing the expected
   `.blend`/PNG has not actually finished the task.

## Environment notes

- Target platform is KDE Wayland on Debian 13. If a script needs a visible
  UI window rather than headless execution, it must pass through the
  Wayland environment variables explicitly — don't assume an X11 display.
- `run_blender_python` executes arbitrary Python with full `bpy` access and
  inherits the host environment. See [SECURITY.md](SECURITY.md) before
  running scripts from untrusted sources through it.

## Naming conventions

Follow the existing pattern in `blender-project/scripts/` (see
[DESIGN.md](DESIGN.md#script-conventions)):
`model_<subject>.py`, `render_<subject>.py`, `render_<subject>_<angle>.py`,
with a `_precise` suffix for higher-fidelity variants.
