"""
Upper Leg Assembly Model -- Standalone 9-part linkage with wheel actuation (issue #104)

A fully standalone upper leg assembly with dual-shear construction:
  - Hip servo (STS3032) drives the Drive Rod via servo spline
  - Drive Rod (driven): upper link, dual-shear construction
  - Thigh Rod1 (passive): lower link, dual-shear construction
  - Crus Side Rod: rigid brace connecting Drive Rod to Thigh Rod1 (35mm)
  - Knee Rod: coupler/pivot at the knee junction
  - Calf Rod1/Calf Rod2: paired dual-plate segment from knee to wheel axle (25mm)
  - Damping Spring: between knee rod and calf rod (PEA pattern placeholder)
  - Wheel hub motor: STS3032 servo (actuates the wheel)
  - Wheel: treaded cylinder driven by wheel-hub motor

Sweep range: 15°–120°. Default rest pose: 58°.

This is a standalone implementation (no imports from other model scripts) per issue #104
specifications. All dual-shear joints, spring geometry, and servo dimensions are
self-contained.

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (box, cylinder)
  3. Component builders (servo, dual-shear link, spring, knee rod, crus rod, wheel hub motor, wheel)
  4. Assembly: servo + upper/lower links + crus rod + knee rod + calf rods + spring + wheel motor + wheel
  5. Animation: keyframes at 15°, 58°, 120° for validation
  6. Main
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 1. Units / cleanup / materials
# ---------------------------------------------------------------------------

COLLECTION_NAME = "UpperLegAssembly"
PREFIX = "ULA_"
MM = 0.001  # 1mm in Blender meters


def mm(*vals):
    """Convert mm to Blender meters."""
    if len(vals) == 1:
        return vals[0] * MM
    return tuple(v * MM for v in vals)


def mm_inv(vec):
    """Convert Blender meters back to mm."""
    return (vec.x / MM, vec.y / MM, vec.z / MM)


def clear_previous():
    """Remove all objects and meshes from the previous build."""
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
    """Create a new Blender collection for this assembly."""
    coll = bpy.data.collections.new(COLLECTION_NAME)
    bpy.context.scene.collection.children.link(coll)
    return coll


_MAT_CACHE = {}


def get_material(name, rgba):
    """Get or create a material with given RGBA color."""
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


MAT_PLATE = lambda: get_material("Plate", (0.05, 0.05, 0.055, 1.0))       # black CNC plate
MAT_METAL = lambda: get_material("Metal", (0.5, 0.5, 0.55, 1.0))          # pivots, bolts, servo
MAT_BLACK = lambda: get_material("Black", (0.015, 0.015, 0.018, 1.0))     # wheel tire
MAT_SPRING = lambda: get_material("Spring", (0.6, 0.6, 0.65, 1.0))        # spring (metallic)


def assign_material(obj, mat):
    """Assign a material to an object."""
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# 2. Mesh primitives
# ---------------------------------------------------------------------------

AXIS_ROT = {
    'Z': None,
    'X': Matrix.Rotation(math.radians(90), 3, 'Y'),
    'Y': Matrix.Rotation(math.radians(90), 3, 'X'),
}


def _link(obj, collection):
    """Link an object to a collection."""
    collection.objects.link(obj)
    return obj


def apply_transforms(obj):
    """Apply rotation and scale transforms to an object."""
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)


def shade_flat(obj):
    """Shade an object flat."""
    for poly in obj.data.polygons:
        poly.use_smooth = False


def make_box(name, collection, size_mm, pivot_mm=(0.0, 0.0, 0.0),
             location_mm=(0.0, 0.0, 0.0), material=None):
    """
    Box of size_mm (x,y,z), local origin offset by pivot_mm from geometric center.
    """
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


def make_cylinder(name, collection, radius_mm, depth_mm, axis='Z', segments=32,
                   pivot_mm=(0.0, 0.0, 0.0), location_mm=(0.0, 0.0, 0.0),
                   cap=True, material=None):
    """
    Cylinder with given radius and depth along specified axis.
    """
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


# ---------------------------------------------------------------------------
# 3. Component builders
# ---------------------------------------------------------------------------

# Servo dimensions (Feetech STS3032)
SERVO_W = 20.0
SERVO_L = 40.0
SERVO_H = 36.0
SPLINE_R = 3.0
SPLINE_H = 4.5
SPLINE_OFFSET_Y = 12.0

# Linkage geometry
DRIVE_ROD_LEN = 40.0      # length of drive rod (driven by hip motor)
THIGH_ROD_LEN = 30.0      # length of thigh rod (passive follower)
CALF_ROD_LEN = 25.0       # length of calf rods (from knee to wheel axle)
PLATE_GAP = 7.0           # lateral (Y) gap between outer plates
PLATE_THICK_OUTER = 3.0
PLATE_THICK_INNER = 4.0
PLATE_WIDTH = 10.0

# Hip and coupler spacing
HIP_SPACING = 50.0        # Y-spacing between the two hip pivots
HIP_Z = 20.0              # height of hip pivots above base
KNEE_SPACING = 50.0       # Y-spacing between knee rod pivots (parallel to hip)

# Crus Side Rod (triangulation brace, 35mm per spec)
CRUS_ROD_LEN = 35.0

# Spring dimensions (PEA spring pattern)
SPRING_RADIUS_MM = 4.0
SPRING_LENGTH_MM = 20.0
SPRING_LATERAL_OFFSET_MM = 5.0

# Wheel dimensions
WHEEL_R = 40.0
WHEEL_W = 16.0
WHEEL_STUB = 22.0

# Rest pose angle
DEFAULT_HIP_ANGLE = 58.0


def build_servo_body(collection):
    """STS3032 servo body (rectangular housing)."""
    return make_box(f"{PREFIX}ServoBody", collection,
                    (SERVO_H, SERVO_L, SERVO_W),
                    pivot_mm=(SERVO_H / 2, SPLINE_OFFSET_Y, 0.0),
                    material=MAT_METAL())


def build_servo_spline(collection):
    """STS3032 servo output spline (rotation axis)."""
    return make_cylinder(f"{PREFIX}ServoSpline", collection, SPLINE_R, SPLINE_H,
                         axis='X', location_mm=(SPLINE_H / 2, 0.0, 0.0),
                         material=MAT_METAL())


def build_knuckle(name, collection, location_mm=(0.0, 0.0, 0.0)):
    """Round pivot knuckle representing a bolt head."""
    return make_cylinder(name, collection, 3.0, 2.5, axis='X', segments=6,
                         location_mm=location_mm, material=MAT_METAL())


def build_dual_shear_link(name_prefix, collection, link_length_mm, plate_y_offset=0.0):
    """
    Builds a dual-shear link: two outer plates sandwiching an inner link body.

    Each link consists of:
    - Two outer plates (thin, parallel, offset in Y by PLATE_GAP)
    - One inner link body (thicker, centered between the outer plates)
    - Pivot bolts at both ends pass through all three

    The link spans from local origin (hip-side pivot) to (0, 0, -link_length_mm)
    (coupler-side pivot).

    Args:
        name_prefix: Base name for the link components
        collection: Blender collection to link objects to
        link_length_mm: Distance between hip and coupler pivots
        plate_y_offset: Y-offset for this link pair

    Returns:
        Dictionary with references to all components
    """
    # Outer plate (front)
    outer_front = make_box(
        f"{name_prefix}_OuterPlateFront",
        collection,
        (PLATE_WIDTH, PLATE_THICK_OUTER, link_length_mm),
        pivot_mm=(0.0, 0.0, link_length_mm / 2),
        location_mm=(0.0, plate_y_offset + PLATE_GAP / 2, 0.0),
        material=MAT_PLATE()
    )

    # Outer plate (back)
    outer_back = make_box(
        f"{name_prefix}_OuterPlateBack",
        collection,
        (PLATE_WIDTH, PLATE_THICK_OUTER, link_length_mm),
        pivot_mm=(0.0, 0.0, link_length_mm / 2),
        location_mm=(0.0, plate_y_offset - PLATE_GAP / 2, 0.0),
        material=MAT_PLATE()
    )

    # Inner link body (thicker, spans the same length as outer plates)
    inner_link = make_box(
        f"{name_prefix}_InnerLink",
        collection,
        (PLATE_WIDTH - 2.0, PLATE_THICK_INNER, link_length_mm),
        pivot_mm=(0.0, 0.0, link_length_mm / 2),
        location_mm=(0.0, plate_y_offset, 0.0),
        material=MAT_PLATE()
    )

    # Pivot knuckles at hip-side (front/back pair)
    hip_knuckle_front = build_knuckle(
        f"{name_prefix}_HipKnuckleFront",
        collection,
        location_mm=(0.0, plate_y_offset + PLATE_GAP / 2, 0.0)
    )

    hip_knuckle_back = build_knuckle(
        f"{name_prefix}_HipKnuckleBack",
        collection,
        location_mm=(0.0, plate_y_offset - PLATE_GAP / 2, 0.0)
    )

    # Pivot knuckles at coupler-side (front/back pair)
    coupler_knuckle_front = build_knuckle(
        f"{name_prefix}_CouplerKnuckleFront",
        collection,
        location_mm=(0.0, plate_y_offset + PLATE_GAP / 2, mm(-link_length_mm))
    )

    coupler_knuckle_back = build_knuckle(
        f"{name_prefix}_CouplerKnuckleBack",
        collection,
        location_mm=(0.0, plate_y_offset - PLATE_GAP / 2, mm(-link_length_mm))
    )

    return {
        'outer_front': outer_front,
        'outer_back': outer_back,
        'inner_link': inner_link,
        'hip_knuckle_front': hip_knuckle_front,
        'hip_knuckle_back': hip_knuckle_back,
        'coupler_knuckle_front': coupler_knuckle_front,
        'coupler_knuckle_back': coupler_knuckle_back,
    }


def build_pea_spring(tag, collection, sign):
    """
    Placeholder PEA (parallel elastic actuation) spring geometry.
    A simple representative cylinder standing in for a real helical spring.

    The spring constant (N*m/rad) is computed separately in orchestration layer;
    this is visual geometry only. Built once at DEFAULT_HIP_ANGLE and parented
    to the drive rod, so it swings rigidly with the hip angle.
    """
    return make_cylinder(f"{tag}_PeaSpring", collection, SPRING_RADIUS_MM, SPRING_LENGTH_MM,
                          axis='Z', segments=10,
                          location_mm=(-sign * SPRING_LATERAL_OFFSET_MM, 0.0, -SPRING_LENGTH_MM / 2),
                          material=MAT_SPRING())


def build_knee_rod(collection, location_z_mm):
    """
    Knee rod coupler: receives the drive rod and thigh rod at the same spacing
    as the hip pivots, then connects down to the calf rods. Acts as the knee joint.
    """
    knee_rod = make_box(
        f"{PREFIX}KneeRod",
        collection,
        (20.0, KNEE_SPACING + 10.0, 14.0),
        material=MAT_METAL()
    )
    knee_rod.location = mm(0.0, 0.0, -location_z_mm)
    return knee_rod


def build_crus_side_rod(collection):
    """
    Crus Side Rod: a rigid brace connecting the drive rod to the thigh rod.
    This triangulation creates a virtual pivot effect, shaping the wheel's motion path.

    Positioned as a diagonal strut from the upper region of the drive rod
    to the upper region of the thigh rod, anchored to the hip servo mount.

    Per issue #104 specifications: rigid (does not add a second DOF), 35mm length.
    """
    crus = make_box(
        f"{PREFIX}CrusSideRod",
        collection,
        (6.0, 8.0, CRUS_ROD_LEN),
        pivot_mm=(0.0, 0.0, CRUS_ROD_LEN / 2),
        location_mm=(0.0, KNEE_SPACING / 2 + 10.0, mm(-CRUS_ROD_LEN / 2 - 5.0)),
        material=MAT_PLATE()
    )
    return crus


def build_calf_link(name_prefix, collection, calf_len_mm):
    """
    Builds dual-shear calf link: two outer plates + inner body, spanning from
    knee pivot to the wheel axle (25mm per spec).

    Similar to the drive/thigh rods but shorter, for the knee-to-ankle segment.
    """
    # Outer plate (front)
    outer_front = make_box(
        f"{name_prefix}_OuterPlateFront",
        collection,
        (PLATE_WIDTH, PLATE_THICK_OUTER, calf_len_mm),
        pivot_mm=(0.0, 0.0, calf_len_mm / 2),
        location_mm=(0.0, PLATE_GAP / 2, 0.0),
        material=MAT_PLATE()
    )

    # Outer plate (back)
    outer_back = make_box(
        f"{name_prefix}_OuterPlateBack",
        collection,
        (PLATE_WIDTH, PLATE_THICK_OUTER, calf_len_mm),
        pivot_mm=(0.0, 0.0, calf_len_mm / 2),
        location_mm=(0.0, -PLATE_GAP / 2, 0.0),
        material=MAT_PLATE()
    )

    # Inner link body
    inner_link = make_box(
        f"{name_prefix}_InnerLink",
        collection,
        (PLATE_WIDTH - 2.0, PLATE_THICK_INNER, calf_len_mm),
        pivot_mm=(0.0, 0.0, calf_len_mm / 2),
        location_mm=(0.0, 0.0, 0.0),
        material=MAT_PLATE()
    )

    # Pivot knuckles at knee-side (front/back pair)
    knee_knuckle_front = build_knuckle(
        f"{name_prefix}_KneeKnuckleFront",
        collection,
        location_mm=(0.0, PLATE_GAP / 2, 0.0)
    )

    knee_knuckle_back = build_knuckle(
        f"{name_prefix}_KneeKnuckleBack",
        collection,
        location_mm=(0.0, -PLATE_GAP / 2, 0.0)
    )

    # Pivot knuckles at ankle-side (front/back pair)
    ankle_knuckle_front = build_knuckle(
        f"{name_prefix}_AnkleKnuckleFront",
        collection,
        location_mm=(0.0, PLATE_GAP / 2, mm(-calf_len_mm))
    )

    ankle_knuckle_back = build_knuckle(
        f"{name_prefix}_AnkleKnuckleBack",
        collection,
        location_mm=(0.0, -PLATE_GAP / 2, mm(-calf_len_mm))
    )

    return {
        'outer_front': outer_front,
        'outer_back': outer_back,
        'inner_link': inner_link,
        'knee_knuckle_front': knee_knuckle_front,
        'knee_knuckle_back': knee_knuckle_back,
        'ankle_knuckle_front': ankle_knuckle_front,
        'ankle_knuckle_back': ankle_knuckle_back,
    }


def build_wheel_hub_motor_body(collection):
    """STS3032 servo body mounted at the wheel hub (inverted orientation)."""
    return make_box(f"{PREFIX}WheelHubMotorBody", collection,
                    (SERVO_H, SERVO_L, SERVO_W),
                    pivot_mm=(SERVO_H / 2, SPLINE_OFFSET_Y, 0.0),
                    material=MAT_METAL())


def build_wheel_hub_motor_spline(collection):
    """STS3032 wheel-hub motor output spline."""
    return make_cylinder(f"{PREFIX}WheelHubMotorSpline", collection, SPLINE_R, SPLINE_H,
                         axis='X', location_mm=(SPLINE_H / 2, 0.0, 0.0),
                         material=MAT_METAL())


def build_wheel(collection):
    """Treaded wheel with tread grooves (40mm radius, 16mm width)."""
    r = WHEEL_R
    w = WHEEL_W
    wheel = make_cylinder(f"{PREFIX}Wheel", collection, r, w, axis='Z',
                          segments=48, material=MAT_BLACK())

    # Add tread grooves
    grooves = []
    n = 20
    for i in range(n):
        ang = (2 * math.pi / n) * i
        gx = (r - 1.2) * math.cos(ang)
        gy = (r - 1.2) * math.sin(ang)
        grooves.append({
            'type': 'box',
            'size': (4.0, 3.0, w - 3.0),
            'location': (gx, gy, 0.0)
        })

    cutter = merge_cutters(f"{PREFIX}WheelGrooves", collection, grooves)
    boolean_diff_apply(wheel, cutter)

    # Wheel hub
    hub = make_cylinder(f"{PREFIX}WheelHub", collection, 9.0, w + 6.0, axis='Z',
                        segments=24, material=MAT_METAL())
    hub.parent = wheel

    # Rotate wheel to lie flat (axle along X)
    wheel.rotation_euler = (0.0, math.radians(90), 0.0)

    return wheel


def merge_cutters(name, collection, cutter_specs):
    """Merges multiple cutter specs into a single mesh."""
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
            bmesh.ops.create_cone(sub, cap_ends=True, cap_tris=False,
                                   segments=spec.get('segments', 24),
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
    """Apply a boolean difference modifier and clean up."""
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
# 4. Assembly: complete upper leg assembly
# ---------------------------------------------------------------------------

def build_assembly(collection):
    """
    Assemble the complete upper leg assembly (10 parts):
    1. Hip servo (STS3032)
    2. Servo spline
    3. Drive Rod (dual-shear, driven by hip)
    4. Thigh Rod1 (dual-shear, passive)
    5. Crus Side Rod (rigid brace, 35mm)
    6. Knee Rod (coupler)
    7. Calf Rod1/Rod2 (dual-plate, 25mm)
    8. Damping Spring (PEA pattern)
    9. Wheel hub motor (STS3032)
    10. Wheel (40mm R, 16mm W, treaded)
    """

    default_rad = math.radians(DEFAULT_HIP_ANGLE)

    # 1. Hip servo mounting assembly
    servo_body = build_servo_body(collection)
    servo_body.location = (0.0, 0.0, mm(HIP_Z))
    servo_body.rotation_euler.x = default_rad

    # 2. Servo spline (output of hip motor)
    servo_spline = build_servo_spline(collection)
    servo_spline.parent = servo_body

    # 3. Drive Rod (driven by hip servo)
    drive_rod = build_dual_shear_link(f"{PREFIX}DriveRod", collection, DRIVE_ROD_LEN, plate_y_offset=0.0)
    for key in drive_rod:
        drive_rod[key].parent = servo_body

    # 4. Thigh Rod1 (passive follower)
    thigh_rod = build_dual_shear_link(f"{PREFIX}ThighRod1", collection, THIGH_ROD_LEN, plate_y_offset=0.0)
    for key in thigh_rod:
        thigh_rod[key].parent = servo_body

    # 5. Crus Side Rod (rigid triangulation brace, 35mm)
    crus_rod = build_crus_side_rod(collection)
    crus_rod.parent = servo_body

    # 6. Knee Rod coupler
    knee_rod = build_knee_rod(collection, DRIVE_ROD_LEN)
    knee_rod.parent = servo_body

    # 8. Damping Spring (parented to drive rod, springs between knee and calf)
    spring = build_pea_spring(f"{PREFIX}DampingSpring", collection, 1.0)
    spring.parent = drive_rod['outer_front']
    # Position spring from knee pivot downward
    spring.location = mm(0.0, 0.0, -DRIVE_ROD_LEN - 5.0)

    # 7. Calf Rod1 and Calf Rod2 (dual-plate, 25mm from knee to wheel axle)
    # Note: Calf Rod1 and Rod2 are two parts of the same dual-shear assembly
    calf_rod = build_calf_link(f"{PREFIX}CalfRod", collection, CALF_ROD_LEN)
    for key in calf_rod:
        calf_rod[key].parent = knee_rod

    # 9. Wheel hub motor (mounted at the wheel axle, below the calf rod)
    wheel_motor_body = build_wheel_hub_motor_body(collection)
    wheel_motor_body.location = mm(0.0, 0.0, -CALF_ROD_LEN - 10.0)
    wheel_motor_body.parent = knee_rod

    wheel_motor_spline = build_wheel_hub_motor_spline(collection)
    wheel_motor_spline.parent = wheel_motor_body

    # 10. Wheel (actuated by wheel hub motor, 40mm R, 16mm W)
    wheel = build_wheel(collection)
    wheel.location = mm(0.0, 0.0, -CALF_ROD_LEN - 10.0 - WHEEL_STUB)
    wheel.parent = wheel_motor_body

    return {
        'servo_body': servo_body,
        'servo_spline': servo_spline,
        'drive_rod': drive_rod,
        'thigh_rod': thigh_rod,
        'crus_rod': crus_rod,
        'knee_rod': knee_rod,
        'spring': spring,
        'calf_rod': calf_rod,
        'wheel_motor_body': wheel_motor_body,
        'wheel_motor_spline': wheel_motor_spline,
        'wheel': wheel,
    }


# ---------------------------------------------------------------------------
# 5. Animation: keyframes at key angles for validation (15°, 58°, 120°)
# ---------------------------------------------------------------------------

def set_keyframe_shape(obj, data_path, frame, interp, easing, array_index=None):
    """Sets interpolation/easing on the keyframe point at `frame`."""
    if not (obj.animation_data and obj.animation_data.action):
        return
    for fc in obj.animation_data.action.fcurves:
        if fc.data_path != data_path:
            continue
        if array_index is not None and fc.array_index != array_index:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                kp.interpolation = interp
                kp.easing = easing
                break


def kf_rot_x(obj, frame, deg, interp='BEZIER', easing='EASE_IN_OUT'):
    """Keyframe rotation around X axis."""
    obj.rotation_euler.x = math.radians(deg)
    obj.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
    set_keyframe_shape(obj, "rotation_euler", frame, interp, easing, array_index=0)


def animate_leg_sweep(assembly):
    """
    Create keyframes at three key angles per issue #104 specs:
    - Frame 1: Minimum angle (15°)
    - Frame 90: Rest pose (58°)
    - Frame 180: Maximum angle (120°)

    This allows validation of the linkage's full range of motion.
    """
    # Frame 1: Minimum angle (15°)
    kf_rot_x(assembly['servo_body'], 1, 15.0)

    # Frame 90: Rest pose (58°)
    kf_rot_x(assembly['servo_body'], 90, DEFAULT_HIP_ANGLE)

    # Frame 180: Maximum angle (120°)
    kf_rot_x(assembly['servo_body'], 180, 120.0)


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point: clean up previous builds, build assembly, animate, save."""
    # Clean up previous builds
    clear_previous()

    # Create collection
    collection = new_collection()

    # Build assembly
    assembly = build_assembly(collection)

    # Animate sweep through key angles
    animate_leg_sweep(assembly)

    # Save .blend file when running headless
    if bpy.app.background:
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/upper_leg_assembly.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
