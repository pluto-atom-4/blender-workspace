"""Ursina 3D scene for real-time maze generation visualization."""

import math
import time
import __main__

from ursina import Ursina, Entity, camera, Vec3

from maze.prims import prims_maze_generator, StepKind
from render.settings import settings
from render.shaders import dynamic_lighting_shader, _light_dir_from_angles
from render import ui_panel
from render import playback_bar

# Configuration: tune these to control maze size and animation speed
WIDTH = 31  # Maze width (must be odd)
HEIGHT = 31  # Maze height (must be odd)
ANIMATION_SPEED = 0.05  # Seconds between animation steps
START_CELL = (1, 1)  # Expose start coordinate for visual initialization

# Camera framing constants
CAMERA_MARGIN = 1.15  # headroom so maze edges aren't flush with viewport edges
CELL_Y_EXTENT = 1.0   # cube half-extent (0.5) + travel between wall/path y (±0.5)

# Camera presets: Isometric only
CAMERA_PRESETS = {
    "Isometric": dict(rotation_x=60, rotation_y=30, orthographic=True),
}

# Module-level state for the update loop
_step_log = []  # Pre-computed list of MazeStep objects
_current_step_index = 0  # Current playback index
_playback_state = "playing"  # "playing" or "paused"
_timer = 0.0

_grid_entities = {}
_cell_state = {}  # Track each cell's logical role: 'wall'|'path'|'frontier'|'current'

# Camera state
_base_camera_position = Vec3(0, 0, 0)  # Stored after preset application
_base_camera_rotation = Vec3(0, 0, 0)  # Stored after preset application


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
    """Apply a camera preset and store the base position and rotation for offset adjustments.

    Args:
        name: Preset name (key in CAMERA_PRESETS dict)
    """
    if name not in CAMERA_PRESETS:
        print(f"Unknown preset: {name}, ignoring")
        return

    settings.camera_preset = name
    preset = CAMERA_PRESETS[name]

    # Orthographic preset (only Isometric exists now)
    _frame_camera_on_maze(
        WIDTH,
        HEIGHT,
        margin=CAMERA_MARGIN,
        rotation_x=preset["rotation_x"],
        rotation_y=preset["rotation_y"],
        orthographic=True,
    )

    # Store base position and rotation, reset rotation offset
    global _base_camera_position, _base_camera_rotation
    _base_camera_position = Vec3(camera.position)
    _base_camera_rotation = Vec3(camera.rotation_x, camera.rotation_y, camera.rotation_z)
    settings.camera_rotation_offset = Vec3(0, 0, 0)


def _apply_camera_rotation_offset():
    """Apply rotation offset on top of base rotation."""
    camera.rotation_x = _base_camera_rotation.x + settings.camera_rotation_offset.x
    camera.rotation_y = _base_camera_rotation.y + settings.camera_rotation_offset.y
    camera.rotation_z = _base_camera_rotation.z + settings.camera_rotation_offset.z


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


def _reset_grid_state():
    """Reset grid to initial state: all walls + start cell carved."""
    global _grid_entities, _cell_state

    # Reset all cells to wall state
    for (x, z) in _grid_entities:
        entity = _grid_entities[(x, z)]
        entity.color = settings.wall_color
        entity.position = (x, 0.5, z)  # Raised position
        _cell_state[(x, z)] = "wall"

    # Initialize start cell to carved visual state
    start_x, start_z = START_CELL
    if (start_x, start_z) in _grid_entities:
        start_entity = _grid_entities[(start_x, start_z)]
        start_entity.color = settings.path_color
        start_entity.position = (start_x, -0.5, start_z)  # Lowered position
        _cell_state[(start_x, start_z)] = "path"


def _process_step(step, instant=False):
    """Process a single maze generation step and update the scene.

    Args:
        step: MazeStep object to process
        instant: If True, snap positions; if False, animate over duration
    """
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
                if instant:
                    entity.position = (x, -0.5, z)
                else:
                    entity.animate_position((x, -0.5, z), duration=0.1)


def seek_to(index):
    """Seek to a specific step in the maze generation.

    Args:
        index: Target step index (clamped to [0, len(_step_log)])
    """
    global _current_step_index

    index = max(0, min(index, len(_step_log)))
    _reset_grid_state()

    # Replay all steps up to target index with instant mode
    for step in _step_log[:index]:
        _process_step(step, instant=True)

    _current_step_index = index
    playback_bar.set_frame_text(index, len(_step_log))
    playback_bar.set_seek_slider(index, call_on_value_changed=False)


def play():
    """Resume playback."""
    global _playback_state
    _playback_state = "playing"
    playback_bar.update_play_pause_label(True)


def pause():
    """Pause playback."""
    global _playback_state
    _playback_state = "paused"
    playback_bar.update_play_pause_label(False)


def rewind():
    """Rewind to beginning and pause."""
    seek_to(0)
    pause()


def forward():
    """Fast-forward to end."""
    seek_to(len(_step_log))


def _on_play_pause():
    """Toggle play/pause state."""
    if _playback_state == "playing":
        pause()
    else:
        play()


def update():
    """Ursina update function called every frame. Process maze generation steps."""
    global _timer, _current_step_index, _playback_state

    # Handle panel scroll every frame regardless of playback state (no-ops if panel hidden)
    ui_panel.update_scroll()

    # Gate timer accrual on playback state
    if _playback_state != "playing":
        return

    _timer += time.dt

    # Process steps at controlled rate
    while _timer >= ANIMATION_SPEED and _current_step_index < len(_step_log):
        _timer -= ANIMATION_SPEED
        _process_step(_step_log[_current_step_index], instant=False)
        _current_step_index += 1
        playback_bar.set_frame_text(_current_step_index, len(_step_log))
        playback_bar.set_seek_slider(_current_step_index, call_on_value_changed=False)


def input(key):
    """Handle keyboard input."""
    if key == "tab":
        ui_panel.toggle()


def run():
    """Initialize and run the Ursina scene."""
    global _step_log, _current_step_index, _grid_entities, _timer, _playback_state

    # Create Ursina application (opens window only when called)
    app = Ursina(title="Prim's Maze Generation")

    # Pre-compute all maze generation steps
    _step_log = list(prims_maze_generator(WIDTH, HEIGHT, seed=42))

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
            _cell_state[(x, z)] = "wall"

    # Initialize start cell to carved visual state (path_color, lowered position)
    _reset_grid_state()

    # Apply initial camera preset and lighting
    _apply_camera_preset("Isometric")
    _apply_light_settings()

    # Build UI panels with callbacks
    def on_camera_rotation(axis, value):
        setattr(settings.camera_rotation_offset, axis, value)
        _apply_camera_rotation_offset()

    def on_light_changed(attr, value):
        setattr(settings, attr, value)
        _apply_light_settings()

    def on_color_changed(attr, value):
        setattr(settings, attr, value)
        _recolor_all_cells()

    # Build main control panel (no camera preset selector, no offset sliders)
    ui_panel.build_panel(on_camera_rotation, on_light_changed, on_color_changed)

    # Build playback bar with callbacks
    playback_bar.build_bar(
        on_rewind=rewind,
        on_play_pause=_on_play_pause,
        on_forward=forward,
        on_seek=seek_to,
    )

    # Initialize playback bar with step counts
    playback_bar.set_frame_text(_current_step_index, len(_step_log))
    playback_bar.set_seek_slider(0, max_value=len(_step_log))
    playback_bar.update_play_pause_label(True)  # Start in playing state

    # Register update and input functions with __main__ module globals
    # Ursina's _update() task looks for update() and input() in __main__ module
    __main__.update = update
    __main__.input = input

    # Run the application
    app.run()
