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

This launches an interactive 3D window (requires a display). The visualization shows a grid of solid blocks that animate and change color as the maze carves itself:

- **Unvisited walls** (initial state): Slate blue (based on current settings)
- **Frontier cells** (reachable but not yet carved): Orange (customizable)
- **Current cell** (selected for carving): Green (customizable)
- **Carved paths**: Light sand (customizable), lowered by 0.5 units

### In-App Controls

Press **Tab** to toggle the control panel. The interface consists of:

#### Right-Side Control Panel (scrollable)
A unified vertical panel positioned on the right edge of the screen with three main sections:

- **Camera**:
  - *Rotation X, Y, Z*: Fine-tune camera pitch, yaw, and roll (±45° per axis)
  - Applied as an offset after the Isometric framing, allowing rotation without changing zoom/distance

- **Light**:
  - *Azimuth*: Rotate light around the maze (0–360°)
  - *Elevation*: Adjust light height (−10° to 90°)
  - *Intensity*: Scale diffuse shading strength (0–2×)

- **Colors**:
  - Primary colors: Wall, Path
  - Animation colors subsection: Frontier, Current
  - Use color pickers to customize in real time

The panel is scrollable via mouse wheel when the cursor hovers over it.

#### Bottom Playback Bar
A control bar at the bottom of the screen for maze generation animation:

- **Rewind Button** (|<): Jump to the start of the maze
- **Play/Pause Toggle** (> / ||): Resume or pause the animation
- **Forward Button** (>|): Jump to the end of the maze
- **Frame Counter**: Displays current step / total steps
- **Seek Slider**: Drag to jump to any point in the generation sequence

Changes to colors, light, and camera are applied instantly to the running visualization. Playback can be paused, resumed, and seeked without losing state.

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

For more advanced tuning (light angle defaults, camera margin, cell heights), see the constants in `render/scene.py`.

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
- **`render/scene.py`** — Ursina scene consumer. Builds a 3D grid of Entity cubes, pre-computes the full step log at startup, and registers an `update()` loop that consumes steps at a controlled rate. Dispatch on step kind to animate and recolor cells. Manages playback state (playing/paused) and provides seek/play/pause/rewind/forward controls.
- **`render/settings.py`** — Central `RenderSettings` dataclass holding all mutable state (colors, lighting angles/intensity, camera rotation offset). Shared singleton accessed by scene, shaders, and UI.
- **`render/shaders.py`** — Custom `dynamic_lighting_shader` (parameterized lighting via uniforms) and `_light_dir_from_angles()` conversion. Replaces the fixed `basic_lighting_shader` for real-time light angle/intensity adjustment.
- **`render/ui_panel.py`** — Right-side unified control panel builder: scrollable vertical layout with camera rotation sliders, light controls, and color pickers. Registered callbacks drive scene updates.
- **`render/playback_bar.py`** — Bottom playback control bar: rewind/play-pause/forward buttons, frame counter, and seek slider. Exposes helper functions for scene.py to update display without triggering feedback loops.
- **`main.py`** — Entry point; calls `run()` to initialize Ursina and start the visualization.
- **`tests/test_prims.py`** — Pytest suite for the algorithm; does not depend on Ursina.

## Limitations

- Requires an interactive display and window system (X11, Wayland, etc.). The visualization will fail in a headless environment.
- Cross-session persistence (saving/loading settings) is not implemented.
- Smooth camera interpolation between presets is deferred (camera is fixed to Isometric).
- Multi-light types (e.g., point lights, multiple directional lights) are deferred; the current shader uses a single directional light.
- Maze size, animation speed, and light defaults can only be tuned by editing source code — CLI flags are not yet implemented.
- Auto re-framing on window resize is not implemented.
