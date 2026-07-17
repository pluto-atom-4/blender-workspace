# Blender Agentic Workspace

A local workspace for driving Blender through an AI agent via the Model
Context Protocol (MCP). A FastMCP server exposes a `run_blender_python` tool
that executes Python inside Blender's background engine, letting an agent
(e.g. Claude Code) generate 3D models, scenes, and renders end to end.

## Structure

```
blender-mcp/       FastMCP server exposing Blender to agents
  blender_mcp.py    MCP tool definition (run_blender_python)
  main.py           Entry point stub
  pyproject.toml     uv-managed Python project (>=3.12)

blender-project/    Operational workspace
  scripts/           Generative Python automations (models, renders)
  assets/            Reference images / source assets
  renders/           .blend files and rendered preview images
```

## Requirements

- Blender installed and on `PATH` (Debian native package assumed).
- [uv](https://docs.astral.sh/uv/) for Python dependency management.
- KDE Wayland desktop (Debian 13) — see [DESIGN.md](DESIGN.md) for display
  environment handling.

## Setup

```bash
cd blender-mcp
uv sync
```

The MCP server is registered in `.mcp.json` for use by an MCP-compatible
agent client (e.g. Claude Code):

```json
{
  "mcpServers": {
    "blender-local-agent": {
      "command": "uv",
      "args": ["--directory", "/path/to/blender-mcp", "run", "blender_mcp.py"]
    }
  }
}
```

## Usage

1. Write or iterate a Python automation script in `blender-project/scripts/`.
   Scripts use `import bpy` to interact with Blender data blocks.
2. Run the script through the `blender-local-agent` MCP tool
   (`run_blender_python`), which launches Blender headless
   (`blender --background --python-expr ...`) and returns stdout/stderr.
3. Outputs (`.blend` files, preview renders) land in `blender-project/renders/`.

See [DESIGN.md](DESIGN.md) for architecture, [AGENTS.md](AGENTS.md) for
agent operating rules, [SKILLS.md](SKILLS.md) for the automation scripts
available today, [CONTRIBUTE.md](CONTRIBUTE.md) for contribution guidelines,
and [SECURITY.md](SECURITY.md) for the security model.
