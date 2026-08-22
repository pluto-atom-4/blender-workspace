---
name: orchestration
description: Rules for the uv project isolation, pytest workflow, and dependency management
applies_to: ["blender-project/orchestration/**/*.py"]
---

# Orchestration Subproject Rules

Isolated uv subproject for non-Blender numeric/simulation code (LQR, Webots, telemetry parsing).

## Project Isolation

- **Separate uv subproject** — `blender-project/orchestration/` has its own `pyproject.toml` and `uv.lock`.
  - Mirrors `blender-mcp/`'s pattern, not a monolithic root environment.
  - Adding deps to a root environment leaks this subproject's numeric stack (`numpy`, `scipy`, `control`, `pandas`) into the MCP server's footprint.
  - **Do not merge** `uv.lock` changes across subprojects.

## Python Requirements

- **Pure Python only** — never `import bpy`.
  - This code runs under plain `uv` (not inside Blender), so a `bpy` import is an unconditional `ModuleNotFoundError`.
  - If interaction with Blender geometry is needed (e.g., export), write a separate `blender-project/scripts/export_*.py` that calls orchestration functions.

## Testing & Validation

- **Run tests with exactly:**
  ```bash
  cd blender-project/orchestration && uv run --extra test pytest
  ```
  - `pytest` is in the `test` extra only; `uv run pytest` bare fails to resolve.
  - CI will use this exact command; local deviation masks CI failures.

- **Test layout:**
  - Place tests in `tests/` as `test_<module>.py`.
  - Discovery is layout-based; a test file elsewhere in the subproject never runs and gives false confidence.

- **Test scope:**
  - **No Webots dependencies** — CI has no simulator installed. A test that shells out to `webots` turns a green suite red on CI only.
  - **No display dependencies** — no GUI, no X11/Wayland assumptions.
  - **Cross-check numeric results** — against a closed-form answer or a second library (e.g., `control.lqr()` cross-checks a Riccati solve). A converged gain that's wrong still returns cleanly; only an independent value catches it.

## External Process Handling

- **Subprocess wrappers** — wrap external processes (e.g., `webots`) with an explicit timeout and separate telemetry parsing:
  ```python
  def run_webots_headless(world_file, timeout=60):
      """Run Webots and return raw telemetry; timeout prevents hangs."""
      
  def parse_telemetry(telemetry_csv):
      """Parse separately from running; isolates failure modes."""
  ```
  - A hung simulator otherwise stalls the tuning loop with no output to diagnose.
  - Always capture `stdout`/`stderr` and log them on failure.

## Module Documentation

- **Include module-level docstring** noting deliberately out-of-scope work:
  ```python
  """
  LQR tuning loop for the armed inverted pendulum.
  
  Deferred scope:
  - LangGraph workflow orchestration
  - ESP32/PlatformIO firmware generation
  - HIL bridge (hardware-in-the-loop)
  - Web dashboard
  
  See WEBOTS.md for architecture notes.
  """
  ```
  - Without it, the next agent re-implements deferred scope as if it were missing.

## Dependencies

- Keep numeric/simulation logic in this subproject; keep scripting/glue in `blender-project/scripts/`.
- Use `control` for control theory (Riccati, LQR); `webots` for simulation; `pandas`/`numpy` for data manipulation.
- Document why each dependency is needed (not just "for Webots") in `pyproject.toml` comments or module docstrings.
