# Blender Agentic Workspace Guide

## Project Structure
- `blender-mcp/`: Contains the localized Python FastMCP engine server.
- `blender-project/`: The operational space containing script code and visual outputs.
  - `scripts/`: Store generative Python automations here.
  - `renders/`: Target folder for pipeline image/video renders.

## Environment and Display
- Running on KDE Wayland (Debian 13).
- Blender commands executed inside `blender-mcp` wrapper scripts must pass proper environment parameters if a UI window needs tracking.

## Development Workflow
1. Write or iterate Python automation scripts directly inside `./blender-project/scripts/`.
2. Execute and test them using the `blender-local-agent` tool.
3. Always ensure your Python code uses `import bpy` to interact with Blender data blocks.

