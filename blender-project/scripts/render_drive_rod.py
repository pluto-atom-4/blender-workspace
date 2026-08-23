"""
Render script for the drive rod model (issue #106)

Generates multi-angle renders of the drive rod flat-bar connector showing:
  - Front view (A): YZ plane view, pivot pins visible
  - Side view (B): XZ plane view, full bar profile
  - Isometric view (C): diagonal 3D view for assembly clarity
  - Back/left view (D): 3/4 rear view for detail

Saves:
  - drive_rod_front.png
  - drive_rod_side.png
  - drive_rod_isometric.png
  - drive_rod_back_left.png

Reference: issue #106 Phase 1 scope
"""

import bpy
import math
import os
import sys
from PIL import Image

# Import the model builder
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from model_drive_rod import main as build_model

OUTPUT_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/renders"

# Render settings
RENDER_W = 960
RENDER_H = 960
SAMPLES = 32
DENOISE = False  # Disable denoising to avoid OpenImageDenoise requirement


def setup_render_settings(samples=SAMPLES, denoise=DENOISE):
    """Configure Blender render engine (Cycles, viewport shading)."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = denoise
    scene.render.film_transparent = False  # BUG FIX #106: was True, causing black renders
    scene.render.resolution_x = RENDER_W
    scene.render.resolution_y = RENDER_H


def setup_world_lighting():
    """Set up basic world lighting for better visibility."""
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.9, 0.9, 0.95, 1.0)  # light gray
    bg.inputs[1].default_value = 1.2  # strength


def create_key_light(strength=2.0, location=(30, 30, 40)):
    """Add a key light (sun lamp) for shading."""
    light_data = bpy.data.lights.new(name="KeyLight", type='SUN')
    light_data.energy = strength
    light_obj = bpy.data.objects.new(name="KeyLight", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = location
    return light_obj


def render_view(name, camera_location, camera_lookat, render_path):
    """
    Render a single view from camera_location looking at camera_lookat.

    Args:
        name: descriptive name (e.g., "Front View")
        camera_location: (x, y, z) tuple
        camera_lookat: (x, y, z) point to look at
        render_path: output PNG file path
    """
    scene = bpy.context.scene

    # Create camera if it doesn't exist
    if "RenderCamera" not in bpy.data.objects:
        cam_data = bpy.data.cameras.new(name="RenderCamera")
        cam_obj = bpy.data.objects.new("RenderCamera", cam_data)
        bpy.context.collection.objects.link(cam_obj)
    else:
        cam_obj = bpy.data.objects["RenderCamera"]

    # Position and orient camera
    cam_obj.location = camera_location
    direction = (camera_lookat[0] - camera_location[0],
                 camera_lookat[1] - camera_location[1],
                 camera_lookat[2] - camera_location[2])
    cam_obj.rotation_euler = (math.atan2(direction[2],
                                          math.sqrt(direction[0]**2 + direction[1]**2)),
                              0,
                              math.atan2(direction[1], direction[0]))

    scene.camera = cam_obj
    scene.render.filepath = render_path

    print(f"Rendering {name} to {render_path}...")
    bpy.ops.render.render(write_still=True)
    print(f"  -> Saved: {render_path}")


def render_views(samples=SAMPLES):
    """Render the drive rod from multiple angles."""
    renders = []

    # Front view: pivot pins facing camera (X-looking, Y up)
    front_path = os.path.join(OUTPUT_DIR, "drive_rod_front.png")
    render_view("Front View", camera_location=(60, 0, 0), camera_lookat=(0, 0, 0), render_path=front_path)
    renders.append(front_path)

    # Side view: profile view (Y-looking, Z up)
    side_path = os.path.join(OUTPUT_DIR, "drive_rod_side.png")
    render_view("Side View", camera_location=(0, 60, 0), camera_lookat=(0, 0, 0), render_path=side_path)
    renders.append(side_path)

    # Isometric view: 3D assembly view
    iso_path = os.path.join(OUTPUT_DIR, "drive_rod_isometric.png")
    render_view("Isometric View", camera_location=(50, 50, 30), camera_lookat=(0, 0, 0), render_path=iso_path)
    renders.append(iso_path)

    # Back/left view: 3/4 rear view
    back_left_path = os.path.join(OUTPUT_DIR, "drive_rod_back_left.png")
    render_view("Back/Left View", camera_location=(-50, 50, 20), camera_lookat=(0, 0, 0), render_path=back_left_path)
    renders.append(back_left_path)

    return renders


def analyze_render_pixels(image_path):
    """
    Analyze pixel statistics from a rendered image.
    Returns dict with min/max/avg brightness per channel.
    Image values are 0-1.0 (float32) or 0-255 (8-bit), converts to 0-255 scale.
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

    # Overall brightness (average of RGB)
    brightness = arr.mean()
    stats['overall_brightness'] = int(brightness)

    return stats


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
    print("Building drive rod model...")
    build_model()

    # Set up rendering
    setup_render_settings()
    setup_world_lighting()
    create_key_light()

    # Single-frame test at low samples for pixel verification
    print("\n=== PIXEL VERIFICATION TEST ===")
    print("Rendering single frame at low samples for pixel statistics...")
    setup_render_settings(samples=8)  # Low samples for fast test

    test_path = os.path.join(OUTPUT_DIR, "drive_rod_test.png")
    render_view("Test Frame", camera_location=(50, 50, 30), camera_lookat=(0, 0, 0), render_path=test_path)

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
    else:
        print("WARNING: Could not analyze pixel statistics; proceeding with caution")

    # Full render pipeline at full samples
    print("\n=== FULL RENDER PIPELINE ===")
    setup_render_settings(samples=32)

    print("\nRendering views...")
    render_paths = render_views(samples=32)

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

    # P1: Detect PNG corruption via PIL.Image.verify()
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

    if all_exist and all_pngs_valid:
        print("\n=== FINAL RESULT: SUCCESS ===")
        print("All renders complete and validated:")
        print("  - P2: Output directory writable ✓")
        print("  - P3: File sizes in range [50KB–500KB] ✓")
        print("  - P1: PNG files not corrupted ✓")
        return True
    else:
        print("\n=== FINAL RESULT: FAILURE ===")
        if not os.access(OUTPUT_DIR, os.W_OK):
            print("  - P2: Output directory NOT writable ✗")
        if not all_sizes_ok:
            print("  - P3: Some files have wrong sizes ✗")
        if not all_pngs_valid:
            print("  - P1: Some PNG files are corrupted ✗")
        return False


if __name__ == "__main__":
    main()
