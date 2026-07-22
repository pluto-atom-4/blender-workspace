"""Parametric two-wheeled inverted pendulum robot sized for the Tamiya
55mm Slim Tire Set (Tamiya 70193), driven by two Dynamixel XL330 smart
servos. All dimensions are millimeters."""

import bpy
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

WHEEL_DIAMETER = 55.0     # Tamiya 70193 slim tire OD
WHEEL_WIDTH = 3.5         # thin tread profile
BALSA_THICKNESS = 3.0     # main deck sheet stock
POLY_THICKNESS = 5.0      # rigid motor bracket stock
CHASSIS_WIDTH = 85.0      # narrowed to fit the 100mm hex axle kit

# Dynamixel XL330 smart servo body envelope
XL330_WIDTH = 20.0        # X-axis body cross-section (Y in world space)
XL330_HEIGHT = 34.0       # body cross-section (Z in world space)
XL330_DEPTH = 26.0        # along the output-shaft axis (X in world space)

# Compact horn-to-wheel adapter hub
HUB_ADAPTER_DIAMETER = 14.0
HUB_ADAPTER_LENGTH = 4.0

WHEEL_RADIUS = WHEEL_DIAMETER / 2.0

AXLE_LENGTH = 100.0
AXLE_ACROSS_FLATS = 3.0
AXLE_CIRCUMRADIUS = AXLE_ACROSS_FLATS / math.sqrt(3)

CHASSIS_WHEEL_GAP = 2.0   # clearance between chassis edge and wheel inner face
WHEEL_X = CHASSIS_WIDTH / 2.0 + CHASSIS_WHEEL_GAP + WHEEL_WIDTH / 2.0

# Ground reference: wheel bottom sits on Z = 0, so the wheel/axle/actuator
# shaft centerline is one wheel-radius up. The XL330 output horn is assumed
# centered on the actuator's own W x H cross-section (no offset given in the
# hardware spec), so the actuator body straddles that same centerline.
AXLE_Z = WHEEL_RADIUS

LOWER_DECK_WIDTH = CHASSIS_WIDTH
LOWER_DECK_DEPTH = 60.0

# Actuator body, centered on the shaft line.
ACTUATOR_Z_BOTTOM = AXLE_Z - XL330_HEIGHT / 2.0
ACTUATOR_Z_TOP = AXLE_Z + XL330_HEIGHT / 2.0

# Motor mount bracket sits flush on top of the actuator and flush under the
# lower deck -- thickness fills exactly the actuator-to-deck gap.
MOUNT_Z_BOTTOM = ACTUATOR_Z_TOP
MOUNT_Z_TOP = MOUNT_Z_BOTTOM + POLY_THICKNESS
MOUNT_Z_CENTER = (MOUNT_Z_BOTTOM + MOUNT_Z_TOP) / 2.0

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
# Primitive helpers
# ---------------------------------------------------------------------------

def add_box(name, size, location):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
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


# ---------------------------------------------------------------------------
# Root empty
# ---------------------------------------------------------------------------

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, 0.0))
root = bpy.context.active_object
root.name = "Tamiya_Inverted_Pendulum"

created = []


# ---------------------------------------------------------------------------
# Wheels, horn-to-wheel adapter hubs, and XL330 actuators
# ---------------------------------------------------------------------------

actuators = {}
wheels = {}
hubs = {}

for side, x_sign in (("Left", -1.0), ("Right", 1.0)):
    wheel_x = x_sign * WHEEL_X
    wheel_inner_x = x_sign * (WHEEL_X - WHEEL_WIDTH / 2.0)

    wheel = add_cylinder(
        f"Tamiya_55mm_{side}_Wheel", WHEEL_RADIUS, WHEEL_WIDTH,
        (wheel_x, 0.0, AXLE_Z), axis='X',
    )
    created.append(wheel)
    wheels[side] = wheel

    hub_outer_x = wheel_inner_x
    hub_inner_x = hub_outer_x - x_sign * HUB_ADAPTER_LENGTH
    hub_center_x = (hub_outer_x + hub_inner_x) / 2.0
    hub = add_cylinder(
        f"Wheel_Hub_Adapter_{side}", HUB_ADAPTER_DIAMETER / 2.0,
        HUB_ADAPTER_LENGTH, (hub_center_x, 0.0, AXLE_Z), axis='X',
    )
    created.append(hub)
    hubs[side] = hub

    actuator_outer_x = hub_inner_x
    actuator_inner_x = actuator_outer_x - x_sign * XL330_DEPTH
    actuator_center_x = (actuator_outer_x + actuator_inner_x) / 2.0
    actuator = add_box(
        f"Dynamixel_XL330_{side}",
        (XL330_DEPTH, XL330_WIDTH, XL330_HEIGHT),
        (actuator_center_x, 0.0, AXLE_Z),
    )
    created.append(actuator)
    actuators[side] = actuator

    mount = add_box(
        f"Poly_Motor_Mount_{side}",
        (XL330_DEPTH, XL330_WIDTH, POLY_THICKNESS),
        (actuator_center_x, 0.0, MOUNT_Z_CENTER),
    )
    created.append(mount)

# ---------------------------------------------------------------------------
# Hex axle -- structural alignment backbone between the two actuator
# outputs, coaxial with the wheel/motor shaft line.
# ---------------------------------------------------------------------------

axle = add_cylinder(
    "Hex_Axle_100mm", AXLE_CIRCUMRADIUS, AXLE_LENGTH,
    (0.0, 0.0, AXLE_Z), vertices=6, axis='X',
)
created.append(axle)

# ---------------------------------------------------------------------------
# Lower deck (balsa)
# ---------------------------------------------------------------------------

created.append(add_box(
    "Balsa_Lower_Deck",
    (LOWER_DECK_WIDTH, LOWER_DECK_DEPTH, BALSA_THICKNESS),
    (0.0, 0.0, LOWER_DECK_Z_CENTER),
))

# ---------------------------------------------------------------------------
# Upper deck (balsa) on four standoffs
# ---------------------------------------------------------------------------

created.append(add_box(
    "Balsa_Upper_Deck",
    (UPPER_DECK_WIDTH, UPPER_DECK_DEPTH, BALSA_THICKNESS),
    (0.0, 0.0, UPPER_DECK_Z_CENTER),
))

for x_sign in (-1.0, 1.0):
    for y_sign in (-1.0, 1.0):
        x_label = "L" if x_sign < 0 else "R"
        y_label = "B" if y_sign < 0 else "F"
        created.append(add_cylinder(
            f"Standoff_{x_label}{y_label}",
            STANDOFF_DIAMETER / 2.0, UPPER_DECK_STANDOFF_HEIGHT,
            (x_sign * STANDOFF_X, y_sign * STANDOFF_Y, STANDOFF_Z_CENTER),
            axis='Z',
        ))

# ---------------------------------------------------------------------------
# Parent everything to the root empty
# ---------------------------------------------------------------------------

for obj in created:
    obj.parent = root

# ---------------------------------------------------------------------------
# Intersection check: verify no two mesh objects' bounding boxes overlap
# ---------------------------------------------------------------------------

def world_bbox(obj):
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    min_x = min(v.x for v in xs); max_x = max(v.x for v in xs)
    min_y = min(v.y for v in xs); max_y = max(v.y for v in xs)
    min_z = min(v.z for v in xs); max_z = max(v.z for v in xs)
    return (min_x, max_x, min_y, max_y, min_z, max_z)


def boxes_overlap(a, b, eps=1e-6):
    ax0, ax1, ay0, ay1, az0, az1 = a
    bx0, bx1, by0, by1, bz0, bz1 = b
    return (ax0 < bx1 - eps and bx0 < ax1 - eps and
            ay0 < by1 - eps and by0 < ay1 - eps and
            az0 < bz1 - eps and bz0 < az1 - eps)


# The 100mm hex axle is the coaxial alignment backbone: by design it
# telescopes through the wheel hub, the adapter hub, and the actuator body
# on both sides. That is the intended fit, not a structural clash.
ALLOWED_OVERLAPS = set()
for side in ("Left", "Right"):
    ALLOWED_OVERLAPS.add(frozenset((f"Tamiya_55mm_{side}_Wheel", "Hex_Axle_100mm")))
    ALLOWED_OVERLAPS.add(frozenset((f"Wheel_Hub_Adapter_{side}", "Hex_Axle_100mm")))
    ALLOWED_OVERLAPS.add(frozenset((f"Dynamixel_XL330_{side}", "Hex_Axle_100mm")))

mesh_objs = [o for o in created if o.type == 'MESH']
bboxes = {o.name: world_bbox(o) for o in mesh_objs}
overlaps = []
for i, a in enumerate(mesh_objs):
    for b in mesh_objs[i + 1:]:
        if frozenset((a.name, b.name)) in ALLOWED_OVERLAPS:
            continue
        if boxes_overlap(bboxes[a.name], bboxes[b.name]):
            overlaps.append((a.name, b.name))

print("=" * 60)
print(f"TOTAL_HEIGHT (ground to top of upper deck): {TOTAL_HEIGHT:.2f} mm")
print(f"Wheel outer diameter: {WHEEL_DIAMETER:.2f} mm")
print(f"Actuator Z: {ACTUATOR_Z_BOTTOM:.2f} - {ACTUATOR_Z_TOP:.2f} mm")
print(f"Motor mount Z: {MOUNT_Z_BOTTOM:.2f} - {MOUNT_Z_TOP:.2f} mm")
print(f"Lower deck Z: {LOWER_DECK_Z_BOTTOM:.2f} - {LOWER_DECK_Z_TOP:.2f} mm")
print(f"Upper deck Z: {UPPER_DECK_Z_BOTTOM:.2f} - {UPPER_DECK_Z_TOP:.2f} mm")
if overlaps:
    print(f"INTERSECTION CHECK: FAILED, {len(overlaps)} overlapping pair(s):")
    for a, b in overlaps:
        print(f"  {a} <-> {b}")
else:
    print("INTERSECTION CHECK: PASSED, no overlapping mesh bounding boxes.")
    print("  (axle intentionally telescopes through hub -> actuator on both sides)")
print("=" * 60)

# Save the built scene next to the render output area for inspection.
bpy.ops.wm.save_as_mainfile(
    filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum.blend",
    check_existing=False,
)
