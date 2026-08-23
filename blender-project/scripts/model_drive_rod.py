"""
Drive Rod 3D Model -- Standalone flat-bar linkage connector (issue #106)

A high-fidelity flat-bar connector with rounded edges and pivot pins.
Used in the upper leg assembly to transmit drive force from the hip servo
to the thigh rod via dual-shear parallel linkage.

Structure:
  - Main bar: rectangular cross-section with rounded edges (bmesh capsule profile)
  - Two pivot pins: cylinders at each end for assembly/joint context
  - Pivot pins positioned on top (Z direction) for top attachment
  - Solid construction (no lightening slots)

Dimensions (measured from reference image using servo scale anchor):
  - Length (pivot-to-pivot): 81.5mm
  - Width: 6.0mm
  - Thickness: 3.5mm (estimated from proportions in reference)
  - Pivot pin radius: 1.5mm (bolt hole scale)
  - Pivot boss height: 2.5mm (extends 1.25mm on each side)
  - Pivot pins: positioned on top (Z+) with 5mm inward offset from rod ends

Scale anchor: Feetech STS-3032 servo (SERVO_W=20mm, SERVO_L=40mm)
Reference: Screenshot_20260822_191609.png (Drive Rod callout, grey bar from
           pivot bracket to hip motor)

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (bmesh capsule bar, cylinder for pins)
  3. Component builders (flat bar with rounded edges, pivot pins)
  4. Assembly: bar + 2 pins (top-mounted with inward offset)
  5. Viewport configuration (hide Cube, frame model, optimize viewing)
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

# Pivot pin positioning (top-mounted, 5mm inward from rod ends)
PIVOT_PIN_INWARD_OFFSET = 5.0   # 5mm inward from rod ends
PIVOT_PIN_Z_TOP = DRIVE_ROD_THICK / 2 + PIVOT_PIN_HEIGHT / 2  # on top with head protruding


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
    - Two pivot pins at each end (top-mounted with 5mm inward offset)

    The bar is centered at origin:
      - X: -40.75mm to +40.75mm
      - Y: -3.0mm to +3.0mm (centered)
      - Z: -1.75mm to +1.75mm (centered)

    Pivot pins are positioned on TOP of the bar (Z+ direction):
      - X: ±35.75mm (5mm inward from bar ends)
      - Y: 0.0mm (center, 3mm inward from side surface)
      - Z: 3.0mm (on top with pin head protruding upward)
    """

    # Build main bar (centered at origin)
    bar = build_flat_bar(collection)

    # Calculate pivot pin positions
    # X: DRIVE_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET (5mm inward from rod ends)
    pin_x_offset = DRIVE_ROD_LEN / 2 - PIVOT_PIN_INWARD_OFFSET

    # Pivot pins positioned on TOP of the bar
    # Front pivot (at x = -35.75mm, top position)
    front_pin = build_pivot_pin(
        f"{PREFIX}PivotPinFront",
        collection,
        location_mm=(-pin_x_offset, 0.0, PIVOT_PIN_Z_TOP)
    )

    # Back pivot (at x = +35.75mm, top position)
    back_pin = build_pivot_pin(
        f"{PREFIX}PivotPinBack",
        collection,
        location_mm=(pin_x_offset, 0.0, PIVOT_PIN_Z_TOP)
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
    Configure viewport for optimal DriveRod viewing:
    - Hide the Cube object from the viewport
    - Frame the DriveRod collection in view
    - Set appropriate zoom level for inspection
    - Position camera for isometric view of the model
    """
    # Hide Cube object
    if "Cube" in bpy.data.objects:
        cube = bpy.data.objects["Cube"]
        cube.hide_viewport = True
        cube.hide_render = True
        print("✓ Hidden Cube from viewport")

    # Frame the DriveRod model in view
    # Select all DriveRod objects to frame them
    if COLLECTION_NAME in bpy.data.collections:
        collection = bpy.data.collections[COLLECTION_NAME]

        # Select all objects in DriveRod collection
        for obj in collection.objects:
            obj.select_set(True)

        # Make one object active
        if collection.objects:
            bpy.context.view_layer.objects.active = collection.objects[0]

        # Frame all selected objects (Home key equivalent)
        try:
            bpy.ops.view3d.view_all(center=True)
            print("✓ Framed DriveRod model in viewport")
        except:
            print("⚠ Could not frame model (may not be in interactive mode)")

        # Deselect all
        for obj in collection.objects:
            obj.select_set(False)

    # Set viewport zoom and camera distance
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Set a moderate zoom for good visibility
                    if hasattr(space, 'region_3d') and space.region_3d:
                        # Use view_distance for better control
                        if hasattr(space.region_3d, 'view_distance'):
                            space.region_3d.view_distance = 0.2  # Closer to model for better visibility
                            print("✓ Set view distance for optimal visibility")

                        # Set zoom (moderate - not too zoomed in)
                        if hasattr(space.region_3d, 'view_camera_zoom'):
                            space.region_3d.view_camera_zoom = 1.5
                            print("✓ Set viewport zoom to 1.5x")


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
    print(f"✓ Built DriveRod assembly with {len(assembly)} components")
    print(f"  - Pivot pins are now top-mounted (5mm inward from rod ends)")
    print(f"  - Front pin at x=-{DRIVE_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET}mm, y=0mm, z={PIVOT_PIN_Z_TOP}mm")
    print(f"  - Back pin at x=+{DRIVE_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET}mm, y=0mm, z={PIVOT_PIN_Z_TOP}mm")

    # Configure viewport (hide Cube, frame model, optimize viewing)
    configure_viewport()

    # Save .blend file when running headless
    if bpy.app.background:
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/drive_rod.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
