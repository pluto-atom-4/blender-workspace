"""Ursina 3D scene for real-time maze generation visualization."""

from ursina import Ursina, Entity, camera, color
import time
import __main__

from maze.prims import prims_maze_generator, StepKind

# Configuration: tune these to control maze size and animation speed
WIDTH = 31  # Maze width (must be odd)
HEIGHT = 31  # Maze height (must be odd)
ANIMATION_SPEED = 0.05  # Seconds between animation steps
START_CELL = (1, 1)  # Expose start coordinate for visual initialization

# Module-level state for the update loop
_maze_gen = None
_grid_entities = {}
_timer = 0.0


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

    # Build initial grid of solid cubes (all light gray, representing unvisited walls)
    for x in range(WIDTH):
        for z in range(HEIGHT):
            entity = Entity(
                model="cube",
                color=color.light_gray,
                position=(x, 0.5, z),
                scale=(1, 1, 1),
                collider="box",
            )
            _grid_entities[(x, z)] = entity

    # Initialize start cell to carved visual state (dark gray, lowered position)
    start_x, start_z = START_CELL
    if (start_x, start_z) in _grid_entities:
        start_entity = _grid_entities[(start_x, start_z)]
        start_entity.color = color.dark_gray
        start_entity.position = (start_x, -0.5, start_z)

    # Set up isometric camera
    camera.position = (WIDTH // 2, WIDTH, -HEIGHT // 2)
    camera.rotation_x = 60
    camera.rotation_y = 30

    # Register update function with __main__ module globals
    # Ursina's _update() task looks for update() in __main__ module
    __main__.update = update

    # Run the application
    app.run()


def _process_step(step):
    """Process a single maze generation step and update the scene."""
    if step.kind == StepKind.FRONTIER_ADDED:
        # Color frontier cells yellow/orange
        for x, z in step.cells:
            if (x, z) in _grid_entities:
                _grid_entities[(x, z)].color = color.orange

    elif step.kind == StepKind.CURRENT:
        # Color current cell green
        if step.current:
            x, z = step.current
            if (x, z) in _grid_entities:
                _grid_entities[(x, z)].color = color.green

    elif step.kind == StepKind.CARVED:
        # Animate carved cells downward and darken them
        for x, z in step.cells:
            if (x, z) in _grid_entities:
                entity = _grid_entities[(x, z)]
                entity.color = color.dark_gray
                # Animate to lowered position over 0.1 seconds
                entity.animate_position((x, -0.5, z), duration=0.1)
