@AGENTS.md

# Blender Agentic Workspace Guide

AGENTS.md (imported above) is canonical for MCP tools, workflow, branching,
and environment notes — don't re-add those sections here; extend AGENTS.md
instead.

## Commands (exact — don't probe for alternatives)

```bash
cd blender-project/orchestration && uv run --extra test pytest  # tests
cd blender-project/orchestration && uv sync --extra test        # deps
python3 scripts/context-audit.py                                # audit
```

- Blender: never shell out to `blender` — use the `run_blender_python` MCP tool.
- Lint/format: none configured (no `black`/`flake8`/`ruff`); don't invent one.
- Per-directory rules: `.github/instructions/*.instructions.md`.

## Live Bridge Notes (learned from playtest, see issue #10)
- Scene state can drift between calls if the user edits the GUI manually mid-session — re-read baseline (`bpy.data.objects`) before assuming a name still exists rather than trusting an earlier snapshot.
- `run_blender_python_live` has no auto-cleanup of orphaned data-blocks. Removing an object with `bpy.data.objects.remove()` does not remove its mesh/material data-blocks — remove those explicitly (check `.users == 0` first) or they leak in `bpy.data`.
- Multi-op scripts (create object + keyframe + material in one call) work fine in a single round-trip — no need to split into multiple live calls.
- Errors (e.g. `KeyError` from a missing object) come back as a clean `Execution Failed` result with full Python traceback — no hang, no Blender crash. Safe to probe/validate object names this way.
- Round-trip latency is sub-second even for multi-op scripts.

## Graph Intelligence Tools (code-review-graph, graphify)

MCP servers registered user-level in `~/.claude/settings.json` (not repo
`.mcp.json` — both tools are `uv tool install`-ed per-machine, not assumed
present on every teammate's PATH). See issue #119.

- **code-review-graph** — micro/structural: caller/callee tracing, blast
  radius. DB at `.code-review-graph/graph.db` (self-gitignored). Refresh
  after edits: `Bash(code-review-graph update)`; full rebuild after a large
  refactor: `Bash(code-review-graph build)`.
- **graphify** — macro/architectural: multi-modal map incl. docs/schemas.
  Output at `graphify-out/graph.json` (gitignored globally, not per-repo).
  Refresh: `Bash(graphify update .)`.

Routing: check architecture/design questions against graphify first; once
the relevant module is isolated, use code-review-graph for exact
caller/callee/impact paths. If either tool errors or returns empty, fall
back to a narrow `Grep` — don't retry the same graph query.
