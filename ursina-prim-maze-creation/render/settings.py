"""Mutable render settings for the maze visualization — camera, lighting, colors."""
from dataclasses import dataclass, field
from ursina import color, Vec3


@dataclass
class RenderSettings:
    """Central settings object for camera, lighting, and color customization."""

    # Color scheme: 3D depth via hue differentiation + height + lighting
    wall_color: object = field(default_factory=lambda: color.hsv(225, 0.45, 0.55))    # slate blue
    path_color: object = field(default_factory=lambda: color.hsv(35, 0.55, 0.85))     # warm sand
    frontier_color: object = field(default_factory=lambda: color.orange)               # transient
    current_color: object = field(default_factory=lambda: color.green)                 # transient

    # Light parameters (converted to light_dir via spherical coords)
    light_azimuth: float = 45.0      # degrees, 0=+X, 90=+Z, 180=-X, 270=-Z
    light_elevation: float = 55.0    # degrees, 0=horizon, 90=zenith
    light_intensity: float = 1.0     # multiplier on diffuse component
    light_ambient: float = 0.35      # base ambient level (0.0-1.0)

    # Camera preset and offset
    camera_preset: str = "Isometric"  # e.g. "Top-Down", "Isometric", "Side", "First-Person"
    camera_offset: object = field(default_factory=lambda: Vec3(0, 0, 0))  # relative nudge


# Module-level singleton
settings = RenderSettings()
