# Design

## Overview

The workspace splits into two concerns:

- **`blender-mcp/`** — a thin FastMCP server that is the only bridge between
  an agent and Blender. It has no Blender-specific logic beyond invoking the
  binary; all modeling/rendering logic lives in agent-authored scripts.
- **`blender-project/`** — the content produced and consumed by that bridge:
  scripts in, `.blend`/image files out.

This keeps the server generic and disposable — regenerating a model or
render is "write a script, run the tool," not "modify the server."

## Execution model

The MCP server exposes two independent execution paths, chosen per call
depending on whether the agent needs a disposable scene or the user's
actual open Blender window.

### Background execution (`run_blender_python`)

`run_blender_python` (`blender-mcp/blender_mcp.py`) takes a Python script as
a string and executes it via:

```
blender --background --python-expr <script>
```

Key properties:

- **Headless by default.** `--background` runs without a UI window, which is
  the common case (batch modeling/rendering). If a script needs to interact
  with a visible window (e.g. Wayland-specific preview tooling), the caller
  is responsible for passing the environment needed to attach to the running
  KDE Wayland session — the MCP process does not launch a UI on its own.
- **Environment passthrough.** The subprocess inherits the full parent
  environment (`os.environ.copy()`), so `WAYLAND_DISPLAY`,
  `XDG_RUNTIME_DIR`, etc. carry through without extra plumbing.
- **`import bpy` guaranteed.** The tool prepends `import bpy` if the script
  doesn't already import it, so agent-generated scripts can assume `bpy` is
  available.
- **Synchronous, blocking call.** `subprocess.run(..., check=True)` waits
  for Blender to exit and surfaces stdout on success or stderr (plus stdout)
  on failure. There is no streaming/progress channel — long-running renders
  block the tool call until completion.

### Live execution (`run_blender_python_live`)

`run_blender_python_live` and `check_blender_live_status`
(`blender-mcp/blender_mcp.py`) talk to a Blender addon
(`blender-mcp/addon/mcp_bridge_addon.py`) that must already be enabled
inside a running, interactive Blender instance:

```
[MCP server]  --TCP, length-prefixed JSON-->  [mcp_bridge_addon socket thread]
                                                        |
                                                queue.Queue handoff
                                                        v
                                          bpy.app.timers callback (main thread)
                                                        |
                                                 exec(code, {"bpy": bpy})
```

Key properties:

- **Main-thread execution only.** `bpy` is not thread-safe. The addon's
  socket server runs on a background `threading.Thread` per connection, but
  never calls `bpy` directly — it enqueues the request and registers a
  `bpy.app.timers` callback, which Blender drains on its own main thread on
  the next event-loop tick. The result is handed back to the waiting socket
  thread via a `threading.Event`.
- **Requires an interactive Blender process.** `bpy.app.timers` only ticks
  while Blender's event loop is running, i.e. a GUI instance — `--background`
  processes have no loop to drive it, so the live path is structurally
  incompatible with headless mode. This is why the two tools are separate
  rather than one tool with a flag.
- **Wire protocol.** 4-byte big-endian length prefix + UTF-8 JSON, both
  directions. Request: `{"code": "..."}`. Response:
  `{"status": "ok", "stdout": "...", "object_count_delta": N}` or
  `{"status": "error", "stdout": "...", "error": "<traceback>"}`. Raw TCP
  was chosen over WebSocket/HTTP to avoid adding a dependency on either
  side — both `blender-mcp` and Blender's bundled Python only need the
  standard library (`socket`, `json`, `struct`, `threading`, `queue`).
  This is a deliberate deviation from the WebSocket/HTTP framing sketched
  in the originating feature request; revisit if a browser-based client
  ever needs to talk to the bridge directly.
- **Mutates real state.** Unlike the background path, there is no process
  isolation — a script run live acts on the scene the user is actually
  looking at. `check_blender_live_status` exists so an agent can confirm
  reachability cheaply before running something that changes visible state.
- **Host/port configurable via env vars** (`BLENDER_MCP_LIVE_HOST`,
  `BLENDER_MCP_LIVE_PORT`, `BLENDER_MCP_LIVE_TIMEOUT`), defaulting to
  `127.0.0.1:9876` / 30s, matching the addon's default bind address.

## Script conventions

Scripts in `blender-project/scripts/` follow a naming pattern that separates
modeling from rendering, and rendering by camera angle:

- `model_<subject>.py` — builds the scene/mesh and saves a `.blend`.
- `render_<subject>.py` / `render_<subject>_<angle>.py` — loads or rebuilds
  the scene and renders a preview PNG from a specific viewpoint (`front`,
  `side`, `top`).

A `_precise` suffix marks a higher-fidelity variant of a model built from
more exact reference measurements, kept alongside the original rather than
replacing it, so both remain reproducible.

## Why FastMCP + subprocess instead of Blender's own Python API server

Blender's Python API (`bpy`) only runs inside a Blender process. For the
default case, rather than keeping a long-lived Blender instance with an RPC
layer, each tool call spawns a fresh `blender --background` process. This
trades startup latency per call for process isolation: a crashing or hung
script can't take down a shared Blender instance or leak state into the
next script run.

The live bridge addon is the deliberate exception to that isolation
tradeoff: when the task requires acting on an open Blender window (not a
disposable one), there is no way around talking to that specific long-lived
process. The design keeps the two paths cleanly separated (`run_blender_python`
vs `run_blender_python_live`) rather than unifying them, so the safe,
isolated default stays the default and the live path is opt-in per call.
