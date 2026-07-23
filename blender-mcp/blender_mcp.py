# ~/blender-mcp/blender_mcp.py
import json
import os
import socket
import struct
import subprocess
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server instance
mcp = FastMCP("Blender Agent")

# Connection settings for the MCP Live Bridge addon (addon/mcp_bridge_addon.py),
# which must be enabled inside an already-open, interactive Blender instance.
LIVE_HOST = os.environ.get("BLENDER_MCP_LIVE_HOST", "127.0.0.1")
LIVE_PORT = int(os.environ.get("BLENDER_MCP_LIVE_PORT", "9876"))
LIVE_TIMEOUT = float(os.environ.get("BLENDER_MCP_LIVE_TIMEOUT", "30"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("connection closed before full message received")
        data += chunk
    return data


def _send_live_request(script_contents: str, host: str, port: int, timeout: float) -> dict:
    payload = json.dumps({"code": script_contents}).encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        sock.settimeout(timeout)
        length = struct.unpack(">I", _recv_exact(sock, 4))[0]
        body = _recv_exact(sock, length)
        return json.loads(body.decode("utf-8"))


@mcp.tool()
def run_blender_python(script_contents: str) -> str:
    """
    Executes a Python script inside a disposable, headless Blender process.
    Safe default: spins up a fresh background Blender instance per call, runs
    the script, and exits. Does NOT touch any Blender window you may have
    open. Use this for one-shot scene generation/rendering that doesn't need
    to interact with a live UI.
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


@mcp.tool()
def check_blender_live_status(host: str = LIVE_HOST, port: int = LIVE_PORT) -> str:
    """
    Checks whether a live, already-open Blender instance is reachable via the
    MCP Live Bridge addon (blender-mcp/addon/mcp_bridge_addon.py). Call this
    before run_blender_python_live to avoid a slow timeout when no GUI
    instance with the bridge enabled is currently running.
    """
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return f"Live Blender instance reachable at {host}:{port}."
    except OSError as e:
        return (
            f"No live Blender instance reachable at {host}:{port} ({e}). "
            "Is Blender open with the MCP Live Bridge addon enabled?"
        )


@mcp.tool()
def run_blender_python_live(script_contents: str, host: str = LIVE_HOST, port: int = LIVE_PORT) -> str:
    """
    Executes a Python script inside an ALREADY-OPEN, live Blender GUI session
    via the MCP Live Bridge addon (blender-mcp/addon/mcp_bridge_addon.py).
    This MUTATES the user's real open scene -- unlike run_blender_python,
    nothing here is disposable. Requires Blender to be running interactively
    (GUI, not --background) with the bridge addon enabled. Use
    check_blender_live_status first if unsure it's reachable.
    """
    if "import bpy" not in script_contents:
        script_contents = "import bpy\n" + script_contents

    try:
        response = _send_live_request(script_contents, host, port, LIVE_TIMEOUT)
    except (OSError, ConnectionError) as e:
        return (
            f"Execution Failed: could not reach live Blender instance at {host}:{port} ({e}). "
            "Is Blender open with the MCP Live Bridge addon enabled?"
        )

    if response.get("status") == "ok":
        delta = response.get("object_count_delta", 0)
        return f"Execution Success (object count delta: {delta:+d}):\n{response.get('stdout', '')}"
    return f"Execution Failed:\n{response.get('error', 'unknown error')}\nOutput:\n{response.get('stdout', '')}"


if __name__ == "__main__":
    mcp.run()

