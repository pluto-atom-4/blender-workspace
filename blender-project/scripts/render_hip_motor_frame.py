"""
Render script for the Hip Motor Robot Frame assembly model (issue #112, refactored Phase 1)

Generates isometric render of the hip motor frame assembly showing:
  - Hip Motor Housing (structural frame box)
  - STS-3032 Servo (body + output spline)
  - Servo Wheel (70mm diameter wheel mounted on top)

Phase 1 scope: isometric view only, 4-component assembly (rod linkage deferred to Phase 2)

Output:
  - hip_motor_frame.png (isometric view)

Reference: issue #112, architect plan
"""

import bpy
import math
import os
import sys
from PIL import Image

# Import the model builder
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from model_hip_motor_frame import main as build_model

OUTPUT_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/renders"

# Render settings
RENDER_W = 960
RENDER_H = 960
SAMPLES = 32
DENOISE = False

# Millimeter scaling helper
MM = 0.001

def mm(*vals):
    """Convert millimeter coordinates to Blender units (0.001 scale)."""
    if len(vals) == 1:
        return vals[0] * MM
    return tuple(v * MM for v in vals)


def setup_render_settings(samples=SAMPLES, denoise=DENOISE):
    """Configure Blender render engine (Cycles, viewport shading)."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = denoise
    scene.render.film_transparent = False
    scene.render.resolution_x = RENDER_W
    scene.render.resolution_y = RENDER_H


def setup_world_lighting():
    """Set up basic world lighting for better visibility."""
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)  # slightly brighter gray
    bg.inputs[1].default_value = 12.0  # increased strength


def create_key_light(strength=6.0, location=None):
    """Add a key light (sun lamp) for shading."""
    if location is None:
        location = mm(100, 50, 100)
    light_data = bpy.data.lights.new(name="KeyLight", type='SUN')
    light_data.energy = strength
    light_obj = bpy.data.objects.new(name="KeyLight", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = location
    return light_obj


def create_fill_light(strength=6.0, location=None):
    """Add a fill light (SUN lamp) for side illumination."""
    if location is None:
        location = mm(-100, -50, 100)
    light_data = bpy.data.lights.new(name="FillLight", type='SUN')
    light_data.energy = strength
    light_obj = bpy.data.objects.new(name="FillLight", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = location
    return light_obj


def render_view(name, camera_location, camera_lookat, render_path):
    """
    Render a single view from camera_location looking at camera_lookat.
    Uses TRACK_TO constraint for proper look-at behavior.

    Args:
        name: descriptive name (e.g., "Isometric View")
        camera_location: (x, y, z) tuple
        camera_lookat: (x, y, z) point to look at
        render_path: output PNG file path
    """
    scene = bpy.context.scene

    # Create camera if it doesn't exist
    if "RenderCamera" not in bpy.data.objects:
        cam_data = bpy.data.cameras.new(name="RenderCamera")
        cam_data.clip_start = 0.001  # 1mm near-clip
        cam_obj = bpy.data.objects.new("RenderCamera", cam_data)
        bpy.context.collection.objects.link(cam_obj)
    else:
        cam_obj = bpy.data.objects["RenderCamera"]

    # Position camera
    cam_obj.location = camera_location

    # Create or reuse camera target empty
    if "RenderCameraTarget" not in bpy.data.objects:
        empty_target = bpy.data.objects.new("RenderCameraTarget", None)
        bpy.context.collection.objects.link(empty_target)
    else:
        empty_target = bpy.data.objects["RenderCameraTarget"]

    empty_target.location = camera_lookat

    # Apply TRACK_TO constraint
    for constraint in cam_obj.constraints:
        if constraint.type == 'TRACK_TO':
            cam_obj.constraints.remove(constraint)

    constraint = cam_obj.constraints.new(type='TRACK_TO')
    constraint.target = empty_target
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    scene.camera = cam_obj
    scene.render.filepath = render_path

    print(f"Rendering {name} to {render_path}...")
    bpy.ops.render.render(write_still=True)
    print(f"  -> Saved: {render_path}")


def render_isometric(samples=SAMPLES):
    """Render isometric view (Phase 1 scope)."""
    iso_path = os.path.join(OUTPUT_DIR, "hip_motor_frame.png")
    render_view("Isometric View",
                camera_location=mm(60, 60, 35),
                camera_lookat=(0, 0, 0),
                render_path=iso_path)
    return [iso_path]


def analyze_render_pixels(image_path):
    """
    Analyze pixel statistics from a rendered image.
    Returns dict with min/max/avg brightness per channel.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("PIL/numpy not available; skipping pixel analysis")
        return None

    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return None

    img = Image.open(image_path).convert('RGB')
    arr = np.array(img, dtype=np.float32)

    # Convert to 0-255 range if needed
    if arr.max() <= 1.0:
        arr = arr * 255.0

    # Calculate statistics per channel
    stats = {}
    for i, channel in enumerate(['R', 'G', 'B']):
        channel_data = arr[:, :, i]
        stats[channel] = {
            'min': int(channel_data.min()),
            'max': int(channel_data.max()),
            'avg': int(channel_data.mean()),
        }

    # Overall brightness
    brightness = arr.mean()
    stats['overall_brightness'] = int(brightness)

    return stats


def validate_contrast(stats, render_name, threshold=50):
    """
    Validate contrast in a render via histogram/range check.
    Returns True if contrast passes (all channels have range >= threshold).
    """
    if not stats:
        return False

    r_range = stats['R']['max'] - stats['R']['min']
    g_range = stats['G']['max'] - stats['G']['min']
    b_range = stats['B']['max'] - stats['B']['min']

    if r_range >= threshold and g_range >= threshold and b_range >= threshold:
        print(f"  CONTRAST_OK: {render_name} R_range={r_range}, G_range={g_range}, B_range={b_range}")
        return True
    else:
        print(f"  LOW_CONTRAST: {render_name} R_range={r_range}, G_range={g_range}, B_range={b_range} (threshold: ≥{threshold} each)")
        return False


def main():
    """Run render pipeline with pixel verification."""
    # P2: Verify output directory is writable
    print("=== VALIDATION: Output Directory ===")
    if not os.path.isdir(OUTPUT_DIR):
        print(f"  Creating output directory: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.access(OUTPUT_DIR, os.W_OK):
        raise PermissionError(f"Output dir not writable: {OUTPUT_DIR}")
    print(f"  OK: Output directory writable ({OUTPUT_DIR})")

    # Build model
    print("\n=== Building Model ===")
    print("Building hip motor frame assembly...")

    try:
        build_model()
    except Exception as e:
        print(f"ERROR: Model build failed: {type(e).__name__}: {str(e)}")
        return False

    # P6: Geometry Validation
    print("\n=== VALIDATION: Geometry (P6) ===")
    required_objects = ["HMF_Housing", "HMF_ServoBody", "HMF_ServoSpline", "HMF_ServoWheel"]

    for obj_name in required_objects:
        if obj_name not in bpy.data.objects:
            print(f"ERROR: Geometry validation failed: {obj_name}: object not found")
            return False

    print("  OK: All required geometry objects found")
    print(f"    - Housing: {bpy.data.objects['HMF_Housing'].name}")
    print(f"    - Servo Body: {bpy.data.objects['HMF_ServoBody'].name}")
    print(f"    - Servo Spline: {bpy.data.objects['HMF_ServoSpline'].name}")
    print(f"    - Servo Wheel: {bpy.data.objects['HMF_ServoWheel'].name}")

    # Validate each geometry has faces
    for obj_name in required_objects:
        obj = bpy.data.objects[obj_name]
        mesh = obj.data
        if len(mesh.polygons) == 0:
            print(f"ERROR: Geometry validation failed: {obj_name}: has 0 faces")
            return False

    print("  OK: All geometry objects have valid mesh data")

    # Set up rendering
    setup_render_settings()
    setup_world_lighting()
    create_key_light(strength=20.0)
    create_fill_light(strength=20.0)

    # Single-frame test at low samples for pixel verification
    print("\n=== PIXEL VERIFICATION TEST (Pre-flight Contrast Check) ===")
    print("Rendering single frame at low samples for pixel statistics...")
    setup_render_settings(samples=8)

    test_path = os.path.join(OUTPUT_DIR, "hip_motor_frame_test.png")
    render_view("Test Frame", camera_location=mm(80, 80, 45), camera_lookat=(0, 0, 0), render_path=test_path)

    stats = analyze_render_pixels(test_path)
    if stats:
        print(f"\nPixel Statistics (test frame):")
        print(f"  R: min={stats['R']['min']}, max={stats['R']['max']}, avg={stats['R']['avg']}")
        print(f"  G: min={stats['G']['min']}, max={stats['G']['max']}, avg={stats['G']['avg']}")
        print(f"  B: min={stats['B']['min']}, max={stats['B']['max']}, avg={stats['B']['avg']}")
        print(f"  Overall brightness: {stats['overall_brightness']}/255")

        if stats['overall_brightness'] < 100:
            print(f"\nERROR: Brightness {stats['overall_brightness']}/255 is too low (threshold: 100/255)")
            print("DO NOT proceeding to full renders. Check lighting setup.")
            return False
        else:
            print(f"\nPASS: Brightness {stats['overall_brightness']}/255 exceeds threshold")

        if not validate_contrast(stats, "test_frame", threshold=50):
            print(f"\nERROR: Test frame has low contrast. DO NOT proceeding to full renders.")
            return False
        else:
            print(f"\nPASS: Test frame contrast passes threshold")
    else:
        print("WARNING: Could not analyze pixel statistics; proceeding with caution")

    # Full render pipeline at full samples
    print("\n=== FULL RENDER PIPELINE ===")
    setup_render_settings(samples=32)

    print("\nRendering isometric view (Phase 1 scope)...")
    render_paths = render_isometric(samples=32)

    # P3: File Size Range Validation
    print("\n=== VALIDATION: Output Files (P3: File Size Range) ===")
    all_exist = True
    all_sizes_ok = True
    MIN_SIZE = 100_000    # 100 KB
    MAX_SIZE = 1_500_000  # 1.5 MB

    for path in render_paths:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if MIN_SIZE <= size <= MAX_SIZE:
                print(f"  OK: {path} ({size} bytes)")
            else:
                print(f"  WRONG SIZE: {path} is {size} bytes (expected {MIN_SIZE:,}–{MAX_SIZE:,})")
                all_sizes_ok = False
                all_exist = False
        else:
            print(f"  MISSING: {path}")
            all_exist = False

    # P1: PNG Corruption Detection
    print("\n=== VALIDATION: PNG Corruption Detection (P1) ===")
    all_pngs_valid = True
    for path in render_paths:
        if os.path.exists(path):
            try:
                img = Image.open(path)
                img.verify()
                print(f"  OK: {path} (no corruption)")
            except Exception as e:
                print(f"  CORRUPT PNG: {path}: {e}")
                all_pngs_valid = False
                all_exist = False

    # Per-Render Pixel Analysis
    print("\n=== VALIDATION: Phase 2 - Per-Render Analysis ===")

    render_brightness = {}
    all_brightness_ok = True
    all_contrast_ok = True

    for path in render_paths:
        if not os.path.exists(path):
            continue

        # P4: Per-Render Pixel Analysis
        stats = analyze_render_pixels(path)
        if not stats:
            print(f"  WARNING: Could not analyze {path}")
            continue

        brightness = stats['overall_brightness']
        render_name = os.path.basename(path).replace('.png', '')
        render_brightness[render_name] = brightness

        # Check brightness threshold
        if brightness >= 100:
            print(f"  BRIGHTNESS_OK: {render_name} brightness {brightness}/255")
        else:
            print(f"  BRIGHTNESS_LOW: {render_name} brightness {brightness}/255 (threshold: ≥100)")
            all_brightness_ok = False

        # P7: Contrast Validation
        if not validate_contrast(stats, render_name, threshold=50):
            all_contrast_ok = False

    if all_exist and all_pngs_valid and all_brightness_ok and all_contrast_ok:
        print("\n=== FINAL RESULT: SUCCESS ===")
        print("Isometric render complete and validated:")
        print("  - P2: Output directory writable ✓")
        print("  - P3: File sizes in range [100KB–1.5MB] ✓")
        print("  - P1: PNG files not corrupted ✓")
        print("  - P4: Per-render brightness ≥100/255 ✓")
        print("  - P7: Histogram contrast (range ≥50 per channel) ✓")
        return True
    else:
        print("\n=== FINAL RESULT: FAILURE ===")
        if not os.access(OUTPUT_DIR, os.W_OK):
            print("  - P2: Output directory NOT writable ✗")
        if not all_sizes_ok:
            print("  - P3: Some files have wrong sizes ✗")
        if not all_pngs_valid:
            print("  - P1: Some PNG files are corrupted ✗")
        if not all_brightness_ok:
            print("  - P4: Some renders have low brightness ✗")
        if not all_contrast_ok:
            print("  - P7: Some renders have low contrast ✗")
        return False


if __name__ == "__main__":
    main()
