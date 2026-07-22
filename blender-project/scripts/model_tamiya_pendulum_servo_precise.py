"""High-fidelity parametric two-wheeled inverted pendulum robot, sized for
the Tamiya 55mm Slim Tire Set (Tamiya 70193) and driven by two Dynamixel
XL330 smart servos. All dimensions are millimeters.

Merges the wheel/deck/bracket precision techniques from
model_tamiya_pendulum_precise.py (multi-part tread/rim/hub wheels,
rounded-corner decks with interlocking slots, M2 mounting holes,
per-material shading) with the XL330 actuator layout from
model_tamiya_pendulum.py (hex-bored hub adapters, actuator bodies, and the
100mm alignment backbone axle that telescopes through both drivetrains).
"""

import bpy
import bmesh
import math

# ---------------------------------------------------------------------------
# Scene setup
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for data_block_collection in (
        bpy.data.meshes, bpy.data.curves, bpy.data.metaballs,
        bpy.data.armatures, bpy.data.lights, bpy.data.cameras,
        bpy.data.materials,
    ):
        for block in list(data_block_collection):
            if block.users == 0:
                data_block_collection.remove(block)


def set_units_mm():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 0.001  # 1 Blender unit == 1 mm


clear_scene()
set_units_mm()


# ---------------------------------------------------------------------------
# Hardware & material globals (mm)
# ---------------------------------------------------------------------------

# Wheel (3-part assembly)
TIRE_OD = 55.0
TIRE_ID = 49.0
WHEEL_WIDTH = 3.5
HUB_OD = 12.0
HUB_HEX_AF = 3.0                    # hex bore, across-flats -- shared by the
                                     # wheel hub, adapter hub, and actuator
RIM_SPOKE_COUNT = 5
RIM_SPOKE_WIDTH = 4.0
RIM_SPOKE_EDGE_MARGIN = 2.0

WHEEL_RADIUS = TIRE_OD / 2.0
TIRE_ID_RADIUS = TIRE_ID / 2.0
HUB_RADIUS = HUB_OD / 2.0
HEX_CIRCUMRADIUS = HUB_HEX_AF / math.sqrt(3)

# Axle -- structural alignment backbone between the two actuator outputs
AXLE_LENGTH = 100.0
AXLE_ACROSS_FLATS = HUB_HEX_AF
AXLE_CIRCUMRADIUS = AXLE_ACROSS_FLATS / math.sqrt(3)

# Horn-to-wheel adapter hub
HUB_ADAPTER_DIAMETER = 14.0
HUB_ADAPTER_LENGTH = 4.0

# Dynamixel XL330 smart servo body envelope
XL330_WIDTH = 20.0        # Y
XL330_HEIGHT = 34.0       # Z
XL330_DEPTH = 26.0        # X, along the output-shaft axis

# Chassis / decks (balsa)
BALSA_THICKNESS = 3.0
CHASSIS_WIDTH = 85.0
CHASSIS_WHEEL_GAP = 2.0
DECK_CORNER_RADIUS = 5.0
DECK_SLOT_WIDTH = 3.0
DECK_SLOT_DEPTH = 5.0

WHEEL_X = CHASSIS_WIDTH / 2.0 + CHASSIS_WHEEL_GAP + WHEEL_WIDTH / 2.0

# Ground reference: wheel bottom on Z = 0, so the wheel/axle/actuator shaft
# centerline sits one wheel-radius up. The XL330 output horn is assumed
# centered on the actuator's own W x H cross-section (no offset given in the
# hardware spec), so the actuator body straddles that same centerline.
AXLE_Z = WHEEL_RADIUS

LOWER_DECK_WIDTH = CHASSIS_WIDTH
LOWER_DECK_DEPTH = 60.0

ACTUATOR_Z_BOTTOM = AXLE_Z - XL330_HEIGHT / 2.0
ACTUATOR_Z_TOP = AXLE_Z + XL330_HEIGHT / 2.0

POLY_THICKNESS = 5.0
MOUNT_Z_BOTTOM = ACTUATOR_Z_TOP
MOUNT_Z_TOP = MOUNT_Z_BOTTOM + POLY_THICKNESS
MOUNT_Z_CENTER = (MOUNT_Z_BOTTOM + MOUNT_Z_TOP) / 2.0
MOUNT_HOLE_DIAMETER = 2.0            # M2 clearance hole
MOUNT_HOLE_INSET = 5.0               # from bracket end

LOWER_DECK_Z_BOTTOM = MOUNT_Z_TOP
LOWER_DECK_Z_TOP = LOWER_DECK_Z_BOTTOM + BALSA_THICKNESS
LOWER_DECK_Z_CENTER = (LOWER_DECK_Z_BOTTOM + LOWER_DECK_Z_TOP) / 2.0

UPPER_DECK_WIDTH = CHASSIS_WIDTH
UPPER_DECK_DEPTH = LOWER_DECK_DEPTH
UPPER_DECK_STANDOFF_HEIGHT = 50.0
UPPER_DECK_Z_BOTTOM = LOWER_DECK_Z_TOP + UPPER_DECK_STANDOFF_HEIGHT
UPPER_DECK_Z_TOP = UPPER_DECK_Z_BOTTOM + BALSA_THICKNESS
UPPER_DECK_Z_CENTER = (UPPER_DECK_Z_BOTTOM + UPPER_DECK_Z_TOP) / 2.0

STANDOFF_DIAMETER = 4.0
STANDOFF_INSET = 10.0
STANDOFF_X = UPPER_DECK_WIDTH / 2.0 - STANDOFF_INSET
STANDOFF_Y = UPPER_DECK_DEPTH / 2.0 - STANDOFF_INSET
STANDOFF_Z_CENTER = (LOWER_DECK_Z_TOP + UPPER_DECK_Z_BOTTOM) / 2.0

TOTAL_HEIGHT = UPPER_DECK_Z_TOP


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def get_material(name, base_color, metallic=0.0, roughness=0.5, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = 'BLEND'
    return mat


MAT_BALSA = get_material("Balsa_Wood", (0.80, 0.64, 0.40), roughness=0.65)
MAT_POLY = get_material("Poly_White", (0.92, 0.93, 0.95), roughness=0.35, alpha=0.55)
MAT_RUBBER = get_material("Tire_Rubber", (0.03, 0.03, 0.035), roughness=0.9)
MAT_STEEL = get_material("Hex_Steel", (0.72, 0.73, 0.76), metallic=1.0, roughness=0.15)
MAT_RIM_PLASTIC = get_material("Rim_Plastic", (0.55, 0.56, 0.60), roughness=0.35)
MAT_SERVO_CASE = get_material("Dynamixel_Case", (0.07, 0.07, 0.08), roughness=0.45)


def assign_material(obj, mat):
    obj.data.materials.append(mat)


def smooth_shade(obj, angle_deg=30.0):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def add_box(name, size, location, rotation_euler=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    obj.rotation_euler = rotation_euler
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


def add_cylinder(name, radius, depth, location, vertices=32, axis='Z'):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    if axis == 'X':
        obj.rotation_euler = (0.0, math.radians(90.0), 0.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def boolean_diff(target, cutter):
    mod = target.modifiers.new(name="bool_cut", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mesh_data = cutter.data
    bpy.data.objects.remove(cutter, do_unlink=True)
    if mesh_data.users == 0:
        bpy.data.meshes.remove(mesh_data)


def add_rounded_plate(name, width, depth, thickness, radius, z_bottom, segments=8):
    """Rounded-rectangle plate, footprint centered at world (0, 0), extruded
    from z_bottom to z_bottom + thickness."""
    hw, hd = width / 2.0, depth / 2.0
    corners = [
        (hw - radius, hd - radius, 0.0),
        (-(hw - radius), hd - radius, 90.0),
        (-(hw - radius), -(hd - radius), 180.0),
        (hw - radius, -(hd - radius), 270.0),
    ]
    bm = bmesh.new()
    verts = []
    for cx, cy, start_deg in corners:
        for i in range(segments + 1):
            ang = math.radians(start_deg + 90.0 * i / segments)
            verts.append(bm.verts.new((cx + radius * math.cos(ang),
                                        cy + radius * math.sin(ang), 0.0)))
    face = bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    top_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top_verts, vec=(0.0, 0.0, thickness))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0.0, 0.0, z_bottom)
    return obj


def cut_corner_slots(plate, depth, thickness, z_bottom, slot_x, slot_y):
    """Cut 3mm x 5mm interlocking tab slots into the plate edge nearest each
    standoff position (x = +/-slot_x, y = +/-slot_y)."""
    overhang = 2.0
    margin = 2.0
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            y_edge = y_sign * (depth / 2.0)
            if y_sign > 0:
                y_min, y_max = y_edge - DECK_SLOT_DEPTH, y_edge + overhang
            else:
                y_min, y_max = y_edge - overhang, y_edge + DECK_SLOT_DEPTH
            cutter = add_box(
                f"__slot_cut_{x_sign}_{y_sign}",
                (DECK_SLOT_WIDTH, y_max - y_min, thickness + 2 * margin),
                (x_sign * slot_x, (y_min + y_max) / 2.0,
                 z_bottom + thickness / 2.0),
            )
            boolean_diff(plate, cutter)


# ---------------------------------------------------------------------------
# Root empty
# ---------------------------------------------------------------------------

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, 0.0))
root = bpy.context.active_object
root.name = "Tamiya_Inverted_Pendulum"

created = []


# ---------------------------------------------------------------------------
# Wheels: tread ring + spoked rim + hex-bored hub
# ---------------------------------------------------------------------------

def build_wheel(side, x_sign):
    wheel_x = x_sign * WHEEL_X

    tread = add_cylinder(f"Tamiya_55mm_{side}_Wheel_Tread", WHEEL_RADIUS,
                          WHEEL_WIDTH, (wheel_x, 0.0, AXLE_Z), axis='X')
    tread_hole = add_cylinder("__tread_bore", TIRE_ID_RADIUS, WHEEL_WIDTH + 1.0,
                               (wheel_x, 0.0, AXLE_Z), axis='X')
    boolean_diff(tread, tread_hole)
    assign_material(tread, MAT_RUBBER)
    smooth_shade(tread)
    created.append(tread)

    rim = add_cylinder(f"{side}_Wheel_Rim", TIRE_ID_RADIUS, WHEEL_WIDTH,
                        (wheel_x, 0.0, AXLE_Z), axis='X')
    rim_bore = add_cylinder("__rim_bore", HUB_RADIUS, WHEEL_WIDTH + 1.0,
                             (wheel_x, 0.0, AXLE_Z), axis='X')
    boolean_diff(rim, rim_bore)

    spoke_len = (TIRE_ID_RADIUS - HUB_RADIUS) - 2.0 * RIM_SPOKE_EDGE_MARGIN
    mid_r = (HUB_RADIUS + RIM_SPOKE_EDGE_MARGIN + TIRE_ID_RADIUS - RIM_SPOKE_EDGE_MARGIN) / 2.0
    for i in range(RIM_SPOKE_COUNT):
        theta = 2.0 * math.pi * i / RIM_SPOKE_COUNT
        cy, cz = mid_r * math.cos(theta), mid_r * math.sin(theta)
        spoke_cut = add_box(
            f"__spoke_cut_{side}_{i}",
            (WHEEL_WIDTH + 1.0, spoke_len, RIM_SPOKE_WIDTH),
            (wheel_x, cy, AXLE_Z + cz),
            rotation_euler=(theta, 0.0, 0.0),
        )
        boolean_diff(rim, spoke_cut)
    assign_material(rim, MAT_RIM_PLASTIC)
    smooth_shade(rim)
    created.append(rim)

    hub = add_cylinder(f"{side}_Wheel_Hub", HUB_RADIUS, WHEEL_WIDTH,
                        (wheel_x, 0.0, AXLE_Z), axis='X')
    hex_hole = add_cylinder("__hex_bore", HEX_CIRCUMRADIUS, WHEEL_WIDTH + 1.0,
                             (wheel_x, 0.0, AXLE_Z), vertices=6, axis='X')
    boolean_diff(hub, hex_hole)
    assign_material(hub, MAT_RIM_PLASTIC)
    smooth_shade(hub)
    created.append(hub)

    return tread, rim, hub


left_wheel = build_wheel("Left", -1.0)
right_wheel = build_wheel("Right", 1.0)


# ---------------------------------------------------------------------------
# Horn-to-wheel adapter hubs + XL330 actuators + motor mounts, hex-bored
# to pass the alignment axle cleanly through each drivetrain.
# ---------------------------------------------------------------------------

hub_adapters = {}
actuators = {}

for side, x_sign in (("Left", -1.0), ("Right", 1.0)):
    wheel_inner_x = x_sign * (WHEEL_X - WHEEL_WIDTH / 2.0)

    hub_outer_x = wheel_inner_x
    hub_inner_x = hub_outer_x - x_sign * HUB_ADAPTER_LENGTH
    hub_center_x = (hub_outer_x + hub_inner_x) / 2.0
    hub_adapter = add_cylinder(
        f"Wheel_Hub_Adapter_{side}", HUB_ADAPTER_DIAMETER / 2.0,
        HUB_ADAPTER_LENGTH, (hub_center_x, 0.0, AXLE_Z), axis='X',
    )
    hub_adapter_bore = add_cylinder(
        "__hub_adapter_bore", HEX_CIRCUMRADIUS, HUB_ADAPTER_LENGTH + 1.0,
        (hub_center_x, 0.0, AXLE_Z), vertices=6, axis='X',
    )
    boolean_diff(hub_adapter, hub_adapter_bore)
    assign_material(hub_adapter, MAT_RIM_PLASTIC)
    smooth_shade(hub_adapter)
    created.append(hub_adapter)
    hub_adapters[side] = hub_adapter

    actuator_outer_x = hub_inner_x
    actuator_inner_x = actuator_outer_x - x_sign * XL330_DEPTH
    actuator_center_x = (actuator_outer_x + actuator_inner_x) / 2.0
    actuator = add_box(
        f"Dynamixel_XL330_{side}",
        (XL330_DEPTH, XL330_WIDTH, XL330_HEIGHT),
        (actuator_center_x, 0.0, AXLE_Z),
    )
    actuator_bore = add_cylinder(
        "__actuator_bore", HEX_CIRCUMRADIUS, XL330_DEPTH + 1.0,
        (actuator_center_x, 0.0, AXLE_Z), vertices=6, axis='X',
    )
    boolean_diff(actuator, actuator_bore)
    assign_material(actuator, MAT_SERVO_CASE)
    created.append(actuator)
    actuators[side] = actuator

    mount = add_box(
        f"Poly_Motor_Mount_{side}",
        (XL330_DEPTH, XL330_WIDTH, POLY_THICKNESS),
        (actuator_center_x, 0.0, MOUNT_Z_CENTER),
    )
    for hole_sign in (-1.0, 1.0):
        hole_x = actuator_center_x + hole_sign * (XL330_DEPTH / 2.0 - MOUNT_HOLE_INSET)
        hole = add_cylinder(
            f"__mount_hole_{side}_{hole_sign}",
            MOUNT_HOLE_DIAMETER / 2.0, POLY_THICKNESS + 2.0,
            (hole_x, 0.0, MOUNT_Z_CENTER), vertices=24,
        )
        boolean_diff(mount, hole)
    assign_material(mount, MAT_POLY)
    created.append(mount)


# ---------------------------------------------------------------------------
# Hex axle
# ---------------------------------------------------------------------------

axle = add_cylinder("Hex_Axle_100mm", AXLE_CIRCUMRADIUS, AXLE_LENGTH,
                     (0.0, 0.0, AXLE_Z), vertices=6, axis='X')
assign_material(axle, MAT_STEEL)
smooth_shade(axle)
created.append(axle)


# ---------------------------------------------------------------------------
# Decks (balsa): rounded corners + interlocking standoff slots
# ---------------------------------------------------------------------------

lower_deck = add_rounded_plate("Balsa_Lower_Deck", LOWER_DECK_WIDTH,
                                LOWER_DECK_DEPTH, BALSA_THICKNESS,
                                DECK_CORNER_RADIUS, LOWER_DECK_Z_BOTTOM)
cut_corner_slots(lower_deck, LOWER_DECK_DEPTH, BALSA_THICKNESS,
                  LOWER_DECK_Z_BOTTOM, STANDOFF_X, STANDOFF_Y)
assign_material(lower_deck, MAT_BALSA)
smooth_shade(lower_deck, angle_deg=20.0)
created.append(lower_deck)

upper_deck = add_rounded_plate("Balsa_Upper_Deck", UPPER_DECK_WIDTH,
                                UPPER_DECK_DEPTH, BALSA_THICKNESS,
                                DECK_CORNER_RADIUS, UPPER_DECK_Z_BOTTOM)
cut_corner_slots(upper_deck, UPPER_DECK_DEPTH, BALSA_THICKNESS,
                  UPPER_DECK_Z_BOTTOM, STANDOFF_X, STANDOFF_Y)
assign_material(upper_deck, MAT_BALSA)
smooth_shade(upper_deck, angle_deg=20.0)
created.append(upper_deck)


# ---------------------------------------------------------------------------
# Standoffs (steel pins)
# ---------------------------------------------------------------------------

standoffs = []
for x_sign in (-1.0, 1.0):
    for y_sign in (-1.0, 1.0):
        x_label = "L" if x_sign < 0 else "R"
        y_label = "B" if y_sign < 0 else "F"
        standoff = add_cylinder(
            f"Standoff_{x_label}{y_label}",
            STANDOFF_DIAMETER / 2.0, UPPER_DECK_STANDOFF_HEIGHT,
            (x_sign * STANDOFF_X, y_sign * STANDOFF_Y, STANDOFF_Z_CENTER),
            axis='Z',
        )
        assign_material(standoff, MAT_STEEL)
        smooth_shade(standoff)
        standoffs.append(standoff)
        created.append(standoff)


# ---------------------------------------------------------------------------
# Parent everything to the root empty, apply rotation + scale
# ---------------------------------------------------------------------------

for obj in created:
    obj.parent = root

bpy.ops.object.select_all(action='DESELECT')
for obj in created:
    obj.select_set(True)
bpy.context.view_layer.objects.active = created[0]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


# ---------------------------------------------------------------------------
# Structural clash check (group-level, ignores the intentional telescoping
# fit: axle passing through wheel -> hub adapter -> actuator on both sides)
# ---------------------------------------------------------------------------

def world_bbox(obj):
    corners = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in corners]; ys = [v.y for v in corners]; zs = [v.z for v in corners]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def union_bbox(objs):
    boxes = [world_bbox(o) for o in objs]
    return (min(b[0] for b in boxes), max(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes),
            min(b[4] for b in boxes), max(b[5] for b in boxes))


def boxes_overlap(a, b, eps=1e-6):
    ax0, ax1, ay0, ay1, az0, az1 = a
    bx0, bx1, by0, by1, bz0, bz1 = b
    return (ax0 < bx1 - eps and bx0 < ax1 - eps and
            ay0 < by1 - eps and by0 < ay1 - eps and
            az0 < bz1 - eps and bz0 < az1 - eps)


groups = {
    "wheel_L": list(left_wheel),
    "wheel_R": list(right_wheel),
    "hub_L": [hub_adapters["Left"]],
    "hub_R": [hub_adapters["Right"]],
    "actuator_L": [actuators["Left"]],
    "actuator_R": [actuators["Right"]],
    "axle": [axle],
    "mount_L": [o for o in created if o.name == "Poly_Motor_Mount_Left"],
    "mount_R": [o for o in created if o.name == "Poly_Motor_Mount_Right"],
    "lower_deck": [lower_deck],
    "upper_deck": [upper_deck],
    "standoffs": standoffs,
}
group_boxes = {k: union_bbox(v) for k, v in groups.items()}

# The 100mm axle intentionally telescopes through the wheel hub, the
# adapter hub, and the actuator body on both sides -- that is the design
# intent (a coaxial alignment backbone), not a clash.
ALLOWED_GROUP_OVERLAPS = set()
for side_key in ("L", "R"):
    for part in ("wheel", "hub", "actuator"):
        ALLOWED_GROUP_OVERLAPS.add(frozenset(("axle", f"{part}_{side_key}")))

clashes = []
names = list(group_boxes.keys())
for i, ga in enumerate(names):
    for gb in names[i + 1:]:
        if frozenset((ga, gb)) in ALLOWED_GROUP_OVERLAPS:
            continue
        if boxes_overlap(group_boxes[ga], group_boxes[gb]):
            clashes.append((ga, gb))

print("=" * 70)
print(f"TOTAL_HEIGHT (ground to top of upper deck): {TOTAL_HEIGHT:.2f} mm")
print(f"Wheel OD/ID: {TIRE_OD:.2f} / {TIRE_ID:.2f} mm | Hub OD: {HUB_OD:.2f} mm")
print(f"Actuator Z: {ACTUATOR_Z_BOTTOM:.2f} - {ACTUATOR_Z_TOP:.2f} mm")
print(f"Motor mount Z: {MOUNT_Z_BOTTOM:.2f} - {MOUNT_Z_TOP:.2f} mm")
print(f"Lower deck Z: {LOWER_DECK_Z_BOTTOM:.2f} - {LOWER_DECK_Z_TOP:.2f} mm")
print(f"Upper deck Z: {UPPER_DECK_Z_BOTTOM:.2f} - {UPPER_DECK_Z_TOP:.2f} mm")
if clashes:
    print(f"CLASH CHECK: FAILED, {len(clashes)} overlapping sub-assembly pair(s):")
    for a, b in clashes:
        print(f"  {a} <-> {b}")
else:
    print("CLASH CHECK: PASSED, no unintended overlap between sub-assemblies.")
    print("  (axle intentionally telescopes through wheel -> hub -> actuator)")


# ---------------------------------------------------------------------------
# Centers of mass (vertex centroid, world space) for the deck plates
# ---------------------------------------------------------------------------

def vertex_centroid(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    n = len(verts)
    cx = sum(v.x for v in verts) / n
    cy = sum(v.y for v in verts) / n
    cz = sum(v.z for v in verts) / n
    return (cx, cy, cz)


lower_com = vertex_centroid(lower_deck)
upper_com = vertex_centroid(upper_deck)
print(f"Lower deck Center of Mass: ({lower_com[0]:.4f}, {lower_com[1]:.4f}, {lower_com[2]:.4f}) mm")
print(f"Upper deck Center of Mass: ({upper_com[0]:.4f}, {upper_com[1]:.4f}, {upper_com[2]:.4f}) mm")
print("=" * 70)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_servo_precise.blend",
    check_existing=False,
)
