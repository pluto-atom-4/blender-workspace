"""Load the precise servo-driven Tamiya pendulum assembly and render a front orthographic PNG."""

import bpy
import math

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_servo_precise.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_servo_precise_preview_front.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene
TARGET = (0.0, 0.0, 52.75)

bpy.ops.object.camera_add(location=(0.0, -400.0, TARGET[2]))
camera = bpy.context.active_object
camera.name = "Preview_Camera_Front"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 180.0
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target_Front", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=(150.0, -200.0, 300.0))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35.0), 0.0, math.radians(20.0))

bpy.ops.object.light_add(type='AREA', location=(-150.0, -150.0, 150.0))
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
print(f"Rendered servo-precise front preview: {OUTPUT_PATH}")
