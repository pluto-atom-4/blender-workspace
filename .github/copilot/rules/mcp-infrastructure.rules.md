---
name: mcp-infrastructure
description: FastMCP server rules, MCP tool safety, and run_blender_python vs run_blender_python_live
applies_to: ["blender-mcp/**/*.py"]
---

# MCP Infrastructure Rules

FastMCP server and live bridge addon — the only interface between agents and Blender.

## Architectural Principles

- **Change only for tool-interface reasons** — this is infrastructure every script depends on.
  - Refactors here break all three tools at once for no modeling benefit.
  - Before modifying, verify the change affects the MCP method signature (input/output).

- **Keep server generic** — no Blender-specific business logic.
  - Modeling/rendering logic lives in agent-authored scripts in `blender-project/scripts/`.
  - The server's only job: spawn `blender` or talk to the live addon.

## Two Execution Paths (Not Interchangeable)

### `run_blender_python` — Default (Headless, Disposable)

- **Use when:** modeling, rendering, or one-shot data generation.
  - No live GUI needed; reproducibility is paramount.
  - Process isolation: each call is a fresh `blender --background` process.
  - Crashing/hung scripts can't leak state to the next call.

- **How it works:**
  ```bash
  blender --background --python-expr <script>
  ```
  - Prepends `import bpy` if missing (script can assume `bpy` is available).
  - Inherits parent environment (`WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, etc.).
  - Synchronous, blocking until Blender exits.
  - Returns stdout on success, stderr+stdout on failure.

### `run_blender_python_live` — Interactive (GUI, Stateful)

- **Use only when:** the task requires acting on the user's open Blender window.
  - **Mutates real scene state** — changes are live and visible to the user.
  - Talk to the bridge addon (must be enabled and running in an interactive Blender GUI).
  - Never use `--background`; `bpy.app.timers` doesn't tick headlessly.

- **Before calling:** use `check_blender_live_status` (cheap reachability probe) to avoid a 30s timeout.

- **Wire protocol:**
  - 4-byte big-endian length prefix + UTF-8 JSON, both directions.
  - Request: `{"code": "..."}`
  - Response: `{"status": "ok", "stdout": "...", "object_count_delta": N}` or `{"status": "error", "stdout": "...", "error": "<traceback>"}`
  - Raw TCP chosen over WebSocket/HTTP to avoid third-party dependencies (both sides use stdlib only).

## Live Bridge Addon (`addon/mcp_bridge_addon.py`)

### Thread Safety

- **Main-thread execution only** — `bpy` is not thread-safe.
  - Socket server runs on a background `threading.Thread` per connection.
  - Never calls `bpy` directly — enqueues request via `queue.Queue`.
  - Registers a `bpy.app.timers` callback to drain the queue on Blender's main thread.
  - Result handed back to socket thread via `threading.Event`.

### Dependencies

- **Standard library only** — `bpy`, `socket`, `json`, `struct`, `threading`, `queue`, `contextlib`, `io`, `traceback`.
  - The addon runs inside Blender's bundled Python, which has no access to this subproject's `uv` environment.
  - Third-party imports make the addon fail to register.

### Configuration

- **Environment variables:**
  - `BLENDER_MCP_LIVE_HOST` (default `127.0.0.1`)
  - `BLENDER_MCP_LIVE_PORT` (default `9876`)
  - `BLENDER_MCP_LIVE_TIMEOUT` (default `30` seconds)
  - Addon defaults must match server defaults (divergent defaults look like "addon not enabled").

### Error Handling

- Return errors as structured JSON with traceback, not as exceptions that crash tool calls.
  - Agents rely on `Execution Failed` + traceback to probe scene state safely (see issue #10).
  - Example: `{"status": "error", "stdout": "", "error": "Traceback..."}`

## Wire Protocol Implementation

### Message Format

- **Sender side:**
  ```python
  length = struct.pack(">I", len(json_bytes))
  socket.sendall(length + json_bytes)
  ```
  - 4-byte big-endian unsigned int (network byte order).

- **Receiver side:**
  ```python
  length_bytes = _recv_exact(sock, 4)
  msg_len = struct.unpack(">I", length_bytes)[0]
  msg_bytes = _recv_exact(sock, msg_len)
  ```
  - Always read exactly the declared number of bytes (`_recv_exact`).
  - A single `recv()` can return short reads on large payloads (e.g., multi-MB scripts).
  - Mismatched length = `json.JSONDecodeError` on valid input (subtle, hard to debug).

- **Keep both ends in sync** — change one side only and the peer blocks forever.

## Safety & Resilience

- **Avoid silent fallbacks:**
  - If a task requests the live path and a technical limitation forces headless, say so explicitly in PR/commit/issue comment.
  - It's a stated requirement, not an implementation detail.

- **Scene state drift warning (issue #10):**
  - User manual edits in the GUI mid-session can drift scene state between calls.
  - Re-read baseline (`bpy.data.objects`) before assuming an object name still exists.
  - Don't trust earlier snapshots; probe object names with `KeyError` handling (safe under the error-return protocol).

- **Data-block cleanup:**
  - `bpy.data.objects.remove()` does not remove mesh/material data-blocks.
  - Remove orphaned data-blocks explicitly (check `.users == 0` first) or they leak.

## Headless-Specific Constraints

- **No timers under `--background`:**
  - `bpy.app.timers` doesn't tick in headless mode.
  - Live bridge is GUI-only by construction; headless path must stay a separate tool.
  - Trying to use live timers headlessly results in silent failure (no error, just no execution).

- **Use `bpy.app.background` to detect mode:**
  ```python
  if bpy.app.background:
      # Headless: save but don't show UI
      bpy.ops.wm.save_as_mainfile(filepath=path)
  else:
      # Live: skip save or handle UI
      pass
  ```
