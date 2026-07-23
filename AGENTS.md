# Agent Operating Guide

Instructions for AI agents (Claude Code or otherwise) working in this
repository. See also [CLAUDE.md](CLAUDE.md) for the canonical Claude Code
project instructions — this file restates the same rules in
tool-agnostic form.

## Project layout

- `blender-mcp/` — the local FastMCP server that exposes Blender to agents.
  Treat it as infrastructure: change it only when the tool interface itself
  needs to change, not to work around a one-off script issue.
  - `blender-mcp/addon/mcp_bridge_addon.py` — Blender addon that opens a
    local TCP bridge inside an already-running, interactive Blender GUI
    session, backing the `run_blender_python_live` tool.
- `blender-project/scripts/` — generative Python automations. This is where
  day-to-day modeling/rendering work happens.
- `blender-project/renders/` — pipeline output (`.blend` files, preview
  PNGs). Treat existing files here as build artifacts: regenerate via
  scripts rather than hand-editing.

## MCP tools

`blender-local-agent` exposes three tools — pick deliberately, they are not
interchangeable:

- `run_blender_python` — disposable, headless `blender --background`
  process per call. Default choice for scene generation/rendering; never
  touches a window the user has open.
- `check_blender_live_status` — cheap probe for whether a live, addon-
  enabled Blender GUI instance is reachable. Call this before
  `run_blender_python_live` rather than eating its timeout blind.
- `run_blender_python_live` — runs Python inside an already-open Blender
  GUI session via the bridge addon. This **mutates the user's real open
  scene**, unlike the background tool. Only use it when the task explicitly
  needs to act on a live/open Blender window (e.g. the user is watching).
  Requires the MCP Live Bridge addon enabled and Blender running
  interactively — it depends on `bpy.app.timers`, which does not tick under
  `--background`.

## Workflow

1. Write or iterate a script in `blender-project/scripts/`. Every script
   must `import bpy` to touch Blender data blocks.
2. Execute it via the `blender-local-agent` MCP tool — `run_blender_python`
   for the normal headless case, not by shelling out to `blender` directly.
   The tool guarantees the right environment (Wayland display variables,
   `bpy` import) is in place. Reach for `run_blender_python_live` only when
   the task specifically requires touching an already-open Blender window.
3. Verify output landed in `blender-project/renders/` before reporting a
   task complete; a script that exits 0 without producing the expected
   `.blend`/PNG has not actually finished the task.

## Environment notes

- Target platform is KDE Wayland on Debian 13. If a script needs a visible
  UI window rather than headless execution, it must pass through the
  Wayland environment variables explicitly — don't assume an X11 display.
- `run_blender_python` executes arbitrary Python with full `bpy` access and
  inherits the host environment. See [SECURITY.md](SECURITY.md) before
  running scripts from untrusted sources through it. The same applies to
  `run_blender_python_live`, with higher stakes — it runs against a live
  session instead of a disposable process, so an untrusted or buggy script
  can corrupt scene state the user is actively working on.

## Naming conventions

Follow the existing pattern in `blender-project/scripts/` (see
[DESIGN.md](DESIGN.md#script-conventions)):
`model_<subject>.py`, `render_<subject>.py`, `render_<subject>_<angle>.py`,
with a `_precise` suffix for higher-fidelity variants.
