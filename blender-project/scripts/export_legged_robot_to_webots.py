"""Export the dual-wheel legged balancing robot (issue #25, precise variant:
model_dual_wheel_legged_robot_precise.py) to Wavefront OBJ meshes for import
into Webots (issue #28/#25 Phase 2 -- the first ARTICULATED-joint export in
this repo; export_pendulum_to_webots.py's mesh was a single static flattened
Shape with no HingeJoints).

Follows export_pendulum_to_webots.py's pattern (exec() the model script
in-process, guard on bpy.app.background, OBJ not Collada -- this Blender
build has no Collada exporter, see that script's NOTE) with one structural
difference: HingeJoints need DISTINCT rigid bodies to rotate against each
other, so this exports SEVEN separate OBJ files (one static flattened mesh
would bake every joint's current pose in permanently) instead of one.

Per-body split (resolves an apparent tension in the issue #25 Phase 2 plan
comment, which names the split as "chassis, per-leg upper-link, per-leg
lower-link+wheel-servo+wheel" -- three items -- while ALSO requiring "one
HingeJoint per wheel (continuous, axle axis)". A HingeJoint needs two
DISTINCT Solid endpoints, so the wheel disc cannot be baked into the same
static mesh as the lower-link/wheel-servo assembly it spins relative to.
Resolved here as a documented decision, not a silent deviation: the wheel
gets its own (fourth) mesh, giving 1 chassis + 2x(upper-link + lower-link +
wheel) = 7 files total):

  1. legged_robot_chassis.obj -- base plate, standoffs, deck, battery,
     ATOM S3, rear extension, AND both legs' hip knuckle pairs (these are
     bolted to the base plate and never rotate in the source rig -- see
     build_leg(), hip_knuckle_front/back are parented to base_plate, not
     to hip_servo/upper_plate, and are never keyframed). Robot's own root
     frame; local origin == world origin (base_plate.location is (0,0,0)
     in the source model, so no re-centering needed).
  2. legged_robot_upper_link_{L,R}.obj -- hip_servo + horn bracket +
     upper_plate_front/back (the rigid doubled fork) + knee_knuckle.
     Rotates about the hip axis (HingeJoint #1). Local origin == the hip
     pivot (hip_world in build_leg()).
  3. legged_robot_lower_link_{L,R}.obj -- lower_plate + ankle_block +
     ankle_knuckle + wheel_servo + axle_stub (NOT the wheel disc itself).
     Per the issue #25 Phase 2 plan's already-resolved knee/2nd-DOF
     decision ("one driven hip HingeJoint + a rigid lower-leg subtree, no
     second HingeJoint for the knee"), this is NOT its own HingeJoint --
     it's a plain rigid Solid nested inside the upper-link's endPoint
     Solid, so it inherits the hip's rotation directly with no
     counter-rotation. This deliberately does NOT reproduce
     kf_leg_angle()'s knee-knuckle counter-rotation (which keeps the wheel
     level through the hip sweep in the Blender animation) -- the static
     Webots world has no controller driving that cancellation, and the
     plan explicitly says not to re-litigate the knee decision. Local
     origin == the knee pivot, expressed in the upper-link's own local
     frame (i.e. hip-relative, not world-relative).
  4. legged_robot_wheel_{L,R}.obj -- wheel hub + hub cap only. Rotates
     about the axle axis (HingeJoint #2, continuous -- the real
     independently-actuated STS3032 wheel-drive DOF, unlike the knee).
     Local origin == the wheel axle center, expressed in the lower-link's
     own local frame (knee-relative).

Pivot-centering (the architect's flagged central risk: "OBJ export drops
joint hierarchy/pivot info, so pivot-setting must be deliberate in Blender,
not automatic/assumed"): each object group above is temporarily
re-centered and un-rotated in Blender BEFORE export, so the exported mesh's
own local origin (0,0,0) sits exactly at that body's real hinge pivot in
build_leg() (hip axis / knee pivot / wheel axle), matching how Webots
expects an endPoint Solid's geometry to be authored relative to its own
local frame. Concretely, for each leg:
  - hip_pivot is captured from hip_servo.matrix_world.translation BEFORE
    any edits (hip_servo/upper_plate_front/upper_plate_back/knee_knuckle
    all have rotation_euler.x zeroed -- animation_data_clear() is called
    on every object first so Blender's F-curve evaluation can't silently
    reassert the animated DEFAULT_HIP_ANGLE value on the next depsgraph
    update -- then hip_servo/upper_plate_front/upper_plate_back have
    hip_pivot subtracted from their .location). This represents the joint
    at position=0; the real rest-stance angle (DEFAULT_HIP_ANGLE_DEG, from
    linkage_kinematics.py) is applied instead via the HingeJoint's own
    JointParameters.position field in the .wbt, not baked into the mesh.
  - knee_pivot is then read back off knee_knuckle.matrix_world (now
    hip-relative, since upper_plate_front was just re-centered), and
    lower_plate's location is shifted by it.
  - wheel_pivot is read off the wheel object's own matrix_world (now
    knee-relative) and subtracted from the wheel's own location.
  matrix_parent_inverse is never set anywhere in
  model_dual_wheel_legged_robot_precise.py/_model_common.py (confirmed by
  grep), so every child.matrix_world here is simple parent.matrix_world @
  child.matrix_basis with no inverse-cancellation trick to account for --
  the re-centering math above is exact, not approximate.

Axis convention -- the OTHER half of the architect's flagged risk
("verify the exporter's forward_axis/up_axis transform doesn't silently
flip [the hip axis] before hardcoding HingeJoint.axis values"). Verified
EMPIRICALLY in this environment (not assumed): exporting a known
asymmetric test box via bpy.ops.wm.obj_export with
forward_axis='NEGATIVE_Z'/up_axis='Y' confirmed OBJ_xyz =
(Blender_x, Blender_z, -Blender_y) -- Blender X is preserved, but Y/Z are
swapped/negated. Both this rig's hip rotation axis (hip_servo/upper_plate's
rotation_euler.x, i.e. local/world X, since base_plate has identity
rotation) and its wheel axle axis (derived in kf_wheel_spin's own docstring:
the wheel's "tip" transform sends the spin axis to local X too) are along X,
so NEITHER axis gets flipped by that mapping -- HingeJoint.axis = 1 0 0
would have been correct either way. BUT a second, orthogonal problem was
found while checking this: Webots R2025a's WorldInfo.coordinateSystem
default is "ENU" (confirmed by reading
/usr/local/webots/resources/nodes/WorldInfo.wrl directly in this
environment: `w3dField SFString{"ENU","NUE","EUN"} coordinateSystem "ENU"
# X -> East, Y -> North, Z -> Up`) -- Z is vertical, NOT Y. An early
version of export_pendulum_to_webots.py used up_axis='Y', which would have
meant Blender's vertical (Z) ends up as the exported mesh's local Y, which
Webots would then treat as a HORIZONTAL axis, not vertical -- meaning that
mesh would have been oriented sideways relative to gravity (its
Gyro/Accelerometer children ARE placed using Z for height, which only makes
physical sense if Z is vertical -- inconsistent with an up_axis='Y' choice).
Issue #52 corrected that exporter to use forward_axis='Y', up_axis='Z'
instead, fixing the mesh orientation. This script deliberately uses the same
correct mapping: exporting with forward_axis='Y', up_axis='Z' was verified
(same empirical test) to produce an IDENTITY mapping (OBJ xyz == Blender xyz
exactly, just scaled), so this export's local axes match Blender's own X/Y/Z
1:1, which in turn match Webots' actual ENU (Z-up) default with zero
compensating rotation needed anywhere in the .wbt.

Headless -- run via run_blender_python (or `blender --background --python`
directly if the MCP tool isn't available in the calling environment; note
that substitution explicitly here rather than silently pretending the MCP
tool was used). Export only runs when bpy.app.background is true, same
guard model_dual_wheel_legged_robot_precise.py itself uses for
save_as_mainfile.
"""

import bpy
import json
import os
import sys

SCRIPTS_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/scripts"
ORCH_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/orchestration"
MESH_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/physics/worlds/meshes"

if ORCH_DIR not in sys.path:
    sys.path.insert(0, ORCH_DIR)
# Pure-Python (math/dataclasses stdlib only), no bpy dependency -- safe to
# import directly into Blender's Python. Single source of truth for the
# geometry constants and the PEA spring constant (issue #25 Phase 1); NOT
# re-derived here.
import linkage_kinematics as lk  # noqa: E402

exec(open(os.path.join(SCRIPTS_DIR, "model_dual_wheel_legged_robot_precise.py")).read())
# From here on, every top-level name model_dual_wheel_legged_robot_precise.py
# defines (COLLECTION_NAME, BASE_W/L/T, REAR_EXT_T, PLATE_GAP, HIP_LATERAL,
# HIP_Z, UPPER_LEN, LOWER_LEN, ANKLE_DROP, WHEEL_STUB, WHEEL_R, WHEEL_W,
# DEFAULT_HIP_ANGLE, mm/MM from _model_common, etc.) is available as a plain
# global in this script's own namespace, same exec() pattern
# export_pendulum_to_webots.py uses for model_pendulum.py. `legs`/
# `base_plate` themselves are NOT available (local to that script's main()),
# so objects below are looked up by their deterministic names instead.

assert DEFAULT_HIP_ANGLE == lk.DEFAULT_HIP_ANGLE_DEG, (
    "model_dual_wheel_legged_robot_precise.py's DEFAULT_HIP_ANGLE has drifted "
    "from linkage_kinematics.py's DEFAULT_HIP_ANGLE_DEG -- these must stay in "
    "sync (linkage_kinematics.py's own module docstring says to re-check the "
    "model file if they ever diverge)."
)

if bpy.app.background:
    os.makedirs(MESH_DIR, exist_ok=True)
    scene = bpy.context.scene

    # Frame 90 == build_balance_and_jump()'s own SETTLE_START constant: the
    # first frame where the exploded-assembly animation (frames 1-90, see
    # build_exploded_view()) has fully seated EVERY part (base_plate legs,
    # standoffs, deck, etc. all animate location keyframes starting
    # EXPLODED at frame 1, not assembled -- frame 1 is explicitly the wrong
    # frame to export from, it would bake in the mid-explosion offsets) AND
    # kf_leg_angle(legs, 90, DEFAULT_HIP_ANGLE) has just set the hip/knee
    # rotation keyframes to the rest stance. Confirmed empirically during
    # this script's own development: exporting at frame 1 produced hip
    # pivots offset by exactly each part's own explode-direction vector
    # (e.g. hip_servo's (sign*55, -15, 0)mm explode offset plus
    # base_plate's own (0,0,120)mm explode-in-Z showed up verbatim in the
    # captured pivot coordinates) -- frame 90 does not have this problem.
    scene.frame_set(90)

    def get_obj(name):
        o = bpy.data.objects.get(name)
        if o is None:
            raise KeyError(f"Expected object {name!r} not found after rebuilding the rig")
        return o

    # Strip every object's animation data AFTER evaluating frame 90 (so the
    # rest-stance property values are already baked into the raw
    # location/rotation_euler fields) but BEFORE any manual repose below --
    # without this, the next depsgraph update (view_layer.update()) would
    # re-evaluate each object's F-curves and silently overwrite our manual
    # edits (the rotation zeroing / pivot-recentering) right back to their
    # animated frame-90 values. Removing the animation outright avoids
    # relying on any frame-evaluation subtlety for the rest of this script.
    coll = bpy.data.collections[COLLECTION_NAME]
    for o in coll.objects:
        o.animation_data_clear()
    bpy.context.view_layer.update()

    CHASSIS_NAMES = [
        "DWLRP_BasePlate", "DWLRP_Battery", "DWLRP_UpperDeck", "DWLRP_ATOM_S3",
        "DWLRP_RearExtension",
    ] + [f"DWLRP_Standoff_{i}" for i in range(4)]

    pivots_m = {}  # side -> {'hip':Vector, 'knee':Vector, 'wheel':Vector}, meters

    def recenter_to_pivot(pivot_source, zero_rotation_objs=(), recenter_objs=()):
        # Shared "capture pivot -> zero rotation -> shift location ->
        # view_layer.update()" pattern, factored out of what were 3
        # near-identical inline blocks (hip/knee/wheel) per leg side
        # (issue #25 Phase 2 review, finding 2 -- see architect follow-up
        # plan comment on issue #25). Call sites intentionally pass
        # DIFFERENT zero_rotation_objs/recenter_objs sets per joint (they
        # are not identical in shape -- e.g. the hip site zeroes rotation
        # on 4 objects but re-centers only 3 of them, since knee_knuckle's
        # own pivot still needs to be read off its now-unrotated, but not
        # yet re-centered, matrix_world by the NEXT call), so this stays a
        # thin, generic helper rather than hardcoding a fixed object list.
        pivot = pivot_source.matrix_world.translation.copy()
        for o in zero_rotation_objs:
            o.rotation_euler.x = 0.0
        for o in recenter_objs:
            o.location = o.location - pivot
        bpy.context.view_layer.update()
        return pivot

    def export_group(filepath, names):
        bpy.ops.object.select_all(action='DESELECT')
        for n in names:
            get_obj(n).select_set(True)
        bpy.context.view_layer.objects.active = get_obj(names[0])
        bpy.ops.wm.obj_export(
            filepath=filepath,
            export_selected_objects=True,
            # global_scale=1.0, NOT export_pendulum_to_webots.py's 0.001: THIS
            # model's own docstring says "1 Blender unit = 1 meter, mm()
            # converts" -- _model_common.py's mm()/MM=0.001 helper already
            # divides every millimeter input by 1000 before it's ever stored
            # as a Blender coordinate, so this scene's raw Blender units are
            # already real meters (unlike model_pendulum.py, which sets
            # scene.unit_settings.scale_length=0.001 for UI DISPLAY purposes
            # only and stores raw millimeter numbers directly as Blender
            # units -- a different, incompatible convention). Confirmed
            # empirically during this script's own development: exporting
            # with 0.001 here produced a chassis mesh ~1000x too small
            # (sub-millimeter vertex spread instead of the expected ~90mm),
            # exactly the double-scaling this comment describes.
            global_scale=1.0,
            forward_axis='Y',         # identity mapping -- see module docstring's
            up_axis='Z',              # "Axis convention" section for why NOT
                                       # export_pendulum_to_webots.py's old
                                       # NEGATIVE_Z/Y setting.
            export_materials=True,
        )
        print(f"Exported: {filepath} ({len(names)} objects)")

    for side in ('R', 'L'):
        tag = f"DWLRP_{side}"
        CHASSIS_NAMES += [f"{tag}_HipKnuckleFront", f"{tag}_HipKnuckleBack"]

        hip_servo = get_obj(f"{tag}_HipServo_Body")
        upper_front = get_obj(f"{tag}_UpperPlateFront")
        upper_back = get_obj(f"{tag}_UpperPlateBack")
        knee = get_obj(f"{tag}_KneeKnuckle")
        lower_plate = get_obj(f"{tag}_LowerPlate")
        wheel = get_obj(f"{tag}_WheelHub")

        # --- hip pivot: capture BEFORE any edits, then zero rotation and
        # re-center the 3 independent upper-link roots (hip_servo,
        # upper_plate_front, upper_plate_back are siblings parented
        # directly to base_plate in build_leg(), not chained through each
        # other -- see that function's own comment) on it. knee_knuckle only
        # gets its rotation zeroed here (needed so its OWN pivot reads back
        # correctly below), not re-centered -- that happens via lower_plate
        # in the next call.
        hip_pivot = recenter_to_pivot(
            hip_servo,
            zero_rotation_objs=(hip_servo, upper_front, upper_back, knee),
            recenter_objs=(hip_servo, upper_front, upper_back),
        )

        # --- knee pivot: now hip-relative (knee_knuckle is parented to
        # upper_plate_front, which was just re-centered above).
        knee_pivot = recenter_to_pivot(knee, recenter_objs=(lower_plate,))

        # --- wheel/axle pivot: now knee-relative. wheel.rotation_euler
        # (the static (0, 90deg, 0) shape "tip" from build_wheel(), NOT a
        # joint DOF) is deliberately left untouched -- only its location
        # is re-centered.
        wheel_pivot = recenter_to_pivot(wheel, recenter_objs=(wheel,))

        pivots_m[side] = {'hip': tuple(hip_pivot), 'knee': tuple(knee_pivot), 'wheel': tuple(wheel_pivot)}

        upper_names = [
            f"{tag}_HipServo_Body", f"{tag}_HipServo_Spline", f"{tag}_HornBracket",
            f"{tag}_UpperPlateFront", f"{tag}_UpperPlateBack", f"{tag}_KneeKnuckle",
        ]
        lower_names = [
            f"{tag}_LowerPlate", f"{tag}_AnkleBlock", f"{tag}_AnkleKnuckle",
            f"{tag}_WheelServo_Body", f"{tag}_WheelServo_Spline", f"{tag}_AxleStub",
        ]
        wheel_names = [f"{tag}_WheelHub", f"{tag}_WheelHub_Hub"]

        export_group(os.path.join(MESH_DIR, f"legged_robot_upper_link_{side}.obj"), upper_names)
        export_group(os.path.join(MESH_DIR, f"legged_robot_lower_link_{side}.obj"), lower_names)
        export_group(os.path.join(MESH_DIR, f"legged_robot_wheel_{side}.obj"), wheel_names)

    export_group(os.path.join(MESH_DIR, "legged_robot_chassis.obj"), CHASSIS_NAMES)

    print("=" * 70)
    print("Pivots (meters; hip is Robot-root-relative, knee is upper-link-")
    print("relative, wheel is lower-link-relative -- matches legged_robot_")
    print("world.wbt's nested Solid/HingeJoint translation/anchor fields):")
    for side, p in pivots_m.items():
        print(f"  {side}: hip={p['hip']}  knee={p['knee']}  wheel={p['wheel']}")
    print("=" * 70)

    # Machine-readable pivot manifest (issue #54): the anchor/translation
    # fields legged_robot_world.wbt hand-transcribes from the printout above
    # have nothing forcing them to stay in sync with a re-export -- this
    # gives orchestration/legged_robot_pivot_drift.py something to check
    # against instead of relying on eyeballing the stdout block.
    PIVOT_MANIFEST_PATH = os.path.join(MESH_DIR, "legged_robot_pivots.json")
    manifest = {
        "schema_version": 1,
        "units": "m",
        "generated_by": "export_legged_robot_to_webots.py",
        "source_frame": 90,
        "pivots": pivots_m,
    }
    with open(PIVOT_MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"Wrote pivot manifest: {PIVOT_MANIFEST_PATH}")

    print("Exported dual-wheel legged robot meshes for Webots (issue #25 Phase 2).")
else:
    print("Skipped mesh export -- not running headless (bpy.app.background is False); "
          "re-run via run_blender_python to actually export.")
