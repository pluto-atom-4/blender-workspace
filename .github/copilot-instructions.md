# GitHub Copilot Instructions

This mirrors [AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md) — read
those for the full picture; this file is the Copilot-facing trim (Copilot
does not read CLAUDE.md). Keep the three in sync by hand when the MCP tools
or workflow change.

## Project layout

- `blender-mcp/` — FastMCP server exposing Blender to agents. Change only
  when the tool interface itself needs to change.
  - `addon/mcp_bridge_addon.py` — Blender addon: TCP bridge into a live,
    already-open Blender GUI session.
- `blender-project/scripts/` — generative Python automations (day-to-day
  modeling/rendering work happens here).
- `blender-project/renders/` — pipeline output (`.blend` files, preview
  PNGs). Build artifacts — regenerate via scripts, don't hand-edit.

## MCP tools (`blender-local-agent`)

Three tools, not interchangeable:

- `run_blender_python` — default. Disposable, headless `blender --background`
  process per call. Never touches a window the user has open.
- `check_blender_live_status` — cheap reachability probe for a live Blender
  GUI instance running the MCP Live Bridge addon. Call before
  `run_blender_python_live` to avoid a blind timeout.
- `run_blender_python_live` — runs Python inside an **already-open** Blender
  GUI session via the bridge addon. Mutates the user's real open scene.
  Requires the addon enabled and Blender running interactively — it depends
  on `bpy.app.timers`, which does not tick under `--background`.

## Workflow

1. Write or iterate a script in `blender-project/scripts/`. Every script
   must `import bpy`.
2. Execute via the MCP tool above — `run_blender_python` for the normal
   headless case, `run_blender_python_live` only when the task specifically
   needs to act on an open Blender window.
3. Verify output landed in `blender-project/renders/` before calling a task
   complete — exit code 0 alone doesn't mean the expected `.blend`/PNG
   exists.

## Naming conventions

`model_<subject>.py`, `render_<subject>.py`, `render_<subject>_<angle>.py`,
with a `_precise` suffix for higher-fidelity variants. See
[SKILLS.md](../SKILLS.md) for the current script inventory.

## Environment

- KDE Wayland on Debian 13. A script needing a visible UI window must pass
  through the Wayland environment variables explicitly.
- No linter/formatter/test suite is configured in this repo (no
  `black`/`flake8`/`pytest` installed) — don't invent build/lint gates that
  aren't actually wired up.

## Security

- `run_blender_python` executes arbitrary Python with full `bpy` access and
  inherits the host environment — see [SECURITY.md](../SECURITY.md) before
  running scripts from untrusted sources.
- `run_blender_python_live` carries the same risk against a live session
  instead of a disposable one — a bad script there can corrupt scene state
  the user is actively working on.
- `.claude/settings.json` (Claude Code side) blocks `rm -rf` / `git reset
  --hard` / `git push --force` via a `PreToolUse` hook; there is no
  Copilot-side equivalent enforcement mechanism today.
- If a task explicitly requests the live/interactive MCP path and a
  technical limitation forces a fallback to headless `run_blender_python`,
  say so explicitly in the PR description, commit message, or issue
  comment — don't substitute silently. Live-mode was a stated requirement,
  not an implementation detail left to the agent's discretion.
