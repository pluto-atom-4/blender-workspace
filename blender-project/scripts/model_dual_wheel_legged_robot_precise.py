"""
Dual-Wheel Legged Balancing Robot -- precise variant (XGO-style), refined
against reference photos of the real hardware: sandwich CNC chassis stack,
true parallelogram 4-bar leg linkage, inverted ankle-mounted drive servo
tucked inside the wheel. Real-world millimeters throughout (1 Blender unit
= 1 meter, mm() converts). Supersedes model_dual_wheel_legged_robot.py with
image-informed mechanical detail; see DESIGN.md's "_precise" convention.

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (box, cylinder) with explicit pivot control
  3. Boolean hole/groove cutting helper
  4. Component builders (chassis stack, servo, 4-bar link, ankle, wheel)
  5. Assembly: sandwich stack + parallelogram leg FK chain
  6. Animation: exploded assembly (1-90), settle/balance/crouch/jump/land/
     balance/stand (90-STAND_FRAME, physics-derived from JUMP_APEX_MM --
     see build_balance_and_jump)
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
    MM, mm, mm_inv, make_box, make_cylinder, merge_cutters,
    boolean_diff_apply, set_ease, animate_assembly, kf_loc, kf_loc_z, kf_rot_x,
    kf_rot_full, lock_wheels_to_floor,
)

# ---------------------------------------------------------------------------
# 1. Units / cleanup / materials
# ---------------------------------------------------------------------------

COLLECTION_NAME = "DualWheelLeggedRobotPrecise"
PREFIX = "DWLRP_"


def clear_previous():
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        return
    objs = list(coll.objects)
    meshes = set()
    for obj in objs:
        if obj.type == 'MESH' and obj.data:
            meshes.add(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)
    for m in meshes:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    bpy.data.collections.remove(coll)


def new_collection():
    coll = bpy.data.collections.new(COLLECTION_NAME)
    bpy.context.scene.collection.children.link(coll)
    return coll


_MAT_CACHE = {}


def get_material(name, rgba):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    mat = bpy.data.materials.get(PREFIX + name) or bpy.data.materials.new(PREFIX + name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.55
    _MAT_CACHE[name] = mat
    return mat


MAT_PLATE = lambda: get_material("Plate", (0.05, 0.05, 0.055, 1.0))       # black CNC plate (legs, brackets)
MAT_METAL = lambda: get_material("Metal", (0.5, 0.5, 0.55, 1.0))          # standoffs, bolts, knuckles
MAT_WHITE = lambda: get_material("White", (0.85, 0.85, 0.83, 1.0))        # ATOM S3 housing
MAT_PCB = lambda: get_material("PCB", (0.06, 0.32, 0.14, 1.0))            # PCB deck / battery accent
MAT_BLACK = lambda: get_material("Black", (0.015, 0.015, 0.018, 1.0))     # servos, wheel tire


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# 2-3. Mesh primitives, boolean cutting -- shared with the non-_precise
# sibling via _model_common (make_box/make_cylinder/merge_cutters/
# boolean_diff_apply, imported above).
# ---------------------------------------------------------------------------
# 4. Component builders
# ---------------------------------------------------------------------------

# --- Sandwich chassis stack --------------------------------------------------
BASE_W, BASE_L, BASE_T = 90.0, 70.0, 3.0
DECK_W, DECK_L, DECK_T = 78.0, 52.0, 3.0
STANDOFF_R, STANDOFF_H = 2.5, 18.0
BATTERY_W, BATTERY_L, BATTERY_T = 45.0, 24.0, 10.0
ATOM_W, ATOM_L, ATOM_H = 24.0, 24.0, 13.6
REAR_EXT_W, REAR_EXT_T, REAR_EXT_H = 130.0, 3.0, 28.0


def build_base_plate(collection):
    plate = make_box("DWLRP_BasePlate", collection, (BASE_W, BASE_L, BASE_T), material=MAT_PLATE())
    holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append({'type': 'cyl', 'radius': 1.5, 'depth': BASE_T * 4, 'axis': 'Z',
                          'location': (sx * (BASE_W / 2 - 10), sy * (BASE_L / 2 - 10), 0.0)})
    cutter = merge_cutters("DWLRP_BaseHoles", collection, holes)
    boolean_diff_apply(plate, cutter)
    return plate


def build_standoff(name, collection):
    return make_cylinder(name, collection, STANDOFF_R, STANDOFF_H, axis='Z', segments=16, material=MAT_METAL())


def build_deck_plate(collection):
    deck = make_box("DWLRP_UpperDeck", collection, (DECK_W, DECK_L, DECK_T), material=MAT_PCB())
    holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append({'type': 'cyl', 'radius': 1.5, 'depth': DECK_T * 4, 'axis': 'Z',
                          'location': (sx * (BASE_W / 2 - 10), sy * (BASE_L / 2 - 10), 0.0)})
    cutter = merge_cutters("DWLRP_DeckHoles", collection, holes)
    boolean_diff_apply(deck, cutter)
    return deck


def build_battery(collection):
    return make_box("DWLRP_Battery", collection, (BATTERY_W, BATTERY_L, BATTERY_T), material=MAT_BLACK())


def build_atom_s3(collection):
    body = make_box("DWLRP_ATOM_S3", collection, (ATOM_W, ATOM_L, ATOM_H), material=MAT_WHITE())
    # clear port cutouts on one side face
    ports = [{'type': 'box', 'size': (3.0, 8.0, 4.0), 'location': (ATOM_W / 2 - 1.0, 0.0, -ATOM_H / 2 + 3.0)}]
    cutter = merge_cutters("DWLRP_AtomPorts", collection, ports)
    boolean_diff_apply(body, cutter)
    return body


def build_rear_extension(collection):
    """Vertical structural tab rising from the base plate's rear edge,
    anchoring the two hip linkage pivot rods (upper driven, lower follower)."""
    ext = make_box("DWLRP_RearExtension", collection, (REAR_EXT_W, REAR_EXT_T, REAR_EXT_H),
                    pivot_mm=(0.0, 0.0, -REAR_EXT_H / 2), material=MAT_PLATE())
    return ext


# --- STS3032 servo (shared by hip drive + ankle drive) ----------------------
SERVO_W = 20.0
SERVO_L = 40.0
SERVO_H = 36.0
SPLINE_R = 3.0
SPLINE_H = 4.5
SPLINE_OFFSET_Y = 12.0


def build_servo(name, collection, sign=1.0):
    """Built in its mounted orientation: output-spline axis (= joint hinge
    axis) is local X, object origin at the spline's rotation center. Caller
    animates rotation_euler.x directly as the joint angle -- no post-hoc
    object rotation is ever applied, so parented children can't desync.

    The body's bulk sits on ONE side of its own origin (SERVO_H long, origin
    at the output face), so which world direction it extends in depends on
    pivot.x's sign. A fixed pivot.x (independent of `sign`) would make the
    body extend toward the same world direction on both legs -- inward
    (tucked toward the centerline, matching the reference hardware) on
    whichever leg that direction happens to point in, and outward -- sticking
    out past its own pivot, away from the robot -- on the other. Flipping
    pivot.x by `sign` makes both legs' servo bodies tuck inward instead."""
    pivot = (sign * SERVO_H / 2, SPLINE_OFFSET_Y, 0.0)
    body = make_box(name + "_Body", collection, (SERVO_H, SERVO_L, SERVO_W), pivot_mm=pivot, material=MAT_BLACK())
    spline = make_cylinder(name + "_Spline", collection, SPLINE_R, SPLINE_H, axis='X',
                            location_mm=(SPLINE_H / 2 * sign, 0.0, 0.0), material=MAT_METAL())
    spline.parent = body
    return body


def build_servo_horn_bracket(collection, tag, sign):
    """Small metal bracket connecting the hip servo's horn to the driven
    link's pivot -- purely visual, rides rigidly with the servo body.
    hip_servo itself is never mirrored (L and R share the same local
    orientation, only their world X position differs), so this bracket's
    local +X nub must be sign-flipped explicitly or it ends up sitting
    outward on one leg and inward on the other."""
    bracket = make_box(f"{tag}_HornBracket", collection, (4.0, 14.0, 6.0),
                        pivot_mm=(0.0, -SPLINE_OFFSET_Y, 0.0), location_mm=(SPLINE_H * sign, 0.0, 0.0),
                        material=MAT_METAL())
    return bracket


def build_knuckle(name, collection, location_mm=(0.0, 0.0, 0.0)):
    """Round pivot knuckle with a hex-ish bolt head -- visual detail at a
    linkage pin. Low segment count reads as a bolt head, not a cylinder."""
    return make_cylinder(name, collection, 3.0, 2.5, axis='X', segments=6,
                          location_mm=location_mm, material=MAT_METAL())


# --- 4-bar parallel linkage bar ---------------------------------------------
def build_link_bar(name, collection, length_mm, width_mm=10.0, thick_mm=4.0):
    """Flat CNC plate bar. Spans from local origin (head pivot, z=0) down to
    (0, 0, -length) (tail pivot)."""
    return make_box(name, collection, (width_mm, thick_mm, length_mm),
                     pivot_mm=(0.0, 0.0, length_mm / 2), material=MAT_PLATE())


def build_ankle_block(name, collection):
    return make_box(name, collection, (16.0, 20.0, 14.0), material=MAT_METAL())


# --- PEA (parallel elastic actuation) spring -- placeholder geometry -------
SPRING_LENGTH_MM = 22.0  # placeholder coil housing length
SPRING_RADIUS_MM = 2.5
SPRING_LATERAL_OFFSET_MM = 6.0  # tucks the spring toward centerline, same
                                 # "tuck inward" convention as build_servo's
                                 # sign-flipped pivot.x (see that docstring)


def build_pea_spring(tag, collection, sign):
    """Placeholder PEA (parallel elastic actuation) spring geometry --
    issue #25 Phase 1, Task 4. A simple representative tube (matches
    build_knuckle()'s fidelity level: one low-segment primitive standing in
    for a real part, not a physically modeled coil), NOT a simulated
    spring -- no Blender spring/soft-body constraint is attached here.
    Sizing (target N*m/rad spring constant) is computed separately in
    orchestration/linkage_kinematics.py's pea_spring_constant_n_m_per_rad();
    Phase 2 is where that number actually gets used, as a Webots
    HingeJoint.springConstant.

    Conceptually spans from a fixed anchor near the hip on the chassis side
    to a point partway up upper_plate_front, running roughly parallel to
    the plate -- but this is a single rigid mesh, built once at
    DEFAULT_HIP_ANGLE and then parented to upper_plate_front (see
    build_leg()'s call site) so it swings rigidly with the hip angle like
    knee_knuckle/horn do. It is only geometrically exact at the rest pose;
    a static single-piece mesh can't stretch between two independently
    moving points across the animation without per-frame deformation,
    which is out of scope for this placeholder (same simplification this
    file already accepts for every other rigid FK-chain part).

    sign mirrors the small lateral tuck-inward offset for L/R legs, same
    convention as build_servo's pivot.x flip.
    """
    return make_cylinder(f"{tag}_PeaSpring", collection, SPRING_RADIUS_MM, SPRING_LENGTH_MM,
                          axis='Z', segments=10,
                          location_mm=(-sign * SPRING_LATERAL_OFFSET_MM, 0.0, -SPRING_LENGTH_MM / 2),
                          material=MAT_METAL())


def build_wheel(name, collection):
    r = WHEEL_R
    w = WHEEL_W
    wheel = make_cylinder(name, collection, r, w, axis='Z', segments=48, material=MAT_BLACK())
    grooves = []
    n = 20
    for i in range(n):
        ang = (2 * math.pi / n) * i
        gx = (r - 1.2) * math.cos(ang)
        gy = (r - 1.2) * math.sin(ang)
        grooves.append({'type': 'box', 'size': (4.0, 3.0, w - 3.0), 'location': (gx, gy, 0.0)})
    cutter = merge_cutters(name + "_Grooves", collection, grooves)
    boolean_diff_apply(wheel, cutter)
    hub = make_cylinder(name + "_Hub", collection, 9.0, w + 6.0, axis='Z', segments=24, material=MAT_METAL())
    hub.parent = wheel
    # Reorient the axle to lateral X via a LIVE (unapplied) object rotation
    # on the wheel only -- hub is its child and inherits the same rotation
    # through the parent matrix. transform_apply here would bake the
    # rotation into the wheel's mesh while leaving the hub's matrix_basis
    # untouched, desyncing the two (same trap noted on the servo builder).
    wheel.rotation_euler = (0.0, math.radians(90), 0.0)
    return wheel


WHEEL_R = 40.0
WHEEL_W = 16.0


# ---------------------------------------------------------------------------
# 5. Assembly: sandwich stack + forked-plate leg FK chain
#
#    Chassis stack: BasePlate -> Standoffs / RearExtension / (Deck -> Atom S3)
#    Leg (per side): BasePlate -> HipServo, UpperPlateFront, UpperPlateBack
#                     (all three parent directly to BasePlate as siblings,
#                     not chained through RearExtension or through each
#                     other -- RearExtension is a visual chassis tab only)
#                     UpperPlateFront -> KneeKnuckle -> LowerPlate -> AnkleBlock
#                                                     -> WheelServo(inverted) -> WheelHub
#
#    Matches the reference hardware's leg: two thin plates sandwich the hip
#    and knee pivots (a fork, for a wider/stiffer bearing surface than one
#    plate alone), converging at a single knuckle, then ONE plate continues
#    from there down to the wheel. Only the hip is actuated; UpperPlateFront
#    and UpperPlateBack are keyframed to the SAME rotation_euler.x (a rigid
#    doubled pair, not independent links), and KneeKnuckle is keyframed to
#    the NEGATIVE of that angle so the subtree below it (LowerPlate,
#    AnkleBlock, wheel) never accumulates net rotation -- the wheel stays
#    level through the full range of motion without a second actuator,
#    exactly like the earlier parallelogram's coupler did. This is
#    deterministic FK rather than a live constraint solve, per the same
#    lesson as the base script: Blender's runtime bone-IK didn't re-solve
#    under headless/live evaluation there, so joint motion is authored
#    directly as keyframed angles throughout this project.
# ---------------------------------------------------------------------------

UPPER_LEN = 40.0
LOWER_LEN = 30.0
PLATE_GAP = 7.0  # lateral (Y) air gap between the two upper plates
HIP_LATERAL = 50.0  # wheel centers 2*HIP_LATERAL=100mm apart; WHEEL_R=40mm needs
                     # >=80mm to just touch, so this leaves a 20mm clearance gap
HIP_Z = 20.0       # height of the hip pivot above the base plate
ANKLE_DROP = 10.0  # ankle block center below the lower plate's tail
DEFAULT_HIP_ANGLE = 58.0  # resting-stance hip bend -- the rest pose used at
                           # both ends of the animation and while balancing;
                           # the jump snap (frame 168) goes DEFAULT+70deg
                           # from here, it does not itself equal this value
WHEEL_STUB = 22.0  # axle standoff between the wheel-servo body and the wheel
                    # disc -- without it the servo body (which extends
                    # SERVO_H=36mm from its pivot) clips straight through the
                    # wheel (WHEEL_R=40mm), since both are coincident with
                    # the same axle/spline pivot by construction


def build_leg(side, collection, base_plate):
    sign = 1.0 if side == 'R' else -1.0
    tag = f"DWLRP_{side}"

    hip_world = (sign * HIP_LATERAL, -BASE_L / 2 - REAR_EXT_T, HIP_Z)
    default_rad = math.radians(DEFAULT_HIP_ANGLE)

    # Hip servo: mounted horizontally under the rear deck, its output spline
    # coincides with the hip pivot axis -- the servo horn bracket is the
    # visual link from servo body to the upper plates' pivot. Per
    # build_servo()'s own contract ("Caller animates rotation_euler.x
    # directly as the joint angle"), hip_servo's rotation IS the joint
    # angle, same as upper_plate_front/back -- kf_leg_angle drives all
    # three together so the horn bracket stays bolted to the plate instead
    # of freezing at the static build pose while the plate sweeps away.
    hip_servo = build_servo(f"{tag}_HipServo", collection, sign)
    hip_servo.location = mm(*hip_world)
    hip_servo.rotation_euler.x = default_rad
    hip_servo.parent = base_plate
    horn = build_servo_horn_bracket(collection, tag, sign)
    horn.parent = hip_servo

    # One bolt-head knuckle per plate (matching the reference hardware's
    # sandwiched fork -- two pivot points, PLATE_GAP apart in Y), not a
    # single one straddling both.
    hip_knuckle_front = build_knuckle(f"{tag}_HipKnuckleFront", collection,
                                       location_mm=(hip_world[0], hip_world[1] + PLATE_GAP / 2, hip_world[2]))
    hip_knuckle_front.parent = base_plate
    hip_knuckle_back = build_knuckle(f"{tag}_HipKnuckleBack", collection,
                                      location_mm=(hip_world[0], hip_world[1] - PLATE_GAP / 2, hip_world[2]))
    hip_knuckle_back.parent = base_plate

    # Two thin plates sandwiching the hip/knee pivots (a fork), offset apart
    # laterally by PLATE_GAP. Both rotate identically -- a rigid doubled bar,
    # not two independent links.
    # Static baseline rotation is DEFAULT_HIP_ANGLE, not 0 -- the leg stands
    # visibly hinged at rest (matching the reference hardware) rather than
    # straightened. kf_leg_angle's later keyframes (starting frame 90) begin
    # from this same value, so there's no snap when balancing motion starts;
    # frames 1-89 (exploded assembly) show the hinged stance throughout since
    # nothing keyframes rotation before frame 90.
    upper_plate_front = build_link_bar(f"{tag}_UpperPlateFront", collection, UPPER_LEN,
                                        width_mm=9.0, thick_mm=3.0)
    upper_plate_front.location = mm(hip_world[0], hip_world[1] + PLATE_GAP / 2, hip_world[2])
    upper_plate_front.rotation_euler.x = default_rad
    upper_plate_front.parent = base_plate

    upper_plate_back = build_link_bar(f"{tag}_UpperPlateBack", collection, UPPER_LEN,
                                       width_mm=9.0, thick_mm=3.0)
    upper_plate_back.location = mm(hip_world[0], hip_world[1] - PLATE_GAP / 2, hip_world[2])
    upper_plate_back.rotation_euler.x = default_rad
    upper_plate_back.parent = base_plate

    # Knee knuckle: shared convergence point for both upper plates, parented
    # to the front plate so it inherits that plate's rotation, then given an
    # equal-and-opposite LOCAL rotation (see kf_leg_angle) to cancel it back
    # out -- the single-plate lower leg hangs from here.
    knee_knuckle = build_knuckle(f"{tag}_KneeKnuckle", collection, location_mm=(0.0, 0.0, -UPPER_LEN))
    knee_knuckle.rotation_euler.x = -default_rad
    knee_knuckle.parent = upper_plate_front

    # PEA spring (issue #25 Phase 1, Task 4) -- placeholder geometry only,
    # parented to upper_plate_front so it swings rigidly with the hip angle
    # like knee_knuckle does (see build_pea_spring()'s docstring for why a
    # static mesh can only be geometrically exact at the rest pose).
    pea_spring = build_pea_spring(tag, collection, sign)
    pea_spring.parent = upper_plate_front

    lower_plate = build_link_bar(f"{tag}_LowerPlate", collection, LOWER_LEN,
                                  width_mm=12.0, thick_mm=6.0)
    lower_plate.location = (0.0, 0.0, 0.0)
    lower_plate.parent = knee_knuckle

    ankle_block = build_ankle_block(f"{tag}_AnkleBlock", collection)
    ankle_block.location = (0.0, 0.0, mm(-LOWER_LEN))
    ankle_block.parent = lower_plate

    ankle_knuckle = build_knuckle(f"{tag}_AnkleKnuckle", collection, location_mm=(0.0, 0.0, 0.0))
    ankle_knuckle.parent = ankle_block

    # No rotation on the wheel servo: it mounts flush against ankle_block
    # (which is itself unrotated), so their mating faces stay parallel --
    # a static tilt here previously put a visible kink between the two.
    wheel_servo = build_servo(f"{tag}_WheelServo", collection, sign)
    wheel_servo.location = (0.0, 0.0, mm(-ANKLE_DROP))
    wheel_servo.parent = ankle_block

    # Wheel sits WHEEL_STUB further out along the axle than the spline
    # pivot itself -- see WHEEL_STUB's definition for why (avoids the wheel
    # disc clipping through the servo body). The body's build_servo()
    # docstring establishes it extends toward local -sign*X from its own
    # pivot, so "away from the body" is the +sign*X direction.
    axle_stub = make_cylinder(f"{tag}_AxleStub", collection, 4.0, WHEEL_STUB, axis='X',
                               location_mm=(sign * WHEEL_STUB / 2, 0.0, 0.0), material=MAT_METAL())
    axle_stub.parent = wheel_servo

    wheel = build_wheel(f"{tag}_WheelHub", collection)
    wheel.location = mm(sign * WHEEL_STUB, 0.0, 0.0)
    wheel.parent = wheel_servo

    return {
        'hip_servo': hip_servo, 'horn': horn,
        'upper_plate_front': upper_plate_front, 'upper_plate_back': upper_plate_back,
        'pea_spring': pea_spring,
        'knee_knuckle': knee_knuckle, 'lower_plate': lower_plate,
        'ankle_block': ankle_block, 'wheel_servo': wheel_servo, 'wheel': wheel,
        'hip_world': hip_world,
    }


# ---------------------------------------------------------------------------
# 6. Animation -- set_ease/animate_assembly/mm_inv/kf_loc/kf_loc_z/kf_rot_x
# are shared via _model_common (imported above).
# ---------------------------------------------------------------------------


def build_exploded_view(base_plate, standoffs, deck, battery, atom, rear_ext, legs):
    animate_assembly(base_plate, (0.0, 0.0, 0.0), (0.0, 0.0, 120.0), seat_frame=20)

    for i, so in enumerate(standoffs):
        animate_assembly(so, mm_inv(so.location), (0.0, 0.0, 60.0), seat_frame=28 + i * 2)

    animate_assembly(deck, mm_inv(deck.location), (0.0, 0.0, 70.0), seat_frame=45)
    animate_assembly(battery, mm_inv(battery.location), (60.0, 0.0, 0.0), seat_frame=40)
    animate_assembly(atom, mm_inv(atom.location), (0.0, -50.0, 50.0), seat_frame=55)
    animate_assembly(rear_ext, mm_inv(rear_ext.location), (0.0, -40.0, 0.0), seat_frame=32)

    for side, leg in legs.items():
        sign = 1.0 if side == 'R' else -1.0
        animate_assembly(leg['hip_servo'], mm_inv(leg['hip_servo'].location), (sign * 55.0, -15.0, 0.0), seat_frame=50)
        animate_assembly(leg['upper_plate_front'], mm_inv(leg['upper_plate_front'].location), (sign * 45.0, 6.0, 10.0), seat_frame=58)
        animate_assembly(leg['upper_plate_back'], mm_inv(leg['upper_plate_back'].location), (sign * 45.0, -6.0, 10.0), seat_frame=61)
        # Z components here must stay >=0 (fly in from ABOVE, matching the
        # upper_plate/hip_servo convention below) -- these three parent the
        # wheel, so any negative Z explode offset drags the wheel below its
        # already-floor-touching assembled position and it visibly plunges
        # through the floor while still converging (issue #23 follow-up).
        animate_assembly(leg['lower_plate'], mm_inv(leg['lower_plate'].location), (sign * 30.0, 0.0, 15.0), seat_frame=68)
        animate_assembly(leg['ankle_block'], mm_inv(leg['ankle_block'].location), (sign * 20.0, 0.0, 20.0), seat_frame=72)
        animate_assembly(leg['wheel_servo'], mm_inv(leg['wheel_servo'].location), (0.0, 0.0, 15.0), seat_frame=78)
        animate_assembly(leg['wheel'], mm_inv(leg['wheel'].location), (sign * 35.0, 0.0, 0.0), seat_frame=85)


def kf_leg_angle(legs, frame, angle_deg, easing='EASE_IN_OUT', interp='BEZIER'):
    """Drive the forked upper plates (rigid doubled pair) to the hip angle,
    and counter-rotate the knee knuckle by the same amount so the lower
    plate/ankle/wheel subtree it carries never accumulates net rotation --
    the wheel stays level through the full range of motion with only the
    hip actuated, same as the parallelogram coupler this replaced. Also
    drives hip_servo to the same angle -- its rotation_euler.x IS the joint
    axis (see build_servo's docstring), so without this the servo body and
    its horn bracket would stay frozen at the static build pose while the
    plates it's bolted to sweep away from it.

    interp defaults to BEZIER, matching every other kf_* helper -- but note
    Blender's `easing` enum is only honored for non-BEZIER interpolation
    modes (QUAD/CUBIC/EXPO/etc); under BEZIER it's silently ignored and the
    curve shape comes entirely from the (default AUTO_CLAMPED) handles
    instead, regardless of what `easing` says (issue #23 code review,
    confirmed empirically). Pass a real interp mode when the `easing` value
    needs to actually do something, e.g. the explosive launch snap."""
    for leg in legs.values():
        kf_rot_x(leg['hip_servo'], frame, angle_deg, easing=easing, interp=interp)
        kf_rot_x(leg['upper_plate_front'], frame, angle_deg, easing=easing, interp=interp)
        kf_rot_x(leg['upper_plate_back'], frame, angle_deg, easing=easing, interp=interp)
        kf_rot_x(leg['knee_knuckle'], frame, -angle_deg, easing=easing, interp=interp)


def kf_wheel_pitch(legs, frame, deg, easing='EASE_IN_OUT', interp='BEZIER'):
    for leg in legs.values():
        kf_rot_x(leg['wheel_servo'], frame, deg, easing=easing, interp=interp)


def kf_wheel_spin(legs, frame, spin_deg, easing='EASE_IN_OUT', interp='BEZIER'):
    """Rolls each wheel forward by spin_deg around its own axle -- the
    "pulse the wheel drive motors forward slightly to lock down the
    horizontal balance plane" cue from the explosive-takeoff physics brief
    (issue #23 follow-up), which had no implementation anywhere before this.

    build_wheel() bakes a static (0, 90deg, 0) tip onto the wheel object so
    its cylinder axis (originally local Z) ends up pointing along the
    axle direction. A further "roll" has to spin around THAT (tipped)
    axle, which does not correspond to incrementing any single
    rotation_euler channel on top of the existing (0, 90, 0) -- Euler
    channels compose in a fixed order, not around the object's current
    axes. Composing spin BEFORE the tip instead sidesteps the ambiguity
    entirely: spin(local Z) leaves the local Z axis itself fixed (points on
    a rotation axis don't move), and the tip is a rigid transform applied
    after, so "spin around original Z, then tip" is mathematically
    identical to "spin around wherever the axle ends up," regardless of
    Blender's Euler composition order. Both wheels share the same
    (non-mirrored) tip, so identical spin_deg on both rolls them forward
    together with no L/R sign flip needed.
    """
    tip = Matrix.Rotation(math.radians(90.0), 4, 'Y')
    spin = Matrix.Rotation(math.radians(spin_deg), 4, 'Z')
    euler = (tip @ spin).to_euler('XYZ')
    for leg in legs.values():
        kf_rot_full(leg['wheel'], frame, euler, interp=interp, easing=easing)


def balance_oscillation(base_plate, legs, frames, pitches):
    """IMU self-balance wobble: chassis pitch plus a 0.6x-coupled wheel
    counter-tilt, at the given (frame, degrees) pairs. Shared by both
    balance windows (98-140 pre-jump, 205-235 post-landing) so they can't
    silently diverge in behavior."""
    for f, p in zip(frames, pitches):
        kf_rot_x(base_plate, f, p)
        kf_wheel_pitch(legs, f, p * 0.6)


GRAVITY = 9.8  # m/s^2
LAUNCH_FRAME = 168  # explosive snap lands here; wheel leaves the floor

# CROUCH_ANGLE and LAUNCH_ANGLE are NOT DEFAULT_HIP_ANGLE +/- an offset --
# empirically swept needed-chassis-Z against hip angle across the leg's
# full range (issue #23 code review) and it is a SINGLE MONOTONIC curve,
# decreasing as angle increases, with no local min/max to exploit: smaller
# angles hold the chassis higher (taller stance), larger angles let it
# drop lower (crouch), passing through 0 at DEFAULT_HIP_ANGLE=58. A
# previous version had these backwards -- CROUCH_ANGLE below 58 (which
# actually raises the chassis) and the push angle above 58 (which actually
# lowers it) -- so the labeled "crouch" stood the robot up taller and the
# labeled "explosive push" sank it further down right before liftoff.
# Sampled values (needed base_plate.z in mm, at 5deg steps):
#   15deg->+17.4  38deg->+10.3  58deg->0  90deg->-21.2  120deg->-41.2
CROUCH_ANGLE = 120.0   # deep crouch: chassis genuinely lowers, stores energy
LAUNCH_ANGLE = 15.0    # explosive extension: chassis genuinely rises


def build_balance_and_jump(base_plate, legs):
    """Rebuilt from scratch per the assemble->stand->jump spec (issue #23
    follow-up): every leg pose is DEFAULT_HIP_ANGLE=58deg plus or minus an
    explicit delta off it -- no other absolute angle is invented -- and the
    model's feet are on the floor (base_plate.z == 0) at both ends of the
    clip, only leaving the ground for the single jump arc in the middle.

    Rebuilt again (issue #23 code review) after simulating the actual
    per-frame chassis motion and finding two physics problems:

    1. CROUCH_ANGLE/the push angle were on the WRONG SIDES of
       DEFAULT_HIP_ANGLE. Sweeping needed-chassis-Z against hip angle
       across the leg's full range shows ONE monotonic curve (decreasing
       as angle increases, no local min/max -- see CROUCH_ANGLE/
       LAUNCH_ANGLE's own comment for the sampled values): smaller angles
       hold the chassis HIGHER, larger angles let it drop LOWER. The
       previous CROUCH_ANGLE (38, below 58) therefore stood the robot up
       TALLER, and the previous push angle (128, above 58) sank it
       FURTHER DOWN right before liftoff -- both backwards from what
       "crouch to store energy, explode upward" needs. Now CROUCH_ANGLE
       (120, above 58) genuinely lowers the chassis and LAUNCH_ANGLE (15,
       below 58) genuinely raises it -- the push phase is a real ~59mm
       rise while the foot is still planted.
    2. The ascent used to derive its height from an independently-chosen
       JUMP_APEX_MM, with no connection to the velocity the planted-foot
       push actually produced -- simulated per-frame Z showed the chassis
       nearly stationary the frame before LAUNCH_FRAME (dz=+0.26mm) then
       "teleporting" to dz=+102.57mm the frame after, a ~390x
       discontinuity with no physical cause. The ascent now measures the
       REAL liftoff velocity (v0, two FK evaluations of the already-
       keyframed push right at the LAUNCH_FRAME boundary) and derives
       apex height/ascent time FROM that v0 (h=v0^2/2g, t=v0/g) --
       APEX_Z_MM and ascent_frames are OUTPUTS of the push's own motion,
       not independent inputs, so there is no discontinuity at liftoff.
       Descent is a separate, simpler free-fall of the resulting
       APEX_Z_MM back down to the floor-level reference (base_plate.z=0)
       -- landing keyframes CROUCH_ANGLE, not DEFAULT_HIP_ANGLE (touchdown
       is meant to look like an impact-absorbing crouch, not a stiff-
       legged landing), so lock_wheels_to_floor's second range (which
       starts at LANDING_FRAME) nudges the actual contact height a few mm
       off exactly 0 to match that pose; descent_frames uses the z=0
       reference purely for timing and is a close approximation, not
       exact, but lock_wheels_to_floor still guarantees zero clipping at
       LANDING_FRAME itself regardless.

    Phase frames below are computed at each build (from CROUCH_ANGLE/
    LAUNCH_ANGLE and the real liftoff velocity they produce), so retuning
    either angle keeps the whole timeline physically consistent instead of
    needing every downstream frame number hand-updated too:

      90-98    Touchdown settle: assembly (1-90) already ends grounded at
               z=0/58deg: a small absorb-and-recover dip sells the parts
               having just landed together as one rigid body.
      98-140   Balancing: +/-1.5deg pitch oscillation on chassis AND wheels
               (IMU self-balancing) while feet stay flat on the floor, legs
               held at the rest angle (58deg).
      140-162  Crouch: hip angle swings from 58 to CROUCH_ANGLE (120),
               genuinely lowering the chassis (anticipation, storing
               energy), chassis stays flat/level.
      162-LAUNCH_FRAME  Explosive Jump (load-and-explode spring): legs
               snap from CROUCH_ANGLE to LAUNCH_ANGLE (120->15) in a fast
               EXPO/EASE_OUT burst while the foot stays locked to the
               floor (lock_wheels_to_floor covers this window) -- the leg
               pushes the body up from the planted foot, same as a real
               spring extending against the ground, and the chassis
               genuinely rises (~59mm) doing it. A forward wheel-spin
               pulse (kf_wheel_spin) fires over the same window -- "pulse
               the wheel drive motors forward slightly to lock down the
               horizontal balance plane" per the takeoff-physics brief.
      LAUNCH_FRAME-APEX_FRAME  Ascent: legs relax back to exactly
               DEFAULT_HIP_ANGLE (58) while coasting up on the push's own
               real liftoff velocity to APEX_Z_MM -- no discontinuity at
               LAUNCH_FRAME (see above).
      APEX_FRAME-LANDING_FRAME  Descent: free-fall (approximately)
               APEX_Z_MM back down to the floor-level reference, where
               the impact-absorb crouch (CROUCH_ANGLE) touches down --
               lock_wheels_to_floor corrects the exact contact height.
      LANDING_FRAME  Landing: touchdown compression absorbs the impact
               (legs fold to CROUCH_ANGLE, not DEFAULT_HIP_ANGLE -- this
               is meant to look like a cushioning crouch), wheel-spin
               pulse relaxes back to zero.
      LANDING_FRAME-STAND_FRAME-10  Balancing: same +/-1.5deg pitch
               oscillation as 98-140, feet flat on the floor again.
      STAND_FRAME-10-STAND_FRAME  Stable stand: settle to exactly 58deg /
               z=0 / level pitch and hold -- final resting frame.

    Ends with lock_wheels_to_floor's dense correction pass, which re-derives
    base_plate's required Z every frame in the grounded ranges instead of
    trusting hand-picked anchor values to interpolate correctly in between.
    """
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base

    # Boundary frames for the two grounded ranges lock_wheels_to_floor
    # corrects -- named once here and reused at every call site below (and
    # in the lock_wheels_to_floor call itself) so retiming a phase can't
    # silently desync the correction range from the anchors it covers.
    SETTLE_START = 90
    CROUCH_END = 162

    scene = bpy.context.scene
    # Reference "floor" height: wheel-bottom world Z at the rig's static
    # built pose (hip=DEFAULT_HIP_ANGLE, base_plate.z=0). No leg-angle or
    # pitch keyframes exist yet at this point in the function, and the
    # assembly animation (already keyframed by build_exploded_view) holds
    # base_plate at its assembled position by frame 90, so evaluating here
    # gives the exact same rest-pose reference used throughout this file.
    scene.frame_set(SETTLE_START)
    bpy.context.view_layer.update()
    floor_z = min((legs['R']['wheel'].matrix_world @ Vector(c)).z
                   for c in legs['R']['wheel'].bound_box)

    # 90-98: touchdown settle right after assembly -- brief absorb-and-
    # recover beat, feet stay on the floor throughout (this just sells
    # weight settling in, it is not the main crouch). Z values here are
    # placeholders only -- lock_wheels_to_floor overwrites every frame in
    # 90-LAUNCH_FRAME with the exact FK-derived height afterward, since the
    # hip-angle FK chain's effect on wheel height doesn't interpolate
    # linearly between hand-picked anchors (see that function's docstring).
    kf_leg_angle(legs, SETTLE_START, DEFAULT_HIP_ANGLE)
    kf_loc(base_plate, SETTLE_START, (0.0, 0.0, 0.0))
    kf_leg_angle(legs, 94, DEFAULT_HIP_ANGLE - 8.0, easing='EASE_OUT')
    kf_loc(base_plate, 94, (0.0, 0.0, 0.0), easing='EASE_OUT')
    kf_leg_angle(legs, 98, DEFAULT_HIP_ANGLE)
    kf_loc(base_plate, 98, (0.0, 0.0, 0.0))

    # 98-140: IMU balance -- chassis AND wheel micro pitch oscillation,
    # legs held at the rest angle, feet flat on the floor (z=0 throughout).
    balance_oscillation(base_plate, legs, [98, 111, 124, 132, 140], [0.0, 1.5, -1.4, 1.2, 0.0])
    kf_leg_angle(legs, 140, DEFAULT_HIP_ANGLE)

    # 140-CROUCH_END: crouch -- >=20% compression off the rest angle (using
    # 34%: 58 -> 38), chassis stays flat and grounded.
    #
    # The "load"/"explode"/"ascent"/"descent" shapes below only work
    # because of two things verified empirically (issue #23 code review,
    # see set_keyframe_shape's docstring for the full explanation): (1)
    # BEZIER interpolation ignores the `easing` enum entirely, so getting
    # a real EASE_IN/EASE_OUT shape needs a real interp mode (QUAD/EXPO),
    # and (2) a keyframe's shape governs the segment LEAVING it, not
    # arriving -- so each phase's easing is set on the EARLIER keyframe of
    # its segment (frame 141 for the load into CROUCH_END, CROUCH_END for
    # the explode into LAUNCH_FRAME, etc).
    #
    # base_plate's location-Z easing/interp at frames 141/CROUCH_END/
    # LAUNCH_FRAME is intentionally left at kf_loc's BEZIER default and
    # NOT set here: all three fall inside lock_wheels_to_floor's locked
    # range below, which re-keyframes Z at every single frame in that
    # range regardless -- any shape set here would just get overwritten
    # (issue #23 code review). LAUNCH_FRAME is the one exception (it's the
    # LAST locked frame, so its shape controls the real, unlocked ascent
    # after it) -- that one is set via lock_wheels_to_floor's
    # boundary_shapes param below, not here, for the same reason.
    kf_rot_x(base_plate, 141, 0.0)
    # Load: starts slow, accelerates down into full compression over
    # 141->CROUCH_END -- reads as the spring winding up under building
    # force, not a lazy drift down.
    kf_leg_angle(legs, 141, DEFAULT_HIP_ANGLE, easing='EASE_IN', interp='QUAD')
    kf_loc(base_plate, 141, (0.0, 0.0, 0.0))
    kf_rot_x(base_plate, CROUCH_END, 0.0)
    kf_wheel_spin(legs, CROUCH_END, 0.0)

    # CROUCH_END-LAUNCH_FRAME: explosive jump -- legs stretch outward past
    # the rest angle in a spring RELEASE: EXPO/EASE_IN (set on CROUCH_END,
    # which governs this outgoing segment), near-motionless at first (the
    # leg still winding up against the planted foot) then a massive
    # velocity spike right at the very end -- deliberately the opposite of
    # EASE_OUT. A push that DEcelerates into LAUNCH_FRAME leaves the
    # chassis nearly stationary the instant it's supposed to leave the
    # ground (issue #23 code review: measured a ~390x velocity
    # discontinuity into the ascent from exactly that mistake) -- real
    # liftoff needs maximum velocity AT the moment of separation, which
    # means ACcelerating through the whole push, not decelerating into it.
    # lock_wheels_to_floor's range now extends through LAUNCH_FRAME, so the
    # foot stays planted while the leg pushes the body up (load-and-explode
    # spring), instead of the body sitting still while the foot floats
    # free. Wheel-drive forward pulse fires over the same window (takeoff-
    # physics brief point 2: lock down the horizontal balance plane during
    # launch).
    kf_leg_angle(legs, CROUCH_END, CROUCH_ANGLE, easing='EASE_IN', interp='EXPO')
    kf_loc(base_plate, CROUCH_END, (0.0, 0.0, 0.0))
    # LAUNCH_FRAME's rotation easing governs the leg's outgoing ascent
    # shape directly (EASE_OUT/QUAD, a physically-plausible decelerating
    # rise); its Z-location shape for the same segment is set via
    # lock_wheels_to_floor's boundary_shapes below instead, since this
    # kf_loc call's own shape would otherwise be overwritten there anyway.
    kf_leg_angle(legs, LAUNCH_FRAME, LAUNCH_ANGLE, easing='EASE_OUT', interp='QUAD')
    kf_loc(base_plate, LAUNCH_FRAME, (0.0, 0.0, 0.0))
    kf_wheel_spin(legs, LAUNCH_FRAME, 18.0)

    # Velocity continuity at liftoff (issue #23 code review): the ascent
    # must start with the SAME vertical velocity the planted-foot push
    # actually ends with, not an independently-chosen apex height's
    # implied v0 -- otherwise the chassis is nearly stationary the frame
    # before LAUNCH_FRAME and "teleports" into a large upward velocity the
    # frame after (previously measured: dz=+0.26mm going in, +102.57mm mm
    # coming out, a ~390x discontinuity). Measured here from two real FK
    # evaluations of the already-keyframed crouch/push curve (base_plate.z
    # temporarily overridden to 0 for each, matching floor_z's own
    # measurement convention), not assumed.
    def locked_z_mm(frame):
        scene.frame_set(frame)
        base_plate.location.z = 0.0
        bpy.context.view_layer.update()
        offset = min((legs['R']['wheel'].matrix_world @ Vector(c)).z
                      for c in legs['R']['wheel'].bound_box)
        return (floor_z - offset) / MM

    launch_z_mm = locked_z_mm(LAUNCH_FRAME)
    prelaunch_z_mm = locked_z_mm(LAUNCH_FRAME - 1)
    v0_mm_per_frame = launch_z_mm - prelaunch_z_mm
    v0 = (v0_mm_per_frame * MM) * fps  # m/s, real liftoff velocity
    assert v0 > 0, (
        f"liftoff velocity ({v0:.3f} m/s) must be positive -- the planted-"
        "foot push isn't still rising the frame it leaves the ground"
    )
    apex_gain_mm = (v0 * v0) / (2.0 * GRAVITY) / MM  # height climbed under pure momentum
    APEX_Z_MM = launch_z_mm + apex_gain_mm
    ascent_frames = round((v0 / GRAVITY) * fps)  # time to decelerate v0 -> 0
    descent_frames = round(math.sqrt(2.0 * (APEX_Z_MM * MM) / GRAVITY) * fps)
    APEX_FRAME = LAUNCH_FRAME + ascent_frames
    LANDING_FRAME = APEX_FRAME + descent_frames
    STAND_FRAME = LANDING_FRAME + 40  # matches the original 205->245 spacing

    # LAUNCH_FRAME-APEX_FRAME: ascent -- legs relax back to exactly the
    # rest angle (the only pose used while off the ground) while coasting
    # up on pure liftoff momentum (v0, measured above) to APEX_Z_MM. Frame
    # count and height are both derived from that same real v0 -- not
    # independent inputs -- so there's no discontinuity at LAUNCH_FRAME;
    # the decelerating shape itself is set on LAUNCH_FRAME above (the
    # keyframe governing this segment), not here.
    kf_leg_angle(legs, APEX_FRAME, DEFAULT_HIP_ANGLE)
    # APEX_FRAME's own easing governs the NEXT segment (APEX_FRAME->
    # LANDING_FRAME, the descent) -- EASE_IN/QUAD for an accelerating fall,
    # matching real gravity, set here rather than on LANDING_FRAME.
    kf_loc(base_plate, APEX_FRAME, (0.0, 0.0, APEX_Z_MM), easing='EASE_IN', interp='QUAD')
    kf_rot_x(base_plate, APEX_FRAME, -1.0)

    # APEX_FRAME-LANDING_FRAME: descent -- free-fall the full APEX_Z_MM
    # back down to floor level (base_plate.z=0), accelerating in (QUAD/
    # EASE_IN, matching gravity) rather than BEZIER's symmetric ease.
    # Touchdown compression absorbs the impact and the wheel-spin pulse
    # relaxes back to zero.
    kf_loc(base_plate, LANDING_FRAME, (0.0, 0.0, 0.0), easing='EASE_IN', interp='QUAD')
    kf_rot_x(base_plate, LANDING_FRAME, 0.0)
    kf_leg_angle(legs, LANDING_FRAME, CROUCH_ANGLE, easing='EASE_IN_OUT')
    kf_wheel_spin(legs, LANDING_FRAME, 0.0, easing='EASE_IN')

    # LANDING_FRAME-STAND_FRAME-10: balance again, feet flat on the floor.
    balance2_start = LANDING_FRAME + 5
    kf_loc(base_plate, balance2_start, (0.0, 0.0, 0.0), easing='EASE_IN_OUT')
    kf_leg_angle(legs, balance2_start, DEFAULT_HIP_ANGLE)
    balance2_frames = [balance2_start + off for off in (0, 8, 16, 21, 25)]
    balance_oscillation(base_plate, legs, balance2_frames, [0.0, 1.3, -1.2, 0.8, 0.0])
    kf_leg_angle(legs, balance2_frames[-1], DEFAULT_HIP_ANGLE)

    # STAND_FRAME-10-STAND_FRAME: stable stand -- exact rest pose, held.
    kf_loc(base_plate, STAND_FRAME, (0.0, 0.0, 0.0), easing='EASE_IN_OUT')
    kf_rot_x(base_plate, STAND_FRAME, 0.0)
    kf_leg_angle(legs, STAND_FRAME, DEFAULT_HIP_ANGLE)
    kf_wheel_pitch(legs, STAND_FRAME, 0.0)

    # boundary_shapes preserves the explosive-ascent shape on LAUNCH_FRAME:
    # it's the last frame of the first locked range, so without this its Z
    # keyframe's interp/easing would get silently reset to plain BEZIER by
    # the dense correction loop, and the real (unlocked) ascent right after
    # it would fall back to a symmetric bell curve instead of decelerating
    # (issue #23 code review).
    lock_wheels_to_floor(
        base_plate, legs, floor_z,
        [(SETTLE_START, LAUNCH_FRAME), (LANDING_FRAME, STAND_FRAME)],
        boundary_shapes={LAUNCH_FRAME: ('QUAD', 'EASE_OUT')},
    )
    return STAND_FRAME


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------

def main():
    clear_previous()
    collection = new_collection()

    base_plate = build_base_plate(collection)

    standoffs = []
    for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        so = build_standoff(f"DWLRP_Standoff_{i}", collection)
        so.location = mm(sx * (BASE_W / 2 - 10), sy * (BASE_L / 2 - 10), BASE_T / 2 + STANDOFF_H / 2)
        so.parent = base_plate
        standoffs.append(so)

    battery = build_battery(collection)
    battery.location = mm(0.0, 0.0, BASE_T / 2 + BATTERY_T / 2 + 1.0)
    battery.parent = base_plate

    deck = build_deck_plate(collection)
    deck_z = BASE_T / 2 + STANDOFF_H + DECK_T / 2
    deck.location = mm(0.0, 0.0, deck_z)
    deck.parent = base_plate

    atom = build_atom_s3(collection)
    atom.location = mm(0.0, 0.0, deck_z + DECK_T / 2 + ATOM_H / 2)
    atom.parent = base_plate

    rear_ext = build_rear_extension(collection)
    rear_ext.location = mm(0.0, -BASE_L / 2 - REAR_EXT_T / 2, BASE_T / 2)
    rear_ext.parent = base_plate

    legs = {
        'R': build_leg('R', collection, base_plate),
        'L': build_leg('L', collection, base_plate),
    }

    build_exploded_view(base_plate, standoffs, deck, battery, atom, rear_ext, legs)
    stand_frame = build_balance_and_jump(base_plate, legs)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = stand_frame
    scene.frame_set(1)

    print("Dual-Wheel Legged Balancing Robot (precise) build complete.")
    print(f"Objects created: {len(collection.objects)}")

    if bpy.app.background:
        # Headless (render pipeline) run -- persist the build per the
        # model_<subject>.py contract in DESIGN.md. Skipped when run live via
        # run_blender_python_live so it never hijacks the GUI session's own
        # open file.
        bpy.ops.wm.save_as_mainfile(
            filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/model_dual_wheel_legged_robot_precise.blend",
            check_existing=False,
        )


main()
