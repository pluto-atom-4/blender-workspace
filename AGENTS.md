# Agent Operating Guide

Canonical guide for AI agents in this repo. [CLAUDE.md](CLAUDE.md) layers
Claude-Code specifics on top; Copilot reads this file natively, leaving
[.github/copilot-instructions.md](.github/copilot-instructions.md) as
safety-critical rules only.

Permissions/safety: [.claude/settings.json](.claude/settings.json) —
deny→ask→allow tiers plus a `PreToolUse` hook blocking destructive Bash
(`.claude/settings.local.json` is personal and gitignored).

## Agent roles and handover

`ARCHITECT → CODER → REVIEWER (creates PR) → HUMAN (review/merge)`.
- Gate 1: Plan approval before code (architect + human)
- Gate 2: Verification before PR (reviewer verifies + creates PR if passed)
- Gate 3: Human review + merge on GitHub

Roles defined in `.claude/agents/{architect,coder,reviewer}.md`:
- **Architect:** Plans (read-only), uses AskUserQuestion to clarify ambiguities, posts plan to issue for approval
- **Coder:** Implements `src/`+`tests/` (forbidden from governance files), pushes branch
- **Reviewer:** Verifies against checklist, creates PR if approved (via `gh pr create`), posts PR link to issue

Workflow prevents duplicate PRs: only reviewer creates them, after verification.

## Branching / isolation policy

Default to a plain branch (`git checkout -b <name>` off `main`). Use
`git worktree` only for genuinely concurrent multi-agent work or an
explicit human request — not by default. Rationale + cleanup pitfalls:
issue #48.

## Project layout

- `blender-mcp/` — infrastructure; change only when the tool interface does.
- `blender-project/renders/` — build artifacts; regenerate, don't hand-edit.

## MCP tools

`blender-local-agent` exposes three, not interchangeable:

- `run_blender_python` — disposable headless `blender --background` process
  per call. Default; never touches a window the user has open.
- `check_blender_live_status` — cheap probe for a reachable, addon-enabled
  live instance. Call before `run_blender_python_live`, not blind.
- `run_blender_python_live` — Python inside an **already-open** Blender GUI
  via the bridge addon. **Mutates the user's real open scene**; use only when
  the task needs a live window. Needs the addon enabled and Blender running
  interactively (depends on `bpy.app.timers`, dead under `--background`).

Only the **coder** subagent lists the first two in its `tools:` frontmatter;
architect/reviewer exclude them to keep their read-only guarantee.

If a task requests the live/interactive path and a technical limitation
forces a headless fallback, say so explicitly (PR/commit/issue comment) —
never substitute silently. It's a stated requirement, not an agent's call.

## Workflow

1. Write/iterate a script in `blender-project/scripts/`. Must `import bpy`.
2. Run it through the MCP tool, never by shelling out to `blender` (the tool
   guarantees env + `bpy` import).
3. Verify output landed in `blender-project/renders/` before calling it
   done — exit 0 doesn't mean the `.blend`/PNG exists.

## Environment notes

- KDE Wayland, Debian 13. A visible-UI script must pass Wayland env vars
  explicitly — don't assume X11.
- `run_blender_python` runs arbitrary Python with full `bpy`/host access —
  see [SECURITY.md](SECURITY.md); the live variant risks the user's real scene.
- No linter/formatter (no `black`/`flake8`/`ruff`); the only tests live in
  `blender-project/orchestration/`. Assume no build gates beyond
  `.github/workflows/`.

## Project skills

Claude Code auto-discovers `.claude/skills/<name>/SKILL.md` by scanning
frontmatter metadata (name + description). **Discovery is not path-conditional** —
the skill loader indexes by frontmatter, independent of directory structure or agent role.

Each skill's `SKILL.md` must include YAML frontmatter:
```yaml
---
name: skill-identifier
description: One-line description (shown in skill picker)
---
```

Skills are invoked per-task by any agent needing them (architect plans,
coder implements, reviewer verifies). See [SKILLS.md](SKILLS.md) for the
current inventory of agent skills and Blender scripts.

## Naming conventions

`model_<subject>.py`, `render_<subject>[_<angle>].py`, `_precise` for
higher-fidelity variants ([DESIGN.md](DESIGN.md#script-conventions)).
Per-directory detail: `.github/instructions/*.instructions.md`.
