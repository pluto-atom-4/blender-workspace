"""Animated two-wheeled inverted pendulum: reuses the studio-quality asset
build from model_tamiya_pendulum_servo_studio.py, adds a sensor cap + LED
indicator and a ground plane, ports the 4-phase physics simulation from
assets/inverted_pendulum_simulation.py, and keyframes the whole thing across
144 frames (6 fps, 24s). All geometry dimensions are millimeters; the
physics engine runs in the reference's abstract units and is mapped to mm
only for translation (wheel spin is scale-invariant, see SIM_TO_MM below).
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
# Hardware globals (mm) -- identical to model_tamiya_pendulum_servo_studio.py
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

HORN_BOSS_DIAMETER = 12.0
HORN_BOSS_DEPTH = 2.0

XL330_WIDTH = 20.0
XL330_HEIGHT = 34.0
XL330_DEPTH = 26.0

BALSA_THICKNESS = 3.0
POLY_THICKNESS = 5.0
CHASSIS_WIDTH = 85.0
CHASSIS_WHEEL_GAP = 2.0
DECK_CORNER_RADIUS = 5.0
DECK_SLOT_WIDTH = 3.0
DECK_SLOT_DEPTH = 5.0

BEVEL_RADIUS = 0.5

WHEEL_X = CHASSIS_WIDTH / 2.0 + CHASSIS_WHEEL_GAP + WHEEL_WIDTH / 2.0
AXLE_Z = WHEEL_RADIUS

LOWER_DECK_WIDTH = CHASSIS_WIDTH
LOWER_DECK_DEPTH = 60.0

ACTUATOR_Z_BOTTOM = AXLE_Z - XL330_HEIGHT / 2.0
ACTUATOR_Z_TOP = AXLE_Z + XL330_HEIGHT / 2.0

MOUNT_Z_BOTTOM = ACTUATOR_Z_TOP
MOUNT_Z_TOP = MOUNT_Z_BOTTOM + POLY_THICKNESS
MOUNT_Z_CENTER = (MOUNT_Z_BOTTOM + MOUNT_Z_TOP) / 2.0
MOUNT_HOLE_DIAMETER = 2.0
MOUNT_HOLE_INSET = 5.0

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

# Sensor cap + LED, mounted on top of the upper deck
CAP_RADIUS = 6.0
CAP_HEIGHT = 4.0
CAP_Z_BOTTOM = UPPER_DECK_Z_TOP
LED_RADIUS = 2.0
LED_Z_CENTER = CAP_Z_BOTTOM + CAP_HEIGHT + LED_RADIUS * 0.6

GROUND_SIZE = 2000.0


# ---------------------------------------------------------------------------
# Physics simulation (ported from assets/inverted_pendulum_simulation.py --
# same equations, same gains, same disturbance frames; abstract units)
# ---------------------------------------------------------------------------

SIM_WHEEL_RADIUS = 0.3   # abstract units (the reference's "meters")
SIM_L = 1.0
SIM_G = 9.81
FPS = 6
TOTAL_FRAMES = 144
DT = 1.0 / FPS
SUB_STEPS = 10
S_DT = DT / SUB_STEPS

# Millimeters per abstract unit, derived from matching wheel radii. Only
# used for translation -- wheel spin angle = x / SIM_WHEEL_RADIUS is
# already scale-invariant.
SIM_TO_MM = WHEEL_RADIUS / SIM_WHEEL_RADIUS


def _sign(val):
    return 1.0 if val >= 0 else -1.0


def simulate_states():
    states = []

    # Phase 1: CONSTRUCTION (frames 0-24) -- static, model being built
    for f in range(25):
        states.append({
            "x": 0.0, "v": 0.0, "theta": 0.0, "omega": 0.0,
            "phase": "CONSTRUCTION", "p_progress": f / 24.0,
        })

    # Phase 2: NO CONTROL (frames 25-48) -- falling from initial tilt
    s2 = {"x": 0.0, "v": 0.0, "theta": 0.12, "omega": 0.0}
    for f in range(25, 49):
        for _ in range(SUB_STEPS):
            theta_accel = (SIM_G * math.sin(s2["theta"])) / SIM_L - 0.1 * s2["omega"]
            s2["omega"] += theta_accel * S_DT
            s2["theta"] += s2["omega"] * S_DT

            wheel_accel = -0.15 * SIM_G * math.sin(s2["theta"]) - 0.3 * s2["v"]
            s2["v"] += wheel_accel * S_DT
            s2["x"] += s2["v"] * S_DT

            if abs(s2["theta"]) >= math.pi / 2:
                s2["theta"] = _sign(s2["theta"]) * (math.pi / 2)
                s2["omega"] = -s2["omega"] * 0.35
                s2["v"] *= 0.2
        states.append({**s2, "phase": "NO CONTROL", "p_progress": 1.0})

    # Phase 3: UNSTABLE PID (frames 49-84) -- high Kp, low Kd, oscillates
    s3 = {"x": 0.0, "v": 0.0, "theta": 0.12, "omega": 0.0, "integral": 0.0}
    bad_kp, bad_ki, bad_kd = 7.5, 0.05, 0.1
    for f in range(49, 85):
        for _ in range(SUB_STEPS):
            error = s3["theta"]
            s3["integral"] += error * S_DT
            u = bad_kp * error + bad_ki * s3["integral"] + bad_kd * s3["omega"]
            u = max(-15.0, min(15.0, u))

            theta_accel = (SIM_G * math.sin(s3["theta"]) - math.cos(s3["theta"]) * u) / SIM_L - 0.05 * s3["omega"]
            s3["omega"] += theta_accel * S_DT
            s3["theta"] += s3["omega"] * S_DT

            s3["v"] += u * S_DT - 0.2 * s3["v"]
            s3["x"] += s3["v"] * S_DT

            if abs(s3["theta"]) >= math.pi / 2:
                s3["theta"] = _sign(s3["theta"]) * (math.pi / 2)
                s3["omega"] = 0.0
                s3["v"] = 0.0
        states.append({**s3, "phase": "UNSTABLE PID", "p_progress": 1.0})

    # Phase 4: STABLE PID with disturbance (frames 85-143)
    s4 = {"x": 0.0, "v": 0.0, "theta": 0.15, "omega": 0.0, "integral": 0.0, "target_x": 0.0}
    kp, ki, kd = 14.5, 0.3, 4.2
    pos_kp, pos_kd = 0.8, 1.2
    for f in range(85, TOTAL_FRAMES):
        if f == 115:
            s4["omega"] += 1.6  # punch disturbance
        if f >= 130:
            s4["target_x"] = 0.6  # position command shift

        for _ in range(SUB_STEPS):
            pos_err = s4["x"] - s4["target_x"]
            target_theta = -0.15 * math.tanh(pos_kp * pos_err + pos_kd * s4["v"])

            balance_err = s4["theta"] - target_theta
            s4["integral"] += balance_err * S_DT

            u = kp * balance_err + ki * s4["integral"] + kd * s4["omega"]
            u = max(-18.0, min(18.0, u))

            theta_accel = (SIM_G * math.sin(s4["theta"]) - math.cos(s4["theta"]) * u) / SIM_L - 0.1 * s4["omega"]
            s4["omega"] += theta_accel * S_DT
            s4["theta"] += s4["omega"] * S_DT

            s4["v"] += u * S_DT - 0.4 * s4["v"]
            s4["x"] += s4["v"] * S_DT

            if abs(s4["theta"]) >= math.pi / 2:
                s4["theta"] = _sign(s4["theta"]) * (math.pi / 2)
                s4["omega"] = 0.0
        states.append({**s4, "phase": "STABLE PID", "p_progress": 1.0})

    return states


def led_color_for(state):
    if abs(state["theta"]) > 0.4:
        return "ef4444"  # red
    if state["phase"] == "UNSTABLE PID":
        return "f59e0b"  # orange
    if state["phase"] == "CONSTRUCTION":
        return "3b82f6"  # blue
    return "22c55e"      # green


# ---------------------------------------------------------------------------
# Materials
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
MAT_GROUND = get_material("Ground_Plane", (0.03, 0.03, 0.035), roughness=0.95)

MAT_LED = bpy.data.materials.get("LED_Indicator") or bpy.data.materials.new("LED_Indicator")
MAT_LED.use_nodes = True
_led_bsdf = MAT_LED.node_tree.nodes.get("Principled BSDF")
_led_bsdf.inputs["Base Color"].default_value = (*hex_to_rgb("22c55e"), 1.0)
_led_bsdf.inputs["Emission Color"].default_value = (*hex_to_rgb("22c55e"), 1.0)
_led_bsdf.inputs["Emission Strength"].default_value = 3.0
_led_bsdf.inputs["Roughness"].default_value = 0.3


def assign_material(obj, mat):
    obj.data.materials.append(mat)


def smooth_shade(obj, angle_deg=30.0):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))


def refine_structural(obj, bevel_width=BEVEL_RADIUS, segments=2):
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
# Rig empties: root (X translate) -> chassis pivot (Y tilt) / wheel spins
# ---------------------------------------------------------------------------

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, 0.0))
root = bpy.context.active_object
root.name = "Tamiya_Inverted_Pendulum"

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, AXLE_Z))
chassis_pivot = bpy.context.active_object
chassis_pivot.name = "Chassis_Pivot"
chassis_pivot.parent = root

wheel_assemblies = {}
for side in ("Left", "Right"):
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, AXLE_Z))
    wa = bpy.context.active_object
    wa.name = f"Wheel_Assembly_{side}"
    wa.parent = root
    wheel_assemblies[side] = wa

chassis_parts = []   # tilts with Chassis_Pivot
spin_parts = {"Left": [], "Right": []}   # spins with its Wheel_Assembly


# ---------------------------------------------------------------------------
# Wheels: tread ring + spoked rim + hex-bored hub (spins with the wheel)
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

    hub = add_cylinder(f"{side}_Wheel_Hub", HUB_RADIUS, WHEEL_WIDTH,
                        (wheel_x, 0.0, AXLE_Z), axis='X')
    hex_hole = add_cylinder("__hex_bore", HEX_CIRCUMRADIUS, WHEEL_WIDTH + 1.0,
                             (wheel_x, 0.0, AXLE_Z), vertices=6, axis='X')
    boolean_diff(hub, hex_hole)
    assign_material(hub, MAT_RIM_PLASTIC)
    smooth_shade(hub)

    return [tread, rim, hub]


for side, x_sign in (("Left", -1.0), ("Right", 1.0)):
    spin_parts[side].extend(build_wheel(side, x_sign))


# ---------------------------------------------------------------------------
# Horn-to-wheel adapter hubs (spin) + motor horn bosses (spin) + XL330
# actuators (chassis) + motor mounts (chassis)
# ---------------------------------------------------------------------------

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
    spin_parts[side].append(hub_adapter)

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
    spin_parts[side].append(boss)

    actuator_outer_x = boss_inner_x
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
    refine_structural(actuator)
    chassis_parts.append(actuator)

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
    chassis_parts.append(mount)


# ---------------------------------------------------------------------------
# Hex axle (chassis -- structural/alignment, does not spin with the wheels)
# ---------------------------------------------------------------------------

axle = add_cylinder("Hex_Axle_100mm", AXLE_CIRCUMRADIUS, AXLE_LENGTH,
                     (0.0, 0.0, AXLE_Z), vertices=6, axis='X')
assign_material(axle, MAT_STEEL)
smooth_shade(axle)
chassis_parts.append(axle)


# ---------------------------------------------------------------------------
# Decks (chassis)
# ---------------------------------------------------------------------------

lower_deck = add_rounded_plate("Balsa_Lower_Deck", LOWER_DECK_WIDTH,
                                LOWER_DECK_DEPTH, BALSA_THICKNESS,
                                DECK_CORNER_RADIUS, LOWER_DECK_Z_BOTTOM)
cut_corner_slots(lower_deck, LOWER_DECK_DEPTH, BALSA_THICKNESS,
                  LOWER_DECK_Z_BOTTOM, STANDOFF_X, STANDOFF_Y)
assign_material(lower_deck, MAT_BALSA)
refine_structural(lower_deck)
chassis_parts.append(lower_deck)

upper_deck = add_rounded_plate("Balsa_Upper_Deck", UPPER_DECK_WIDTH,
                                UPPER_DECK_DEPTH, BALSA_THICKNESS,
                                DECK_CORNER_RADIUS, UPPER_DECK_Z_BOTTOM)
cut_corner_slots(upper_deck, UPPER_DECK_DEPTH, BALSA_THICKNESS,
                  UPPER_DECK_Z_BOTTOM, STANDOFF_X, STANDOFF_Y)
assign_material(upper_deck, MAT_BALSA)
refine_structural(upper_deck)
chassis_parts.append(upper_deck)

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
        chassis_parts.append(standoff)


# ---------------------------------------------------------------------------
# Sensor cap + LED indicator (chassis, mounted on top of the upper deck)
# ---------------------------------------------------------------------------

sensor_cap = add_cylinder("Sensor_Cap", CAP_RADIUS, CAP_HEIGHT,
                           (0.0, 0.0, CAP_Z_BOTTOM + CAP_HEIGHT / 2.0))
assign_material(sensor_cap, MAT_POLY)
smooth_shade(sensor_cap)
chassis_parts.append(sensor_cap)

led = add_cylinder("LED_Indicator", LED_RADIUS, LED_RADIUS,
                    (0.0, 0.0, LED_Z_CENTER))
assign_material(led, MAT_LED)
smooth_shade(led)
chassis_parts.append(led)


# ---------------------------------------------------------------------------
# Ground plane (static world geometry -- not part of the vehicle rig)
# ---------------------------------------------------------------------------

ground = add_box("Ground_Plane", (GROUND_SIZE, GROUND_SIZE, 2.0), (0.0, 0.0, -1.0))
assign_material(ground, MAT_GROUND)


# ---------------------------------------------------------------------------
# Parent into the rig, apply rotation + scale on the static mesh parts
# ---------------------------------------------------------------------------

for obj in chassis_parts:
    obj.parent = chassis_pivot
for side in ("Left", "Right"):
    for obj in spin_parts[side]:
        obj.parent = wheel_assemblies[side]

all_meshes = chassis_parts + spin_parts["Left"] + spin_parts["Right"] + [ground]
bpy.ops.object.select_all(action='DESELECT')
for obj in all_meshes:
    obj.select_set(True)
bpy.context.view_layer.objects.active = all_meshes[0]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


# ---------------------------------------------------------------------------
# Keyframe animation
# ---------------------------------------------------------------------------

def set_linear(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    for fcurve in obj.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'LINEAR'


def set_constant(mat):
    if not mat.node_tree.animation_data or not mat.node_tree.animation_data.action:
        return
    for fcurve in mat.node_tree.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'CONSTANT'


states = simulate_states()
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = TOTAL_FRAMES
scene.render.fps = FPS

prev_led_hex = None
for i, state in enumerate(states):
    frame = i + 1

    # Wheel spin axis is X (fixed by every prior script -- Left/Right wheels
    # sit at +/-WHEEL_X along X). Rolling contact on the X-Y ground plane
    # then only works out geometrically along Y, so travel is Y and chassis
    # tip (which must fall the way it rolls to catch itself) rotates about X.
    root.location.y = state["x"] * SIM_TO_MM
    root.keyframe_insert(data_path="location", index=1, frame=frame)

    chassis_pivot.rotation_euler.x = state["theta"]
    chassis_pivot.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)

    if state["phase"] == "CONSTRUCTION":
        chassis_scale = max(0.0, min(1.0, state["p_progress"] * 1.5))
        wheel_scale = max(0.0, min(1.0, (state["p_progress"] - 0.4) * 2.0))
    else:
        chassis_scale = 1.0
        wheel_scale = 1.0

    chassis_pivot.scale = (chassis_scale, chassis_scale, chassis_scale)
    chassis_pivot.keyframe_insert(data_path="scale", frame=frame)

    wheel_spin = state["x"] / SIM_WHEEL_RADIUS
    for side in ("Left", "Right"):
        wa = wheel_assemblies[side]
        wa.rotation_euler.x = wheel_spin
        wa.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
        wa.scale = (wheel_scale, wheel_scale, wheel_scale)
        wa.keyframe_insert(data_path="scale", frame=frame)

    led_hex = led_color_for(state)
    if led_hex != prev_led_hex:
        rgb = (*hex_to_rgb(led_hex), 1.0)
        _led_bsdf.inputs["Base Color"].default_value = rgb
        _led_bsdf.inputs["Base Color"].keyframe_insert(data_path="default_value", frame=frame)
        _led_bsdf.inputs["Emission Color"].default_value = rgb
        _led_bsdf.inputs["Emission Color"].keyframe_insert(data_path="default_value", frame=frame)
        prev_led_hex = led_hex

set_linear(root)
set_linear(chassis_pivot)
set_linear(wheel_assemblies["Left"])
set_linear(wheel_assemblies["Right"])
set_constant(MAT_LED)

scene.frame_set(1)


# ---------------------------------------------------------------------------
# Studio camera + 3-point light rig -- static, wide enough for the full
# travel range (SUN lights: AREA went nearly black at this mm scale, see
# model_tamiya_pendulum_servo_studio.py for that fix)
# ---------------------------------------------------------------------------

mid_z = TOTAL_HEIGHT / 2.0

bpy.ops.object.camera_add(location=(320.0, -320.0, mid_z + 200.0))
camera = bpy.context.active_object
camera.name = "Studio_Camera_Isometric"
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 500.0
cam_constraint = camera.constraints.new(type='TRACK_TO')
cam_constraint.target = root
cam_constraint.track_axis = 'TRACK_NEGATIVE_Z'
cam_constraint.up_axis = 'UP_Y'
scene.camera = camera


def add_studio_light(name, location, energy, rotation_euler):
    bpy.ops.object.light_add(type='SUN', location=location)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.rotation_euler = rotation_euler
    return light


add_studio_light("Key_Light", (280.0, -280.0, mid_z + 220.0), 3.5,
                  (math.radians(45.0), 0.0, math.radians(45.0)))
add_studio_light("Fill_Light", (-280.0, -180.0, mid_z + 120.0), 1.5,
                  (math.radians(55.0), 0.0, math.radians(-120.0)))
add_studio_light("Rim_Light", (0.0, 280.0, mid_z + 180.0), 2.0,
                  (math.radians(60.0), 0.0, math.radians(200.0)))

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)


# ---------------------------------------------------------------------------
# Clash check at the fully-assembled rest pose (frame 1, pre-construction
# scale collapses everything to zero, so evaluate against the geometry
# itself before the construction-reveal scale keyframes are considered)
# ---------------------------------------------------------------------------

def world_bbox(obj):
    corners = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in corners]; ys = [v.y for v in corners]; zs = [v.z for v in corners]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def boxes_overlap(a, b, eps=1e-6):
    ax0, ax1, ay0, ay1, az0, az1 = a
    bx0, bx1, by0, by1, bz0, bz1 = b
    return (ax0 < bx1 - eps and bx0 < ax1 - eps and
            ay0 < by1 - eps and by0 < ay1 - eps and
            az0 < bz1 - eps and bz0 < az1 - eps)


chassis_pivot.scale = (1.0, 1.0, 1.0)
wheel_assemblies["Left"].scale = (1.0, 1.0, 1.0)
wheel_assemblies["Right"].scale = (1.0, 1.0, 1.0)
bpy.context.view_layer.update()

actuator_L_box = world_bbox(bpy.data.objects["Dynamixel_XL330_Left"])
actuator_R_box = world_bbox(bpy.data.objects["Dynamixel_XL330_Right"])
actuator_clash = boxes_overlap(actuator_L_box, actuator_R_box)

print("=" * 70)
print(f"TOTAL_HEIGHT (ground to top of upper deck): {TOTAL_HEIGHT:.2f} mm")
print(f"SIM_TO_MM scale factor: {SIM_TO_MM:.4f}")
print(f"Simulated frames: {len(states)} (expected {TOTAL_FRAMES})")
print("Actuator L/R clash check:", "FAILED" if actuator_clash else "PASSED")
print("=" * 70)

scene.frame_set(1)

bpy.ops.wm.save_as_mainfile(
    filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/inverted_pendulum_simulation.blend",
    check_existing=False,
)
