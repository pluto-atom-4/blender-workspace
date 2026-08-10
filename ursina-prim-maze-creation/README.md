# ursina-prim-maze-creation

Isolated `uv` subproject: Real-time 3D animated maze generation using **Prim's Algorithm** on the **Ursina Engine** (which sits on top of Panda3D). This project is completely standalone — it has its own `pyproject.toml`, `uv.lock`, and virtual environment, with zero shared dependencies or imports from `blender-mcp/` or `blender-project/`. Ursina and Panda3D are **not** added to any Blender-related manifest, and `bpy` has no place here.

## Install

```bash
cd ursina-prim-maze-creation
uv sync --extra test
```

`requires-python = ">=3.12"`. Core dependency: `ursina>=8.3.0` (which brings in Panda3D). The `test` extra adds `pytest`.

## Run

```bash
uv run main.py
```

This launches an interactive 3D window (requires a display). The visualization shows a grid of solid blocks (light gray = unvisited walls) that animate and change color as the maze carves itself:

- **Unvisited walls** (initial state): Light gray
- **Frontier cells** (reachable but not yet carved): Yellow/orange
- **Current cell** (selected for carving): Green
- **Carved paths**: Dark gray, lowered by 0.5 units

### Tuning Parameters

Edit constants at the top of `render/scene.py` to customize:

- `WIDTH` / `HEIGHT` — Maze dimensions (must be odd; default 31×31)
- `ANIMATION_SPEED` — Seconds between animation steps (default 0.05; smaller = faster)

Example: 7×7 maze with faster animation:

```python
WIDTH = 7
HEIGHT = 7
ANIMATION_SPEED = 0.02
```

Camera is set to an isometric-style 3D view; you can adjust `camera.position`, `camera.rotation_x`, and `camera.rotation_y` in the same file if you prefer a different angle.

## Tests

```bash
uv run --extra test pytest
```

`tests/test_prims.py` covers the core algorithm (`maze/prims.py`), which is pure Python with zero graphics dependencies:

- Odd dimensions enforced (even input raises `ValueError`)
- Full generator exhaustion verifies all interior cells are carved
- Determinism: identical seed produces identical step sequences
- Frontier consistency: every yielded frontier snapshot contains only unvisited cells at that moment
- Step sequencing: `CURRENT` steps are preceded by the cell appearing in `FRONTIER_ADDED`

The test suite does not import Ursina, so it runs without a display.

## Architecture

- **`maze/prims.py`** — Pure Python Prim's Algorithm generator. Yields `MazeStep` objects marking state transitions (frontier growth, current selection, carve events). No graphics code.
- **`render/scene.py`** — Ursina scene consumer. Builds a 3D grid of Entity cubes, registers an `update()` loop that consumes generator steps at a controlled rate, and dispatches on step kind to animate and recolor cells.
- **`main.py`** — Entry point; calls `run()` to initialize Ursina and start the visualization.
- **`tests/test_prims.py`** — Pytest suite for the algorithm; does not depend on Ursina.

## Limitations

- Requires an interactive display and window system (X11, Wayland, etc.). The visualization will fail in a headless environment.
- Camera is fixed (not user-controllable mid-run). Pause/resume and per-step control may be added in future work.
- Maze size and animation speed can only be tuned by editing `render/scene.py` — no CLI flags yet.
