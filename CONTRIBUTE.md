# Contributing

This is a personal/experimental Blender agent workspace, but the same rules
apply if you fork or submit changes.

## Workflow

1. Fork/branch from `main`.
2. Add or edit scripts in `blender-project/scripts/` following the naming
   convention described in [SKILLS.md](SKILLS.md) and
   [DESIGN.md](DESIGN.md#script-conventions).
3. Run scripts through the `blender-local-agent` MCP tool (or
   `blender --background --python-expr` directly, if not using an agent) and
   confirm the expected `.blend`/PNG output appears in
   `blender-project/renders/`.
4. Keep `blender-mcp/` changes minimal and backward compatible — it's a
   shared interface, not a place for one-off logic.

## Commit / PR guidelines

- One logical change per commit; keep generated render artifacts out of
  unrelated commits.
- Describe *why* a script or model changed (e.g. "corrected pendulum arm
  length from reference photo"), not just what changed.
- Do not commit large binary regenerations (`.blend`, previews) unless the
  underlying script actually changed.

## Reporting issues

Open a GitHub issue describing the script/tool involved, the command run,
and the full output (stdout/stderr) from `run_blender_python`.

See [SECURITY.md](SECURITY.md) before submitting anything that changes how
`blender-mcp` executes scripts.
