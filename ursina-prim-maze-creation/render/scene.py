"""Ursina 3D scene for real-time maze generation visualization."""

import math
import time
import __main__

from ursina import Ursina, Entity, camera, Vec3

from maze.prims import prims_maze_generator, StepKind
from render.settings import settings
from render.shaders import dynamic_lighting_shader, _light_dir_from_angles
from render import ui_panel

# Configuration: tune these to control maze size and animation speed
WIDTH = 31  # Maze width (must be odd)
HEIGHT = 31  # Maze height (must be odd)
ANIMATION_SPEED = 0.05  # Seconds between animation steps
START_CELL = (1, 1)  # Expose start coordinate for visual initialization

# Camera framing constants
CAMERA_MARGIN = 1.15  # headroom so maze edges aren't flush with viewport edges
CELL_Y_EXTENT = 1.0   # cube half-extent (0.5) + travel between wall/path y (±0.5)

# Camera presets: orthographic and perspective variants
CAMERA_PRESETS = {
    "Top-Down": dict(rotation_x=90, rotation_y=0, orthographic=True),
    "Isometric": dict(rotation_x=60, rotation_y=30, orthographic=True),
    "Side": dict(rotation_x=10, rotation_y=90, orthographic=True),
    "First-Person": dict(orthographic=False),  # Special handling in _apply_camera_preset
}

# Module-level state for the update loop
_maze_gen = None
_grid_entities = {}
_cell_state = {}  # Track each cell's logical role: 'wall'|'path'|'frontier'|'current'
_timer = 0.0
_base_camera_position = Vec3(0, 0, 0)  # Stored after preset application


def _frame_camera_on_maze(width, height, margin=CAMERA_MARGIN, rotation_x=60, rotation_y=30, orthographic=True):
    """Position/size an orthographic camera so the full width x height maze
    fits the viewport regardless of maze size or window aspect ratio.

    Args:
        width: Maze width in cells
        height: Maze height in cells
        margin: Scale factor for headroom (e.g. 1.15 = 15% padding)
        rotation_x: Camera pitch in degrees (60 = typical isometric)
        rotation_y: Camera yaw in degrees (30 = typical isometric)
        orthographic: If True, use orthographic; if False, use perspective (ignored here; caller handles)
    """
    camera.orthographic = orthographic
    camera.rotation_x = rotation_x
    camera.rotation_y = rotation_y

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


def _apply_camera_preset(name):
    """Apply a camera preset and store the base position for offset adjustments.

    Args:
        name: Preset name (key in CAMERA_PRESETS dict)
    """
    if name not in CAMERA_PRESETS:
        print(f"Unknown preset: {name}, ignoring")
        return

    settings.camera_preset = name
    preset = CAMERA_PRESETS[name]

    if name == "First-Person":
        # First-Person: perspective view near start cell at eye height
        # Does NOT call _frame_camera_on_maze (intentional - user won't see full maze)
        camera.orthographic = False
        camera.fov = 90
        start_x, start_z = START_CELL
        camera.position = Vec3(start_x, 0.5, start_z)
        camera.rotation_x = 0
        camera.rotation_y = 0
    else:
        # Orthographic presets: all use _frame_camera_on_maze with specified rotation
        _frame_camera_on_maze(
            WIDTH,
            HEIGHT,
            margin=CAMERA_MARGIN,
            rotation_x=preset["rotation_x"],
            rotation_y=preset["rotation_y"],
            orthographic=True,
        )

    # Store base position and reset offset
    global _base_camera_position
    _base_camera_position = Vec3(camera.position)
    settings.camera_offset = Vec3(0, 0, 0)


def _apply_camera_offset():
    """Apply relative camera offset on top of base position."""
    camera.position = _base_camera_position + settings.camera_offset


def _apply_light_settings():
    """Convert light_azimuth/elevation to light_dir and set shader uniforms."""
    light_dir = _light_dir_from_angles(settings.light_azimuth, settings.light_elevation)
    # Set shader uniforms on the root scene entity (propagates to all children with the shader)
    camera.parent.set_shader_input("light_dir", light_dir)
    camera.parent.set_shader_input("light_intensity", settings.light_intensity)
    camera.parent.set_shader_input("light_ambient", settings.light_ambient)


def _recolor_all_cells():
    """Recolor all cells based on their current state and settings colors."""
    for (x, z), state in _cell_state.items():
        if (x, z) in _grid_entities:
            color_map = {
                "wall": settings.wall_color,
                "path": settings.path_color,
                "frontier": settings.frontier_color,
                "current": settings.current_color,
            }
            _grid_entities[(x, z)].color = color_map.get(state, settings.wall_color)


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


def input(key):
    """Handle keyboard input."""
    if key == "tab":
        ui_panel.toggle()


def run():
    """Initialize and run the Ursina scene."""
    global _maze_gen, _grid_entities, _timer

    # Create Ursina application (opens window only when called)
    app = Ursina(title="Prim's Maze Generation")

    # Initialize maze generator
    _maze_gen = prims_maze_generator(WIDTH, HEIGHT, seed=42)

    # Build initial grid of solid cubes (all wall_color, representing unvisited walls)
    # with dynamic_lighting_shader for parameterizable 3D depth via light angle/intensity
    for x in range(WIDTH):
        for z in range(HEIGHT):
            entity = Entity(
                model="cube",
                color=settings.wall_color,
                shader=dynamic_lighting_shader,
                position=(x, 0.5, z),
                scale=(1, 1, 1),
                collider="box",
            )
            _grid_entities[(x, z)] = entity
            _cell_state[(x, z)] = "wall"  # Track initial state

    # Initialize start cell to carved visual state (path_color, lowered position)
    start_x, start_z = START_CELL
    if (start_x, start_z) in _grid_entities:
        start_entity = _grid_entities[(start_x, start_z)]
        start_entity.color = settings.path_color
        start_entity.position = (start_x, -0.5, start_z)
        _cell_state[(start_x, start_z)] = "path"

    # Apply initial camera preset and lighting
    _apply_camera_preset("Isometric")
    _apply_light_settings()

    # Build UI panel with callbacks
    def on_camera_preset(name):
        _apply_camera_preset(name)

    def on_camera_offset(axis, value):
        setattr(settings.camera_offset, axis, value)
        _apply_camera_offset()

    def on_light_changed(attr, value):
        setattr(settings, attr, value)
        _apply_light_settings()

    def on_color_changed(attr, value):
        setattr(settings, attr, value)
        _recolor_all_cells()

    ui_panel.build_panel(on_camera_preset, on_camera_offset, on_light_changed, on_color_changed)

    # Register update and input functions with __main__ module globals
    # Ursina's _update() task looks for update() and input() in __main__ module
    __main__.update = update
    __main__.input = input

    # Run the application
    app.run()


def _process_step(step):
    """Process a single maze generation step and update the scene."""
    if step.kind == StepKind.FRONTIER_ADDED:
        # Color frontier cells based on settings
        for x, z in step.cells:
            if (x, z) in _grid_entities:
                _grid_entities[(x, z)].color = settings.frontier_color
                _cell_state[(x, z)] = "frontier"

    elif step.kind == StepKind.CURRENT:
        # Color current cell based on settings
        if step.current:
            x, z = step.current
            if (x, z) in _grid_entities:
                _grid_entities[(x, z)].color = settings.current_color
                _cell_state[(x, z)] = "current"

    elif step.kind == StepKind.CARVED:
        # Animate carved cells downward and change to path color
        for x, z in step.cells:
            if (x, z) in _grid_entities:
                entity = _grid_entities[(x, z)]
                entity.color = settings.path_color
                _cell_state[(x, z)] = "path"
                # Animate to lowered position over 0.1 seconds
                entity.animate_position((x, -0.5, z), duration=0.1)
