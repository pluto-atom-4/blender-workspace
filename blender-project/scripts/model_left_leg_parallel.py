"""
Left Leg Parallel Linkage Model -- independent validation build (issue #100)

A standalone four-bar parallel linkage leg assembly with dual-shear joint
construction. Each link arm is built as two outer plates sandwiching an inner
body, with pivot bolts passing through both plates and the inner link,
splitting the load across two shear planes per joint instead of one.

Structure:
  - STS3032 servo (hip drive) with reused dimensions (SERVO_W/L/H = 20/40/36mm)
  - Upper link (driven): two parallel outer plates + inner body, dual-shear
    pivots at hip and coupler
  - Lower link (passive): two parallel outer plates + inner body, dual-shear
    pivots at hip and coupler
  - Coupler bracket: receives both links at the same pivot spacing as the hip
    (forms true parallelogram constraint)
  - Wheel: static/un-actuated (WHEEL_R=40mm, WHEEL_W=16mm), single-bolt
    cantilevered hub attachment per the reference photo

Sweep range: 15°–120°. Default rest pose: 58°. Link lengths and spacing
derived to match the production model's parallelogram geometry while
emphasizing dual-shear joint construction as an independent structural
design choice (not photo-derived).

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (box, cylinder) with explicit pivot control
  3. Component builders (servo, dual-shear link pair, coupler, wheel)
  4. Assembly: servo + upper link + lower link + coupler + wheel
  5. Animation: rest pose with keyframes at 15°, 58°, 120° for validation
  6. Main
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 1. Units / cleanup / materials
# ---------------------------------------------------------------------------

COLLECTION_NAME = "LeftLegParallel"
PREFIX = "LLP_"
MM = 0.001  # 1mm in Blender meters


def mm(*vals):
    if len(vals) == 1:
        return vals[0] * MM
    return tuple(v * MM for v in vals)


def mm_inv(vec):
    return (vec.x / MM, vec.y / MM, vec.z / MM)


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


MAT_PLATE = lambda: get_material("Plate", (0.05, 0.05, 0.055, 1.0))       # black CNC plate
MAT_METAL = lambda: get_material("Metal", (0.5, 0.5, 0.55, 1.0))          # pivots, bolts, servo
MAT_BLACK = lambda: get_material("Black", (0.015, 0.015, 0.018, 1.0))     # wheel tire


def assign_material(obj, mat):
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


def make_box(name, collection, size_mm, pivot_mm=(0.0, 0.0, 0.0),
             location_mm=(0.0, 0.0, 0.0), material=None):
    """Box of size_mm (x,y,z), local origin offset by pivot_mm from geometric center."""
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

# Servo dimensions (reused from production model)
SERVO_W = 20.0
SERVO_L = 40.0
SERVO_H = 36.0
SPLINE_R = 3.0
SPLINE_H = 4.5
SPLINE_OFFSET_Y = 12.0

# Linkage geometry
UPPER_LEN = 40.0      # length of upper link (driven)
LOWER_LEN = 30.0      # length of lower link (passive)
PLATE_GAP = 7.0       # lateral (Y) gap between outer plates
PLATE_THICK_OUTER = 3.0
PLATE_THICK_INNER = 4.0
PLATE_WIDTH = 10.0

# Hip and coupler spacing
HIP_SPACING = 50.0    # Y-spacing between the two hip pivots (must equal coupler spacing for parallelogram)
HIP_Z = 20.0          # height of hip pivots above base
COUPLER_SPACING = 50.0  # Y-spacing between coupler pivots (same as hip for true parallelogram)

# Wheel dimensions (reused from production model)
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
    """STS3032 servo output spline (hinge axis = joint rotation axis)."""
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
        plate_y_offset: Y-offset for this link pair (e.g., +PLATE_GAP/2 for front,
                        -PLATE_GAP/2 for back in a dual-plate assembly)

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


def build_coupler(collection):
    """
    Coupler bracket: receives both upper and lower link pivots at the same
    spacing as the hip pivots (forms true parallelogram constraint).

    Also serves as the wheel-hub mount point (single-bolt attachment).
    """
    coupler = make_box(
        f"{PREFIX}Coupler",
        collection,
        (20.0, COUPLER_SPACING + 10.0, 14.0),
        material=MAT_METAL()
    )
    return coupler


def build_wheel(collection):
    """Static wheel with treaded surface."""
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
# 4. Assembly: servo + upper link + lower link + coupler + wheel
# ---------------------------------------------------------------------------

def build_assembly(collection):
    """
    Assemble the complete leg: servo -> upper link -> coupler -> lower link + wheel.

    The servo is mounted at the origin. Both links are driven by the servo
    (upper is directly driven; lower is passive follower in a true parallelogram).
    """

    default_rad = math.radians(DEFAULT_HIP_ANGLE)

    # Servo mounting assembly
    servo_body = build_servo_body(collection)
    servo_body.location = (0.0, 0.0, mm(HIP_Z))
    servo_body.rotation_euler.x = default_rad

    servo_spline = build_servo_spline(collection)
    servo_spline.parent = servo_body

    # Upper link (driven by servo)
    upper_link = build_dual_shear_link(f"{PREFIX}UpperLink", collection, UPPER_LEN, plate_y_offset=0.0)
    upper_link['outer_front'].parent = servo_body
    upper_link['outer_back'].parent = servo_body
    upper_link['inner_link'].parent = servo_body
    upper_link['hip_knuckle_front'].parent = servo_body
    upper_link['hip_knuckle_back'].parent = servo_body
    upper_link['coupler_knuckle_front'].parent = servo_body
    upper_link['coupler_knuckle_back'].parent = servo_body

    # Lower link (passive follower)
    lower_link = build_dual_shear_link(f"{PREFIX}LowerLink", collection, LOWER_LEN, plate_y_offset=0.0)
    lower_link['outer_front'].parent = servo_body
    lower_link['outer_back'].parent = servo_body
    lower_link['inner_link'].parent = servo_body
    lower_link['hip_knuckle_front'].parent = servo_body
    lower_link['hip_knuckle_back'].parent = servo_body
    lower_link['coupler_knuckle_front'].parent = servo_body
    lower_link['coupler_knuckle_back'].parent = servo_body

    # Coupler bracket (receives both links)
    coupler = build_coupler(collection)
    coupler.location = mm(0.0, 0.0, -UPPER_LEN)
    coupler.parent = servo_body

    # Wheel (static, parented to coupler)
    wheel = build_wheel(collection)
    wheel.location = mm(0.0, 0.0, -UPPER_LEN - 10.0)
    wheel.parent = coupler

    return {
        'servo_body': servo_body,
        'servo_spline': servo_spline,
        'upper_link': upper_link,
        'lower_link': lower_link,
        'coupler': coupler,
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
    Create keyframes at three key angles: 15° (minimum), 58° (rest), 120° (maximum).
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
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/left_leg_parallel.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
