"""Load the built Tamiya pendulum assembly and render a top-down preview PNG."""

import bpy

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_preview_top.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene
TARGET = (0.0, 0.0, 47.75)

bpy.ops.object.camera_add(location=(0.0, 0.0, 500.0))
camera = bpy.context.active_object
camera.name = "Preview_Camera_Top"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 140.0
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target_Top", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=(0.0, 0.0, 400.0))
sun = bpy.context.active_object
sun.data.energy = 3.5

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered top-down preview: {OUTPUT_PATH}")
