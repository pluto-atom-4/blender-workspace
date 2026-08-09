# Agent Operating Guide

Instructions for AI agents (Claude Code or otherwise) in this repo. See
[CLAUDE.md](CLAUDE.md) for the canonical Claude Code instructions — this
file restates them tool-agnostically. Copilot reads
[.github/copilot-instructions.md](.github/copilot-instructions.md), a
manually-synced trim of this file.

Tool permissions/safety hooks: [.claude/settings.json](.claude/settings.json)
(committed) + `.claude/settings.local.json` (personal, gitignored) — includes
the `PreToolUse` hook blocking destructive Bash commands.

## Agent Roles

Authoritative role details: `.claude/agents/architect.md`,
`.claude/agents/coder.md`, `.claude/agents/reviewer.md`. Summary only:

| Role | Can | Forbidden |
|---|---|---|
| Architect | Read code; write tasks.md/docs/ | Write production code |
| Coder | Write src/, tests/; commit | Edit tasks.md, CLAUDE.md, AGENTS.md; skip tests |
| Reviewer | Read code; run verification | Edit production code; merge w/o approval |

## Handover Protocol

```
ARCHITECT → CODER → REVIEWER → HUMAN (merge)
```

**Approval gates:** Gate 1 (plan) before code → Gate 2 (verification) before merge

## Branching / isolation policy

Default to a plain branch (`git checkout -b <name>` off `main`). Use
`git worktree` only for genuinely concurrent multi-agent work or an
explicit human request — not by default. Rationale + cleanup pitfalls:
issue #48.

## Project layout

- `blender-mcp/` — infrastructure; change only when the tool interface itself must change.
- `blender-project/renders/` — build artifacts; regenerate via scripts, don't hand-edit.

## MCP tools

`blender-local-agent` exposes three, not interchangeable:

- `run_blender_python` — disposable headless `blender --background` process
  per call. Default; never touches a window the user has open.
- `check_blender_live_status` — cheap probe for a reachable, addon-enabled
  live instance. Call before `run_blender_python_live`, not blind.
- `run_blender_python_live` — runs Python inside an **already-open** Blender
  GUI session via the bridge addon. **Mutates the user's real open scene**.
  Only when the task explicitly needs a live window. Requires the addon
  enabled and Blender running interactively — depends on `bpy.app.timers`,
  which doesn't tick under `--background`.

If a task explicitly requests the live/interactive path and a technical
limitation forces a fallback to headless `run_blender_python` instead, say
so explicitly in the PR description, commit message, or issue comment —
don't substitute silently. The live-mode request is a stated requirement,
not an implementation detail left to the agent's discretion.

## Workflow

1. Write/iterate a script in `blender-project/scripts/`. Must `import bpy`.
2. Execute via the MCP tool — `run_blender_python` normally, not by shelling
   out to `blender` directly (the tool guarantees env + `bpy` import). Reach
   for `run_blender_python_live` only when the task needs a live window.
3. Verify output landed in `blender-project/renders/` before calling it
   done — exit 0 doesn't mean the `.blend`/PNG exists.

## Environment notes

- KDE Wayland, Debian 13. A visible-UI script must pass Wayland env vars
  explicitly — don't assume X11.
- `run_blender_python` runs arbitrary Python with full `bpy`/host access —
  see [SECURITY.md](SECURITY.md). `run_blender_python_live` carries the same
  risk against the user's live scene, not a disposable one.
- No linter/formatter/test suite is configured (no `black`/`flake8`/`pytest`
  installed) — don't assume `wc -l`/`jq`/build gates exist beyond what's
  wired up in `.github/workflows/`.

## Project skills

Claude Code auto-discovers `.claude/skills/<name>/SKILL.md` (name +
description frontmatter) — see [SKILLS.md](SKILLS.md) for the current
inventory.

## Naming conventions

See [DESIGN.md](DESIGN.md#script-conventions):
`model_<subject>.py`, `render_<subject>.py`, `render_<subject>_<angle>.py`,
`_precise` suffix for higher-fidelity variants.
