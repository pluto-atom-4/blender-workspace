"""
Dual-Wheel Legged Balancing Robot (XGO-style) - CNC-accurate procedural model.

Chassis houses an ATOM S3 controller + UART motor driver PCB, drives two
STS3032 serial-bus servos per leg (hip + knee) through a 4-bar linkage
terminating in a driven wheel. Built entirely from bmesh geometry in
real-world millimeters (1 Blender unit = 1 meter, so mm() converts).

Sections:
  1. Units / cleanup
  2. Mesh primitives (box, cylinder) with explicit pivot control
  3. Boolean hole/groove cutting helper
  4. Component builders (chassis, servo, leg links, wheel, electronics)
  5. Assembly: parenting hierarchy + IK leg rig
  6. Animation: exploded-view assembly (1-120), balance/jump (121-250)
  7. Main
"""

import sys
import bpy
import math
from mathutils import Vector, Matrix

_SCRIPTS_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/scripts"
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from _model_common import (  # noqa: E402
    MM, mm, mm_inv, AXIS_ROT, make_box, make_cylinder, merge_cutters,
    boolean_diff_apply, set_ease, animate_assembly, kf_loc, kf_loc_z, kf_rot_x,
)

# ---------------------------------------------------------------------------
# 1. Units / cleanup
# ---------------------------------------------------------------------------

COLLECTION_NAME = "DualWheelLeggedRobot"
PREFIX = "DWLR_"


def clear_previous():
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        return
    objs = list(coll.objects)
    meshes = set()
    armatures = set()
    for obj in objs:
        if obj.type == 'MESH' and obj.data:
            meshes.add(obj.data)
        if obj.type == 'ARMATURE' and obj.data:
            armatures.add(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)
    for m in meshes:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    for a in armatures:
        if a.users == 0:
            bpy.data.armatures.remove(a)
    bpy.data.collections.remove(coll)


def new_collection():
    coll = bpy.data.collections.new(COLLECTION_NAME)
    bpy.context.scene.collection.children.link(coll)
    return coll


# ---------------------------------------------------------------------------
# 2-3. Mesh primitives, boolean cutting -- shared with the _precise sibling
# via _model_common (make_box/make_cylinder/merge_cutters/boolean_diff_apply,
# imported above).
# ---------------------------------------------------------------------------
# 4. Component builders
# ---------------------------------------------------------------------------

# --- Chassis ---------------------------------------------------------------
CHASSIS_L = 110.0   # Y (forward/back)
CHASSIS_W = 70.0    # X (lateral)
CHASSIS_H = 45.0    # Z (vertical)
WALL = 2.5


def build_chassis(collection):
    outer = make_box("DWLR_Chassis", collection, (CHASSIS_W, CHASSIS_L, CHASSIS_H))
    inner_cutter = merge_cutters("DWLR_ChassisShell", collection, [{
        'type': 'box',
        'size': (CHASSIS_W - 2 * WALL, CHASSIS_L - 2 * WALL, CHASSIS_H - WALL),
        'location': (0, 0, WALL),  # leave floor solid, open-ish top area still enclosed by lid
    }])
    boolean_diff_apply(outer, inner_cutter)

    holes = []
    # 4x M2 lid screw holes (through top wall), corner pattern
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append({'type': 'cyl', 'radius': 1.0, 'depth': WALL * 4, 'axis': 'Z',
                          'location': (sx * (CHASSIS_W / 2 - 6), sy * (CHASSIS_L / 2 - 6), CHASSIS_H / 2)})
    # 4x M2 PCB standoff holes (through floor)
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append({'type': 'cyl', 'radius': 1.0, 'depth': WALL * 4, 'axis': 'Z',
                          'location': (sx * 20.0, sy * 12.5, -CHASSIS_H / 2)})
    # 4x M3 hip-servo mounting holes (through side walls, 2 per side)
    for sy in (-1, 1):
        for sz in (-1, 1):
            holes.append({'type': 'cyl', 'radius': 1.5, 'depth': WALL * 4, 'axis': 'X',
                          'location': (CHASSIS_W / 2, sy * 15.0, sz * 8.0 - CHASSIS_H / 2 + 10.0)})
    cutter = merge_cutters("DWLR_ChassisHoles", collection, holes)
    boolean_diff_apply(outer, cutter)
    return outer


# --- STS3032 servo ----------------------------------------------------------
SERVO_W = 20.0   # casing cross-section
SERVO_L = 40.0   # casing length
SERVO_H = 36.0   # casing depth (mounting face to output face)
SPLINE_R = 3.0
SPLINE_H = 4.5
SPLINE_OFFSET_Y = 12.0  # output spline is offset toward one end along the long axis


def build_servo(name, collection):
    """Built directly in its mounted orientation: the output-spline axis (and
    therefore the joint hinge axis) is local X, with the object origin at the
    spline's rotation center. This lets a caller animate rotation_euler.x on
    the returned body directly as the joint angle -- no post-hoc object
    rotation is ever applied to it, so children parented to it can't desync
    (see the exploded-view trap noted on the wheel builder above)."""
    pivot = (SERVO_H / 2, SPLINE_OFFSET_Y, 0.0)
    body = make_box(name + "_Body", collection, (SERVO_H, SERVO_L, SERVO_W), pivot_mm=pivot)
    spline = make_cylinder(name + "_Spline", collection, SPLINE_R, SPLINE_H, axis='X',
                            location_mm=(SPLINE_H / 2, 0.0, 0.0))
    spline.parent = body
    return body


# --- Leg linkage (4-bar) ----------------------------------------------------
def build_link_bar(name, collection, length_mm, width_mm=10.0, thick_mm=5.0):
    """Bar spans from local origin (head pivot, z=0) down to (0, 0, -length) (tail pivot)."""
    return make_box(name, collection, (width_mm, thick_mm, length_mm),
                     pivot_mm=(0.0, 0.0, length_mm / 2))


def build_wheel(name, collection):
    r = WHEEL_R
    w = WHEEL_W
    wheel = make_cylinder(name, collection, r, w, axis='Z', segments=48)
    grooves = []
    n = 16
    for i in range(n):
        ang = (2 * math.pi / n) * i
        gx = (r - 1.0) * math.cos(ang)
        gy = (r - 1.0) * math.sin(ang)
        grooves.append({'type': 'box', 'size': (4.0, 3.0, w - 4.0), 'location': (gx, gy, 0.0)})
    cutter = merge_cutters(name + "_Grooves", collection, grooves)
    boolean_diff_apply(wheel, cutter)
    # hub boss (visual axle mount), built in the same canonical Z-axis local
    # frame as the wheel mesh. Reorient the axle to lateral X via a LIVE
    # (unapplied) object rotation on the wheel only -- hub is its child, so it
    # inherits the same rotation through the parent matrix automatically.
    # (transform_apply here would bake the rotation into the wheel's mesh
    # while leaving the already-parented hub's matrix_basis untouched,
    # desyncing the two -- see hip/knee servo builders for the same trap.)
    hub = make_cylinder(name + "_Hub", collection, 8.0, w + 6.0, axis='Z', segments=24)
    hub.parent = wheel
    wheel.rotation_euler = (0.0, math.radians(90), 0.0)
    return wheel


WHEEL_R = 32.5
WHEEL_W = 18.0


# --- Electronics -------------------------------------------------------------
def build_atom_s3(collection):
    return make_box("DWLR_ATOM_S3", collection, (24.0, 24.0, 13.6))


def build_pcb(collection):
    pcb = make_box("DWLR_MotorDriverPCB", collection, (55.0, 35.0, 1.6))
    for i, (ox, oy) in enumerate([(-22, -14), (22, -14), (-22, 14), (22, 14)]):
        chip = make_box(f"DWLR_PCB_Chip_{i}", collection, (6.0, 6.0, 2.0),
                         location_mm=(ox, oy, 1.8))
        chip.parent = pcb
    return pcb


# ---------------------------------------------------------------------------
# 5. Assembly: strict FK parenting hierarchy
#    Chassis -> Hip Servo -> Upper Leg -> Knee Servo -> Lower Leg ->
#    Wheel Actuator -> Wheel Hub
#
#    Each joint servo's origin sits exactly at its physical spline pivot
#    (build_servo) with the hinge axis baked in as local X, so animating
#    rotation_euler.x on Hip/Knee Servo alone drives everything distal to it
#    -- ordinary FK composition through the chain, no IK solver involved.
#    (A live Blender bone-IK constraint was tried first but does not
#    re-solve under headless/background evaluation in this Blender build;
#    direct FK keyframes are used instead and are fully deterministic.)
# ---------------------------------------------------------------------------

UPPER_LEG_LEN = 65.0
LOWER_LEG_LEN = 65.0
HIP_X = CHASSIS_W / 2 + SERVO_H / 2 - 4.0
HIP_Y = 0.0
HIP_Z = -CHASSIS_H / 2 + 6.0


def build_leg(side, collection, chassis):
    sign = 1.0 if side == 'R' else -1.0
    tag = f"DWLR_{side}"
    hip_world = (sign * HIP_X, HIP_Y, HIP_Z)

    hip_servo = build_servo(f"{tag}_HipServo", collection)
    hip_servo.location = mm(*hip_world)
    hip_servo.parent = chassis

    upper_link = build_link_bar(f"{tag}_UpperLeg", collection, UPPER_LEG_LEN)
    upper_link.location = (0.0, 0.0, 0.0)
    upper_link.parent = hip_servo

    knee_servo = build_servo(f"{tag}_KneeServo", collection)
    knee_servo.location = (0.0, 0.0, mm(-UPPER_LEG_LEN))
    knee_servo.parent = upper_link

    lower_link = build_link_bar(f"{tag}_LowerLeg", collection, LOWER_LEG_LEN)
    lower_link.location = (0.0, 0.0, 0.0)
    lower_link.parent = knee_servo

    wheel_actuator = build_servo(f"{tag}_WheelActuator", collection)
    wheel_actuator.location = (0.0, 0.0, mm(-LOWER_LEG_LEN))
    wheel_actuator.parent = lower_link

    wheel = build_wheel(f"{tag}_WheelHub", collection)
    wheel.location = (0.0, 0.0, 0.0)
    wheel.parent = wheel_actuator

    return {
        'hip_servo': hip_servo, 'upper_link': upper_link,
        'knee_servo': knee_servo, 'lower_link': lower_link,
        'wheel_actuator': wheel_actuator, 'wheel': wheel,
        'hip_world': hip_world,
    }


# ---------------------------------------------------------------------------
# 6. Animation -- set_ease/animate_assembly/mm_inv/kf_loc/kf_loc_z/kf_rot_x
# are shared via _model_common (imported above). This script's exploded
# view holds at frame 120 (not _model_common's default hold_frame=90), so
# every animate_assembly call below passes hold_frame=120 explicitly.
# ---------------------------------------------------------------------------

def build_exploded_view(chassis, atom, pcb, legs):
    # Chassis itself drops in from above
    chassis_seated = (0.0, 0.0, 0.0)
    animate_assembly(chassis, chassis_seated, (0.0, 0.0, 150.0), seat_frame=45, hold_frame=120)

    animate_assembly(atom, (0.0, 0.0, 0.0), (0.0, -60.0, 40.0), seat_frame=60, hold_frame=120)
    animate_assembly(pcb, (0.0, 0.0, -CHASSIS_H / 2 + 3.0), (0.0, 60.0, -50.0), seat_frame=55, hold_frame=120)

    # Parts are nested (each parented to the previous), so explode offsets
    # are LOCAL and compound down the chain -- keep each link's own delta
    # small; the cumulative lateral spread by wheel_actuator is still ~115mm.
    for side, leg in legs.items():
        sign = 1.0 if side == 'R' else -1.0
        step = (sign * 15.0, 0.0, 0.0)
        animate_assembly(leg['hip_servo'], mm_inv(leg['hip_servo'].location), (sign * 70.0, 0.0, 0.0), seat_frame=25, hold_frame=120)
        animate_assembly(leg['upper_link'], mm_inv(leg['upper_link'].location), step, seat_frame=28, hold_frame=120)
        animate_assembly(leg['knee_servo'], mm_inv(leg['knee_servo'].location), step, seat_frame=31, hold_frame=120)
        animate_assembly(leg['lower_link'], mm_inv(leg['lower_link'].location), step, seat_frame=34, hold_frame=120)
        animate_assembly(leg['wheel_actuator'], mm_inv(leg['wheel_actuator'].location), step, seat_frame=37, hold_frame=120)
        animate_assembly(leg['wheel'], mm_inv(leg['wheel'].location), (0.0, 0.0, sign * -40.0), seat_frame=20, hold_frame=120)


def kf_joints(legs, frame, hip_deg, knee_deg, easing='EASE_IN_OUT'):
    """Keyframe hip/knee joint angles identically on both legs (both hinge
    about the same world-consistent local X axis, so no L/R sign flip)."""
    for leg in legs.values():
        kf_rot_x(leg['hip_servo'], frame, hip_deg, easing=easing)
        kf_rot_x(leg['knee_servo'], frame, knee_deg, easing=easing)


def build_balance_and_jump(chassis, legs):
    """Frames 121-250: IMU balance micro-oscillation, crouch, jump, fall,
    touchdown. Leg "compression" is driven by keyframing hip/knee joint
    angles directly (see build_leg's FK-chain note) rather than an IK target.

    Grounded ranges (121-180, 220-250) end with lock_wheels_to_floor's
    dense per-frame correction, same fix ported from the _precise sibling
    (issue #23) -- this 2-DOF hip+knee leg has no auto-leveling trick, so
    chassis pitch/z and joint angle changes move the wheel a lot more than
    a naively hand-picked chassis.z ever tracked correctly.
    """
    scene = bpy.context.scene
    scene.frame_set(121)
    bpy.context.view_layer.update()
    floor_z = min((legs['R']['wheel'].matrix_world @ Vector(c)).z
                   for c in legs['R']['wheel'].bound_box)

    # 121-160: balancing micro-oscillation (chassis pitch only -- the old
    # hand-picked z-bob is gone, lock_wheels_to_floor derives the correct
    # z from the pitch instead), legs stay extended (neutral stance).
    osc_frames = [121, 131, 141, 151, 160]
    osc_pitch = [0.0, 1.4, -1.2, 1.0, 0.0]
    for f, pitch in zip(osc_frames, osc_pitch):
        kf_rot_x(chassis, f, pitch)
        kf_loc(chassis, f, (0.0, 0.0, 0.0))
    kf_joints(legs, 121, 0.0, 0.0)
    kf_joints(legs, 160, 0.0, 0.0)

    # 161-180: crouch (store energy). z=0.0 placeholder -- lock_wheels_to_floor
    # overwrites every frame in 121-180 with the FK-derived height.
    kf_loc(chassis, 161, (0.0, 0.0, 0.0))
    kf_rot_x(chassis, 161, 0.0)
    kf_loc(chassis, 180, (0.0, 0.0, 0.0))
    kf_rot_x(chassis, 180, -4.0)
    kf_joints(legs, 161, 0.0, 0.0)
    kf_joints(legs, 180, -30.0, 55.0, easing='EASE_IN')

    # 181-195: explosive extension (jump off ground)
    kf_loc(chassis, 187, (0.0, 0.0, 60.0), easing='EASE_OUT')
    kf_rot_x(chassis, 187, 2.0)
    kf_loc(chassis, 195, (0.0, 0.0, 180.0), easing='EASE_OUT')
    kf_rot_x(chassis, 195, 0.0)
    kf_joints(legs, 183, 8.0, -12.0, easing='EASE_OUT')
    kf_joints(legs, 195, -22.0, 48.0)

    # 196-220: free-fall parabolic arc (legs stay tucked, extend for landing)
    kf_loc(chassis, 205, (0.0, 0.0, 200.0), easing='EASE_OUT')  # apex
    kf_rot_x(chassis, 205, -1.0)
    kf_loc(chassis, 220, (0.0, 0.0, 0.0), easing='EASE_IN')
    kf_rot_x(chassis, 220, 0.0)
    kf_joints(legs, 210, -18.0, 40.0)
    kf_joints(legs, 220, 0.0, 0.0, easing='EASE_IN')

    # 221-250: touchdown impact absorb -> resume balancing. z=0.0
    # placeholders, overwritten by lock_wheels_to_floor (220-250 range).
    kf_loc(chassis, 226, (0.0, 0.0, 0.0), easing='EASE_IN')
    kf_rot_x(chassis, 226, -3.0)
    kf_loc(chassis, 238, (0.0, 0.0, 0.0))
    kf_rot_x(chassis, 238, 0.0)
    kf_loc(chassis, 250, (0.0, 0.0, 0.0))
    kf_rot_x(chassis, 250, 0.0)
    kf_joints(legs, 226, -32.0, 58.0, easing='EASE_IN')
    kf_joints(legs, 238, 0.0, 0.0)
    kf_joints(legs, 250, 0.0, 0.0)

    # Range 1 extends one frame past the crouch-bottom anchor (180) to 181:
    # the joint-angle path toward the 183 explosive-extension keyframe dips
    # the wheel slightly before chassis.z's own rise (keyframed at 187)
    # catches up, so 181 needs the same correction as the rest of the
    # grounded stance even though liftoff is already underway by 183.
    lock_wheels_to_floor(chassis, legs, floor_z, [(121, 181), (220, 250)])


def lock_wheels_to_floor(chassis, legs, floor_z, frame_ranges):
    """Densely re-keyframes chassis's Z (every frame, in the given ranges
    only) so the wheel bottom sits exactly at floor_z -- ported from the
    _precise sibling's fix for the same "sinking into the floor" bug
    (issue #23). Derived from the R wheel and applied to both via
    chassis.z (shared by the whole rig); asserted every frame rather than
    assumed, since kf_joints always drives L/R identically here too."""
    scene = bpy.context.scene
    wheel_r = legs['R']['wheel']
    wheel_l = legs['L']['wheel']
    for start, end in frame_ranges:
        for f in range(start, end + 1):
            scene.frame_set(f)
            chassis.location.z = 0.0
            bpy.context.view_layer.update()
            offset_r = min((wheel_r.matrix_world @ Vector(c)).z for c in wheel_r.bound_box)
            offset_l = min((wheel_l.matrix_world @ Vector(c)).z for c in wheel_l.bound_box)
            assert abs(offset_l - offset_r) < 0.001, (
                f"frame {f}: L/R wheel-bottom offsets diverged "
                f"({offset_l:.5f} vs {offset_r:.5f})"
            )
            needed_z_mm = (floor_z - offset_r) / MM
            kf_loc_z(chassis, f, needed_z_mm, easing='EASE_IN_OUT')


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------

def main():
    clear_previous()
    collection = new_collection()

    chassis = build_chassis(collection)
    atom = build_atom_s3(collection)
    atom.parent = chassis
    atom.location = mm(0.0, 0.0, CHASSIS_H / 2 - 13.6 / 2 - WALL)

    pcb = build_pcb(collection)
    pcb.parent = chassis
    pcb.location = mm(0.0, 0.0, -CHASSIS_H / 2 + WALL + 1.6 / 2 + 3.0)

    legs = {}
    legs['R'] = build_leg('R', collection, chassis)
    legs['L'] = build_leg('L', collection, chassis)

    build_exploded_view(chassis, atom, pcb, legs)
    build_balance_and_jump(chassis, legs)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 250
    scene.frame_set(1)

    print("Dual-Wheel Legged Balancing Robot build complete.")
    print(f"Objects created: {len(collection.objects)}")

    if bpy.app.background:
        # Headless (render pipeline) run -- persist the build per the
        # model_<subject>.py contract in DESIGN.md. Skipped when run live via
        # run_blender_python_live so it never hijacks the GUI session's own
        # open file. Matches model_pendulum.py / the _precise sibling.
        bpy.ops.wm.save_as_mainfile(
            filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/model_dual_wheel_legged_robot.blend",
            check_existing=False,
        )


main()
