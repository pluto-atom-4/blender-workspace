"""Load the built leg-linkage-deviation diagnostic scene (issue #42) and
render an orthographic side view PNG, looking down the world X axis at the
Y-Z sweep plane. Run model_leg_linkage_deviation.py first -- it builds and
saves renders/leg_linkage_deviation.blend, which this script loads. This
is the primary/legible view: the "current" and "candidate" passes are
separated only along X (see model_leg_linkage_deviation.py's x_offset_mm),
which is exactly the axis this camera looks down -- so the two ankle
paths/chords/bands render EXACTLY OVERLAID here, which is the actual
side-by-side comparison image (per issue #42's "single comparison image,
not two renders a human has to mentally overlay"). Matches
render_pendulum_side.py's camera/light/EEVEE setup STRUCTURE, but NOT its
raw coordinate literals -- see render_leg_linkage_deviation.py's module
docstring for the unit-convention discrepancy this was fixed against
(model_pendulum.py uses mm-as-native-unit; this model uses real-meters-
as-native-unit via _model_common.py's MM=0.001, so position literals here
are authored in mm and converted, not used raw)."""

import bpy
import math

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_linkage_deviation.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_linkage_deviation_side.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

scene = bpy.context.scene

MM = 0.001  # 1mm in Blender meters -- matches _model_common.py's own constant.


def mm(*vals):
    return tuple(v * MM for v in vals)


# Bounding box (mm, measured from actual mesh/curve geometry, not just
# object origins): X=[-3,263], Y=[-50.7,48.8], Z=[-61.4,47.6]. That
# whole-scene center (used by render_leg_linkage_deviation.py) is skewed
# upward/rightward by the hip servo + label text sitting near the top;
# recentered here toward the ankle-sweep curve's own region (confirmed by
# inspecting a first render: the wheel disc, near the top of frame at the
# whole-scene center, occluded much of the curve/band below it) so the
# diagnostic curve itself -- the actual point of this view -- sits more
# centrally rather than the mechanical wheel.
TARGET_MM = (130.0, -15.0, -30.0)
TARGET = mm(*TARGET_MM)

# Side elevation, looking along -X at the Y-Z plane (same X-offset-only
# camera-to-target convention as render_pendulum_side.py). ortho_scale
# widened from a first attempt (180mm) after that render showed the curve's
# LAUNCH_ANGLE end clipped at the frame edge -- 240mm gives generous margin
# for the full Y=[-50.7,48.8]/Z=[-61.4,47.6] extent plus labels.
bpy.ops.object.camera_add(location=mm(TARGET_MM[0] + 700.0, TARGET_MM[1], TARGET_MM[2]))
camera = bpy.context.active_object
camera.name = "Preview_Camera_Side"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 240.0 * MM
constraint = camera.constraints.new(type='TRACK_TO')
empty_target = bpy.data.objects.new("Camera_Target_Side", None)
empty_target.location = TARGET
scene.collection.objects.link(empty_target)
constraint.target = empty_target
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'
scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=mm(TARGET_MM[0] + 400.0, TARGET_MM[1] - 300.0, TARGET_MM[2] + 500.0))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35.0), 0.0, math.radians(70.0))

bpy.ops.object.light_add(type='AREA', location=mm(TARGET_MM[0] - 300.0, TARGET_MM[1] + 300.0, TARGET_MM[2] + 250.0))
fill = bpy.context.active_object
fill.data.energy = 3000.0
fill.data.size = 300.0 * MM

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered side preview: {OUTPUT_PATH}")
