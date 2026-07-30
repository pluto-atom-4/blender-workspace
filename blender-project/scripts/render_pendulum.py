"""Build (via model_pendulum.py) and render a 3/4 preview PNG of the armed
inverted pendulum robot (issue #21). Headless -- the model build's own
save_as_mainfile guard (bpy.app.background) persists renders/pendulum.blend
here, which render_pendulum_front/side/top.py then load."""

import bpy
import math

exec(open("/home/pluto-atom-4/blender-workspace/blender-project/scripts/model_pendulum.py").read())

OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/pendulum_preview.png"

scene = bpy.context.scene

# Assembly bounding center (mm): ground Z=0 to IMU top ~136mm, midpoint ~70.
TARGET = (0.0, 0.0, 70.0)

bpy.ops.object.camera_add(location=(420.0, -500.0, 340.0))
camera = bpy.context.active_object
camera.name = "Preview_Camera"
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
camera.data.lens = 50.0
scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=(300.0, -300.0, 500.0))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(45.0), 0.0, math.radians(45.0))

bpy.ops.object.light_add(type='AREA', location=(-350.0, 200.0, 250.0))
fill = bpy.context.active_object
fill.data.energy = 3500.0
fill.data.size = 300.0

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered preview: {OUTPUT_PATH}")
