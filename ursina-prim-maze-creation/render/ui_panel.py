"""Unified right-side control panel with scrollable sections."""
from ursina import Entity, Text, camera, mouse
from ursina.prefabs.slider import Slider
from ursina.prefabs.color_picker import ColorPicker

from render.settings import settings

# Module-level root entity for the panel (all UI parented here, toggled together)
panel_root = None
content = None
total_content_height = 0

# Configuration
PANEL_WIDTH = 0.3
PANEL_HALF_WIDTH = PANEL_WIDTH / 2
MARGIN = 0.02
SECTION_SPACING = 0.03
SLIDER_ROW_HEIGHT = 0.07
SLIDER_SECTION_TAIL_GAP = 0.02
COLOR_PICKER_SCALE = 0.6
COLOR_ROW_STEP = 0.14
PANEL_TOP = 0.4
BAR_TOP_Y = -0.45
BAR_CLEARANCE = 0.02
VIEWPORT_HEIGHT = PANEL_TOP - (BAR_TOP_Y + BAR_CLEARANCE)


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

    # === CAMERA SECTION ===
    Text(parent=content, text="Camera", x=-PANEL_HALF_WIDTH + 0.01, y=y_offset, scale=1.2, origin=(0, 0))
    y_offset -= 0.05

    # Rotation sliders (X, Y, Z) with range ±45°
    for i, axis in enumerate("xyz"):
        label_text = f"Rotation {axis.upper()}"
        s = Slider(
            min=-45,
            max=45,
            default=0,
            text=label_text,
            dynamic=True,
            parent=content,
            x=-PANEL_HALF_WIDTH + 0.01,
            y=y_offset - i * 0.07,
            step=1,
            width=0.25,
        )
        s.on_value_changed = (lambda axis=axis, s=s: on_camera_rotation(axis, s.value))

    y_offset -= (2 * SLIDER_ROW_HEIGHT + SLIDER_SECTION_TAIL_GAP)

    # === LIGHT SECTION ===
    y_offset -= SECTION_SPACING
    Text(parent=content, text="Light", x=-PANEL_HALF_WIDTH + 0.01, y=y_offset, scale=1.2, origin=(0, 0))
    y_offset -= 0.05

    az = Slider(
        min=0,
        max=360,
        default=settings.light_azimuth,
        text="Azimuth",
        dynamic=True,
        parent=content,
        x=-PANEL_HALF_WIDTH + 0.01,
        y=y_offset,
        step=1,
        width=0.25,
    )

    el = Slider(
        min=-10,
        max=90,
        default=settings.light_elevation,
        text="Elevation",
        dynamic=True,
        parent=content,
        x=-PANEL_HALF_WIDTH + 0.01,
        y=y_offset - 0.07,
        step=1,
        width=0.25,
    )

    intensity = Slider(
        min=0,
        max=2,
        default=settings.light_intensity,
        text="Intensity",
        dynamic=True,
        parent=content,
        x=-PANEL_HALF_WIDTH + 0.01,
        y=y_offset - 0.14,
        step=0.1,
        width=0.25,
    )

    # Wire light slider callbacks
    for s, attr in ((az, "light_azimuth"), (el, "light_elevation"), (intensity, "light_intensity")):
        s.on_value_changed = (lambda s=s, attr=attr: on_light_changed(attr, s.value))

    y_offset -= (2 * SLIDER_ROW_HEIGHT + SLIDER_SECTION_TAIL_GAP)

    # === COLORS SECTION ===
    y_offset -= SECTION_SPACING
    Text(parent=content, text="Colors", x=-PANEL_HALF_WIDTH + 0.01, y=y_offset, scale=1.2, origin=(0, 0))
    y_offset -= 0.05

    # Primary colors: Wall and Path
    for label, attr in (("Wall", "wall_color"), ("Path", "path_color")):
        cp = ColorPicker(parent=content, x=-PANEL_HALF_WIDTH + 0.05, y=y_offset, scale=COLOR_PICKER_SCALE)
        Text(parent=cp, text=label, y=0.04, origin=(0, 0), scale=0.8)
        cp.value = getattr(settings, attr)
        cp.on_value_changed = (lambda cp=cp, attr=attr: on_color_changed(attr, cp.value))
        y_offset -= COLOR_ROW_STEP

    # Animation colors subsection
    y_offset -= 0.015
    Text(parent=content, text="Animation", x=-PANEL_HALF_WIDTH + 0.01, y=y_offset, scale=1.0, origin=(0, 0))
    y_offset -= 0.02

    for label, attr in (("Frontier", "frontier_color"), ("Current", "current_color")):
        cp = ColorPicker(parent=content, x=-PANEL_HALF_WIDTH + 0.05, y=y_offset, scale=COLOR_PICKER_SCALE)
        Text(parent=cp, text=label, y=0.04, origin=(0, 0), scale=0.8)
        cp.value = getattr(settings, attr)
        cp.on_value_changed = (lambda cp=cp, attr=attr: on_color_changed(attr, cp.value))
        y_offset -= COLOR_ROW_STEP

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
