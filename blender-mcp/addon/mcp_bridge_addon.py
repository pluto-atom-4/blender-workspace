"""MCP Live Bridge addon.

Install: Edit > Preferences > Add-ons > Install... > select this file > enable
"MCP Live Bridge". Starts automatically on enable, stops on disable/Blender exit.

Exposes a localhost TCP socket (default 127.0.0.1:9876) that an external MCP
server (blender-mcp/blender_mcp.py, tool `run_blender_python_live`) can send
Python source to. Code always executes on Blender's main thread via
bpy.app.timers, since bpy is not thread-safe. Requires Blender to be running
interactively (GUI) -- in --background mode there is no running event loop to
drive the timers, so the bridge would never process queued requests.

Wire protocol: 4-byte big-endian length prefix + UTF-8 JSON payload, both
directions.
  request:  {"code": "<python source>"}
  response: {"status": "ok", "stdout": "...", "object_count_delta": N}
         or {"status": "error", "stdout": "...", "error": "<traceback>"}
"""

bl_info = {
    "name": "MCP Live Bridge",
    "author": "blender-workspace",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "N/A (background service, no UI panel)",
    "description": "Local TCP bridge so an external MCP server can run Python inside this live Blender session.",
    "category": "Development",
}

import bpy
import contextlib
import io
import json
import queue
import socket
import struct
import threading
import traceback

HOST = "127.0.0.1"
PORT = 9876
RECV_TIMEOUT = 30.0

_server_socket = None
_server_thread = None
_stop_event = threading.Event()
_job_queue = queue.Queue()


def _recv_exact(conn, n):
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def _recv_message(conn):
    header = _recv_exact(conn, 4)
    if header is None:
        return None
    length = struct.unpack(">I", header)[0]
    body = _recv_exact(conn, length)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


def _send_message(conn, obj):
    payload = json.dumps(obj).encode("utf-8")
    conn.sendall(struct.pack(">I", len(payload)) + payload)


def _drain_queue():
    """bpy.app.timers callback: runs on Blender's main thread."""
    try:
        job = _job_queue.get_nowait()
    except queue.Empty:
        return None
    job()
    return None


def _execute_on_main_thread(code, result, done_event):
    before = len(bpy.data.objects)
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exec(compile(code, "<mcp_live>", "exec"), {"bpy": bpy})
        result["status"] = "ok"
        result["stdout"] = stdout.getvalue()
        result["object_count_delta"] = len(bpy.data.objects) - before
    except Exception:
        result["status"] = "error"
        result["stdout"] = stdout.getvalue()
        result["error"] = traceback.format_exc()
    finally:
        done_event.set()


def _handle_client(conn, addr):
    try:
        request = _recv_message(conn)
        if not request:
            return
        code = request.get("code", "")

        result = {}
        done_event = threading.Event()
        _job_queue.put(lambda: _execute_on_main_thread(code, result, done_event))
        bpy.app.timers.register(_drain_queue, first_interval=0.0)

        if not done_event.wait(timeout=RECV_TIMEOUT):
            result = {"status": "error", "error": "timed out waiting for main-thread execution"}

        _send_message(conn, result)
    except (OSError, ConnectionError):
        pass
    finally:
        conn.close()


def _serve():
    global _server_socket
    _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_socket.bind((HOST, PORT))
    _server_socket.listen(5)
    _server_socket.settimeout(0.5)
    while not _stop_event.is_set():
        try:
            conn, addr = _server_socket.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        threading.Thread(target=_handle_client, args=(conn, addr), daemon=True).start()


def start_bridge():
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return
    _stop_event.clear()
    _server_thread = threading.Thread(target=_serve, daemon=True)
    _server_thread.start()


def stop_bridge():
    _stop_event.set()
    if _server_socket is not None:
        try:
            _server_socket.close()
        except OSError:
            pass


class MCP_OT_start_bridge(bpy.types.Operator):
    bl_idname = "mcp.start_bridge"
    bl_label = "Start MCP Live Bridge"

    def execute(self, context):
        start_bridge()
        return {"FINISHED"}


class MCP_OT_stop_bridge(bpy.types.Operator):
    bl_idname = "mcp.stop_bridge"
    bl_label = "Stop MCP Live Bridge"

    def execute(self, context):
        stop_bridge()
        return {"FINISHED"}


classes = (MCP_OT_start_bridge, MCP_OT_stop_bridge)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    start_bridge()


def unregister():
    stop_bridge()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
