"""
Render the left leg parallel linkage model at rest pose (58°).

Load the pre-built left_leg_parallel.blend and render to PNG with proper
lighting and camera positioning.
"""

import bpy
import math

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/left_leg_parallel.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_parallel_reference.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene

MM = 0.001  # 1mm in Blender meters

def mm(*vals):
    return tuple(v * MM for v in vals)

# Scene bounding box (estimated from the model structure)
# Servo at origin, upper link ~40mm down, coupler at ~40mm, wheel further down
# Scene spans roughly X=[-80, 80], Y=[-80, 80], Z=[-100, 30]
# Centered around (0, 0, -20)
TARGET_MM = (0.0, 0.0, -20.0)
TARGET = mm(*TARGET_MM)

# Position camera for isometric 3/4 perspective view
bpy.ops.object.camera_add(location=mm(TARGET_MM[0] + 400.0, TARGET_MM[1] - 400.0, TARGET_MM[2] + 300.0))
camera = bpy.context.active_object
camera.name = "Preview_Camera"

# Add TRACK_TO constraint to point camera at the model
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
camera.data.lens = 50.0
scene.camera = camera

# Add sun light
bpy.ops.object.light_add(type='SUN', location=mm(TARGET_MM[0] + 300.0, TARGET_MM[1] - 300.0, TARGET_MM[2] + 500.0))
sun = bpy.context.active_object
sun.data.energy = 2.5
sun.rotation_euler = (math.radians(45.0), 0.0, math.radians(45.0))

# Add fill light for shadows
bpy.ops.object.light_add(type='AREA', location=mm(TARGET_MM[0] - 350.0, TARGET_MM[1] + 200.0, TARGET_MM[2] + 250.0))
fill = bpy.context.active_object
fill.data.energy = 3000.0
fill.data.size = 300.0 * MM

# Configure rendering with EEVEE
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

# Set frame to rest pose (58°)
scene.frame_set(90)

# Render
scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered preview: {OUTPUT_PATH}")
