"""
Render script for the drive rod model (issue #106)

Generates multi-angle renders of the drive rod flat-bar connector showing:
  - Isometric view (C): diagonal 3D view for assembly clarity (always rendered)
  - Front view (A): YZ plane view, pivot pins visible (optional via render_all_angles=True)
  - Side view (B): XZ plane view, full bar profile (optional via render_all_angles=True)
  - Back/left view (D): 3/4 rear view for detail (optional via render_all_angles=True)

Saves:
  - drive_rod_isometric.png (always)
  - drive_rod_front.png (optional)
  - drive_rod_side.png (optional)
  - drive_rod_back_left.png (optional)

Reference: issue #106 Phase 1 scope, issue #110 Phase 1 (isometric-only default)
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

# Millimeter scaling helper (issue #110 fix: scale camera/light coordinates)
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
    scene.render.film_transparent = False  # BUG FIX #106: was True, causing black renders
    scene.render.resolution_x = RENDER_W
    scene.render.resolution_y = RENDER_H


def setup_world_lighting():
    """Set up basic world lighting for better visibility."""
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)  # dark gray (issue #106 fix)
    bg.inputs[1].default_value = 3.0  # increased strength to compensate for darker background


def create_key_light(strength=5.0, location=None):
    """Add a key light (sun lamp) for shading."""
    if location is None:
        location = mm(50, 30, 50)
    light_data = bpy.data.lights.new(name="KeyLight", type='SUN')
    light_data.energy = strength
    light_obj = bpy.data.objects.new(name="KeyLight", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = location
    return light_obj


def create_fill_light(strength=5.0, location=None):
    """Add a fill light (SUN lamp) opposite side view camera to create contrast on side view."""
    if location is None:
        location = mm(0, -60, 30)
    light_data = bpy.data.lights.new(name="FillLight", type='SUN')
    light_data.energy = strength
    light_obj = bpy.data.objects.new(name="FillLight", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = location
    return light_obj


def render_view(name, camera_location, camera_lookat, render_path):
    """
    Render a single view from camera_location looking at camera_lookat.
    Uses TRACK_TO constraint for proper look-at behavior (issue #106 fix).

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
        cam_data.clip_start = 0.001  # 1mm near-clip (issue #110: avoid clipping small geometry)
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

    # Apply TRACK_TO constraint (replaces hand-rolled euler rotation, issue #106 fix)
    # Remove old constraints to avoid stacking
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


def render_views(samples=SAMPLES, render_all_angles=False):
    """Render the drive rod from multiple angles.

    Args:
        samples: number of render samples
        render_all_angles: if True, render all 4 views (front/side/iso/back-left)
                          if False, render isometric only (default)
    """
    renders = []

    # Isometric view: 3D assembly view (always rendered)
    iso_path = os.path.join(OUTPUT_DIR, "drive_rod_isometric.png")
    render_view("Isometric View", camera_location=mm(64, 64, 38), camera_lookat=(0, 0, 0), render_path=iso_path)
    renders.append(iso_path)

    if render_all_angles:
        # Front view: pivot pins facing camera (X-looking, Y up)
        front_path = os.path.join(OUTPUT_DIR, "drive_rod_front.png")
        render_view("Front View", camera_location=mm(60, 0, 0), camera_lookat=(0, 0, 0), render_path=front_path)
        renders.append(front_path)

        # Side view: profile view (Y-looking, Z up)
        side_path = os.path.join(OUTPUT_DIR, "drive_rod_side.png")
        render_view("Side View", camera_location=mm(0, 60, 0), camera_lookat=(0, 0, 0), render_path=side_path)
        renders.append(side_path)

        # Back/left view: 3/4 rear view
        back_left_path = os.path.join(OUTPUT_DIR, "drive_rod_back_left.png")
        render_view("Back/Left View", camera_location=mm(-50, 50, 20), camera_lookat=(0, 0, 0), render_path=back_left_path)
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
    print("Building drive rod model...")

    # P5: Model Build Exception Handling
    try:
        build_model()
    except Exception as e:
        print(f"ERROR: Model build failed: {type(e).__name__}: {str(e)}")
        return False

    # P6: Geometry Validation
    print("\n=== VALIDATION: Geometry (P6) ===")
    required_objects = ["DR_FlatBar", "DR_PivotPinFront", "DR_PivotPinBack"]

    for obj_name in required_objects:
        if obj_name not in bpy.data.objects:
            print(f"ERROR: Geometry validation failed: {obj_name}: object not found")
            return False

    # Validate DR_FlatBar geometry
    flatbar = bpy.data.objects["DR_FlatBar"]
    flatbar_mesh = flatbar.data
    vertex_count = len(flatbar_mesh.vertices)
    face_count = len(flatbar_mesh.polygons)

    if vertex_count < 50 or vertex_count > 100:
        print(f"ERROR: Geometry validation failed: DR_FlatBar: vertex count {vertex_count} (expected 50-100)")
        return False

    if face_count == 0:
        print(f"ERROR: Geometry validation failed: DR_FlatBar: has 0 faces")
        return False

    # Validate bounding box (approximate 81.5mm = 0.0815 in Blender meters)
    bounds = [v.co for v in flatbar_mesh.vertices]
    if bounds:
        xs = [v[0] for v in bounds]
        ys = [v[1] for v in bounds]
        zs = [v[2] for v in bounds]
        x_len = max(xs) - min(xs)
        y_len = max(ys) - min(ys)
        z_len = max(zs) - min(zs)

        # Check that one dimension is approximately 0.0815 (81.5mm in Blender units where 1mm=0.001)
        lengths = sorted([x_len, y_len, z_len])
        if lengths[-1] < 0.075 or lengths[-1] > 0.090:
            print(f"ERROR: Geometry validation failed: DR_FlatBar: max bounds {lengths[-1]:.4f} (expected ~0.0815, tolerance 0.075-0.090)")
            return False

    # Validate pivot pins have faces
    for pin_name in ["DR_PivotPinFront", "DR_PivotPinBack"]:
        pin = bpy.data.objects[pin_name]
        pin_mesh = pin.data
        pin_face_count = len(pin_mesh.polygons)
        if pin_face_count == 0:
            print(f"ERROR: Geometry validation failed: {pin_name}: has 0 faces")
            return False

    print("  OK: All geometry checks passed (3 objects, vertex/face/bounds validated)")

    # Set up rendering
    setup_render_settings()
    setup_world_lighting()
    create_key_light()
    create_fill_light()

    # Single-frame test at low samples for pixel verification + contrast validation (issue #106 pre-flight)
    print("\n=== PIXEL VERIFICATION TEST (Pre-flight Contrast Check) ===")
    print("Rendering single frame at low samples for pixel statistics...")
    setup_render_settings(samples=8)  # Low samples for fast test

    test_path = os.path.join(OUTPUT_DIR, "drive_rod_test.png")
    render_view("Test Frame", camera_location=mm(64, 64, 38), camera_lookat=(0, 0, 0), render_path=test_path)

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

        # Contrast validation in pre-flight test (issue #106 fix)
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

    print("\nRendering views...")
    render_paths = render_views(samples=32, render_all_angles=False)

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

    # Phase 2: Per-Render Pixel Analysis (P4), Histogram/Contrast Validation (P7), Cross-Render Consistency (P8)
    print("\n=== VALIDATION: Phase 2 - Per-Render Analysis & Consistency ===")

    render_brightness = {}
    all_brightness_ok = True
    all_contrast_ok = True
    consistency_ok = True

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

        # P7: Histogram/Contrast Validation (reuse validate_contrast helper)
        if not validate_contrast(stats, render_name, threshold=50):
            all_contrast_ok = False

    # P8: Cross-Render Consistency Check
    if render_brightness:
        min_brightness = min(render_brightness.values())
        max_brightness = max(render_brightness.values())
        variance = max_brightness - min_brightness

        if variance <= 30:
            print(f"\n  CONSISTENCY_OK: Brightness variance {variance}/255 across angles")
            print(f"    Isometric={render_brightness.get('drive_rod_isometric', 'N/A')}")
        else:
            print(f"\n  BRIGHTNESS_INCONSISTENT: Variance {variance}/255 across angles (threshold: ≤30)")
            print(f"    Isometric={render_brightness.get('drive_rod_isometric', 'N/A')}")
            consistency_ok = False

    if all_exist and all_pngs_valid and all_brightness_ok and all_contrast_ok and consistency_ok:
        print("\n=== FINAL RESULT: SUCCESS ===")
        print("Isometric render complete and validated:")
        print("  - P2: Output directory writable ✓")
        print("  - P3: File sizes in range [100KB–1.5MB] ✓")
        print("  - P1: PNG files not corrupted ✓")
        print("  - P4: Per-render brightness ≥100/255 ✓")
        print("  - P7: Histogram contrast (range ≥50 per channel) ✓")
        print("  - P8: Cross-render brightness consistency (variance ≤30) ✓")
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
        if not consistency_ok:
            print("  - P8: Brightness inconsistency across angles ✗")
        return False


if __name__ == "__main__":
    main()
