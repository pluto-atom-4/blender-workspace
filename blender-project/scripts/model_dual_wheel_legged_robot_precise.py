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
  6. Animation: exploded assembly (1-90), balance/crouch/jump/land (91-210)
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


def build_servo(name, collection):
    """Built in its mounted orientation: output-spline axis (= joint hinge
    axis) is local X, object origin at the spline's rotation center. Caller
    animates rotation_euler.x directly as the joint angle -- no post-hoc
    object rotation is ever applied, so parented children can't desync."""
    pivot = (SERVO_H / 2, SPLINE_OFFSET_Y, 0.0)
    body = make_box(name + "_Body", collection, (SERVO_H, SERVO_L, SERVO_W), pivot_mm=pivot, material=MAT_BLACK())
    spline = make_cylinder(name + "_Spline", collection, SPLINE_R, SPLINE_H, axis='X',
                            location_mm=(SPLINE_H / 2, 0.0, 0.0), material=MAT_METAL())
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
# 5. Assembly: sandwich stack + parallelogram 4-bar leg FK chain
#
#    Chassis stack: BasePlate -> Standoffs / RearExtension / (Deck -> Atom S3)
#    Leg (per side): RearExtension -> LinkA (driven, hip-servo) -> AnkleBlock
#                                   -> WheelServo(inverted) -> WheelHub
#                     RearExtension -> LinkB (parallel follower, same length)
#
#    True parallelogram: LinkA and LinkB share the same length (LINK_LEN)
#    and the same pivot separation (LINK_SEP) at both the chassis end (hip
#    pivots A/B) and the coupler end (AnkleBlock's two attachment points).
#    Both links are keyframed to IDENTICAL rotation_euler.x at every frame,
#    which is what actually guarantees the parallelogram condition -- this
#    is deterministic FK rather than a live constraint solve, following the
#    same lesson as the base script: Blender's runtime constraint solving
#    was unreliable for the leg IK there, so joint motion here is likewise
#    authored directly as keyframed angles. AnkleBlock (the coupler) is then
#    counter-rotated by -angle relative to LinkA so it never rotates in the
#    world frame -- exactly the "constant relative angle" a parallelogram
#    coupler exhibits.
# ---------------------------------------------------------------------------

LINK_LEN = 60.0
LINK_SEP = 20.0
HIP_LATERAL = 50.0  # wheel centers 2*HIP_LATERAL=100mm apart; WHEEL_R=40mm needs
                     # >=80mm to just touch, so this leaves a 20mm clearance gap
HIP_A_Z = 20.0     # height of the driven (upper) pivot above the base plate
ANKLE_DROP = 10.0  # ankle block center below LinkA's tail (coupler offset)
WHEEL_TILT_DEG = 10.0  # ankle-servo forward tilt, inline with the linkage path


def build_leg(side, collection, base_plate, rear_ext):
    sign = 1.0 if side == 'R' else -1.0
    tag = f"DWLRP_{side}"

    hip_a_world = (sign * HIP_LATERAL, -BASE_L / 2 - REAR_EXT_T, HIP_A_Z)
    hip_b_world = (hip_a_world[0], hip_a_world[1], HIP_A_Z - LINK_SEP)

    # Hip servo: mounted horizontally under the rear deck, its output spline
    # coincides with the upper (driven) pivot axis -- the servo horn bracket
    # is the visual link from servo body to LinkA's pivot.
    hip_servo = build_servo(f"{tag}_HipServo", collection)
    hip_servo.location = mm(*hip_a_world)
    hip_servo.parent = base_plate
    horn = build_servo_horn_bracket(collection, tag, sign)
    horn.parent = hip_servo

    hip_knuckle_a = build_knuckle(f"{tag}_HipKnuckleA", collection, location_mm=hip_a_world)
    hip_knuckle_a.parent = base_plate
    hip_knuckle_b = build_knuckle(f"{tag}_HipKnuckleB", collection, location_mm=hip_b_world)
    hip_knuckle_b.parent = base_plate

    link_a = build_link_bar(f"{tag}_LinkA", collection, LINK_LEN)
    link_a.location = mm(*hip_a_world)
    link_a.parent = base_plate

    link_b = build_link_bar(f"{tag}_LinkB", collection, LINK_LEN)
    link_b.location = mm(*hip_b_world)
    link_b.parent = base_plate

    ankle_block = build_ankle_block(f"{tag}_AnkleBlock", collection)
    ankle_block.location = (0.0, 0.0, mm(-LINK_LEN))
    ankle_block.parent = link_a

    ankle_knuckle = build_knuckle(f"{tag}_AnkleKnuckle", collection,
                                   location_mm=(0.0, 0.0, -LINK_SEP))
    ankle_knuckle.parent = ankle_block

    wheel_servo = build_servo(f"{tag}_WheelServo", collection)
    wheel_servo.location = (0.0, 0.0, mm(-ANKLE_DROP))
    wheel_servo.rotation_euler = (0.0, math.radians(WHEEL_TILT_DEG), 0.0)
    wheel_servo.parent = ankle_block

    wheel = build_wheel(f"{tag}_WheelHub", collection)
    wheel.location = (0.0, 0.0, 0.0)
    wheel.parent = wheel_servo

    return {
        'hip_servo': hip_servo, 'horn': horn, 'link_a': link_a, 'link_b': link_b,
        'ankle_block': ankle_block, 'wheel_servo': wheel_servo, 'wheel': wheel,
        'hip_a_world': hip_a_world, 'hip_b_world': hip_b_world,
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
        animate_assembly(leg['link_a'], mm_inv(leg['link_a'].location), (sign * 45.0, 0.0, 10.0), seat_frame=60)
        animate_assembly(leg['link_b'], mm_inv(leg['link_b'].location), (sign * 45.0, 0.0, -10.0), seat_frame=63)
        animate_assembly(leg['ankle_block'], mm_inv(leg['ankle_block'].location), (sign * 20.0, 0.0, -20.0), seat_frame=72)
        animate_assembly(leg['wheel_servo'], mm_inv(leg['wheel_servo'].location), (0.0, 0.0, -15.0), seat_frame=78)
        animate_assembly(leg['wheel'], mm_inv(leg['wheel'].location), (sign * 35.0, 0.0, 0.0), seat_frame=85)


def kf_leg_angle(legs, frame, angle_deg, easing='EASE_IN_OUT'):
    """Drive both parallelogram links to the SAME angle (parallel condition)
    and counter-rotate the ankle block (coupler) so it stays level -- this
    is what makes the 4-bar behave as a true parallelogram linkage."""
    for leg in legs.values():
        kf_rot_x(leg['link_a'], frame, angle_deg, easing=easing)
        kf_rot_x(leg['link_b'], frame, angle_deg, easing=easing)
        kf_rot_x(leg['ankle_block'], frame, -angle_deg, easing=easing)


def kf_wheel_pitch(legs, frame, deg, easing='EASE_IN_OUT'):
    for leg in legs.values():
        kf_rot_x(leg['wheel_servo'], frame, deg, easing=easing)


def build_balance_and_jump(base_plate, legs):
    """91-140 balance, 141-160 crouch, 161-175 explosive jump,
    176-210 airborne/landing/resume-balance."""

    # 91-140: IMU balance -- chassis AND wheel micro pitch oscillation,
    # legs stay at neutral extension.
    osc_frames = [91, 103, 116, 128, 140]
    osc_pitch = [0.0, 1.5, -1.4, 1.2, 0.0]
    for f, p in zip(osc_frames, osc_pitch):
        kf_rot_x(base_plate, f, p)
        kf_wheel_pitch(legs, f, p * 0.6)
    kf_leg_angle(legs, 91, 0.0)
    kf_leg_angle(legs, 140, 0.0)

    # 141-160: crouch -- 4-bar compresses tightly, chassis stays flat.
    kf_rot_x(base_plate, 141, 0.0)
    kf_leg_angle(legs, 141, 0.0)
    kf_rot_x(base_plate, 160, 0.0)
    kf_leg_angle(legs, 160, -35.0, easing='EASE_IN')
    kf_loc(base_plate, 141, (0.0, 0.0, 0.0))
    kf_loc(base_plate, 160, (0.0, 0.0, -22.0), easing='EASE_IN')

    # 161-175: explosive jump -- linkages snap outward, model launches up.
    kf_leg_angle(legs, 168, 15.0, easing='EASE_OUT')
    kf_loc(base_plate, 168, (0.0, 0.0, 25.0), easing='EASE_OUT')
    kf_leg_angle(legs, 175, -10.0)
    kf_loc(base_plate, 175, (0.0, 0.0, 80.0), easing='EASE_OUT')

    # 176-210: peak -> fall -> touchdown compress -> resume balance.
    kf_loc(base_plate, 190, (0.0, 0.0, 95.0), easing='EASE_OUT')  # apex
    kf_rot_x(base_plate, 190, -1.0)
    kf_leg_angle(legs, 190, -20.0)

    kf_loc(base_plate, 200, (0.0, 0.0, 0.0), easing='EASE_IN')
    kf_rot_x(base_plate, 200, 0.0)
    kf_leg_angle(legs, 200, 5.0, easing='EASE_IN')  # extend for landing

    kf_loc(base_plate, 205, (0.0, 0.0, -18.0), easing='EASE_IN')  # impact absorb
    kf_leg_angle(legs, 205, -30.0, easing='EASE_IN')

    kf_loc(base_plate, 210, (0.0, 0.0, 0.0))
    kf_rot_x(base_plate, 210, 0.0)
    kf_leg_angle(legs, 210, 0.0)
    kf_wheel_pitch(legs, 210, 0.0)


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
        'R': build_leg('R', collection, base_plate, rear_ext),
        'L': build_leg('L', collection, base_plate, rear_ext),
    }

    build_exploded_view(base_plate, standoffs, deck, battery, atom, rear_ext, legs)
    build_balance_and_jump(base_plate, legs)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 210
    scene.frame_set(1)

    print("Dual-Wheel Legged Balancing Robot (precise) build complete.")
    print(f"Objects created: {len(collection.objects)}")


main()
