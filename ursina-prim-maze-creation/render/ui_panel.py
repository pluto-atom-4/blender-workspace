"""In-app control panel: camera presets, light controls, color pickers."""
from ursina import Entity, Text, camera
from ursina.prefabs.slider import Slider
from ursina.prefabs.button_group import ButtonGroup
from ursina.prefabs.color_picker import ColorPicker

from render.settings import settings

# Module-level root entity for the panel (all UI parented here, toggled together)
panel_root = None


def build_panel(on_camera_preset, on_camera_offset, on_light_changed, on_color_changed):
    """Build and return the control panel UI.

    Args:
        on_camera_preset: Callable(preset_name: str) - handles camera preset selection
        on_camera_offset: Callable(axis: str, value: float) - handles X/Y/Z offset sliders
        on_light_changed: Callable(attr: str, value: float) - handles light angle/intensity
        on_color_changed: Callable(attr: str, value: object) - handles color picker changes

    Returns:
        Entity (panel_root) that can be toggled with panel_root.enabled
    """
    global panel_root
    panel_root = Entity(parent=camera.ui, enabled=True)

    # === Camera Presets ===
    presets = ButtonGroup(
        ("Isometric", "Top-Down", "Side", "First-Person"),
        default=settings.camera_preset,
        label="Camera",
        parent=panel_root,
        position=(-0.85, 0.45),
        max_x=1,
    )
    presets.on_value_changed = lambda: on_camera_preset(presets.value)

    # === Camera Offset Sliders (X, Y, Z) ===
    for i, axis in enumerate("xyz"):
        s = Slider(
            min=-10,
            max=10,
            default=0,
            text=f"cam {axis}",
            dynamic=True,
            parent=panel_root,
            position=(-0.85, 0.30 - i * 0.05),
        )
        # Closure to capture current axis
        s.on_value_changed = (lambda axis=axis, s=s: on_camera_offset(axis, s.value))

    # === Light Control Sliders ===
    az = Slider(
        min=0,
        max=360,
        default=settings.light_azimuth,
        text="light azimuth",
        dynamic=True,
        parent=panel_root,
        position=(0.55, 0.45),
    )

    el = Slider(
        min=-10,
        max=90,
        default=settings.light_elevation,
        text="light elevation",
        dynamic=True,
        parent=panel_root,
        position=(0.55, 0.40),
    )

    intensity = Slider(
        min=0,
        max=2,
        default=settings.light_intensity,
        text="light intensity",
        dynamic=True,
        parent=panel_root,
        position=(0.55, 0.35),
    )

    # Wire light slider callbacks
    for s, attr in ((az, "light_azimuth"), (el, "light_elevation"), (intensity, "light_intensity")):
        s.on_value_changed = (lambda s=s, attr=attr: on_light_changed(attr, s.value))

    # === Color Pickers ===
    for i, (label, attr) in enumerate((
        ("Wall", "wall_color"),
        ("Path", "path_color"),
        ("Frontier", "frontier_color"),
        ("Current", "current_color"),
    )):
        cp = ColorPicker(parent=panel_root, position=(-0.85 + i * 0.45, -0.35))
        Text(parent=cp, text=label, y=0.05, origin=(0, 0))
        cp.value = getattr(settings, attr)
        cp.on_value_changed = (lambda cp=cp, attr=attr: on_color_changed(attr, cp.value))

    return panel_root


def toggle():
    """Toggle the panel visibility (call from input() handler on Tab)."""
    if panel_root:
        panel_root.enabled = not panel_root.enabled
