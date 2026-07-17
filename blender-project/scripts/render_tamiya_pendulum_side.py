"""Load the built Tamiya pendulum assembly and render a side orthographic PNG."""

import bpy
import math

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_preview_side.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene

# Assembly bounding center (mm), from model_tamiya_pendulum.py geometry.
TARGET = (0.0, 0.0, 47.75)

# Camera: orthographic side elevation, looking along -X at the Y-Z plane.
bpy.ops.object.camera_add(location=(400.0, 0.0, TARGET[2]))
camera = bpy.context.active_object
camera.name = "Preview_Camera_Side"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 160.0
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target_Side", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
scene.camera = camera

# Angled sun + fill light so the flat side elevation still reads in 3D.
bpy.ops.object.light_add(type='SUN', location=(200.0, -150.0, 300.0))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35.0), 0.0, math.radians(70.0))

bpy.ops.object.light_add(type='AREA', location=(150.0, 150.0, 150.0))
fill = bpy.context.active_object
fill.data.energy = 1500.0
fill.data.size = 200.0

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered side preview: {OUTPUT_PATH}")
