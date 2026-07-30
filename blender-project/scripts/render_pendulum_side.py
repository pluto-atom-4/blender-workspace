"""Load the built armed inverted pendulum assembly and render a side
orthographic PNG (issue #21). Run render_pendulum.py first -- it builds and
saves renders/pendulum.blend, which this script loads."""

import bpy
import math

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/pendulum.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/pendulum_preview_side.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene
TARGET = (0.0, 0.0, 70.0)

# Side elevation, looking along -X at the Y-Z plane.
bpy.ops.object.camera_add(location=(700.0, 0.0, TARGET[2]))
camera = bpy.context.active_object
camera.name = "Preview_Camera_Side"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 230.0
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target_Side", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=(400.0, -300.0, 500.0))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35.0), 0.0, math.radians(70.0))

bpy.ops.object.light_add(type='AREA', location=(-300.0, 300.0, 250.0))
fill = bpy.context.active_object
fill.data.energy = 3000.0
fill.data.size = 300.0

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered side preview: {OUTPUT_PATH}")
