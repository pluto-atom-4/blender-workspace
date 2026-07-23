# Blender Agentic Workspace Guide

## Project Structure
- `blender-mcp/`: Contains the localized Python FastMCP engine server.
  - `addon/mcp_bridge_addon.py`: Blender addon exposing a local TCP bridge into an already-open, interactive Blender GUI session.
- `blender-project/`: The operational space containing script code and visual outputs.
  - `scripts/`: Store generative Python automations here.
  - `renders/`: Target folder for pipeline image/video renders.

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

