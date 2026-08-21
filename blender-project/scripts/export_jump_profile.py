"""
Extract jump animation profile from Blender model.

Extracts DWLRP_R_HipServo_Body rotation_euler.x keyframes over the jump sequence
and generates a configuration profile for the legged_robot_jump controller.

Phases (per issue #90 corrections):
  - CROUCH: frames 141-162, QUAD easing
  - PUSH: frames 162-168, EXPO easing
  - FLIGHT: frames 168+, no easing (free dynamics)

Output: jump_profile.yaml (primary) or jump_profile.json (fallback)
"""

import sys
import json
import math
from pathlib import Path
from typing import Optional, Dict, List, Tuple

try:
    import bpy
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


# Easing functions (matching controller implementations)
def quad_ease_in_out(t: float) -> float:
    """Quadratic ease in-out."""
    if t < 0.5:
        return 2.0 * t * t
    else:
        return -1.0 + (4.0 - 2.0 * t) * t


def expo_ease_in_out(t: float) -> float:
    """Exponential ease in-out."""
    if t < 0.5:
        return 0.5 * (2.0 ** (20.0 * t - 10.0))
    else:
        return 1.0 - 0.5 * (2.0 ** (-20.0 * t + 10.0))


def linear_interpolate(start: float, end: float, t: float) -> float:
    """Linear interpolation."""
    return start + (end - start) * t


def interpolate_with_easing(start: float, end: float, t: float, easing_fn) -> float:
    """Interpolate with easing function."""
    eased_t = easing_fn(t)
    return linear_interpolate(start, end, eased_t)


def extract_jump_profile(output_path: str = "jump_profile.yaml") -> Dict:
    """
    Extract jump animation profile from Blender model.

    Args:
        output_path: Output file path (YAML or JSON based on extension)

    Returns:
        Dictionary with extracted profile data

    Raises:
        RuntimeError: If Blender context is unavailable or hip servo not found
    """
    if not HAS_BLENDER:
        raise RuntimeError("Blender (bpy) not available in this context")

    # Get Blender scene and FPS
    scene = bpy.context.scene
    fps = scene.render.fps
    print(f"Extracting profile: FPS={fps}")

    # Get hip servo object
    hip_servo = bpy.data.objects.get("DWLRP_R_HipServo_Body")
    if not hip_servo:
        raise RuntimeError("DWLRP_R_HipServo_Body not found in scene")

    if not hip_servo.animation_data or not hip_servo.animation_data.action:
        raise RuntimeError("Hip servo has no animation data")

    action = hip_servo.animation_data.action

    # Extract rotation_euler X keyframes
    rotation_fcurve = None
    for fcurve in action.fcurves:
        if fcurve.data_path == "rotation_euler" and fcurve.array_index == 0:
            rotation_fcurve = fcurve
            break

    if not rotation_fcurve:
        raise RuntimeError("No rotation_euler.x F-curve found in hip servo action")

    # Build keyframe data
    keyframes = {}
    for kf in rotation_fcurve.keyframe_points:
        frame = int(kf.co[0])
        value = kf.co[1]
        keyframes[frame] = value

    print(f"Found {len(keyframes)} keyframes")

    # Phase frame boundaries (per Blender animation)
    CROUCH_START_FRAME = 141
    CROUCH_END_FRAME = 162
    PUSH_START_FRAME = 162
    PUSH_END_FRAME = 168  # LAUNCH_FRAME
    FLIGHT_START_FRAME = 168
    FLIGHT_END_FRAME = 213  # End of animation

    # Extract angle values for each phase
    crouch_start_angle = keyframes.get(CROUCH_START_FRAME)
    crouch_end_angle = keyframes.get(CROUCH_END_FRAME)
    push_end_angle = keyframes.get(PUSH_END_FRAME)

    if None in (crouch_start_angle, crouch_end_angle, push_end_angle):
        raise RuntimeError(
            f"Missing keyframes: crouch_start={crouch_start_angle}, "
            f"crouch_end={crouch_end_angle}, push_end={push_end_angle}"
        )

    # Convert frames to time (seconds)
    crouch_start_time = CROUCH_START_FRAME / fps
    crouch_end_time = CROUCH_END_FRAME / fps
    push_start_time = PUSH_START_FRAME / fps
    push_end_time = PUSH_END_FRAME / fps
    flight_start_time = FLIGHT_START_FRAME / fps

    # Phase durations
    crouch_duration = crouch_end_time - crouch_start_time
    push_duration = push_end_time - push_start_time

    print(f"\nPhase Analysis:")
    print(f"  CROUCH: frames {CROUCH_START_FRAME}-{CROUCH_END_FRAME} ({crouch_duration:.4f}s)")
    print(f"    angle: {crouch_start_angle:.6f} -> {crouch_end_angle:.6f} rad")
    print(f"    ({crouch_start_angle * 180 / math.pi:.1f}° -> {crouch_end_angle * 180 / math.pi:.1f}°)")
    print(f"  PUSH: frames {PUSH_START_FRAME}-{PUSH_END_FRAME} ({push_duration:.4f}s)")
    print(f"    angle: {crouch_end_angle:.6f} -> {push_end_angle:.6f} rad")
    print(f"    ({crouch_end_angle * 180 / math.pi:.1f}° -> {push_end_angle * 180 / math.pi:.1f}°)")
    print(f"  FLIGHT: frames {FLIGHT_START_FRAME}-{FLIGHT_END_FRAME}")
    print(f"    angle: {push_end_angle:.6f} rad ({push_end_angle * 180 / math.pi:.1f}°)")

    # Build profile dictionary
    profile = {
        "fps": fps,
        "phases": {
            "crouch": {
                "frame_start": CROUCH_START_FRAME,
                "frame_end": CROUCH_END_FRAME,
                "time_start_s": crouch_start_time,
                "time_end_s": crouch_end_time,
                "duration_s": crouch_duration,
                "angle_start_rad": crouch_start_angle,
                "angle_end_rad": crouch_end_angle,
                "easing": "QUAD",  # CORRECTED per issue #90
            },
            "push": {
                "frame_start": PUSH_START_FRAME,
                "frame_end": PUSH_END_FRAME,
                "time_start_s": push_start_time,
                "time_end_s": push_end_time,
                "duration_s": push_duration,
                "angle_start_rad": crouch_end_angle,
                "angle_end_rad": push_end_angle,
                "easing": "EXPO",  # CORRECTED per issue #90
            },
            "flight": {
                "frame_start": FLIGHT_START_FRAME,
                "frame_end": FLIGHT_END_FRAME,
                "time_start_s": flight_start_time,
                "duration_s": (FLIGHT_END_FRAME - FLIGHT_START_FRAME) / fps,
                "angle_rad": push_end_angle,
                "easing": None,  # Free dynamics
            },
        },
        "keyframe_data": {
            str(frame): {"angle_rad": angle}
            for frame, angle in keyframes.items()
        },
    }

    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".yaml" or output_path.suffix.lower() == ".yml":
        _write_yaml(profile, output_path)
    else:
        _write_json(profile, output_path)
        # Also write YAML variant
        yaml_path = output_path.with_suffix(".yaml")
        _write_yaml(profile, yaml_path)

    print(f"\nProfile saved to: {output_path}")
    return profile


def _write_yaml(profile: Dict, output_path: Path):
    """Write profile as YAML."""
    try:
        import yaml
    except ImportError:
        print("Warning: PyYAML not available, skipping YAML output")
        return

    with open(output_path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False)


def _write_json(profile: Dict, output_path: Path):
    """Write profile as JSON."""
    with open(output_path, "w") as f:
        json.dump(profile, f, indent=2)


# Test: validate extracted profile
def test_profile(profile: Dict) -> bool:
    """
    Validate extracted profile.

    Returns:
        True if valid, raises AssertionError otherwise
    """
    phases = profile["phases"]
    fps = profile["fps"]

    # Check phase durations
    crouch = phases["crouch"]
    push = phases["push"]
    flight = phases["flight"]

    total_duration = (
        crouch["duration_s"] + push["duration_s"] + flight["duration_s"]
    )

    print(f"\nProfile Validation:")
    print(f"  Total jump duration: {total_duration:.4f}s")
    print(f"    CROUCH: {crouch['duration_s']:.4f}s")
    print(f"    PUSH: {push['duration_s']:.4f}s")
    print(f"    FLIGHT: {flight['duration_s']:.4f}s")

    # Validate angle ranges
    angles = [
        crouch["angle_start_rad"],
        crouch["angle_end_rad"],
        push["angle_end_rad"],
        flight["angle_rad"],
    ]
    min_angle = min(angles)
    max_angle = max(angles)

    print(f"  Angle range: {min_angle:.6f} - {max_angle:.6f} rad")
    print(f"    ({min_angle * 180 / math.pi:.1f}° - {max_angle * 180 / math.pi:.1f}°)")

    # Assertions
    assert abs(total_duration - 2.0) < 0.1, (
        f"Jump duration {total_duration:.4f}s should be ~2.0s"
    )
    assert min_angle > 0, f"Minimum angle {min_angle} should be positive"
    assert max_angle < math.pi, f"Maximum angle {max_angle} should be < pi"

    print("  Validation: PASSED")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract jump profile from Blender")
    parser.add_argument(
        "--output",
        "-o",
        default="jump_profile.yaml",
        help="Output file path (YAML or JSON)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run validation tests",
    )

    args = parser.parse_args()

    if not HAS_BLENDER:
        print("Error: This script must be run within Blender (bpy context required)")
        sys.exit(1)

    try:
        profile = extract_jump_profile(args.output)
        if args.test:
            test_profile(profile)
        print("\nExtraction complete!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
