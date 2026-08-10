"""Ursina 3D scene for real-time maze generation visualization."""

import math
import time
import __main__

from ursina import Ursina, Entity, camera, color, Vec3
from ursina.shaders import basic_lighting_shader

from maze.prims import prims_maze_generator, StepKind

# Configuration: tune these to control maze size and animation speed
WIDTH = 31  # Maze width (must be odd)
HEIGHT = 31  # Maze height (must be odd)
ANIMATION_SPEED = 0.05  # Seconds between animation steps
START_CELL = (1, 1)  # Expose start coordinate for visual initialization

# Color scheme: 3D depth via hue differentiation + height + lighting
WALL_COLOR = color.hsv(225, 0.45, 0.55)    # slate blue — unvisited walls (raised)
PATH_COLOR = color.hsv(35, 0.55, 0.85)     # warm sand — carved paths (lowered)
FRONTIER_COLOR = color.orange               # transient generation state
CURRENT_COLOR = color.green                 # transient generation state

# Camera framing constants
CAMERA_MARGIN = 1.15  # headroom so maze edges aren't flush with viewport edges
CELL_Y_EXTENT = 1.0   # cube half-extent (0.5) + travel between wall/path y (±0.5)

# Module-level state for the update loop
_maze_gen = None
_grid_entities = {}
_timer = 0.0


def _frame_camera_on_maze(width, height, margin=CAMERA_MARGIN):
    """Position/size an orthographic camera so the full width x height maze
    fits the viewport regardless of maze size or window aspect ratio.

    Args:
        width: Maze width in cells
        height: Maze height in cells
        margin: Scale factor for headroom (e.g. 1.15 = 15% padding)
    """
    camera.orthographic = True
    camera.rotation_x = 60
    camera.rotation_y = 30

    # Maze center in world space
    center = Vec3((width - 1) / 2, 0, (height - 1) / 2)

    # All corners of the bounding box: x in [0, width-1], y in [-CELL_Y_EXTENT, CELL_Y_EXTENT], z in [0, height-1]
    xs = (0, width - 1)
    ys = (-CELL_Y_EXTENT, CELL_Y_EXTENT)
    zs = (0, height - 1)
    corners = [Vec3(x, y, z) for x in xs for y in ys for z in zs]

    # Get camera orientation vectors (these require a lens to exist, so camera must be initialized)
    right = camera.right
    up = camera.up
    forward = camera.forward

    # Project all corners onto camera-space axes and find the half-extents needed
    half_width = max(abs((c - center).dot(right)) for c in corners)
    half_height = max(abs((c - center).dot(up)) for c in corners)

    # orthographic fov is the vertical film size; horizontal = fov * aspect_ratio
    # We need to fit both axes, so we compute required fov for each and take the max
    required_fov = max(half_height * 2, (half_width * 2) / camera.aspect_ratio)
    camera.fov = required_fov * margin

    # Position camera far enough back so the entire framed scene fits in view
    # (diagonal distance estimate + extra buffer to avoid clipping)
    diagonal = math.hypot(width, height)
    distance = diagonal * margin + 10
    camera.position = center - forward * distance


def update():
    """Ursina update function called every frame. Process maze generation steps."""
    global _timer, _maze_gen
    if _maze_gen is None:
        return

    _timer += time.dt

    # Process maze generation steps at controlled rate
    while _timer >= ANIMATION_SPEED:
        _timer -= ANIMATION_SPEED
        try:
            step = next(_maze_gen)
            _process_step(step)
        except StopIteration:
            # Maze generation complete
            _maze_gen = None
            break


def run():
    """Initialize and run the Ursina scene."""
    global _maze_gen, _grid_entities, _timer

    # Create Ursina application (opens window only when called)
    app = Ursina(title="Prim's Maze Generation")

    # Initialize maze generator
    _maze_gen = prims_maze_generator(WIDTH, HEIGHT, seed=42)

    # Build initial grid of solid cubes (all wall_color, representing unvisited walls)
    # with basic_lighting_shader for 3D depth via per-face normal shading
    for x in range(WIDTH):
        for z in range(HEIGHT):
            entity = Entity(
                model="cube",
                color=WALL_COLOR,
                shader=basic_lighting_shader,
                position=(x, 0.5, z),
                scale=(1, 1, 1),
                collider="box",
            )
            _grid_entities[(x, z)] = entity

    # Initialize start cell to carved visual state (path_color, lowered position)
    start_x, start_z = START_CELL
    if (start_x, start_z) in _grid_entities:
        start_entity = _grid_entities[(start_x, start_z)]
        start_entity.color = PATH_COLOR
        start_entity.position = (start_x, -0.5, start_z)

    # Set up orthographic camera to frame the full maze regardless of size or aspect ratio
    _frame_camera_on_maze(WIDTH, HEIGHT)

    # Register update function with __main__ module globals
    # Ursina's _update() task looks for update() in __main__ module
    __main__.update = update

    # Run the application
    app.run()


def _process_step(step):
    """Process a single maze generation step and update the scene."""
    if step.kind == StepKind.FRONTIER_ADDED:
        # Color frontier cells orange (transient)
        for x, z in step.cells:
            if (x, z) in _grid_entities:
                _grid_entities[(x, z)].color = FRONTIER_COLOR

    elif step.kind == StepKind.CURRENT:
        # Color current cell green (transient)
        if step.current:
            x, z = step.current
            if (x, z) in _grid_entities:
                _grid_entities[(x, z)].color = CURRENT_COLOR

    elif step.kind == StepKind.CARVED:
        # Animate carved cells downward and change to path color
        for x, z in step.cells:
            if (x, z) in _grid_entities:
                entity = _grid_entities[(x, z)]
                entity.color = PATH_COLOR
                # Animate to lowered position over 0.1 seconds
                entity.animate_position((x, -0.5, z), duration=0.1)
