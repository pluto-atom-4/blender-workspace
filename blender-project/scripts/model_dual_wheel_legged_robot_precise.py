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
     balance/stand (90-245)
  7. Main
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 1. Units / cleanup / materials
# ---------------------------------------------------------------------------

MM = 0.001  # 1mm in Blender meters


def mm(*vals):
    if len(vals) == 1:
        return vals[0] * MM
    return tuple(v * MM for v in vals)


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
# 2. Mesh primitives with explicit pivot control (bmesh, real mm dims)
# ---------------------------------------------------------------------------

def _link(obj, collection):
    collection.objects.link(obj)
    return obj


def apply_transforms(obj):
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)


def shade_flat(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = False


def make_box(name, collection, size_mm, pivot_mm=(0.0, 0.0, 0.0), location_mm=(0.0, 0.0, 0.0), material=None):
    """Box of size_mm (x,y,z), local origin offset by pivot_mm from geometric center.
    Scale is baked via bmesh construction directly, then transform_apply is
    still called right after creation (location=False) so any future
    rotation/scale edits on THIS object start from a clean identity basis --
    satisfies the "apply transforms right after creating each plate" brief."""
    sx, sy, sz = mm(*size_mm)
    px, py, pz = mm(*pivot_mm)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = v.co.x * sx - px
        v.co.y = v.co.y * sy - py
        v.co.z = v.co.z * sz - pz
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj, collection)
    obj.location = mm(*location_mm)
    shade_flat(obj)
    apply_transforms(obj)
    if material is not None:
        assign_material(obj, material)
    return obj


AXIS_ROT = {
    'Z': None,
    'X': Matrix.Rotation(math.radians(90), 3, 'Y'),
    'Y': Matrix.Rotation(math.radians(90), 3, 'X'),
}


def make_cylinder(name, collection, radius_mm, depth_mm, axis='Z', segments=32,
                   pivot_mm=(0.0, 0.0, 0.0), location_mm=(0.0, 0.0, 0.0), cap=True, material=None):
    r = mm(radius_mm)
    d = mm(depth_mm)
    px, py, pz = mm(*pivot_mm)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments,
                           radius1=r, radius2=r, depth=d)
    rot = AXIS_ROT.get(axis)
    if rot is not None:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=rot)
    for v in bm.verts:
        v.co.x -= px
        v.co.y -= py
        v.co.z -= pz
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj, collection)
    obj.location = mm(*location_mm)
    shade_flat(obj)
    apply_transforms(obj)
    if material is not None:
        assign_material(obj, material)
    return obj


def merge_cutters(name, collection, cutter_specs):
    """cutter_specs: list of dicts {type:'box'|'cyl', size/radius/depth/axis, location(local mm)}.
    Builds ONE combined mesh so a single boolean modifier removes all of them."""
    bm = bmesh.new()
    for spec in cutter_specs:
        sub = bmesh.new()
        if spec['type'] == 'box':
            sx, sy, sz = mm(*spec['size'])
            bmesh.ops.create_cube(sub, size=1.0)
            for v in sub.verts:
                v.co.x *= sx
                v.co.y *= sy
                v.co.z *= sz
        else:
            r = mm(spec['radius'])
            d = mm(spec['depth'])
            bmesh.ops.create_cone(sub, cap_ends=True, cap_tris=False, segments=spec.get('segments', 24),
                                   radius1=r, radius2=r, depth=d)
            rot = AXIS_ROT.get(spec.get('axis', 'Z'))
            if rot is not None:
                bmesh.ops.rotate(sub, verts=sub.verts, cent=(0, 0, 0), matrix=rot)
        lx, ly, lz = mm(*spec['location'])
        for v in sub.verts:
            v.co.x += lx
            v.co.y += ly
            v.co.z += lz
        tmp_mesh = bpy.data.meshes.new("tmp_cutter")
        sub.to_mesh(tmp_mesh)
        sub.free()
        bm.from_mesh(tmp_mesh)
        bpy.data.meshes.remove(tmp_mesh)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj, collection)
    return obj


def boolean_diff_apply(target, cutter_obj):
    mod = target.modifiers.new(name="Cut", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter_obj
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mesh_data = cutter_obj.data
    bpy.data.objects.remove(cutter_obj, do_unlink=True)
    if mesh_data.users == 0:
        bpy.data.meshes.remove(mesh_data)
    shade_flat(target)


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
        'knee_knuckle': knee_knuckle, 'lower_plate': lower_plate,
        'ankle_block': ankle_block, 'wheel_servo': wheel_servo, 'wheel': wheel,
        'hip_world': hip_world,
    }


# ---------------------------------------------------------------------------
# 6. Animation
# ---------------------------------------------------------------------------

def set_ease(obj, easing='EASE_IN_OUT'):
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = easing


def animate_assembly(obj, assembled_loc_mm, explode_dir_mm, seat_frame=45, hold_frame=90):
    """Frame 1: exploded. seat_frame: seated. Holds static through hold_frame."""
    assembled = Vector(mm(*assembled_loc_mm))
    exploded = assembled + Vector(mm(*explode_dir_mm))

    obj.location = exploded
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location = assembled
    obj.keyframe_insert(data_path="location", frame=seat_frame)
    obj.keyframe_insert(data_path="location", frame=hold_frame)
    set_ease(obj, 'EASE_OUT')


def mm_inv(vec):
    return (vec.x / MM, vec.y / MM, vec.z / MM)


def kf_loc(obj, frame, loc_mm, interp='BEZIER', easing='EASE_IN_OUT'):
    obj.location = Vector(mm(*loc_mm))
    obj.keyframe_insert(data_path="location", frame=frame)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == "location":
                kp = fc.keyframe_points[-1]
                kp.interpolation = interp
                kp.easing = easing


def kf_rot_x(obj, frame, deg, interp='BEZIER', easing='EASE_IN_OUT'):
    obj.rotation_euler.x = math.radians(deg)
    obj.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == "rotation_euler" and fc.array_index == 0:
                kp = fc.keyframe_points[-1]
                kp.interpolation = interp
                kp.easing = easing


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


def kf_leg_angle(legs, frame, angle_deg, easing='EASE_IN_OUT'):
    """Drive the forked upper plates (rigid doubled pair) to the hip angle,
    and counter-rotate the knee knuckle by the same amount so the lower
    plate/ankle/wheel subtree it carries never accumulates net rotation --
    the wheel stays level through the full range of motion with only the
    hip actuated, same as the parallelogram coupler this replaced. Also
    drives hip_servo to the same angle -- its rotation_euler.x IS the joint
    axis (see build_servo's docstring), so without this the servo body and
    its horn bracket would stay frozen at the static build pose while the
    plates it's bolted to sweep away from it."""
    for leg in legs.values():
        kf_rot_x(leg['hip_servo'], frame, angle_deg, easing=easing)
        kf_rot_x(leg['upper_plate_front'], frame, angle_deg, easing=easing)
        kf_rot_x(leg['upper_plate_back'], frame, angle_deg, easing=easing)
        kf_rot_x(leg['knee_knuckle'], frame, -angle_deg, easing=easing)


def kf_wheel_pitch(legs, frame, deg, easing='EASE_IN_OUT'):
    for leg in legs.values():
        kf_rot_x(leg['wheel_servo'], frame, deg, easing=easing)


def balance_oscillation(base_plate, legs, frames, pitches):
    """IMU self-balance wobble: chassis pitch plus a 0.6x-coupled wheel
    counter-tilt, at the given (frame, degrees) pairs. Shared by both
    balance windows (98-140 pre-jump, 205-235 post-landing) so they can't
    silently diverge in behavior."""
    for f, p in zip(frames, pitches):
        kf_rot_x(base_plate, f, p)
        kf_wheel_pitch(legs, f, p * 0.6)


def build_balance_and_jump(base_plate, legs):
    """Rebuilt from scratch per the assemble->stand->jump spec (issue #23
    follow-up): every leg pose is DEFAULT_HIP_ANGLE=58deg plus or minus an
    explicit delta off it -- no other absolute angle is invented -- and the
    model's feet are on the floor (base_plate.z == 0) at both ends of the
    clip, only leaving the ground for the single jump arc in the middle:

      90-98   Touchdown settle: assembly (1-90) already ends grounded at
              z=0/58deg: a small absorb-and-recover dip sells the parts
              having just landed together as one rigid body.
      98-140  Balancing: +/-1.5deg pitch oscillation on chassis AND wheels
              (IMU self-balancing) while feet stay flat on the floor, legs
              held at the rest angle (58deg).
      140-162 Crouch: hip angle compresses >=20% off 58deg (58->38, a 34%
              reduction) as anticipation, chassis stays flat/level.
      162-172 Explosive Jump: legs stretch outward past the rest angle
              (58+70=128deg) in a fast EASE_OUT snap, launching the model
              off the floor.
      172-190 Airborne: legs relax back to exactly DEFAULT_HIP_ANGLE (58)
              while the model rides the parabolic Z path to apex -- the
              only pose used while airborne is the rest angle itself.
      190-205 Landing: fall back to z=0, touchdown compression to absorb
              the impact.
      205-235 Balancing: same +/-1.5deg pitch oscillation as 98-140, feet
              flat on the floor again.
      235-245 Stable stand: settle to exactly 58deg / z=0 / level pitch
              and hold -- final resting frame.

    Ends with lock_wheels_to_floor's dense correction pass, which re-derives
    base_plate's required Z every frame in the grounded ranges instead of
    trusting hand-picked anchor values to interpolate correctly in between.
    """
    # Boundary frames for the two grounded ranges lock_wheels_to_floor
    # corrects -- named once here and reused at every call site below (and
    # in the lock_wheels_to_floor call itself) so retiming a phase can't
    # silently desync the correction range from the anchors it covers.
    SETTLE_START = 90
    CROUCH_END = 162
    LANDING_FRAME = 205
    STAND_FRAME = 245

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
    # 90-162 with the exact FK-derived height afterward, since the
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
    # 34%: 58 -> 38), chassis stays flat and grounded. z=0.0 here is a
    # placeholder -- lock_wheels_to_floor overwrites it (and every frame in
    # between) with the FK-derived height needed to keep the wheel bottomed
    # out on the floor instead of sinking through it.
    CROUCH_ANGLE = DEFAULT_HIP_ANGLE - 20.0  # 58 -> 38, a 34% reduction
    kf_rot_x(base_plate, 141, 0.0)
    kf_leg_angle(legs, 141, DEFAULT_HIP_ANGLE)
    kf_loc(base_plate, 141, (0.0, 0.0, 0.0))
    kf_rot_x(base_plate, CROUCH_END, 0.0)
    kf_leg_angle(legs, CROUCH_END, CROUCH_ANGLE, easing='EASE_IN_OUT')
    kf_loc(base_plate, CROUCH_END, (0.0, 0.0, 0.0), easing='EASE_IN_OUT')

    # CROUCH_END-172: explosive jump -- legs stretch outward past the rest
    # angle in a hard EASE_OUT snap, model leaves the floor on a parabolic
    # Z path.
    kf_leg_angle(legs, 168, DEFAULT_HIP_ANGLE + 70.0, easing='EASE_OUT')
    kf_loc(base_plate, 168, (0.0, 0.0, 30.0), easing='EASE_OUT')

    # 172-190: airborne -- legs relax back to exactly the rest angle (the
    # only pose used while off the ground) while rising to apex.
    kf_leg_angle(legs, 180, DEFAULT_HIP_ANGLE, easing='EASE_IN_OUT')
    kf_loc(base_plate, 180, (0.0, 0.0, 95.0), easing='EASE_OUT')  # apex
    kf_rot_x(base_plate, 180, -1.0)

    # 190-LANDING_FRAME: landing -- fall back to the floor, touchdown
    # compression absorbs the impact.
    kf_loc(base_plate, 190, (0.0, 0.0, 20.0), easing='EASE_IN')
    kf_rot_x(base_plate, 190, 0.0)
    kf_leg_angle(legs, 190, DEFAULT_HIP_ANGLE, easing='EASE_IN_OUT')

    # impact absorb -- legs fold back to CROUCH_ANGLE on touchdown. z=0.0
    # is a placeholder, overwritten by lock_wheels_to_floor (LANDING_FRAME-
    # STAND_FRAME range) same as the crouch above.
    kf_loc(base_plate, LANDING_FRAME, (0.0, 0.0, 0.0), easing='EASE_IN_OUT')
    kf_leg_angle(legs, LANDING_FRAME, CROUCH_ANGLE, easing='EASE_IN_OUT')

    # LANDING_FRAME-235: balance again, feet flat on the floor.
    kf_loc(base_plate, 210, (0.0, 0.0, 0.0), easing='EASE_IN_OUT')
    kf_leg_angle(legs, 210, DEFAULT_HIP_ANGLE)
    balance_oscillation(base_plate, legs, [210, 218, 226, 231, 235], [0.0, 1.3, -1.2, 0.8, 0.0])
    kf_leg_angle(legs, 235, DEFAULT_HIP_ANGLE)

    # 235-STAND_FRAME: stable stand -- exact rest pose, held.
    kf_loc(base_plate, STAND_FRAME, (0.0, 0.0, 0.0), easing='EASE_IN_OUT')
    kf_rot_x(base_plate, STAND_FRAME, 0.0)
    kf_leg_angle(legs, STAND_FRAME, DEFAULT_HIP_ANGLE)
    kf_wheel_pitch(legs, STAND_FRAME, 0.0)

    lock_wheels_to_floor(base_plate, legs, floor_z, [(SETTLE_START, CROUCH_END), (LANDING_FRAME, STAND_FRAME)])


def lock_wheels_to_floor(base_plate, legs, floor_z, frame_ranges):
    """Densely re-keyframes base_plate's Z (every frame, in the given
    ranges only) so the wheel bottom sits exactly at floor_z throughout --
    not just at the hand-authored anchor frames above. The hip-angle FK
    chain's contribution to wheel height is a nonlinear function of the
    (already smoothly-keyframed) hip angle and chassis pitch, so bezier
    interpolation between two *correct* anchor keyframes still drifts a
    few mm off the floor at frames in between (measured up to -4.9mm mid-
    crouch-ramp) -- sampling every frame removes that gap instead of
    guessing more anchor points. Only applied to the two ranges that are
    meant to stay grounded; the 162-205 jump/airborne arc is deliberately
    excluded since it's supposed to leave the floor.

    Correction is derived from the R wheel only and applied to both (via
    base_plate.z, shared by the whole chassis) -- correct as long as
    kf_leg_angle always drives L and R to the identical angle, which it
    does throughout this file. Asserted every sampled frame rather than
    assumed, so a future asymmetric gait change (turning, per-leg balance
    correction) fails loudly here instead of silently floating/sinking L.

    This is a one-shot bake computed from the pose at script-build time --
    if a live session (run_blender_python_live) re-keyframes a leg angle
    inside these ranges afterward, this correction does NOT get re-run and
    the bake goes stale for that frame. Re-run the whole model script (or
    call this function again) after any such live edit.
    """
    scene = bpy.context.scene
    wheel_r = legs['R']['wheel']
    wheel_l = legs['L']['wheel']
    for start, end in frame_ranges:
        for f in range(start, end + 1):
            scene.frame_set(f)
            base_plate.location.z = 0.0
            bpy.context.view_layer.update()
            offset_r = min((wheel_r.matrix_world @ Vector(c)).z for c in wheel_r.bound_box)
            offset_l = min((wheel_l.matrix_world @ Vector(c)).z for c in wheel_l.bound_box)
            assert abs(offset_l - offset_r) < 0.001, (
                f"frame {f}: L/R wheel-bottom offsets diverged "
                f"({offset_l:.5f} vs {offset_r:.5f}) -- lock_wheels_to_floor "
                "assumes symmetric legs and only corrects against R"
            )
            needed_z_mm = (floor_z - offset_r) / MM
            kf_loc(base_plate, f, (0.0, 0.0, needed_z_mm), easing='EASE_IN_OUT')


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
    build_balance_and_jump(base_plate, legs)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 245
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
