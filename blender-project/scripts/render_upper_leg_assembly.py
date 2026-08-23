"""
Render pipeline for Upper Leg Assembly model (issue #104)

Generates multi-angle renders of the upper leg assembly from rest pose (frame 90).
Uses simple orthographic views for clarity.
"""

import bpy
import math
from mathutils import Vector


def setup_render_engine():
    """Configure render engine for fast headless rendering."""
    scene = bpy.context.scene
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.compression = 15
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False


def add_sun_light(name, energy, x, y, z):
    """Add a sun light to the scene."""
    light_data = bpy.data.lights.new(name, type='SUN')
    light_data.energy = energy
    light_data.angle = math.radians(3)
    light_obj = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = (x, y, z)
    return light_obj


def setup_lighting():
    """Setup three-point lighting."""
    # Clear existing lights
    for obj in list(bpy.data.objects):
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Add new lights
    add_sun_light("KeyLight", 2.0, 5, 3, 8)
    add_sun_light("FillLight", 0.7, -5, 2, 4)
    add_sun_light("RimLight", 0.5, 0, -8, 3)


def get_collection_bounds(coll_name):
    """Get world-space bounds of all objects in a collection."""
    coll = bpy.data.collections.get(coll_name)
    if not coll:
        return None

    objs = list(coll.all_objects)
    if not objs:
        return None

    all_points = []
    for obj in objs:
        if obj.type != 'MESH':
            continue
        for v in obj.bound_box:
            v_world = obj.matrix_world @ Vector(v)
            all_points.append(v_world)

    if not all_points:
        return None

    xs = [p.x for p in all_points]
    ys = [p.y for p in all_points]
    zs = [p.z for p in all_points]

    center = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

    return {'center': center, 'size': size}


def create_camera(location, target):
    """Create and setup a camera."""
    # Remove old camera
    for cam in bpy.data.cameras:
        bpy.data.cameras.remove(cam)
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Create new camera
    cam_data = bpy.data.cameras.new("Camera")
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    cam_obj.location = location

    # Point at target
    direction = (target - location).normalized()
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()

    cam_data.type = 'PERSP'
    cam_data.lens = 50

    bpy.context.scene.camera = cam_obj
    return cam_obj


def render_view(name, azimuth_deg, elevation_deg, bounds, distance_scale=2.5, frame=90):
    """Render a single view and save."""
    scene = bpy.context.scene
    scene.frame_set(frame)

    center = bounds['center']
    size = bounds['size']
    distance = size * distance_scale

    # Spherical coordinates
    azimuth_rad = math.radians(azimuth_deg)
    elevation_rad = math.radians(elevation_deg)

    cam_x = center.x + distance * math.cos(elevation_rad) * math.cos(azimuth_rad)
    cam_y = center.y + distance * math.cos(elevation_rad) * math.sin(azimuth_rad)
    cam_z = center.z + distance * math.sin(elevation_rad)
    cam_loc = Vector((cam_x, cam_y, cam_z))

    create_camera(cam_loc, center)

    output_path = f"/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_upper_assembly_{name}.png"
    scene.render.filepath = output_path

    print(f"Rendering {name} view...")
    bpy.ops.render.render(write_still=True)
    print(f"Saved: {output_path}")


def main():
    """Main render pipeline."""
    # Load the model
    blend_file = "/home/pluto-atom-4/blender-workspace/blender-project/renders/upper_leg_assembly.blend"
    print(f"Loading: {blend_file}")

    bpy.ops.wm.open_mainfile(filepath=blend_file)

    # Setup rendering
    setup_render_engine()
    setup_lighting()

    # Get assembly bounds
    bounds = get_collection_bounds("UpperLegAssembly")
    if not bounds:
        print("ERROR: Could not find UpperLegAssembly collection")
        return

    print(f"Assembly center: {bounds['center']}, size: {bounds['size']}")

    # Render angles: (azimuth_deg, elevation_deg, name)
    views = [
        (45, 30, "front_right"),
        (135, 30, "back_right"),
        (225, 30, "back_left"),
        (315, 30, "front_left"),
        (0, 60, "top"),
    ]

    for azimuth, elevation, name in views:
        try:
            render_view(name, azimuth, elevation, bounds, distance_scale=2.5, frame=90)
        except Exception as e:
            print(f"ERROR rendering {name}: {e}")

    print("Render pipeline complete!")


if __name__ == "__main__":
    main()
