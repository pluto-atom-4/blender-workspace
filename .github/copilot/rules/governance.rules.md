---
name: governance
description: Config file modification policy, which files agents can/cannot edit, and approval gates
applies_to: [".claude/**", ".github/copilot-instructions.md", ".github/instructions/**", "CLAUDE.md", "AGENTS.md", ".github/copilot/rules/**"]
---

# Governance Rules

Who can edit governance files, approval gates, and CI validation.

## File Protection Policy

### Read-Only (No Edits)

These files define agent roles and safety boundaries. Only human review/approval.

- **`.claude/agents/*.md`** — Role definitions (architect, coder, reviewer).
  - Frontmatter carries guardrails (e.g., coder forbids editing governance files).
  - Enforcement layer: `.claude/settings.json` permissions; frontmatter is advisory only.

- **`.claude/settings.json`** — Permission tiers and safety rules.
  - Deny patterns must include destructive operations: `rm -rf`, `git reset --hard`, `git push --force`, `sudo`.
  - Tier structure: `deny` (never, high severity), `ask` (confirm each time), `allow` (silent).
  - **Never add `permissions.defaultMode`** — repo scope cannot grant it; would shadow user's global setting.
  - `.claude/settings.local.json` is personal and gitignored (agent cannot edit).

- **`.claude/hooks/block-destructive-bash.sh`** — Pre-tool-use hook blocking dangerous operations.
  - Must contain substrings `rm -rf` and `git push --force` (CI grep validates these).
  - Used by workflow automation; changing it breaks CI.

### Limited Edit (Documented Workflow)

These files guide agents and Copilot. Edit only per documented approval gates and with context-baseline refresh.

- **`CLAUDE.md`** — Claude-Code specific guidance.
  - Line 1 must be exactly `@AGENTS.md` (import directive for config harness).
  - After any edit: run `python3 scripts/context-audit.py` and commit updated `docs/dev-note/context-baseline.json`.
  - Token budgets and context tallies drift silently otherwise.

- **`AGENTS.md`** — Canonical guide for all agents and Copilot.
  - Sections: MCP tools, branching, project layout, workflow, environment, skills, naming.
  - After any edit: run `python3 scripts/context-audit.py` and commit updated `docs/dev-note/context-baseline.json`.

- **`.github/copilot-instructions.md`** — GitHub Copilot-specific rules.
  - Must contain substrings `rm -rf` and `git push --force` (CI grep validates these).
  - Cross-links to AGENTS.md for canonical detail.
  - After any edit: run `python3 scripts/context-audit.py` and commit updated `docs/dev-note/context-baseline.json`.

- **`.github/instructions/*.instructions.md`** — Per-directory guardrails.
  - Frontmatter: `applyTo:` (glob pattern), `description:` (brief).
  - Auto-applied when agents touch matching files (e.g., `blender-project/scripts/**/*.py` auto-loads `blender-scripts.instructions.md`).
  - After any edit: run `python3 scripts/context-audit.py` and commit updated `docs/dev-note/context-baseline.json`.

- **`.github/copilot/rules/*.rules.md`** — GitHub Copilot rule files.
  - Same format as `.github/instructions/` files (YAML frontmatter + markdown).
  - After any edit: run `python3 scripts/context-audit.py` and commit updated `docs/dev-note/context-baseline.json`.

### Free Edit (No Context Refresh Required)

These files evolve with the codebase; no special approval gates.

- **`.claude/skills/*/SKILL.md`** — Skill documentation.
  - Frontmatter: `name:`, `description:` (required for auto-discovery).
  - Edit skill documentation as feature/bug fixes land in the corresponding scripts.
  - No context-audit refresh required (skills are indexed separately).

- **`SKILLS.md`** — Inventory of scripts and skills.
  - Maintained manually; lists scripts, their purpose, and organization by feature.
  - Update when adding new `model_*.py` or `render_*.py` scripts.

- **`DESIGN.md`** — Architecture, execution model, and naming conventions.
  - Normative reference; updated as implementation decisions stabilize.
  - If agent changes script naming or core MCP tool behavior, document it here.

## Workflow Gates

### Gate 1: Plan Approval (Before Code)

**Agents:** Architect (read-only) → Human review

- Architecture plan document (issue body, PR description, or separate `.md`) outlines:
  - Problem statement
  - Solution design
  - Files to be created/modified (including governance files)
  - Approval dependencies (e.g., "must edit `.claude/agents/coder.md`" needs extra review)

### Gate 2: Verification (Before Merge)

**Agents:** Coder → Reviewer (read-only) → Human approval

- Reviewer verifies:
  - Code quality and test coverage
  - Governance file changes align with Gate-1 plan
  - `context-baseline.json` was refreshed (if governance files changed)
  - CI passes

### Context Audit Requirements

After editing any governance file (AGENTS.md, CLAUDE.md, `.github/instructions/*`, `.github/copilot/rules/*`, `.claude/settings.json`):

```bash
python3 scripts/context-audit.py
git add docs/dev-note/context-baseline.json
git commit -m "Refresh context baseline after governance change"
```

**Why:** Token budgets and resident/on-demand context tallies drift silently without this. CI checks `context-baseline.json` is up-to-date.

## CI Validation

### Grep Checks

- `.github/copilot-instructions.md` must contain `rm -rf` and `git push --force` (safety keywords).
- `.claude/hooks/block-destructive-bash.sh` must contain `rm -rf` and `git push --force`.
- `CLAUDE.md` line 1 must be exactly `@AGENTS.md`.
- `docs/dev-note/context-baseline.json` must match latest audit run.

### What Triggers Audit Check

- Any modification to `.github/instructions/*.md`, `.github/copilot/rules/*.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, or `.claude/agents/*.md`.
- PR fails if `context-baseline.json` is out of sync.

## Role-Based Editing Matrix

| File | Architect | Coder | Reviewer | Human |
|------|-----------|-------|----------|-------|
| `.claude/agents/*.md` | No | No | No | Yes |
| `.claude/settings.json` | No | No | No | Yes |
| `.claude/skills/*/SKILL.md` | No | Yes* | No | Yes |
| `AGENTS.md` | No | No | No | Yes |
| `CLAUDE.md` | No | No | No | Yes |
| `.github/copilot-instructions.md` | No | No | No | Yes |
| `.github/instructions/*.md` | No | No | No | Yes |
| `.github/copilot/rules/*.md` | No | No | No | Yes |
| `SKILLS.md` | No | Yes | No | Yes |
| `DESIGN.md` | No | Yes | No | Yes |
| `blender-project/scripts/*.py` | No | Yes | No | Yes |
| `blender-project/orchestration/*.py` | No | Yes | No | Yes |
| Tests (`tests/*.py`) | No | Yes | No | Yes |

*Coder can edit skill content (name, description) to match script changes, but must coordinate with architect on major capability shifts.

## Approval Requirements Summary

| Category | Approval Gate | Audit Refresh? |
|----------|----------------|---------------|
| New feature (script) | Gate 1 plan + Gate 2 review | No |
| Bug fix (script) | Gate 2 review only | No |
| Agent role change | Gate 1 plan + Gate 2 review + human sign-off | Yes |
| MCP tool interface change | Gate 1 plan + Gate 2 review + human sign-off | Yes |
| Governance rule clarification | Human direct edit | Yes |
| Safety constraint update | Human direct edit + audited | Yes |
