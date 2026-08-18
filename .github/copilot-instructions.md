# GitHub Copilot Instructions

Canonical guide: [AGENTS.md](../AGENTS.md) — Copilot reads it natively, so
layout, workflow, naming, and environment notes are no longer duplicated
here. Per-path rules auto-apply from [.github/instructions/](instructions/)
via `applyTo:` frontmatter when you touch a matching file.

> **Discovery bet:** AGENTS.md pickup is surface-gated (VS Code needs
> `chat.useAgentsMdFile`). If yours ignores it, re-inline the sections
> dropped in issue #78 from this file's git history. What follows must not
> depend on that discovery.

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

**No silent fallback:** if a task requests the live/interactive MCP path
and a technical limitation forces a headless fallback, say so explicitly
(PR/commit/issue comment) — it's a stated requirement, not an
implementation detail left to your discretion.

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

## Security

Never propose `rm -rf`, `git reset --hard`, `git push --force`, or `sudo`:
`.claude/settings.json` denies them and a `PreToolUse` hook blocks them,
with no Copilot-side equivalent. `run_blender_python` runs arbitrary Python
with full `bpy`/host access — see [SECURITY.md](../SECURITY.md).
