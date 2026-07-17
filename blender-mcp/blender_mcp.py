# ~/blender-mcp/blender_mcp.py
import os
import subprocess
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server instance
mcp = FastMCP("Blender Agent")

@mcp.tool()
def run_blender_python(script_contents: str) -> str:
    """
    Executes a Python script inside Blender's background engine.
    Use this to create meshes, handle scene nodes, or render frames.
    """
    try:
        # Guarantee bpy is available to Claude
        if "import bpy" not in script_contents:
            script_contents = "import bpy\n" + script_contents

        # Capture your KDE Wayland environment variables to prevent driver/display crashes
        env = os.environ.copy()

        # Launch background execution using Debian's native system Blender binary
        result = subprocess.run(
            ["blender", "--background", "--python-expr", script_contents],
            capture_output=True,
            text=True,
            check=True,
            env=env  # Explicitly pass down the Wayland display context
        )
        return f"Execution Success:\n{result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Execution Failed:\nError:\n{e.stderr}\nOutput:\n{e.stdout}"

if __name__ == "__main__":
    mcp.run()

