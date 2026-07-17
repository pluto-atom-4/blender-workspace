# Security

## Threat model

`blender-mcp` exposes a single MCP tool, `run_blender_python`, that executes
**arbitrary Python with full `bpy` access** inside a `blender --background`
subprocess, inheriting the full host environment (`os.environ.copy()`). This
is by design for a local, single-user agent workspace — it is not sandboxed
and must not be treated as safe against untrusted input.

Concretely, any script passed to `run_blender_python` can:

- Read/write any file the invoking user can access (not limited to
  `blender-project/`).
- Read environment variables (including any secrets present in the shell
  environment) and, via `bpy`'s scripting surface, make network calls or
  spawn further subprocesses.

## Operating rules

- **Local use only.** `.mcp.json` wires this server to a local `uv`
  invocation over stdio. Do not expose the MCP server over a network
  transport or to multiple/untrusted users without adding sandboxing.
- **Do not run scripts from untrusted sources** (random downloaded `.py`
  files, unreviewed PR contents) through `run_blender_python`. Review script
  contents the same way you would review any code before executing it.
- **No secrets in the environment the server inherits.** Because the
  subprocess environment is passed through unmodified, avoid running the
  MCP server from a shell that has sensitive credentials exported.
- **`.mcp.json` contains only local paths**, no credentials. If a future
  MCP server config needs a token, keep it out of version control (use a
  local, gitignored env file) rather than inlining it in `.mcp.json`.

## Reporting a vulnerability

This is a local experimental workspace with no hosted service. If you find
an issue with how `blender-mcp` handles execution or environment data, open
a GitHub issue describing the concern and, if applicable, a minimal
reproduction script.
