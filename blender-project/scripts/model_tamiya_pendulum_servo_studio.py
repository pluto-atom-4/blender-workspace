"""Studio-quality parametric two-wheeled inverted pendulum robot, sized for
the Tamiya 55mm Slim Tire Set (Tamiya 70193) and driven by two Dynamixel
XL330 smart servos. All dimensions are millimeters.

Builds on model_tamiya_pendulum_servo_precise.py, adding: 0.5mm edge
bevels + Weighted Normal shading on structural plates, a motor output horn
boss, a 4-hole M2 bracket bolt pattern, exact PBR material values, explicit
collision/clearance verification, and a built-in studio camera + 3-point
light rig so the .blend is viewport-render-ready immediately after
generation.
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

TIRE_OD = 55.0
TIRE_ID = 49.0
WHEEL_WIDTH = 3.5
HUB_OD = 12.0
HUB_HEX_AF = 3.0
RIM_SPOKE_COUNT = 5
RIM_SPOKE_WIDTH = 4.0
RIM_SPOKE_EDGE_MARGIN = 2.0

WHEEL_RADIUS = TIRE_OD / 2.0
TIRE_ID_RADIUS = TIRE_ID / 2.0
HUB_RADIUS = HUB_OD / 2.0
HEX_CIRCUMRADIUS = HUB_HEX_AF / math.sqrt(3)

AXLE_LENGTH = 100.0
AXLE_ACROSS_FLATS = HUB_HEX_AF
AXLE_CIRCUMRADIUS = AXLE_ACROSS_FLATS / math.sqrt(3)

HUB_ADAPTER_DIAMETER = 14.0
HUB_ADAPTER_LENGTH = 4.0

# Motor output horn boss -- represents the actual rotating horn interface,
# sits flush between each hub adapter and its XL330 actuator.
HORN_BOSS_DIAMETER = 12.0
HORN_BOSS_DEPTH = 2.0

XL330_WIDTH = 20.0        # Y
XL330_HEIGHT = 34.0       # Z
XL330_DEPTH = 26.0        # X, along the output-shaft axis

BALSA_THICKNESS = 3.0
POLY_THICKNESS = 5.0
CHASSIS_WIDTH = 85.0
CHASSIS_WHEEL_GAP = 2.0
DECK_CORNER_RADIUS = 5.0
DECK_SLOT_WIDTH = 3.0
DECK_SLOT_DEPTH = 5.0

BEVEL_RADIUS = 0.5        # global edge bevel/fillet on structural plates

WHEEL_X = CHASSIS_WIDTH / 2.0 + CHASSIS_WHEEL_GAP + WHEEL_WIDTH / 2.0

AXLE_Z = WHEEL_RADIUS

LOWER_DECK_WIDTH = CHASSIS_WIDTH
LOWER_DECK_DEPTH = 60.0

ACTUATOR_Z_BOTTOM = AXLE_Z - XL330_HEIGHT / 2.0
ACTUATOR_Z_TOP = AXLE_Z + XL330_HEIGHT / 2.0

MOUNT_Z_BOTTOM = ACTUATOR_Z_TOP
MOUNT_Z_TOP = MOUNT_Z_BOTTOM + POLY_THICKNESS
MOUNT_Z_CENTER = (MOUNT_Z_BOTTOM + MOUNT_Z_TOP) / 2.0
MOUNT_HOLE_DIAMETER = 2.0            # M2 clearance hole
MOUNT_HOLE_INSET = 5.0               # from bracket edge, both axes

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
# Materials (exact PBR values from the quality-improvement spec)
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def get_material(name, base_color, metallic=0.0, roughness=0.5, specular=0.5, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = specular
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = 'BLEND'
    return mat


MAT_BALSA = get_material("Balsa_Wood", hex_to_rgb("D2B48C"), roughness=0.85, specular=0.1)
MAT_POLY = get_material("Poly_Bracket", hex_to_rgb("1A1A1A"), roughness=0.35, specular=0.5)
MAT_RUBBER = get_material("Tire_Rubber", hex_to_rgb("222222"), roughness=0.9)
MAT_STEEL = get_material("Metal_Steel", hex_to_rgb("CCCCCC"), metallic=1.0, roughness=0.2)
MAT_RIM_PLASTIC = get_material("Rim_Plastic", (0.55, 0.56, 0.60), roughness=0.35)
MAT_SERVO_CASE = get_material("Dynamixel_Case", (0.07, 0.07, 0.08), roughness=0.45)


def assign_material(obj, mat):
    obj.data.materials.append(mat)


def smooth_shade(obj, angle_deg=30.0):
    """Auto-smooth equivalent for cylindrical parts (wheels, axle, hubs,
    standoffs) -- eliminates visible flat polygon facets."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))


def refine_structural(obj, bevel_width=BEVEL_RADIUS, segments=2):
    """Bevel -> Weighted Normal, for flat-faced structural plates (decks,
    brackets, actuator bodies) -- crisp, realistic edge highlights."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.shade_smooth()

    bevel = obj.modifiers.new("Bevel", type='BEVEL')
    bevel.width = bevel_width
    bevel.segments = segments
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(35.0)
    bpy.ops.object.modifier_apply(modifier=bevel.name)

    wn = obj.modifiers.new("WeightedNormal", type='WEIGHTED_NORMAL')
    wn.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=wn.name)


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
# Horn-to-wheel adapter hubs + motor horn bosses + XL330 actuators + mounts
# ---------------------------------------------------------------------------

hub_adapters = {}
horn_bosses = {}
actuators = {}
actuator_centers = {}

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

    # Motor output horn boss -- flush between the hub adapter and the
    # actuator, representing the real rotating horn interface.
    boss_outer_x = hub_inner_x
    boss_inner_x = boss_outer_x - x_sign * HORN_BOSS_DEPTH
    boss_center_x = (boss_outer_x + boss_inner_x) / 2.0
    boss = add_cylinder(
        f"Motor_Horn_Boss_{side}", HORN_BOSS_DIAMETER / 2.0, HORN_BOSS_DEPTH,
        (boss_center_x, 0.0, AXLE_Z), axis='X',
    )
    boss_bore = add_cylinder(
        "__boss_bore", HEX_CIRCUMRADIUS, HORN_BOSS_DEPTH + 1.0,
        (boss_center_x, 0.0, AXLE_Z), vertices=6, axis='X',
    )
    boolean_diff(boss, boss_bore)
    assign_material(boss, MAT_STEEL)
    smooth_shade(boss)
    created.append(boss)
    horn_bosses[side] = boss

    actuator_outer_x = boss_inner_x
    actuator_inner_x = actuator_outer_x - x_sign * XL330_DEPTH
    actuator_center_x = (actuator_outer_x + actuator_inner_x) / 2.0
    actuator_centers[side] = actuator_center_x
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
    refine_structural(actuator)
    created.append(actuator)
    actuators[side] = actuator

    mount = add_box(
        f"Poly_Motor_Mount_{side}",
        (XL330_DEPTH, XL330_WIDTH, POLY_THICKNESS),
        (actuator_center_x, 0.0, MOUNT_Z_CENTER),
    )
    for hole_x_sign in (-1.0, 1.0):
        for hole_y_sign in (-1.0, 1.0):
            hole_x = actuator_center_x + hole_x_sign * (XL330_DEPTH / 2.0 - MOUNT_HOLE_INSET)
            hole_y = hole_y_sign * (XL330_WIDTH / 2.0 - MOUNT_HOLE_INSET)
            hole = add_cylinder(
                f"__mount_hole_{side}_{hole_x_sign}_{hole_y_sign}",
                MOUNT_HOLE_DIAMETER / 2.0, POLY_THICKNESS + 2.0,
                (hole_x, hole_y, MOUNT_Z_CENTER), vertices=24,
            )
            boolean_diff(mount, hole)
    assign_material(mount, MAT_POLY)
    refine_structural(mount)
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
refine_structural(lower_deck)
created.append(lower_deck)

upper_deck = add_rounded_plate("Balsa_Upper_Deck", UPPER_DECK_WIDTH,
                                UPPER_DECK_DEPTH, BALSA_THICKNESS,
                                DECK_CORNER_RADIUS, UPPER_DECK_Z_BOTTOM)
cut_corner_slots(upper_deck, UPPER_DECK_DEPTH, BALSA_THICKNESS,
                  UPPER_DECK_Z_BOTTOM, STANDOFF_X, STANDOFF_Y)
assign_material(upper_deck, MAT_BALSA)
refine_structural(upper_deck)
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
# fit: axle passing through wheel -> hub adapter -> horn boss -> actuator)
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
    "boss_L": [horn_bosses["Left"]],
    "boss_R": [horn_bosses["Right"]],
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

ALLOWED_GROUP_OVERLAPS = set()
for side_key in ("L", "R"):
    for part in ("wheel", "hub", "boss", "actuator"):
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
print(f"Actuator Z: {ACTUATOR_Z_BOTTOM:.2f} - {ACTUATOR_Z_TOP:.2f} mm")
print(f"Lower deck Z: {LOWER_DECK_Z_BOTTOM:.2f} - {LOWER_DECK_Z_TOP:.2f} mm")
print(f"Upper deck Z: {UPPER_DECK_Z_BOTTOM:.2f} - {UPPER_DECK_Z_TOP:.2f} mm")
if clashes:
    print(f"CLASH CHECK: FAILED, {len(clashes)} overlapping sub-assembly pair(s):")
    for a, b in clashes:
        print(f"  {a} <-> {b}")
else:
    print("CLASH CHECK: PASSED, no unintended overlap between sub-assemblies.")

# Explicit spec'd checks -------------------------------------------------

actuator_gap = group_boxes["actuator_R"][0] - group_boxes["actuator_L"][1]  # R.min_x - L.max_x
if boxes_overlap(group_boxes["actuator_L"], group_boxes["actuator_R"]):
    print(f"WARNING: Left/Right Dynamixel actuators intersect (gap {actuator_gap:.2f} mm)")
else:
    print(f"Actuator L/R clearance check: PASSED (gap = {actuator_gap:.2f} mm)")

# Horizontal gap between each wheel's inner face and the lower deck edge.
left_gap = abs(group_boxes["wheel_L"][1]) - LOWER_DECK_WIDTH / 2.0
right_gap = group_boxes["wheel_R"][0] - LOWER_DECK_WIDTH / 2.0
min_tire_gap = min(left_gap, right_gap)
if min_tire_gap < 2.0:
    print(f"WARNING: tire-to-deck clearance {min_tire_gap:.2f} mm is below the 2.0 mm minimum")
else:
    print(f"Tire-to-deck clearance check: PASSED (clearance = {min_tire_gap:.2f} mm, "
          f"{'at the 2.0mm floor -- zero margin' if min_tire_gap < 2.05 else 'comfortable margin'})")
print("=" * 70)


# ---------------------------------------------------------------------------
# Studio camera + 3-point light rig, targeting the root empty directly
# ---------------------------------------------------------------------------

def add_studio_light(name, location, energy, rotation_euler):
    """SUN lamp: distance-independent, so it stays reliably bright at this
    model's mm scale regardless of camera/light placement distance (unlike
    AREA/POINT lights, whose inverse-square falloff makes them read as
    hundreds of meters away here and go nearly black)."""
    bpy.ops.object.light_add(type='SUN', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.rotation_euler = rotation_euler
    return light


scene = bpy.context.scene
mid_z = TOTAL_HEIGHT / 2.0

bpy.ops.object.camera_add(location=(280.0, -280.0, mid_z + 180.0))
camera = bpy.context.active_object
camera.name = "Studio_Camera_Isometric"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 340.0
cam_constraint = camera.constraints.new(type='TRACK_TO')
cam_constraint.target = root
cam_constraint.track_axis = 'TRACK_NEGATIVE_Z'
cam_constraint.up_axis = 'UP_Y'
scene.camera = camera

add_studio_light("Key_Light", (280.0, -280.0, mid_z + 220.0), 3.5,
                  (math.radians(45.0), 0.0, math.radians(45.0)))
add_studio_light("Fill_Light", (-280.0, -180.0, mid_z + 120.0), 1.5,
                  (math.radians(55.0), 0.0, math.radians(-120.0)))
add_studio_light("Rim_Light", (0.0, 280.0, mid_z + 180.0), 2.0,
                  (math.radians(60.0), 0.0, math.radians(200.0)))

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_servo_studio.blend",
    check_existing=False,
)
