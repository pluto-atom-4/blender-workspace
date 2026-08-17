---
applyTo: "blender-mcp/**/*.py"
description: "Rules for the FastMCP server and live bridge addon"
---

# MCP infrastructure

- Change this directory only when the **tool interface** changes. It's
  infrastructure every script depends on; refactors here break all three
  tools at once for no modeling benefit.
- Keep `addon/mcp_bridge_addon.py` on the Python standard library only
  (`bpy`, `socket`, `json`, `struct`, `threading`, `queue`,
  `contextlib`/`io`/`traceback`). The addon runs inside Blender's bundled
  interpreter, which has no access to this subproject's `uv` environment —
  a third-party import makes the addon fail to register.
- Keep both ends of the wire protocol in sync: a 4-byte big-endian length
  prefix (`struct.pack(">I", ...)`) followed by a UTF-8 JSON payload. Change
  one side only and the peer blocks forever waiting on bytes that never
  match the declared length.
- Read exactly the number of bytes the prefix declares (`_recv_exact`).
  A single `recv()` can return a short read on a large script payload, which
  surfaces as a `json.JSONDecodeError` on valid input.
- Touch `bpy` only on Blender's main thread. The socket server runs on a
  worker thread and must hand work to the main thread via a `queue` drained
  from a `bpy.app.timers` callback — calling `bpy` from the socket thread
  crashes Blender rather than raising.
- Never rely on timers under `--background`. `bpy.app.timers` doesn't tick
  headlessly, so the live bridge is GUI-only by construction; the headless
  path must stay a separate `blender --background` subprocess.
- Read connection config from `BLENDER_MCP_LIVE_HOST` (default
  `127.0.0.1`), `BLENDER_MCP_LIVE_PORT` (`9876`), and
  `BLENDER_MCP_LIVE_TIMEOUT` (`30`), keeping the addon's defaults identical
  to the server's. Divergent defaults produce a connection refused that
  looks like a missing addon.
- Return errors as a structured result with the traceback, not an exception
  that kills the tool call. Agents rely on `Execution Failed` + traceback to
  probe scene state safely (issue #10).
