"""
Drive Rod 3D Model -- Standalone flat-bar linkage connector (issue #106)

A high-fidelity flat-bar connector with rounded edges and pivot pins.
Used in the upper leg assembly to transmit drive force from the hip servo
to the thigh rod via dual-shear parallel linkage.

Structure:
  - Main bar: rectangular cross-section with rounded edges (beveled corners)
  - Two pivot pins: cylinders at each end for assembly/joint context
  - Solid construction (no lightening slots)

Dimensions (measured from reference image using servo scale anchor):
  - Length (pivot-to-pivot): 81.5mm
  - Width: 6.0mm
  - Thickness: 3.5mm (estimated from proportions in reference)
  - Pivot pin radius: 1.5mm (bolt hole scale)
  - Pivot boss height: 2.5mm (extends 1.25mm on each side)

Scale anchor: Feetech STS-3032 servo (SERVO_W=20mm, SERVO_L=40mm)
Reference: Screenshot_20260822_191609.png (Drive Rod callout, grey bar from
           pivot bracket to hip motor)

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (box, cylinder, bevel/refine)
  3. Component builders (flat bar, pivot pins)
  4. Assembly: bar + 2 pins
  5. Main
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 1. Units / cleanup / materials
# ---------------------------------------------------------------------------

COLLECTION_NAME = "DriveRod"
PREFIX = "DR_"
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


MAT_PLATE = lambda: get_material("Plate", (0.15, 0.15, 0.16, 1.0))    # dark grey bar
MAT_METAL = lambda: get_material("Metal", (0.5, 0.5, 0.55, 1.0))       # pivot pins, bolts


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


def bevel_sharp_edges(obj, bevel_width_mm=0.3, segments=2, angle_limit=35.0):
    """
    Add a bevel modifier to round sharp edges, then apply it.
    This creates the realistic rounded corners seen in the reference image.
    """
    shade_smooth(obj)

    bevel = obj.modifiers.new("Bevel", type='BEVEL')
    bevel.width = mm(bevel_width_mm)
    bevel.segments = segments
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(angle_limit)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)


# ---------------------------------------------------------------------------
# 3. Component builders
# ---------------------------------------------------------------------------

# Drive rod dimensions (measured from reference image via servo scale anchor)
DRIVE_ROD_LEN = 81.5       # pivot-to-pivot length
DRIVE_ROD_WIDTH = 6.0      # width (Y direction)
DRIVE_ROD_THICK = 3.5      # thickness (Z direction)

# Pivot pin dimensions
PIVOT_PIN_RADIUS = 1.5     # bolt hole radius
PIVOT_PIN_HEIGHT = 2.5     # extends 1.25mm on each side from bar surface


def build_flat_bar(collection):
    """
    Build the main flat bar with rectangular cross-section.
    Will have beveled/rounded edges applied.
    """
    bar = make_box(
        f"{PREFIX}FlatBar",
        collection,
        (DRIVE_ROD_LEN, DRIVE_ROD_WIDTH, DRIVE_ROD_THICK),
        pivot_mm=(DRIVE_ROD_LEN / 2, DRIVE_ROD_WIDTH / 2, DRIVE_ROD_THICK / 2),
        material=MAT_PLATE()
    )

    # Apply bevel to round the edges for a more realistic appearance
    bevel_sharp_edges(bar, bevel_width_mm=0.4, segments=3, angle_limit=40.0)

    return bar


def build_pivot_pin(name, collection, location_mm=(0.0, 0.0, 0.0)):
    """
    Build a single pivot pin (cylinder) for assembly context.
    Positioned at bar surface, extending perpendicular.
    """
    pin = make_cylinder(
        name,
        collection,
        PIVOT_PIN_RADIUS,
        PIVOT_PIN_HEIGHT,
        axis='X',
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
    Build the complete drive rod assembly:
    - Main flat bar (beveled)
    - Two pivot pins at each end
    """

    # Build main bar (at origin, centered on Z, extends along X)
    bar = build_flat_bar(collection)

    # Pivot pins positioned at bar ends
    # Front pivot (at x = -DRIVE_ROD_LEN/2)
    front_pin = build_pivot_pin(
        f"{PREFIX}PivotPinFront",
        collection,
        location_mm=(-DRIVE_ROD_LEN / 2, 0.0, DRIVE_ROD_THICK / 2)
    )

    # Back pivot (at x = +DRIVE_ROD_LEN/2)
    back_pin = build_pivot_pin(
        f"{PREFIX}PivotPinBack",
        collection,
        location_mm=(DRIVE_ROD_LEN / 2, 0.0, DRIVE_ROD_THICK / 2)
    )

    return {
        'bar': bar,
        'front_pin': front_pin,
        'back_pin': back_pin,
    }


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point: clean up previous builds, build assembly, save."""
    # Clean up previous builds
    clear_previous()

    # Create collection
    collection = new_collection()

    # Build assembly
    assembly = build_assembly(collection)

    # Save .blend file when running headless
    if bpy.app.background:
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/drive_rod.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
