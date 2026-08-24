"""
Thigh Rod1 3D Model -- Flat-bar linkage connector with lightening slots (issue #110)

A high-fidelity flat-bar connector with rounded edges, pivot pins, and 2-3 elongated
oval lightening-slot cutouts along the bar's length.
Used in the upper leg assembly as the passive link in the dual-shear parallel linkage.

Structure:
  - Main bar: rectangular cross-section with rounded edges (bmesh capsule profile)
  - Lightening slots: 2-3 elongated oval cutouts along the bar's length
  - Two pivot pins: cylinders at each end for assembly/joint context
  - Pivot pins positioned vertically upward from top surface (Z direction)

Dimensions (matching Drive Rod per issue #110):
  - Length (pivot-to-pivot): 81.5mm
  - Width: 6.0mm
  - Thickness: 3.5mm
  - Pivot pin radius: 1.5mm (bolt hole scale)
  - Pivot pin height: 2.5mm (extends upward from rod top surface)
  - Pivot pins: positioned vertically upward (Z+) with 5mm inward offset from rod ends

Lightening slots:
  - Count: 2-3 elongated oval cutouts
  - Spacing: approximately evenly distributed along bar length
  - Size: approximately 8mm × 3mm (length × width of each slot)

Scale anchor: Feetech STS-3032 servo (same as Drive Rod)
Reference: Issue #110 Phase 1 scope

Sections:
  1. Units / cleanup / materials
  2. Mesh primitives (bmesh capsule bar, cylinder for pins)
  3. Component builders (flat bar with rounded edges, pivot pins, lightening slots)
  4. Assembly: bar + lightening slots + 2 pins (vertical, standing upward with 5mm inward offset)
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

COLLECTION_NAME = "ThighRod1"
PREFIX = "TR1_"
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

# Thigh rod dimensions (matching Drive Rod per issue #110)
THIGH_ROD_LEN = 81.5       # pivot-to-pivot length
THIGH_ROD_WIDTH = 6.0      # width (Y direction)
THIGH_ROD_THICK = 3.5      # thickness (Z direction)

# Corner radius for bmesh capsule profile (smooth rounded edges)
CORNER_RADIUS = 0.4        # mm, creates smooth rounded corners

# Pivot pin dimensions
PIVOT_PIN_RADIUS = 1.5     # bolt hole radius
PIVOT_PIN_HEIGHT = 2.5     # extends upward from rod top surface

# Pivot pin positioning (standing vertically upward, 5mm inward from rod ends)
PIVOT_PIN_INWARD_OFFSET = 5.0   # 5mm inward from rod ends
PIVOT_PIN_Z_BASE = THIGH_ROD_THICK / 2  # at rod top surface (z=1.75mm)
PIVOT_PIN_Z_CENTER = PIVOT_PIN_Z_BASE + PIVOT_PIN_HEIGHT / 2  # center of vertical pin

# Lightening slot dimensions
SLOT_LENGTH = 8.0          # mm, length of each slot along bar
SLOT_WIDTH = 3.0           # mm, width of each slot (Y direction)
SLOT_DEPTH = 2.0           # mm, depth of slot (Z direction, partial thickness)
SLOT_COUNT = 2             # number of slots


def build_flat_bar_with_slots(collection):
    """
    Build the main flat bar with rectangular cross-section, rounded edges,
    and 2-3 lightening slots cut through the bar.

    Bar extends from x=-40.75mm to x=+40.75mm (centered at origin).
    Width (Y): 6.0mm, centered at y=0
    Thickness (Z): 3.5mm, centered at z=0

    Slots are elongated ovals cut along the bar's length.
    """

    # Create the main bar body first
    bm = bmesh.new()

    # Build rounded rectangle profile in the YZ plane (cross-section)
    half_w = mm(THIGH_ROD_WIDTH / 2)
    half_t = mm(THIGH_ROD_THICK / 2)
    corner_r = mm(CORNER_RADIUS)

    # Create vertices for the profile (YZ plane cross-section)
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

    # Create face from profile vertices
    bm.faces.new(profile_verts)

    # Extrude the profile along the X axis (bar length)
    bar_len = mm(THIGH_ROD_LEN)
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

    # Create mesh and object for the main bar
    mesh = bpy.data.meshes.new(PREFIX + "FlatBar_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(PREFIX + "FlatBar", mesh)
    _link(obj, collection)

    shade_smooth(obj)
    apply_transforms(obj)
    assign_material(obj, MAT_PLATE())

    # Now add lightening slots using boolean difference
    add_lightening_slots(obj, collection)

    return obj


def add_lightening_slots(bar_obj, collection):
    """
    Add lightening slots to the bar using boolean difference.
    Creates elongated rectangular cutouts along the bar's length.

    Args:
        bar_obj: the flat bar object to cut slots into
        collection: the collection to temporarily link slot cutters to
    """

    # Calculate slot positions along the bar length
    bar_len = THIGH_ROD_LEN
    slot_spacing = bar_len / (SLOT_COUNT + 1)  # Distribute slots evenly

    slot_positions = []
    for i in range(1, SLOT_COUNT + 1):
        slot_x = -bar_len / 2 + slot_spacing * i
        slot_positions.append(slot_x)

    # Use boolean modifier for each slot
    for i, slot_x in enumerate(slot_positions):
        # Create a slot cutter box
        slot_name = f"{PREFIX}SlotCutter_{i}"

        bm_slot = bmesh.new()

        # Create an elongated slot shape (rectangular)
        slot_half_len = mm(SLOT_LENGTH / 2)
        slot_half_w = mm(SLOT_WIDTH / 2)
        slot_height = mm(SLOT_DEPTH)

        # Position slot in upper half of bar
        slot_z = mm(0.5)

        # Create vertices for the slot box
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

        # Create faces for the box
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

        # Use boolean modifier to cut the slot from the bar
        bpy.context.view_layer.objects.active = bar_obj
        bar_obj.select_set(True)

        mod = bar_obj.modifiers.new(name=f"SlotCut_{i}", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = slot_obj

        # Apply the modifier
        bpy.ops.object.modifier_apply(modifier=mod.name)

        # Delete the temporary slot cutter
        bpy.data.objects.remove(slot_obj, do_unlink=True)
        if slot_mesh.users == 0:
            bpy.data.meshes.remove(slot_mesh)

        bar_obj.select_set(False)


def build_pivot_pin(name, collection, location_mm=(0.0, 0.0, 0.0)):
    """
    Build a single pivot pin (cylinder) for assembly context.
    Positioned vertically upward from rod surface, extending along Z axis.

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
    Build the complete thigh rod assembly:
    - Main flat bar with lightening slots (with rounded edges via bmesh capsule)
    - Two pivot pins at each end (standing vertically upward with 5mm inward offset)

    The bar is centered at origin:
      - X: -40.75mm to +40.75mm
      - Y: -3.0mm to +3.0mm (centered)
      - Z: -1.75mm to +1.75mm (centered)

    Pivot pins are positioned vertically upward from the bar top surface (Z+ direction):
      - X: ±35.75mm (5mm inward from bar ends)
      - Y: 0.0mm (center)
      - Z: 3.0mm (center of 2.5mm tall pin, base at rod top surface z=1.75mm)
    """

    # Build main bar with slots
    bar = build_flat_bar_with_slots(collection)

    # Calculate pivot pin positions
    pin_x_offset = THIGH_ROD_LEN / 2 - PIVOT_PIN_INWARD_OFFSET

    # Pivot pins positioned VERTICALLY UPWARD from the bar top surface
    # Front pivot (at x = -35.75mm, standing upward)
    front_pin = build_pivot_pin(
        f"{PREFIX}PivotPinFront",
        collection,
        location_mm=(-pin_x_offset, 0.0, PIVOT_PIN_Z_CENTER)
    )

    # Back pivot (at x = +35.75mm, standing upward)
    back_pin = build_pivot_pin(
        f"{PREFIX}PivotPinBack",
        collection,
        location_mm=(pin_x_offset, 0.0, PIVOT_PIN_Z_CENTER)
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
    Configure viewport for optimal ThighRod1 viewing:
    - Hide the Cube object from the viewport
    - Frame the ThighRod1 collection in view
    - Set appropriate zoom level for inspection
    """
    # Hide Cube object
    if "Cube" in bpy.data.objects:
        cube = bpy.data.objects["Cube"]
        cube.hide_viewport = True
        cube.hide_render = True
        print("✓ Hidden Cube from viewport")

    # Frame the ThighRod1 model in view
    if COLLECTION_NAME in bpy.data.collections:
        collection = bpy.data.collections[COLLECTION_NAME]

        # Select all objects in ThighRod1 collection
        for obj in collection.objects:
            obj.select_set(True)

        # Make one object active
        if collection.objects:
            bpy.context.view_layer.objects.active = collection.objects[0]

        # Frame all selected objects
        try:
            bpy.ops.view3d.view_all(center=True)
            print("✓ Framed ThighRod1 model in viewport")
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
                    if hasattr(space, 'region_3d') and space.region_3d:
                        if hasattr(space.region_3d, 'view_distance'):
                            space.region_3d.view_distance = 0.2
                            print("✓ Set view distance for optimal visibility")

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
    print(f"✓ Built ThighRod1 assembly with {len(assembly)} components")
    print(f"  - Main bar: 81.5mm × 6.0mm × 3.5mm with {SLOT_COUNT} lightening slots")
    print(f"  - Pivot pins stand VERTICALLY UPWARD (5mm inward from rod ends)")
    print(f"  - Front pin at x=-{THIGH_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET}mm, y=0mm, z={PIVOT_PIN_Z_CENTER}mm")
    print(f"  - Back pin at x=+{THIGH_ROD_LEN/2 - PIVOT_PIN_INWARD_OFFSET}mm, y=0mm, z={PIVOT_PIN_Z_CENTER}mm")

    # Configure viewport
    configure_viewport()

    # Save .blend file when running headless
    if bpy.app.background:
        output_path = "/home/pluto-atom-4/blender-workspace/blender-project/renders/thigh_rod1.blend"
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
