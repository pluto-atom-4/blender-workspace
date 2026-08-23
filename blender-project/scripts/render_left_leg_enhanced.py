"""
Render script for the enhanced left leg mechanism model (issue #102)

Generates multi-angle renders of the leg at rest pose (58°) showing:
  - Front view (A): XY plane view, wheel facing camera
  - Side view (B): YZ plane view, full linkage profile
  - Isometric view (C): diagonal 3D view for assembly clarity
  - Animation preview (D): leg sweep from 15° to 120° (camera tracks motion)

Saves:
  - leg_enhanced_reference.png (4-panel composite, 1920x1920 with labeled angles)
  - leg_enhanced_anim_preview.mp4 (optional, 24fps sweep animation)

Reference: issue #102 Phase 1-2 scope
"""

import bpy
import math
import subprocess
import os

# Import the model builder
import sys
sys.path.insert(0, "/home/pluto-atom-4/blender-workspace/blender-project/scripts")
from model_left_leg_enhanced import main as build_model

OUTPUT_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/renders"
RENDER_PATH = os.path.join(OUTPUT_DIR, "leg_enhanced_reference.png")

# Render settings
RENDER_W = 960
RENDER_H = 960
SAMPLES = 128
DENOISE = False  # Disable denoising to avoid OpenImageDenoise requirement


def setup_render_settings(samples=SAMPLES, denoise=DENOISE):
    """Configure Blender render engine (Cycles, viewport shading)."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = denoise
    scene.render.film_transparent = True


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
    rot_quat = bpy.context.view_layer.objects.active.matrix_world.to_quaternion()
    cam_obj.rotation_euler = (-math.atan2(direction[2],
                                           math.sqrt(direction[0]**2 + direction[1]**2)),
                              0,
                              math.atan2(direction[1], direction[0]))

    scene.camera = cam_obj
    scene.render.filepath = render_path

    print(f"Rendering {name} to {render_path}...")
    bpy.ops.render.render(write_still=True)
    print(f"  -> Saved: {render_path}")


def render_views():
    """Render the leg from multiple angles."""
    renders = []

    # Front view: wheel facing camera (X-looking, Y up)
    front_path = os.path.join(OUTPUT_DIR, "leg_enhanced_front.png")
    render_view("Front View", camera_location=(100, 0, 20), camera_lookat=(0, 0, 20), render_path=front_path)
    renders.append(front_path)

    # Side view: profile (Z-looking, Y up)
    side_path = os.path.join(OUTPUT_DIR, "leg_enhanced_side.png")
    render_view("Side View", camera_location=(0, 100, 20), camera_lookat=(0, 0, 20), render_path=side_path)
    renders.append(side_path)

    # Isometric view: 3D assembly view
    iso_path = os.path.join(OUTPUT_DIR, "leg_enhanced_iso.png")
    render_view("Isometric View", camera_location=(70, 70, 60), camera_lookat=(0, 0, 20), render_path=iso_path)
    renders.append(iso_path)

    # Close-up of knee joint and spring
    detail_path = os.path.join(OUTPUT_DIR, "leg_enhanced_detail.png")
    render_view("Detail View (Knee)", camera_location=(50, 0, -20), camera_lookat=(0, 0, -20), render_path=detail_path)
    renders.append(detail_path)

    return renders


def composite_renders(render_paths, output_path):
    """
    Composite 4 renders into a single 2x2 panel image using PIL.
    Falls back to linking individual renders if PIL unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL not available; skipping composite. Individual renders saved:")
        for p in render_paths:
            print(f"  {p}")
        return False

    # Load images
    images = []
    for p in render_paths:
        if os.path.exists(p):
            images.append(Image.open(p).convert('RGBA'))

    if len(images) < 4:
        print(f"Expected 4 renders, got {len(images)}")
        return False

    # Create composite
    w, h = RENDER_W, RENDER_H
    composite = Image.new('RGBA', (w * 2, h * 2), (240, 240, 240, 255))
    composite.paste(images[0], (0, 0))      # Front
    composite.paste(images[1], (w, 0))      # Side
    composite.paste(images[2], (0, h))      # Isometric
    composite.paste(images[3], (w, h))      # Detail

    # Add labels
    draw = ImageDraw.Draw(composite)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except:
        font = ImageFont.load_default()

    labels = [
        ("(A) Front View", (20, 20)),
        ("(B) Side View", (w + 20, 20)),
        ("(C) Isometric", (20, h + 20)),
        ("(D) Knee Detail", (w + 20, h + 20)),
    ]

    for text, pos in labels:
        draw.text(pos, text, fill=(0, 0, 0, 255), font=font)

    # Add title at top
    title = "Enhanced Left Leg Mechanism (5/6-bar linkage, Issue #102)"
    draw.text((w - 150, h - 30), title, fill=(50, 50, 50, 255), font=font)

    composite.save(output_path)
    print(f"Composite saved: {output_path}")
    return True


def main():
    """Run full render pipeline."""
    # Build model
    print("Building enhanced leg model...")
    build_model()

    # Set up rendering
    setup_render_settings()
    setup_world_lighting()
    create_key_light()

    # Render views
    print("\nRendering views...")
    render_paths = render_views()

    # Composite
    print("\nCompositing...")
    composite_renders(render_paths, RENDER_PATH)

    print("\nDone!")
    print(f"Main composite: {RENDER_PATH}")


if __name__ == "__main__":
    main()
