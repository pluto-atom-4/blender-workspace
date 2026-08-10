"""Prim's Algorithm maze generator - pure Python, zero graphics dependencies."""

from dataclasses import dataclass
from enum import Enum, auto
import random


class StepKind(Enum):
    """State transitions worth animating during maze generation."""
    FRONTIER_ADDED = auto()
    CURRENT = auto()
    CARVED = auto()


@dataclass(frozen=True)
class MazeStep:
    """A single state transition in the maze generation process.

    Attributes:
        kind: Type of state transition (FRONTIER_ADDED, CURRENT, CARVED)
        cells: Tuple of (x, y) coordinates affected by this step
        frontier: Immutable snapshot of unvisited frontier cells at this moment
        current: The cell being processed in a CURRENT step, or None
    """
    kind: StepKind
    cells: tuple[tuple[int, int], ...]
    frontier: frozenset[tuple[int, int]]
    current: tuple[int, int] | None


def prims_maze_generator(width: int, height: int, seed: int | None = None):
    """Generate a maze using Prim's Algorithm.

    Yields MazeStep objects at each state transition: frontier growth,
    current-cell selection, and carve events. Pure Python implementation
    with no graphics dependencies.

    Args:
        width: Maze width in cells (must be odd)
        height: Maze height in cells (must be odd)
        seed: Optional random seed for reproducible generation

    Yields:
        MazeStep objects representing animation-worthy state transitions

    Raises:
        ValueError: If width or height is even
    """
    # Enforce odd dimensions for standard wall/path parity
    if width % 2 == 0 or height % 2 == 0:
        raise ValueError(
            f"Width and height must be odd, got width={width}, height={height}"
        )

    # Initialize grid: 1 = wall (unvisited), 0 = path (carved)
    grid = [[1] * width for _ in range(height)]

    # Set up local RNG instance to avoid polluting global state
    rng = random.Random(seed)

    # Start at an odd interior coordinate (1, 1)
    start_x, start_y = 1, 1
    grid[start_y][start_x] = 0  # Mark start cell as path

    # Wall candidates: list of ((wall_x, wall_y), (target_x, target_y)) tuples
    # representing carving opportunities. We don't deduplicate here;
    # we check at pop time if the target is still unvisited.
    wall_candidates = []

    # Frontier cells: set of unvisited cells adjacent to carved paths
    # This set must stay deduplicated as it's presented to the renderer
    frontier_cells = set()

    # Initialize frontier with cells adjacent to start (distance 2 away)
    for dx, dy in [(0, -2), (0, 2), (-2, 0), (2, 0)]:
        nx, ny = start_x + dx, start_y + dy
        if 0 <= nx < width and 0 <= ny < height:
            # Add the wall between start and target as a candidate
            wall_x, wall_y = start_x + dx // 2, start_y + dy // 2
            wall_candidates.append(((wall_x, wall_y), (nx, ny)))
            frontier_cells.add((nx, ny))

    # Yield initial frontier
    if frontier_cells:
        yield MazeStep(
            kind=StepKind.FRONTIER_ADDED,
            cells=tuple(frontier_cells),
            frontier=frozenset(frontier_cells),
            current=None,
        )

    # Main algorithm loop
    while wall_candidates:
        # Pick a random wall candidate
        idx = rng.randint(0, len(wall_candidates) - 1)
        (wall_x, wall_y), (target_x, target_y) = wall_candidates.pop(idx)

        # Only process if target is still unvisited (grid value == 1)
        if grid[target_y][target_x] == 1:
            # Remove target from frontier before yielding CURRENT
            # (it's about to be carved and won't be a frontier cell anymore)
            frontier_cells.discard((target_x, target_y))

            # Yield CURRENT step: this cell is selected for carving
            yield MazeStep(
                kind=StepKind.CURRENT,
                cells=(),
                frontier=frozenset(frontier_cells),
                current=(target_x, target_y),
            )

            # Carve the wall and the target cell into the grid
            grid[wall_y][wall_x] = 0
            grid[target_y][target_x] = 0

            # Yield CARVED step: the carving is done
            yield MazeStep(
                kind=StepKind.CARVED,
                cells=((wall_x, wall_y), (target_x, target_y)),
                frontier=frozenset(frontier_cells),
                current=None,
            )

            # Discover newly-reachable neighbor cells from the just-carved cell
            new_frontier_cells = []
            for dx, dy in [(0, -2), (0, 2), (-2, 0), (2, 0)]:
                nx, ny = target_x + dx, target_y + dy
                # Check bounds, unvisited status, and not already in frontier
                if (
                    0 <= nx < width
                    and 0 <= ny < height
                    and grid[ny][nx] == 1
                    and (nx, ny) not in frontier_cells
                ):
                    # Add the wall between target and this new neighbor
                    wall_x_new, wall_y_new = (
                        target_x + dx // 2,
                        target_y + dy // 2,
                    )
                    wall_candidates.append(((wall_x_new, wall_y_new), (nx, ny)))
                    frontier_cells.add((nx, ny))
                    new_frontier_cells.append((nx, ny))

            # Yield FRONTIER_ADDED step for newly discovered cells
            if new_frontier_cells:
                yield MazeStep(
                    kind=StepKind.FRONTIER_ADDED,
                    cells=tuple(new_frontier_cells),
                    frontier=frozenset(frontier_cells),
                    current=None,
                )
