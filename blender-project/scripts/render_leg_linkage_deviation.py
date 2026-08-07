"""Load the built leg-linkage-deviation diagnostic scene (issue #42) and
render a 3/4 perspective preview PNG. Run model_leg_linkage_deviation.py
first -- it builds and saves renders/leg_linkage_deviation.blend, which
this script loads. Matches render_pendulum.py's camera/light/EEVEE setup
STRUCTURE (camera_add + TRACK_TO empty + sun + area fill + EEVEE Next), but
NOT its raw coordinate literals -- see the MM note below, a real
unit-convention difference discovered while verifying this script, not a
copy-paste of render_pendulum.py's numbers.

Unit note (found empirically, not assumed): model_pendulum.py builds its
geometry directly in "mm-as-native-Blender-unit" (raw literals, e.g. a
40mm plate is built at native-unit size 40) -- render_pendulum.py's raw
camera/light/target literals (e.g. TARGET=(0,0,70)) are consistent with
that convention. model_dual_wheel_legged_robot_precise.py (via
_model_common.py's MM=0.001/mm() helpers) instead builds geometry in
REAL METERS as the native Blender unit (a 40mm plate is built at native
size 0.04) -- this script's own model_leg_linkage_deviation.py inherits
that convention via its exec()'d production script. Reusing
render_pendulum.py's raw numbers here verbatim (first draft did) placed
the camera ~500 REAL METERS from a ~0.25m-diagonal scene -- render came
back essentially empty (confirmed by inspecting the output PNG). Fixed by
expressing every position literal in "mm" and multiplying by MM=0.001
before use, matching the model's own convention exactly."""

import bpy
import math

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_linkage_deviation.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_linkage_deviation.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene

MM = 0.001  # 1mm in Blender meters -- matches _model_common.py's own constant;
            # this script's positions are authored in mm below, then converted.


def mm(*vals):
    return tuple(v * MM for v in vals)


# Scene bounding box (mm, world space, measured directly from the built
# .blend's actual mesh/curve geometry, not just object origins -- the first
# framing attempt under-shot this by using object origins only, which
# missed the wheels' own ~40mm radius extending past their center):
# X=[-3, 263], Y=[-50.7, 48.8], Z=[-61.4, 47.6] (diagonal ~304mm). Centered
# here, with a ~4x-diagonal camera distance for comfortable margin.
TARGET_MM = (130.0, -1.0, -7.0)
TARGET = mm(*TARGET_MM)

bpy.ops.object.camera_add(location=mm(TARGET_MM[0] + 700.0, TARGET_MM[1] - 850.0, TARGET_MM[2] + 550.0))
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

bpy.ops.object.light_add(type='SUN', location=mm(TARGET_MM[0] + 300.0, TARGET_MM[1] - 300.0, TARGET_MM[2] + 500.0))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(45.0), 0.0, math.radians(45.0))

bpy.ops.object.light_add(type='AREA', location=mm(TARGET_MM[0] - 350.0, TARGET_MM[1] + 200.0, TARGET_MM[2] + 250.0))
fill = bpy.context.active_object
fill.data.energy = 3500.0
fill.data.size = 300.0 * MM

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered preview: {OUTPUT_PATH}")
