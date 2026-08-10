"""Tests for maze.prims Prim's Algorithm implementation."""

import pytest
from maze.prims import prims_maze_generator, StepKind, MazeStep


class TestPrimsMazeGenerator:
    """Test suite for the Prim's maze generator."""

    def test_odd_dimensions_required(self):
        """Even width or height should raise ValueError."""
        with pytest.raises(ValueError, match="must be odd"):
            list(prims_maze_generator(30, 31))

        with pytest.raises(ValueError, match="must be odd"):
            list(prims_maze_generator(31, 30))

        with pytest.raises(ValueError, match="must be odd"):
            list(prims_maze_generator(32, 32))

    def test_valid_odd_dimensions(self):
        """Odd dimensions should work without raising."""
        gen = prims_maze_generator(5, 5)
        steps = list(gen)
        assert len(steps) > 0

    def test_generator_yields_maze_steps(self):
        """Generator should yield MazeStep objects."""
        gen = prims_maze_generator(7, 7)
        for step in gen:
            assert isinstance(step, MazeStep)
            assert step.kind in StepKind
            assert isinstance(step.cells, tuple)
            assert isinstance(step.frontier, frozenset)
            if step.kind == StepKind.CURRENT:
                assert step.current is not None
            else:
                assert step.current is None

    def test_determinism_same_seed(self):
        """Two generators with the same seed should produce identical sequences."""
        gen1 = prims_maze_generator(7, 7, seed=42)
        gen2 = prims_maze_generator(7, 7, seed=42)

        steps1 = list(gen1)
        steps2 = list(gen2)

        assert len(steps1) == len(steps2)
        for s1, s2 in zip(steps1, steps2):
            assert s1.kind == s2.kind
            assert s1.cells == s2.cells
            assert s1.frontier == s2.frontier
            assert s1.current == s2.current

    def test_determinism_different_seed(self):
        """Different seeds should (likely) produce different sequences."""
        gen1 = prims_maze_generator(7, 7, seed=42)
        gen2 = prims_maze_generator(7, 7, seed=123)

        steps1 = list(gen1)
        steps2 = list(gen2)

        # Very unlikely to be identical with different seeds
        assert steps1 != steps2 or len(steps1) == 0

    def test_full_maze_generation_exhaustion(self):
        """Complete maze generation should exhaust the generator.

        After draining, all odd-coordinate interior cells should be carved.
        The start cell (1, 1) is initialized as carved but won't appear in
        CARVED steps; all others should appear via CARVED steps.
        """
        width, height = 9, 9
        gen = prims_maze_generator(width, height, seed=42)
        steps = list(gen)

        # Reconstruct grid from generator behavior
        assert len(steps) > 0

        # Track which cells have been carved from CARVED steps
        carved_cells = set()
        for step in steps:
            if step.kind == StepKind.CARVED:
                carved_cells.update(step.cells)

        # Start cell is initialized as carved but not emitted in a CARVED step
        start_cell = (1, 1)
        carved_cells.add(start_cell)

        # All interior cells (odd coordinates) should have been carved
        for x in range(1, width, 2):
            for z in range(1, height, 2):
                assert (x, z) in carved_cells, f"Cell ({x}, {z}) was not carved"

    def test_frontier_contains_only_unvisited_cells(self):
        """Every yielded step's frontier should contain only unvisited cells.

        Verify by tracking which cells have been carved.
        """
        width, height = 7, 7
        gen = prims_maze_generator(width, height, seed=42)

        # Simulate the grid to track carved vs. unvisited
        grid = [[1] * width for _ in range(height)]
        grid[1][1] = 0  # Start cell is carved

        for step in gen:
            # All frontier cells should currently have grid value 1 (unvisited)
            for x, z in step.frontier:
                assert grid[z][x] == 1, (
                    f"Frontier cell ({x}, {z}) is carved "
                    f"but still in frontier at step {step}"
                )

            # Process this step to update grid
            if step.kind == StepKind.CARVED:
                for x, z in step.cells:
                    grid[z][x] = 0

    def test_current_cell_was_in_frontier(self):
        """A CURRENT step's cell should have been in a preceding FRONTIER_ADDED.

        Track frontier state across steps.
        """
        gen = prims_maze_generator(7, 7, seed=42)

        frontier_cells_ever = set()
        for step in gen:
            if step.kind == StepKind.FRONTIER_ADDED:
                frontier_cells_ever.update(step.cells)
            elif step.kind == StepKind.CURRENT:
                assert step.current in frontier_cells_ever, (
                    f"Current cell {step.current} was never in frontier"
                )

    def test_step_sequence_starts_with_frontier_added(self):
        """First step should be FRONTIER_ADDED (initial frontier)."""
        gen = prims_maze_generator(7, 7, seed=42)
        steps = list(gen)

        assert len(steps) > 0
        assert steps[0].kind == StepKind.FRONTIER_ADDED

    def test_step_kind_patterns(self):
        """After a CURRENT step, next should be CARVED (same cell/wall pair)."""
        gen = prims_maze_generator(7, 7, seed=42)
        steps = list(gen)

        for i, step in enumerate(steps):
            if step.kind == StepKind.CURRENT:
                # Next step should be CARVED
                assert i + 1 < len(steps)
                assert steps[i + 1].kind == StepKind.CARVED

    def test_no_carved_cells_in_frontier(self):
        """Frontier should never contain a cell that was previously carved."""
        gen = prims_maze_generator(7, 7, seed=42)

        carved_ever = set()
        for step in gen:
            # Check that no carved cell is in the frontier
            carved_in_frontier = carved_ever & step.frontier
            assert (
                len(carved_in_frontier) == 0
            ), f"Carved cells in frontier: {carved_in_frontier}"

            # Update carved set
            if step.kind == StepKind.CARVED:
                carved_ever.update(step.cells)

    def test_maze_size_coverage(self):
        """Test with various maze sizes."""
        for size in [5, 7, 11, 15]:
            gen = prims_maze_generator(size, size, seed=42)
            steps = list(gen)
            assert len(steps) > 0, f"Empty step list for {size}x{size}"

    def test_cells_tuple_immutability(self):
        """MazeStep.cells should be a tuple (immutable)."""
        gen = prims_maze_generator(7, 7)
        for step in gen:
            assert isinstance(step.cells, tuple)
            if step.cells:
                # Verify we can't modify it
                with pytest.raises(TypeError):
                    step.cells[0] = (0, 0)

    def test_frontier_frozenset_immutability(self):
        """MazeStep.frontier should be a frozenset (immutable)."""
        gen = prims_maze_generator(7, 7)
        for step in gen:
            assert isinstance(step.frontier, frozenset)
            # Verify we can't modify it
            with pytest.raises(AttributeError):
                step.frontier.add((0, 0))

    def test_none_seed_valid(self):
        """None seed should work (uses current time)."""
        gen = prims_maze_generator(7, 7, seed=None)
        steps = list(gen)
        assert len(steps) > 0
