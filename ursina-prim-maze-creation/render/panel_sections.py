"""Individual control-section renderers for the right-side panel (Camera, Light, Colors).

Each render_*_controls() function is a pure function of (content, y_offset, callback):
it creates Entities parented under `content` and returns the y_offset immediately
after its section, for the caller to thread into the next section. No module-level
state is read or mutated here — panel_root/content/total_content_height stay owned
by render/ui_panel.py's build_panel()/toggle()/handle_scroll().
"""
from pathlib import Path

from ursina import Text
from ursina.prefabs.slider import Slider
from ursina.prefabs.color_picker import ColorPicker

from render.settings import settings

# Panel geometry configuration (moved here verbatim from ui_panel.py — every value
# below encodes a specific fix from issue #70's 4 review rounds; do not change any
# of them as part of this extraction).
PANEL_WIDTH = 0.32
PANEL_HALF_WIDTH = PANEL_WIDTH / 2
MARGIN = 0.02
SECTION_SPACING = 0.03
SLIDER_ROW_HEIGHT = 0.07
SLIDER_SECTION_TAIL_GAP = 0.02
COLOR_PICKER_SCALE = 0.6
COLOR_ROW_STEP = 0.14
SLIDER_WIDTH_FACTOR = 0.25 / 0.525  # Slider.bg is hardcoded to .525 wide (ursina/prefabs/slider.py);
                                     # scale the whole Slider (bg+knob together, siblings) to match the
                                     # originally-intended 0.25 width. Label is counter-scaled back to 1x.
PANEL_TOP = 0.4
BAR_TOP_Y = -0.45
BAR_CLEARANCE = 0.02
VIEWPORT_HEIGHT = PANEL_TOP - (BAR_TOP_Y + BAR_CLEARANCE)

def render_camera_controls(content, y_offset, on_camera_rotation):
    """Render the Camera section (header + X/Y/Z rotation sliders).

    Args:
        content: Parent Entity (panel's scrollable content container).
        y_offset: Starting y-position for this section's header.
        on_camera_rotation: Callable(axis: str, value: float).

    Returns:
        y_offset immediately after this section.
    """
    Text(parent=content, text="Camera", x=-PANEL_HALF_WIDTH + 0.16, y=y_offset, scale=1.0, origin=(0, 0))
    y_offset -= 0.05

    # Rotation sliders (X, Y, Z) with range ±45°
    for i, axis in enumerate("xyz"):
        label_text = f"{axis.upper()}"
        s = Slider(
            min=-45,
            max=45,
            default=0,
            text=label_text,
            dynamic=True,
            parent=content,
            x=-PANEL_HALF_WIDTH + 0.05,
            y=y_offset - i * 0.07,
            step=1,
        )
        s.scale_x = SLIDER_WIDTH_FACTOR
        s.label.scale_x = 1 / SLIDER_WIDTH_FACTOR
        s.on_value_changed = (lambda axis=axis, s=s: on_camera_rotation(axis, s.value))

    y_offset -= (2 * SLIDER_ROW_HEIGHT + SLIDER_SECTION_TAIL_GAP)

    return y_offset


def render_light_controls(content, y_offset, on_light_changed):
    """Render the Light section (header + Azimuth/Elevation/Intensity sliders).

    Args:
        content: Parent Entity.
        y_offset: Starting y-position, as left by the previous section.
        on_light_changed: Callable(attr: str, value: float).

    Returns:
        y_offset immediately after this section.
    """
    y_offset -= SECTION_SPACING
    Text(parent=content, text="Light", x=-PANEL_HALF_WIDTH + 0.16, y=y_offset, scale=1.0, origin=(0, 0))
    y_offset -= 0.05

    az = Slider(
        min=0,
        max=360,
        default=settings.light_azimuth,
        text="A",
        dynamic=True,
        parent=content,
        x=-PANEL_HALF_WIDTH + 0.05,
        y=y_offset,
        step=1,
    )



    el = Slider(
        min=-10,
        max=90,
        default=settings.light_elevation,
        text="E",
        dynamic=True,
        parent=content,
        x=-PANEL_HALF_WIDTH + 0.05,
        y=y_offset - 0.07,
        step=1,
    )


    intensity = Slider(
        min=0,
        max=2,
        default=settings.light_intensity,
        text="I",
        dynamic=True,
        parent=content,
        x=-PANEL_HALF_WIDTH + 0.05,
        y=y_offset - 0.14,
        step=0.1,
    )

    # az.label.font = "EmojiFont.ttf"
    # el.label.font = "EmojiFont.ttf"
    # intensity.label.font = "EmojiFont.ttf"

    # Wire light slider callbacks
    for s, attr in ((az, "light_azimuth"), (el, "light_elevation"), (intensity, "light_intensity")):
        s.scale_x = SLIDER_WIDTH_FACTOR
        s.label.scale_x = 1 / SLIDER_WIDTH_FACTOR
        s.on_value_changed = (lambda s=s, attr=attr: on_light_changed(attr, s.value))

    y_offset -= (2 * SLIDER_ROW_HEIGHT + SLIDER_SECTION_TAIL_GAP)

    return y_offset


def render_color_controls(content, y_offset, on_color_changed):
    """Render the Colors section: Wall/Path pickers, an Animation sub-header,
    then Frontier/Current pickers.

    Args:
        content: Parent Entity.
        y_offset: Starting y-position, as left by the previous section.
        on_color_changed: Callable(attr: str, value: object).

    Returns:
        y_offset immediately after this section.
    """
    y_offset -= SECTION_SPACING
    Text(parent=content, text="Colors", x=-PANEL_HALF_WIDTH + 0.16, y=y_offset, scale=1.0, origin=(0, 0))
    y_offset -= 0.05

    # Primary colors: Wall and Path
    for label, attr in (("Wall", "wall_color"), ("Path", "path_color")):
        cp = ColorPicker(parent=content, x=-PANEL_HALF_WIDTH + 0.16, y=y_offset, scale=COLOR_PICKER_SCALE)
        Text(parent=cp, text=label, y=0.04, origin=(0, 0), scale=0.8)
        cp.value = getattr(settings, attr)
        cp.on_value_changed = (lambda cp=cp, attr=attr: on_color_changed(attr, cp.value))
        y_offset -= COLOR_ROW_STEP

    # Animation colors subsection
    y_offset -= 0.05  # was 0.015 — insufficient clearance from Path ColorPicker's bottom edge
    Text(parent=content, text="Animation", x=-PANEL_HALF_WIDTH + 0.16, y=y_offset, scale=1.0, origin=(0, 0))
    y_offset -= 0.05  # was 0.02 — was smaller than Frontier ColorPicker's own title-label offset (0.024)

    for label, attr in (("Frontier", "frontier_color"), ("Current", "current_color")):
        cp = ColorPicker(parent=content, x=-PANEL_HALF_WIDTH + 0.16, y=y_offset, scale=COLOR_PICKER_SCALE)
        Text(parent=cp, text=label, y=0.04, origin=(0, 0), scale=0.8)
        cp.value = getattr(settings, attr)
        cp.on_value_changed = (lambda cp=cp, attr=attr: on_color_changed(attr, cp.value))
        y_offset -= COLOR_ROW_STEP

    return y_offset
