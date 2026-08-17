---
applyTo: "blender-project/orchestration/**/*.py"
description: "Rules for the isolated uv orchestration subproject"
---

# Orchestration subproject

- Treat this as its own `uv` subproject: it has its own `pyproject.toml` and
  `uv.lock`, mirroring `blender-mcp/`. Adding deps to a root environment
  instead leaks this subproject's numeric stack (`numpy`, `scipy`,
  `control`, `pandas`) into the MCP server's footprint.
- Keep every module here pure Python — no `import bpy`. This code runs under
  plain `uv`, not inside Blender, so a `bpy` import is an unconditional
  `ModuleNotFoundError` rather than a degraded mode.
- Run tests with exactly:
  `cd blender-project/orchestration && uv run --extra test pytest`.
  `pytest` is in the `test` extra only, so a bare `uv run pytest` fails to
  resolve and reads as a broken suite.
- Put tests in `tests/` as `test_<module>.py`. The suite is discovered by
  layout; a test file elsewhere in the subproject never runs and gives false
  confidence.
- Keep tests free of Webots and display dependencies. CI has neither, so a
  test that shells out to `webots` turns a green suite red on the runner
  only.
- Cross-check numeric results against a second source (a closed-form answer
  or the `control` package's own `control.lqr()`), as
  `tests/test_lqr_tuner.py` does. A Riccati solve that converges to the
  wrong gain still returns cleanly — only an independent value catches it.
- Wrap external processes (`webots`) in a subprocess runner with an explicit
  timeout, and parse telemetry separately from running it. A hung simulator
  otherwise stalls the tuning loop with no output to diagnose.
- Note in the module docstring what's deliberately out of scope (LangGraph,
  ESP32 firmware, the HIL bridge, the dashboard — see WEBOTS.md). Without it,
  the next agent re-implements deferred scope as if it were missing.
