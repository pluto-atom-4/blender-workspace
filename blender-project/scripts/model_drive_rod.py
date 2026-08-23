"""
Drive Rod 3D Model -- Standalone flat-bar linkage connector (issue #106)

A high-fidelity flat-bar connector with rounded edges and pivot pins.
Used in the upper leg assembly to transmit drive force from the hip servo
to the thigh rod via dual-shear parallel linkage.

Structure:
  - Main bar: rectangular cross-section with rounded edges (bmesh capsule profile)
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
  2. Mesh primitives (bmesh capsule bar, cylinder for pins)
  3. Component builders (flat bar with rounded edges, pivot pins)
  4. Assembly: bar + 2 pins
  5. Viewport configuration (hide Cube, set zoom)
  6. Main
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

# Drive rod dimensions (measured from reference image via servo scale anchor)
DRIVE_ROD_LEN = 81.5       # pivot-to-pivot length
DRIVE_ROD_WIDTH = 6.0      # width (Y direction)
DRIVE_ROD_THICK = 3.5      # thickness (Z direction)

# Corner radius for bmesh capsule profile (smooth rounded edges)
CORNER_RADIUS = 0.4        # mm, creates smooth rounded corners

# Pivot pin dimensions
PIVOT_PIN_RADIUS = 1.5     # bolt hole radius
PIVOT_PIN_HEIGHT = 2.5     # extends 1.25mm on each side from bar surface


def build_flat_bar(collection):
    """
    Build the main flat bar with rectangular cross-section and rounded edges
    using bmesh capsule/stadium profile (extrude/inset approach).

    Bar extends from x=-40.75mm to x=+40.75mm (centered at origin).
    Width (Y): 6.0mm, centered at y=0
    Thickness (Z): 3.5mm, centered at z=0
    """

    # Create bmesh
    bm = bmesh.new()

    # Build rounded rectangle profile in the YZ plane (cross-section)
    # Width = 6.0mm (Y direction), Thickness = 3.5mm (Z direction)
    # We'll create a profile with rounded corners using a series of vertices

    half_w = mm(DRIVE_ROD_WIDTH / 2)
    half_t = mm(DRIVE_ROD_THICK / 2)
    corner_r = mm(CORNER_RADIUS)

    # Create vertices for the profile (YZ plane cross-section)
    # We create a rounded rectangle with 8 vertices per corner
    profile_verts = []

    # Right edge (X = constant), create profile shape
    # Start from bottom-right, go counterclockwise
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

    # Create face from profile vertices
    bm.faces.new(profile_verts)

    # Extrude the profile along the X axis (bar length)
    bar_len = mm(DRIVE_ROD_LEN)
    extrude_dir = (bar_len, 0, 0)

    # Select all faces for extrude
    for face in bm.faces:
        face.select = True

    # Use bmesh extrude operator
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    geom_extruded = ret["geom"]

    # Move extruded geometry
    for geom in geom_extruded:
        if isinstance(geom, bmesh.types.BMVert):
            geom.co.x += extrude_dir[0]

    # Center the bar at origin in X direction
    for v in bm.verts:
        v.co.x -= bar_len / 2

    # Create mesh and object
    mesh = bpy.data.meshes.new(PREFIX + "FlatBar_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(PREFIX + "FlatBar", mesh)
    _link(obj, collection)

    shade_smooth(obj)
    apply_transforms(obj)
    assign_material(obj, MAT_PLATE())

    return obj


def build_pivot_pin(name, collection, location_mm=(0.0, 0.0, 0.0)):
    """
    Build a single pivot pin (cylinder) for assembly context.
    Positioned at bar surface, extending perpendicular (along X axis).

    Args:
        name: name of the pin object
        collection: Blender collection to link to
        location_mm: (x, y, z) position in mm
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
    - Main flat bar (with rounded edges via bmesh capsule)
    - Two pivot pins at each end

    The bar is centered at origin:
      - X: -40.75mm to +40.75mm
      - Y: -3.0mm to +3.0mm (centered)
      - Z: -1.75mm to +1.75mm (centered)

    Pivot pins are positioned at the bar ends (x = ±40.75mm).
    """

    # Build main bar (centered at origin)
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
# 5. Viewport configuration
# ---------------------------------------------------------------------------

def configure_viewport():
    """
    Configure viewport settings:
    - Hide the Cube object from the viewport
    - Set viewport zoom to 10x
    """
    # Hide Cube object
    if "Cube" in bpy.data.objects:
        cube = bpy.data.objects["Cube"]
        cube.hide_viewport = True
        cube.hide_render = True
        print("Hidden Cube from viewport")

    # Set viewport zoom to 10x
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Set view_camera_zoom to 10.0 for 10x zoom
                    if hasattr(space, 'region_3d') and space.region_3d:
                        if hasattr(space.region_3d, 'view_camera_zoom'):
                            space.region_3d.view_camera_zoom = 10.0
                            print("Set viewport zoom to 10x (view_camera_zoom = 10.0)")

                        if hasattr(space.region_3d, 'view_zoom'):
                            space.region_3d.view_zoom = 10.0
                            print("Set viewport zoom to 10x (view_zoom = 10.0)")


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point: clean up previous builds, build assembly, configure viewport, save."""
    # Clean up previous builds
    clear_previous()

    # Create collection
    collection = new_collection()

    # Build assembly
    assembly = build_assembly(collection)

    # Configure viewport (hide Cube, set zoom)
    configure_viewport()

    # Save .blend file when running headless
    if bpy.app.background:
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/drive_rod.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
