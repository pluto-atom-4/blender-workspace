# GitHub Copilot Instructions

Mirrors [AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md) — read those
for the full picture; this is the Copilot-facing trim (Copilot doesn't read
CLAUDE.md). Keep the three in sync by hand when MCP tools/workflow change.
Path-specific rules already live in
[.github/instructions/*.instructions.md](instructions/) (real Copilot
`applyTo:` frontmatter) — check there before adding blanket rules here.

## Project layout

- `blender-mcp/` — FastMCP server exposing Blender to agents (change only
  when the tool interface changes); `addon/mcp_bridge_addon.py` is the TCP
  bridge into a live, already-open Blender GUI session.
- `blender-project/scripts/` — day-to-day modeling/rendering automations.
- `blender-project/renders/` — pipeline output (`.blend`, preview PNGs);
  build artifacts, regenerate via scripts, don't hand-edit.

## MCP tools (`blender-local-agent`)

Three tools, not interchangeable:

- `run_blender_python` — default; disposable, headless `blender
  --background` process per call, never touches an open window.
- `check_blender_live_status` — cheap reachability probe for a live GUI
  instance running the MCP Live Bridge addon; call before
  `run_blender_python_live` to avoid a blind timeout.
- `run_blender_python_live` — runs Python inside an **already-open**
  Blender GUI session via the bridge addon; mutates the user's real open
  scene. Requires the addon enabled and Blender running interactively —
  depends on `bpy.app.timers`, which doesn't tick under `--background`.

## Workflow

1. Write or iterate a script in `blender-project/scripts/`; every script
   must `import bpy`.
2. Execute via the MCP tool above — `run_blender_python` normally,
   `run_blender_python_live` only for an open Blender window.
3. Verify output landed in `blender-project/renders/` before calling a
   task complete — exit 0 doesn't guarantee the `.blend`/PNG exists.

## Naming conventions

`model_<subject>.py`, `render_<subject>.py`, `render_<subject>_<angle>.py`,
with a `_precise` suffix for higher-fidelity variants. See
[SKILLS.md](../SKILLS.md) for the current script inventory.

## Branching / isolation policy

Default to a plain branch off `main`; reserve `git worktree` for genuinely
concurrent work or an explicit human request, not by default.
`blender-project/renders/*.blend` files are binary (0.5–1.3MB each), so
every worktree duplicates them, and worktrees/branches aren't reliably
auto-cleaned (issue #48: 3 merged worktrees + 4 dangling branches found
unpruned, plus a near-miss where an uncommitted `.blend` in a worktree
nearly got silently discarded by `git worktree remove`). Commit — or flag
explicitly as uncommitted and why — any non-reproducible build artifact a
worktree produces before removing it.

## Environment

KDE Wayland on Debian 13 (visible-UI scripts need explicit Wayland env
vars, don't assume X11); no linter/formatter/test suite configured (no
`black`/`flake8`/`pytest`) — don't invent build/lint gates that aren't
actually wired up.

## Security

- `run_blender_python` runs arbitrary Python with full `bpy`/host access —
  see [SECURITY.md](../SECURITY.md) before untrusted scripts.
  `run_blender_python_live` carries the same risk against the user's live
  scene, not a disposable one, and can corrupt state they're working on.
- `.claude/settings.json` (Claude Code) blocks `rm -rf` / `git reset --hard`
  / `git push --force` via a `PreToolUse` hook; no Copilot-side equivalent
  exists today.
- If a task requests the live/interactive MCP path and a technical
  limitation forces a headless fallback, say so explicitly (PR/commit/issue
  comment) — never substitute silently; it's a stated requirement, not an
  implementation detail.
