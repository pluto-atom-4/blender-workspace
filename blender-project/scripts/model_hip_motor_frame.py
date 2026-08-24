"""
Hip Motor Robot Frame Assembly 3D Model (issue #112)

Standalone assembly model combining:
  - Thigh Rod1: flat-bar connector with lightening slots (81.5mm × 6.0mm × 3.5mm)
  - Drive Rod: flat-bar connector without slots (81.5mm × 6.0mm × 3.5mm)
  - STS-3032 Servo: actuator body (23.2mm H × 12.1mm W × 28.5mm L) with output shaft
  - Hip Motor Housing: structural frame box containing all components

Assembly positioning:
  - Housing centered at origin with pivot holes
  - Servo mounted at top of housing, output shaft extending downward
  - Thigh Rod1 and Drive Rod positioned per reference diagram layout
  - Servo output shaft rotates to drive Drive Rod (articulated pose)

Scale anchor: Feetech STS-3032 servo from datasheet (23.2×12.1×28.5mm)
Reference: Screenshot_20260822_191609.png (assembly diagram)

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (bmesh flat bars, cylinders, boxes)
  3. Component builders (Thigh Rod1, Drive Rod, Servo, Housing)
  4. Assembly positioning
  5. Viewport configuration
  6. Main
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 1. Units / cleanup / materials
# ---------------------------------------------------------------------------

COLLECTION_NAME = "HipMotorFrame"
PREFIX = "HMF_"
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


MAT_PLATE = lambda: get_material("Plate", (0.15, 0.15, 0.16, 1.0))       # dark grey bar
MAT_METAL = lambda: get_material("Metal", (0.5, 0.5, 0.55, 1.0))          # pivot pins, servo
MAT_HOUSING = lambda: get_material("Housing", (0.35, 0.35, 0.36, 1.0))    # light grey frame


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


def shade_smooth(obj):
    """Shade an object smooth."""
    for poly in obj.data.polygons:
        poly.use_smooth = True


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
# 3. Component dimensions
# ---------------------------------------------------------------------------

# Thigh Rod dimensions
THIGH_ROD_LEN = 81.5
THIGH_ROD_WIDTH = 6.0
THIGH_ROD_THICK = 3.5
CORNER_RADIUS = 0.4

# Drive Rod dimensions (same as Thigh Rod)
DRIVE_ROD_LEN = 81.5
DRIVE_ROD_WIDTH = 6.0
DRIVE_ROD_THICK = 3.5

# Pivot pins
PIVOT_PIN_RADIUS = 1.5
PIVOT_PIN_HEIGHT = 2.5
PIVOT_PIN_INWARD_OFFSET = 5.0
PIVOT_PIN_Z_BASE = DRIVE_ROD_THICK / 2
PIVOT_PIN_Z_CENTER = PIVOT_PIN_Z_BASE + PIVOT_PIN_HEIGHT / 2

# Lightening slots (Thigh Rod only)
SLOT_LENGTH = 8.0
SLOT_WIDTH = 3.0
SLOT_DEPTH = 2.0
SLOT_COUNT = 2

# Servo dimensions (Feetech STS-3032 from datasheet)
SERVO_H = 23.2          # height (Y direction)
SERVO_W = 12.1          # width (X direction)
SERVO_L = 28.5          # length/depth (Z direction)
SERVO_SPLINE_RADIUS = 2.0      # output shaft radius
SERVO_SPLINE_LENGTH = 3.5      # output shaft extension length

# Housing dimensions (structural frame box to contain all components)
HOUSING_X = 120.0       # outer dimension in X (length)
HOUSING_Y = 90.0        # outer dimension in Y (width)
HOUSING_Z = 80.0        # outer dimension in Z (height)
HOUSING_WALL = 2.5      # wall thickness

# Positioning in assembly
SERVO_Z_OFFSET = 30.0   # height of servo above housing base
DRIVE_ROD_Z_OFFSET = 15.0  # height of drive rod above housing base
THIGH_ROD_Z_OFFSET = 25.0  # height of thigh rod above housing base
DRIVE_ROD_Y_OFFSET = -20.0  # lateral offset of drive rod
THIGH_ROD_Y_OFFSET = 20.0   # lateral offset of thigh rod


# ---------------------------------------------------------------------------
# 3. Component builders
# ---------------------------------------------------------------------------

def build_flat_bar_with_slots(name, collection, has_slots=False):
    """
    Build a flat bar with optional lightening slots.

    Args:
        name: object name
        collection: Blender collection
        has_slots: if True, add lightening slots (for Thigh Rod)
    """
    bm = bmesh.new()

    # Build rounded rectangle profile in the YZ plane
    half_w = mm(DRIVE_ROD_WIDTH / 2)
    half_t = mm(DRIVE_ROD_THICK / 2)
    corner_r = mm(CORNER_RADIUS)

    profile_verts = []

    # Bottom-right corner arc
    for i in range(9):
        angle = (i / 8.0) * (math.pi / 2)
        y = half_w - corner_r + corner_r * math.sin(angle)
        z = -half_t + corner_r - corner_r * math.cos(angle)
        v = bm.verts.new((0, y, z))
        profile_verts.append(v)

    # Top-right corner arc
    for i in range(1, 9):
        angle = (i / 8.0) * (math.pi / 2)
        y = half_w - corner_r + corner_r * math.cos(angle)
        z = half_t - corner_r + corner_r * math.sin(angle)
        v = bm.verts.new((0, y, z))
        profile_verts.append(v)

    # Top-left corner arc
    for i in range(1, 9):
        angle = (i / 8.0) * (math.pi / 2)
        y = -half_w + corner_r - corner_r * math.sin(angle)
        z = half_t - corner_r + corner_r * math.cos(angle)
        v = bm.verts.new((0, y, z))
        profile_verts.append(v)

    # Bottom-left corner arc
    for i in range(1, 9):
        angle = (i / 8.0) * (math.pi / 2)
        y = -half_w + corner_r - corner_r * math.cos(angle)
        z = -half_t + corner_r - corner_r * math.sin(angle)
        v = bm.verts.new((0, y, z))
        profile_verts.append(v)

    # Create face
    bm.faces.new(profile_verts)

    # Extrude along X axis
    bar_len = mm(DRIVE_ROD_LEN)
    for face in bm.faces:
        face.select = True

    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    geom_extruded = ret["geom"]

    for geom in geom_extruded:
        if isinstance(geom, bmesh.types.BMVert):
            geom.co.x += bar_len

    # Center bar at origin
    for v in bm.verts:
        v.co.x -= bar_len / 2

    mesh = bpy.data.meshes.new(PREFIX + name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(PREFIX + name, mesh)
    _link(obj, collection)

    shade_smooth(obj)
    apply_transforms(obj)
    assign_material(obj, MAT_PLATE())

    # Add lightening slots if requested (Thigh Rod only)
    if has_slots:
        add_lightening_slots(obj, collection)

    return obj


def add_lightening_slots(bar_obj, collection):
    """Add lightening slots to bar via boolean difference."""
    bar_len = DRIVE_ROD_LEN
    slot_spacing = bar_len / (SLOT_COUNT + 1)

    slot_positions = []
    for i in range(1, SLOT_COUNT + 1):
        slot_x = -bar_len / 2 + slot_spacing * i
        slot_positions.append(slot_x)

    for i, slot_x in enumerate(slot_positions):
        slot_name = f"{PREFIX}SlotCutter_{i}"
        bm_slot = bmesh.new()

        slot_half_len = mm(SLOT_LENGTH / 2)
        slot_half_w = mm(SLOT_WIDTH / 2)
        slot_height = mm(SLOT_DEPTH)
        slot_z = mm(0.5)

        vertices = [
            bm_slot.verts.new((mm(slot_x - SLOT_LENGTH/2), -slot_half_w, slot_z - slot_height/2)),
            bm_slot.verts.new((mm(slot_x + SLOT_LENGTH/2), -slot_half_w, slot_z - slot_height/2)),
            bm_slot.verts.new((mm(slot_x + SLOT_LENGTH/2),  slot_half_w, slot_z - slot_height/2)),
            bm_slot.verts.new((mm(slot_x - SLOT_LENGTH/2),  slot_half_w, slot_z - slot_height/2)),
            bm_slot.verts.new((mm(slot_x - SLOT_LENGTH/2), -slot_half_w, slot_z + slot_height/2)),
            bm_slot.verts.new((mm(slot_x + SLOT_LENGTH/2), -slot_half_w, slot_z + slot_height/2)),
            bm_slot.verts.new((mm(slot_x + SLOT_LENGTH/2),  slot_half_w, slot_z + slot_height/2)),
            bm_slot.verts.new((mm(slot_x - SLOT_LENGTH/2),  slot_half_w, slot_z + slot_height/2)),
        ]

        bm_slot.faces.new([vertices[0], vertices[1], vertices[2], vertices[3]])
        bm_slot.faces.new([vertices[4], vertices[7], vertices[6], vertices[5]])
        bm_slot.faces.new([vertices[0], vertices[4], vertices[5], vertices[1]])
        bm_slot.faces.new([vertices[1], vertices[5], vertices[6], vertices[2]])
        bm_slot.faces.new([vertices[2], vertices[6], vertices[7], vertices[3]])
        bm_slot.faces.new([vertices[3], vertices[7], vertices[4], vertices[0]])

        slot_mesh = bpy.data.meshes.new(slot_name + "_mesh")
        bm_slot.to_mesh(slot_mesh)
        bm_slot.free()
        slot_mesh.update()

        slot_obj = bpy.data.objects.new(slot_name, slot_mesh)
        _link(slot_obj, collection)
        slot_obj.location = (0, 0, 0)

        bpy.context.view_layer.objects.active = bar_obj
        bar_obj.select_set(True)

        mod = bar_obj.modifiers.new(name=f"SlotCut_{i}", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = slot_obj

        bpy.ops.object.modifier_apply(modifier=mod.name)

        bpy.data.objects.remove(slot_obj, do_unlink=True)
        if slot_mesh.users == 0:
            bpy.data.meshes.remove(slot_mesh)

        bar_obj.select_set(False)


def build_servo(collection):
    """Build STS-3032 servo body + output spline shaft."""
    # Servo body (box)
    bm_body = bmesh.new()

    # Create a box for servo body (23.2mm H × 12.1mm W × 28.5mm L)
    servo_h = mm(SERVO_H)  # Y direction (height)
    servo_w = mm(SERVO_W)  # X direction (width)
    servo_l = mm(SERVO_L)  # Z direction (length/depth)

    half_w = servo_w / 2
    half_h = servo_h / 2
    half_l = servo_l / 2

    vertices = [
        bm_body.verts.new((-half_w, -half_h, -half_l)),
        bm_body.verts.new(( half_w, -half_h, -half_l)),
        bm_body.verts.new(( half_w,  half_h, -half_l)),
        bm_body.verts.new((-half_w,  half_h, -half_l)),
        bm_body.verts.new((-half_w, -half_h,  half_l)),
        bm_body.verts.new(( half_w, -half_h,  half_l)),
        bm_body.verts.new(( half_w,  half_h,  half_l)),
        bm_body.verts.new((-half_w,  half_h,  half_l)),
    ]

    # Create faces
    bm_body.faces.new([vertices[0], vertices[1], vertices[2], vertices[3]])
    bm_body.faces.new([vertices[4], vertices[7], vertices[6], vertices[5]])
    bm_body.faces.new([vertices[0], vertices[4], vertices[5], vertices[1]])
    bm_body.faces.new([vertices[1], vertices[5], vertices[6], vertices[2]])
    bm_body.faces.new([vertices[2], vertices[6], vertices[7], vertices[3]])
    bm_body.faces.new([vertices[3], vertices[7], vertices[4], vertices[0]])

    mesh_body = bpy.data.meshes.new(PREFIX + "ServoBody_mesh")
    bm_body.to_mesh(mesh_body)
    bm_body.free()
    mesh_body.update()

    obj_body = bpy.data.objects.new(PREFIX + "ServoBody", mesh_body)
    _link(obj_body, collection)
    shade_flat(obj_body)
    assign_material(obj_body, MAT_METAL())

    # Output spline shaft (extends downward from center of servo bottom)
    # Positioned at bottom center (Y=0, X=0, Z=-half_l)
    spline = make_cylinder(
        f"{PREFIX}ServoSpline",
        collection,
        SERVO_SPLINE_RADIUS,
        SERVO_SPLINE_LENGTH,
        axis='Y',  # extends in Y direction (downward from servo body)
        segments=16,
        location_mm=(0, -half_h - mm(SERVO_SPLINE_LENGTH/2), -servo_l/MM/2),
        material=MAT_METAL()
    )

    return {'body': obj_body, 'spline': spline}


def build_housing(collection):
    """Build Hip Motor frame housing (structural box enclosure)."""
    # Housing outer box
    bm = bmesh.new()

    h_x = mm(HOUSING_X)
    h_y = mm(HOUSING_Y)
    h_z = mm(HOUSING_Z)
    h_wall = mm(HOUSING_WALL)

    half_x = h_x / 2
    half_y = h_y / 2
    half_z = h_z / 2

    # Create outer box vertices
    vertices = [
        bm.verts.new((-half_x, -half_y, -half_z)),
        bm.verts.new(( half_x, -half_y, -half_z)),
        bm.verts.new(( half_x,  half_y, -half_z)),
        bm.verts.new((-half_x,  half_y, -half_z)),
        bm.verts.new((-half_x, -half_y,  half_z)),
        bm.verts.new(( half_x, -half_y,  half_z)),
        bm.verts.new(( half_x,  half_y,  half_z)),
        bm.verts.new((-half_x,  half_y,  half_z)),
    ]

    # Create outer faces
    bm.faces.new([vertices[0], vertices[1], vertices[2], vertices[3]])
    bm.faces.new([vertices[4], vertices[7], vertices[6], vertices[5]])
    bm.faces.new([vertices[0], vertices[4], vertices[5], vertices[1]])
    bm.faces.new([vertices[1], vertices[5], vertices[6], vertices[2]])
    bm.faces.new([vertices[2], vertices[6], vertices[7], vertices[3]])
    bm.faces.new([vertices[3], vertices[7], vertices[4], vertices[0]])

    mesh = bpy.data.meshes.new(PREFIX + "Housing_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(PREFIX + "Housing", mesh)
    _link(obj, collection)
    shade_flat(obj)
    assign_material(obj, MAT_HOUSING())

    return obj


def build_pivot_pin(name, collection, location_mm=(0.0, 0.0, 0.0)):
    """Build a single pivot pin (cylinder)."""
    pin = make_cylinder(
        name,
        collection,
        PIVOT_PIN_RADIUS,
        PIVOT_PIN_HEIGHT,
        axis='Z',
        segments=16,
        location_mm=location_mm,
        material=MAT_METAL()
    )
    return pin


# ---------------------------------------------------------------------------
# 4. Assembly
# ---------------------------------------------------------------------------

def build_assembly(collection):
    """
    Build the complete Hip Motor Frame assembly:
    - Housing (structural frame box)
    - Servo (body + output spline)
    - Thigh Rod (flat bar with lightening slots)
    - Drive Rod (flat bar, solid)
    - Pivot pins at assembly junction points
    """

    # Build housing
    housing = build_housing(collection)

    # Build servo
    servo = build_servo(collection)
    servo['body'].location = mm(0, SERVO_Z_OFFSET, 20)  # centered, elevated
    servo['spline'].location = mm(0, SERVO_Z_OFFSET - mm(SERVO_H/2), 20)  # at servo bottom center

    # Build Thigh Rod (with lightening slots)
    thigh_rod = build_flat_bar_with_slots("ThighRod1", collection, has_slots=True)
    thigh_rod.location = mm(0, THIGH_ROD_Y_OFFSET, THIGH_ROD_Z_OFFSET)
    thigh_rod.rotation_euler = (0, math.radians(15), 0)  # slight angle for articulation

    # Build Drive Rod (solid, no slots)
    drive_rod = build_flat_bar_with_slots("DriveRod", collection, has_slots=False)
    drive_rod.location = mm(0, DRIVE_ROD_Y_OFFSET, DRIVE_ROD_Z_OFFSET)
    drive_rod.rotation_euler = (0, math.radians(-20), 0)  # articulated pose

    # Build pivot pins at rod ends (assembly context)
    # Thigh Rod front pivot
    thigh_front_pin = build_pivot_pin(
        f"{PREFIX}ThighRodFrontPin",
        collection,
        location_mm=(-DRIVE_ROD_LEN/2 + PIVOT_PIN_INWARD_OFFSET, THIGH_ROD_Y_OFFSET, THIGH_ROD_Z_OFFSET + PIVOT_PIN_Z_CENTER)
    )

    # Thigh Rod back pivot
    thigh_back_pin = build_pivot_pin(
        f"{PREFIX}ThighRodBackPin",
        collection,
        location_mm=(DRIVE_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET, THIGH_ROD_Y_OFFSET, THIGH_ROD_Z_OFFSET + PIVOT_PIN_Z_CENTER)
    )

    # Drive Rod front pivot
    drive_front_pin = build_pivot_pin(
        f"{PREFIX}DriveRodFrontPin",
        collection,
        location_mm=(-DRIVE_ROD_LEN/2 + PIVOT_PIN_INWARD_OFFSET, DRIVE_ROD_Y_OFFSET, DRIVE_ROD_Z_OFFSET + PIVOT_PIN_Z_CENTER)
    )

    # Drive Rod back pivot
    drive_back_pin = build_pivot_pin(
        f"{PREFIX}DriveRodBackPin",
        collection,
        location_mm=(DRIVE_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET, DRIVE_ROD_Y_OFFSET, DRIVE_ROD_Z_OFFSET + PIVOT_PIN_Z_CENTER)
    )

    return {
        'housing': housing,
        'servo_body': servo['body'],
        'servo_spline': servo['spline'],
        'thigh_rod': thigh_rod,
        'drive_rod': drive_rod,
    }


# ---------------------------------------------------------------------------
# 5. Viewport configuration
# ---------------------------------------------------------------------------

def configure_viewport():
    """Configure viewport for optimal model viewing."""
    # Hide Cube
    if "Cube" in bpy.data.objects:
        cube = bpy.data.objects["Cube"]
        cube.hide_viewport = True
        cube.hide_render = True
        print("✓ Hidden Cube from viewport")

    # Frame the assembly
    if COLLECTION_NAME in bpy.data.collections:
        collection = bpy.data.collections[COLLECTION_NAME]
        for obj in collection.objects:
            obj.select_set(True)

        if collection.objects:
            bpy.context.view_layer.objects.active = collection.objects[0]

        try:
            bpy.ops.view3d.view_all(center=True)
            print("✓ Framed Hip Motor Frame assembly in viewport")
        except:
            print("⚠ Could not frame model (may not be in interactive mode)")

        for obj in collection.objects:
            obj.select_set(False)


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point: clean up, build assembly, configure viewport, save."""
    # Clean up
    clear_previous()

    # Create collection
    collection = new_collection()

    # Build assembly
    assembly = build_assembly(collection)
    print(f"✓ Built Hip Motor Frame assembly with {len(assembly)} main components")
    print(f"  - Housing: {HOUSING_X}×{HOUSING_Y}×{HOUSING_Z}mm structural frame box")
    print(f"  - Servo: {SERVO_H}×{SERVO_W}×{SERVO_L}mm body + {SERVO_SPLINE_RADIUS}mm spline")
    print(f"  - Thigh Rod: {THIGH_ROD_LEN}mm flat bar with {SLOT_COUNT} lightening slots")
    print(f"  - Drive Rod: {DRIVE_ROD_LEN}mm flat bar (solid)")
    print(f"  - Servo output spline rotates to drive Drive Rod linkage")

    # Configure viewport
    configure_viewport()

    # Save .blend file when running headless
    if bpy.app.background:
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/hip_motor_frame.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
