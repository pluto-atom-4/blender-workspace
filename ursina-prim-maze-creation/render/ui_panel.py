"""Unified right-side control panel with scrollable sections."""
from ursina import Entity, camera, mouse

from render.panel_sections import (
    PANEL_WIDTH,
    PANEL_HALF_WIDTH,
    MARGIN,
    PANEL_TOP,
    BAR_TOP_Y,
    BAR_CLEARANCE,
    VIEWPORT_HEIGHT,
    render_camera_controls,
    render_light_controls,
    render_color_controls,
)

# Module-level root entity for the panel (all UI parented here, toggled together)
panel_root = None
content = None
total_content_height = 0


def build_panel(on_camera_rotation, on_light_changed, on_color_changed):
    """Build a unified right-side vertical control panel.

    Args:
        on_camera_rotation: Callable(axis: str, value: float) - handles rotation sliders
        on_light_changed: Callable(attr: str, value: float) - handles light angle/intensity
        on_color_changed: Callable(attr: str, value: object) - handles color picker changes

    Returns:
        Entity (panel_root) that can be toggled with panel_root.enabled
    """
    global panel_root, content, total_content_height

    # === Main Panel Root (right-anchored) ===
    panel_root = Entity(parent=camera.ui, enabled=True)

    # Position panel on right side: aspect-anchored right edge
    # camera.ui spans [-aspect_ratio/2, aspect_ratio/2] horizontally
    # Right edge is at +aspect_ratio/2, so position the panel such that its right edge
    # aligns there with MARGIN spacing
    panel_root.x = camera.aspect_ratio / 2 - PANEL_HALF_WIDTH - MARGIN

    # === Background quad behind panel ===
    bg = Entity(
        parent=panel_root,
        model="quad",
        color=(0.15, 0.15, 0.15, 0.8),
        scale=(PANEL_WIDTH, 0.95),
        z=0.01,
    )

    # === Scrollable Content Container ===
    content = Entity(parent=panel_root, x=0, y=0)
    content.scroll_y_offset = 0  # Track scroll position

    y_offset = PANEL_TOP

    y_offset = render_camera_controls(content, y_offset, on_camera_rotation)
    y_offset = render_light_controls(content, y_offset, on_light_changed)
    y_offset = render_color_controls(content, y_offset, on_color_changed)

    # Calculate total content height for scroll limits
    total_content_height = abs(y_offset - 0.4)

    return panel_root


def toggle():
    """Toggle the panel visibility (call from input() handler on Tab)."""
    if panel_root:
        panel_root.enabled = not panel_root.enabled


def handle_scroll(direction):
    """Handle a discrete mouse-wheel scroll event over the panel.

    Args:
        direction: +1 for scroll up, -1 for scroll down.
    """
    if not panel_root or not panel_root.enabled or content is None:
        return

    # Check if mouse is within panel's x-range (hover-gate, preserved from update_scroll())
    panel_left = panel_root.x - PANEL_HALF_WIDTH
    panel_right = panel_root.x + PANEL_HALF_WIDTH

    if not (panel_left <= mouse.x <= panel_right):
        return

    max_scroll = max(0, total_content_height - VIEWPORT_HEIGHT)

    if direction > 0:  # Scroll up: return toward the top of the content
        content.y = max(0, content.y - 0.05)
    elif direction < 0:  # Scroll down: reveal lower content (content.y grows)
        content.y = min(max_scroll, content.y + 0.05)
