@AGENTS.md

# Blender Agentic Workspace Guide

## Cross-tool configuration
- `.claude/settings.json` — committed baseline: MCP tool permissions and a `PreToolUse` hook (`.claude/hooks/block-destructive-bash.sh`) that blocks `rm -rf` / `git reset --hard` / `git push --force` before they run. `.claude/settings.local.json` layers personal overrides on top (gitignored).
- `.github/copilot-instructions.md` — GitHub Copilot's equivalent of this file, kept in sync manually (Copilot doesn't read CLAUDE.md).
- No linter/formatter/test suite is configured in this repo yet (no `black`/`flake8`/`pytest` installed) — don't assume `wc -l`/`jq`/build-command gates exist beyond what's actually wired up above.

## Environment and Display
- Running on KDE Wayland (Debian 13).
- Blender commands executed inside `blender-mcp` wrapper scripts must pass proper environment parameters if a UI window needs tracking.

## MCP Server Tools
The `blender-local-agent` MCP server exposes three tools:
- `run_blender_python`: disposable, headless `blender --background` process per call. Safe default, never touches an open Blender window.
- `check_blender_live_status`: cheap reachability probe for a live Blender instance running the MCP Live Bridge addon.
- `run_blender_python_live`: executes Python inside an already-open Blender GUI session via the bridge addon. Mutates the user's real open scene — requires the addon enabled and Blender running interactively (not `--background`), since it depends on `bpy.app.timers` ticking.

## Development Workflow
1. Write or iterate Python automation scripts directly inside `./blender-project/scripts/`.
2. Execute and test them using the `blender-local-agent` tool — `run_blender_python` for one-shot headless work, `run_blender_python_live` (after `check_blender_live_status`) when the task needs to act on an already-open Blender window.
3. Always ensure your Python code uses `import bpy` to interact with Blender data blocks.

## Live Bridge Notes (learned from playtest, see issue #10)
- Scene state can drift between calls if the user edits the GUI manually mid-session — re-read baseline (`bpy.data.objects`) before assuming a name still exists rather than trusting an earlier snapshot.
- `run_blender_python_live` has no auto-cleanup of orphaned data-blocks. Removing an object with `bpy.data.objects.remove()` does not remove its mesh/material data-blocks — remove those explicitly (check `.users == 0` first) or they leak in `bpy.data`.
- Multi-op scripts (create object + keyframe + material in one call) work fine in a single round-trip — no need to split into multiple live calls.
- Errors (e.g. `KeyError` from a missing object) come back as a clean `Execution Failed` result with full Python traceback — no hang, no Blender crash. Safe to probe/validate object names this way.
- Round-trip latency is sub-second even for multi-op scripts.

