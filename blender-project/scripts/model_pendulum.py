"""Armed inverted pendulum robot -- compact two-wheel-leg platform (issue #21).

Full parametric build: chassis stack (base plate, battery, PCBs, IMU),
STS3032 hip-servo brackets, leg links, XL330 wheel-actuator servos, and
wheels, wired into a single Chassis -> STS3032 -> Leg Link -> XL330 -> Wheel
parent chain with joint-appropriate transform locks so each hinge can be
hand-posed in the live viewport.

Run via run_blender_python_live -- mutates the actively open Blender scene.
All dimensions are millimeters (1 Blender unit == 1 mm).
"""

import bpy
import math

# ---------------------------------------------------------------------------
# Scene setup -- clear mesh/empty objects, keep any live camera/lights
# ---------------------------------------------------------------------------

def clear_scene_preserve_camera_lights():
    for obj in list(bpy.context.collection.objects):
        if obj.type in {'CAMERA', 'LIGHT'}:
            continue
        bpy.data.objects.remove(obj, do_unlink=True)
    for data_block_collection in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures):
        for block in list(data_block_collection):
            if block.users == 0:
                data_block_collection.remove(block)


def set_units_mm():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 0.001


clear_scene_preserve_camera_lights()
set_units_mm()


# ---------------------------------------------------------------------------
# Hardware dimensions (mm)
# ---------------------------------------------------------------------------

CHASSIS_WIDTH = 60.0
CHASSIS_DEPTH = 45.0
CHASSIS_THICKNESS = 5.0

BATTERY_WIDTH = 46.0
BATTERY_DEPTH = 30.0
BATTERY_THICKNESS = 7.0

PCB_WIDTH = 40.0
PCB_DEPTH = 30.0
PCB_THICKNESS = 1.6
PCB_STANDOFF_HEIGHT = 8.0
PCB_STANDOFF_DIAMETER = 2.5

IMU_SIZE = 8.0

# Feetech STS3032 hip servo
STS3032_L = 32.0   # Y (front-back)
STS3032_W = 12.0   # X (sticks out from chassis side)
STS3032_H = 27.5   # Z

# Leg link bracket
LEG_LENGTH = 50.0   # Z, hip pivot to wheel-actuator mount
LEG_WIDTH = 12.0    # Y
LEG_THICKNESS = 6.0 # X

# Robotis Dynamixel XL330 wheel-actuator servo
XL330_W = 20.0   # Y
XL330_H = 34.0   # Z
XL330_D = 26.0   # X (output-shaft / wheel-axle axis)

# Wheels
WHEEL_DIAMETER = 65.0
WHEEL_WIDTH = 8.0
WHEEL_RADIUS = WHEEL_DIAMETER / 2.0


# ---------------------------------------------------------------------------
# Z-stack layout (bottom to top). CHASSIS_Z_BOTTOM is solved so the wheel
# bottoms land exactly on the Z=0 ground plane used by the rigid body sim.
# ---------------------------------------------------------------------------

CHASSIS_Z_BOTTOM = LEG_LENGTH + XL330_H / 2.0 + WHEEL_RADIUS - CHASSIS_THICKNESS / 2.0
CHASSIS_Z_TOP = CHASSIS_Z_BOTTOM + CHASSIS_THICKNESS
CHASSIS_Z_CENTER = (CHASSIS_Z_BOTTOM + CHASSIS_Z_TOP) / 2.0

BATTERY_Z_BOTTOM = CHASSIS_Z_TOP
BATTERY_Z_CENTER = BATTERY_Z_BOTTOM + BATTERY_THICKNESS / 2.0
BATTERY_Z_TOP = BATTERY_Z_BOTTOM + BATTERY_THICKNESS

PCB1_Z_BOTTOM = BATTERY_Z_TOP + PCB_STANDOFF_HEIGHT
PCB1_Z_CENTER = PCB1_Z_BOTTOM + PCB_THICKNESS / 2.0
PCB1_Z_TOP = PCB1_Z_BOTTOM + PCB_THICKNESS

PCB2_Z_BOTTOM = PCB1_Z_TOP + PCB_STANDOFF_HEIGHT
PCB2_Z_CENTER = PCB2_Z_BOTTOM + PCB_THICKNESS / 2.0
PCB2_Z_TOP = PCB2_Z_BOTTOM + PCB_THICKNESS

IMU_Z_CENTER = PCB2_Z_TOP + IMU_SIZE / 2.0

# Hip pivot: mounted through the chassis plate at its mid-thickness
HIP_Z = CHASSIS_Z_CENTER
HIP_X = CHASSIS_WIDTH / 2.0 + STS3032_W / 2.0


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def get_material(name, base_color, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


MAT_CHASSIS = get_material("Chassis_Plate", (0.15, 0.15, 0.16), roughness=0.5)
MAT_BATTERY = get_material("Battery_Foil", (0.75, 0.76, 0.78), metallic=0.85, roughness=0.25)
MAT_PCB = get_material("PCB_Green", (0.04, 0.35, 0.12), roughness=0.55)
MAT_IMU = get_material("IMU_White", (0.92, 0.92, 0.90), roughness=0.4)
MAT_SERVO_BODY = get_material("Servo_Matte_Black", (0.03, 0.03, 0.035), roughness=0.55)
MAT_SERVO_HORN = get_material("Servo_Horn_Accent", (0.75, 0.1, 0.08), metallic=0.2, roughness=0.35)
MAT_STANDOFF = get_material("Standoff_Steel", (0.7, 0.7, 0.73), metallic=1.0, roughness=0.2)
MAT_LEG = get_material("Leg_Link_Bracket", (0.55, 0.56, 0.60), metallic=0.3, roughness=0.4)
MAT_TIRE = get_material("Wheel_Tire", (0.03, 0.03, 0.035), roughness=0.9)


def assign_material(obj, mat):
    obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def add_box(name, size_xyz, location):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size_xyz
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_cylinder(name, radius, depth, location, axis='Z', vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if axis == 'X':
        obj.rotation_euler = (0.0, math.radians(90.0), 0.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def set_origin_to_point(obj, world_point):
    cursor = bpy.context.scene.cursor
    prev_cursor_loc = cursor.location.copy()
    cursor.location = world_point
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    cursor.location = prev_cursor_loc


def set_parent_keep_transform(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


# ---------------------------------------------------------------------------
# Root empty
# ---------------------------------------------------------------------------

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, 0.0))
root = bpy.context.active_object
root.name = "Armed_Inverted_Pendulum"


# ---------------------------------------------------------------------------
# Torso stack
# ---------------------------------------------------------------------------

chassis = add_box("Chassis_Base_Plate", (CHASSIS_WIDTH, CHASSIS_DEPTH, CHASSIS_THICKNESS),
                   (0.0, 0.0, CHASSIS_Z_CENTER))
assign_material(chassis, MAT_CHASSIS)
set_parent_keep_transform(chassis, root)

battery = add_box("Battery_2S_LiPo", (BATTERY_WIDTH, BATTERY_DEPTH, BATTERY_THICKNESS),
                   (0.0, 0.0, BATTERY_Z_CENTER))
assign_material(battery, MAT_BATTERY)
set_parent_keep_transform(battery, chassis)

pcb1 = add_box("PCB_ESP32_Controller", (PCB_WIDTH, PCB_DEPTH, PCB_THICKNESS),
                (0.0, 0.0, PCB1_Z_CENTER))
assign_material(pcb1, MAT_PCB)
set_parent_keep_transform(pcb1, chassis)

pcb2 = add_box("PCB_Servo_Driver", (PCB_WIDTH, PCB_DEPTH, PCB_THICKNESS),
                (0.0, 0.0, PCB2_Z_CENTER))
assign_material(pcb2, MAT_PCB)
set_parent_keep_transform(pcb2, chassis)

imu = add_box("IMU_Sensor", (IMU_SIZE, IMU_SIZE, IMU_SIZE),
              (0.0, 0.0, IMU_Z_CENTER))
assign_material(imu, MAT_IMU)
set_parent_keep_transform(imu, chassis)

standoff_positions = [
    (x_sign * (PCB_WIDTH / 2.0 - 4.0), y_sign * (PCB_DEPTH / 2.0 - 4.0))
    for x_sign in (-1.0, 1.0) for y_sign in (-1.0, 1.0)
]
for label_i, (sx, sy) in enumerate(standoff_positions):
    so1 = add_cylinder(f"Standoff_Battery_PCB1_{label_i}", PCB_STANDOFF_DIAMETER / 2.0,
                        PCB_STANDOFF_HEIGHT, (sx, sy, (BATTERY_Z_TOP + PCB1_Z_BOTTOM) / 2.0))
    assign_material(so1, MAT_STANDOFF)
    set_parent_keep_transform(so1, chassis)
    so2 = add_cylinder(f"Standoff_PCB1_PCB2_{label_i}", PCB_STANDOFF_DIAMETER / 2.0,
                        PCB_STANDOFF_HEIGHT, (sx, sy, (PCB1_Z_TOP + PCB2_Z_BOTTOM) / 2.0))
    assign_material(so2, MAT_STANDOFF)
    set_parent_keep_transform(so2, chassis)


# ---------------------------------------------------------------------------
# Per-side leg assembly: STS3032 hip servo -> leg link -> XL330 wheel servo
# -> wheel. All joints rotate about world/local X (the hip and wheel shaft
# axes are both aligned to X since nothing upstream is rotated), so each
# hinge locks out Y/Z rotation and all translation, leaving one free DOF.
# ---------------------------------------------------------------------------

def build_leg(side, x_sign):
    hip_x = x_sign * HIP_X
    hip_pivot = (hip_x + x_sign * (STS3032_W / 2.0), 0.0, HIP_Z)

    # STS3032 hip servo -- fixed to chassis, origin at the output-shaft axis
    # (outer face) so a child leg link hinges exactly at the shaft line.
    hip_servo = add_box(f"STS3032_Hip_{side}", (STS3032_W, STS3032_L, STS3032_H),
                         (hip_x, 0.0, HIP_Z))
    assign_material(hip_servo, MAT_SERVO_BODY)
    set_origin_to_point(hip_servo, hip_pivot)
    set_parent_keep_transform(hip_servo, chassis)
    hip_servo.lock_location = (True, True, True)
    hip_servo.lock_rotation = (True, True, True)

    hip_horn = add_cylinder(f"STS3032_Hip_{side}_Horn", 5.0, 2.0,
                             (hip_pivot[0] + x_sign * 1.0, 0.0, HIP_Z), axis='X')
    assign_material(hip_horn, MAT_SERVO_HORN)
    set_parent_keep_transform(hip_horn, hip_servo)
    hip_horn.lock_location = (True, True, True)
    hip_horn.lock_rotation = (True, True, True)

    # Leg link -- hangs from the hip pivot, origin at its top (hip) end so
    # rotating the object about its local X swings the leg like the real
    # hinge. This is the hip joint's free DOF.
    leg_bottom_z = HIP_Z - LEG_LENGTH
    leg = add_box(f"Leg_Link_{side}", (LEG_THICKNESS, LEG_WIDTH, LEG_LENGTH),
                   (hip_pivot[0], 0.0, (HIP_Z + leg_bottom_z) / 2.0))
    assign_material(leg, MAT_LEG)
    set_origin_to_point(leg, hip_pivot)
    # Parented flat to root, not to hip_servo: it's about to become an
    # ACTIVE rigid body, and a dynamic object must not be nested under
    # another Blender parent that itself sits under a dynamic ancestor --
    # the joint itself is wired below via a HINGE rigid_body_constraint.
    set_parent_keep_transform(leg, root)
    leg.lock_location = (True, True, True)
    leg.lock_rotation = (False, True, True)  # free to swing about local X

    # XL330 wheel-actuator servo -- fixed to the leg link's bottom end.
    wheel_servo_center = (hip_pivot[0], 0.0, leg_bottom_z - XL330_H / 2.0)
    wheel_servo = add_box(f"XL330_Wheel_{side}", (XL330_D, XL330_W, XL330_H), wheel_servo_center)
    assign_material(wheel_servo, MAT_SERVO_BODY)
    set_parent_keep_transform(wheel_servo, leg)
    wheel_servo.lock_location = (True, True, True)
    wheel_servo.lock_rotation = (True, True, True)

    # Wheel -- mounted directly on the XL330 output horn (outer end of the
    # servo body, along its shaft axis X), origin at the true rotational
    # (axle) center so spinning about local X matches the real hub.
    wheel_x = wheel_servo_center[0] + x_sign * (XL330_D / 2.0 + WHEEL_WIDTH / 2.0)
    wheel_center = (wheel_x, 0.0, wheel_servo_center[2])
    wheel = add_cylinder(f"Wheel_{side}", WHEEL_RADIUS, WHEEL_WIDTH, wheel_center, axis='X')
    assign_material(wheel, MAT_TIRE)
    set_origin_to_point(wheel, wheel_center)
    # Flat to root for the same reason as the leg link -- physics-driven,
    # connected to the leg via a HINGE constraint rather than Blender parenting.
    set_parent_keep_transform(wheel, root)
    wheel.lock_location = (True, True, True)
    wheel.lock_rotation = (False, True, True)  # free to spin about local X

    return hip_servo, leg, wheel_servo, wheel


left_parts = build_leg("Left", -1.0)
right_parts = build_leg("Right", 1.0)


# ---------------------------------------------------------------------------
# Ground plane
# ---------------------------------------------------------------------------

MAT_GROUND = get_material("Ground_Mat", (0.35, 0.35, 0.37), roughness=0.8)

bpy.ops.mesh.primitive_plane_add(size=1000.0, location=(0.0, 0.0, 0.0))
ground = bpy.context.active_object
ground.name = "Ground_Plane"
assign_material(ground, MAT_GROUND)
set_parent_keep_transform(ground, root)


# ---------------------------------------------------------------------------
# Rigid body physics -- Chassis, Leg_Link_L/R, Wheel_L/R are ACTIVE bodies
# joined by HINGE rigid_body_constraint empties (not by Blender parenting),
# so the chassis can tip like an inverted pendulum while the hip and wheel
# joints stay physically coupled to it.
# ---------------------------------------------------------------------------

def ensure_rigid_body_world():
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    if rbw.collection is None:
        rbw.collection = bpy.data.collections.new("RigidBodyWorld_Objects")
    if rbw.constraints is None:
        rbw.constraints = bpy.data.collections.new("RigidBodyWorld_Constraints")


def add_rigid_body(obj, body_type, shape, mass=1.0, friction=0.7, restitution=0.0):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.rigidbody.object_add(type=body_type)
    rb = obj.rigid_body
    rb.collision_shape = shape
    rb.mass = mass
    rb.friction = friction
    rb.restitution = restitution
    return rb


def add_hinge_constraint(name, world_point, obj1, obj2, limit_deg=None,
                          motor_target_ang_vel=None, motor_max_impulse=None):
    """Hinge axis is the constraint empty's local Z, so it's rotated 90deg
    about Y here to align that axis with world X -- the hip/wheel shaft axis
    everywhere in this model. Passing motor_target_ang_vel enables the
    hinge's built-in angular motor (drives obj2 relative to obj1 about that
    axis, capped by motor_max_impulse -- this is the wheel torque drive)."""
    bpy.ops.object.empty_add(type='ARROWS', location=world_point,
                              rotation=(0.0, math.radians(90.0), 0.0))
    con = bpy.context.active_object
    con.name = name
    set_parent_keep_transform(con, root)
    bpy.context.view_layer.objects.active = con
    bpy.ops.rigidbody.constraint_add(type='HINGE')
    rbc = con.rigid_body_constraint
    rbc.object1 = obj1
    rbc.object2 = obj2
    if limit_deg is not None:
        rbc.use_limit_ang_z = True
        rbc.limit_ang_z_lower = -math.radians(limit_deg)
        rbc.limit_ang_z_upper = math.radians(limit_deg)
    else:
        rbc.use_limit_ang_z = False
    if motor_target_ang_vel is not None:
        rbc.use_motor_ang = True
        rbc.motor_ang_target_velocity = motor_target_ang_vel
        rbc.motor_ang_max_impulse = motor_max_impulse
        rbc.enabled = True
    return con


ensure_rigid_body_world()

add_rigid_body(ground, 'PASSIVE', 'MESH', friction=0.9)
add_rigid_body(chassis, 'ACTIVE', 'BOX', mass=0.15, friction=0.5)

HIP_SWING_LIMIT_DEG = 45.0

# XL330 rated no-load speed (~0.111 sec/60deg at 5V) and a placeholder max
# angular impulse standing in for stall torque -- tune motor_max_impulse
# against the sim (higher = more torque before the motor stalls/slips).
WHEEL_MOTOR_TARGET_ANG_VEL = 9.4    # rad/s, forward roll
WHEEL_MOTOR_MAX_IMPULSE = 0.05

constraints = []
wheel_hinges = {}
for side, parts in (("Left", left_parts), ("Right", right_parts)):
    hip_servo, leg, wheel_servo, wheel = parts
    add_rigid_body(leg, 'ACTIVE', 'BOX', mass=0.02, friction=0.5)
    add_rigid_body(wheel, 'ACTIVE', 'CONVEX_HULL', mass=0.03, friction=1.2)

    hip_pivot_world = leg.matrix_world.translation.copy()
    wheel_axle_world = wheel.matrix_world.translation.copy()

    hip_hinge = add_hinge_constraint(f"Hinge_Hip_{side}", hip_pivot_world,
                                      chassis, leg, limit_deg=HIP_SWING_LIMIT_DEG)
    wheel_hinge = add_hinge_constraint(f"Hinge_Wheel_{side}", wheel_axle_world,
                                        leg, wheel, limit_deg=None,
                                        motor_target_ang_vel=WHEEL_MOTOR_TARGET_ANG_VEL,
                                        motor_max_impulse=WHEEL_MOTOR_MAX_IMPULSE)
    constraints.extend([hip_hinge, wheel_hinge])
    wheel_hinges[side] = wheel_hinge

print("=" * 70)
print("Full build complete: torso stack + STS3032 -> Leg Link -> XL330 -> Wheel")
print(f"Chassis top Z: {CHASSIS_Z_TOP:.2f} mm | IMU center Z: {IMU_Z_CENTER:.2f} mm")
print(f"Hip pivot X: +/-{HIP_X + STS3032_W / 2.0:.2f} mm at Z={HIP_Z:.2f} mm")
print(f"Leg length: {LEG_LENGTH:.2f} mm | Wheel OD: {WHEEL_DIAMETER:.2f} mm, width {WHEEL_WIDTH:.2f} mm")
print(f"Ground contact: wheel bottom at Z={0.0:.2f} mm (chassis lifted {CHASSIS_Z_BOTTOM:.2f} mm)")
print("Rigid bodies: Chassis (active box), Leg_Link_* (active box), Wheel_* (active convex hull)")
print(f"Constraints: Hinge_Hip_* (+/-{HIP_SWING_LIMIT_DEG:.0f} deg swing), "
      f"Hinge_Wheel_* (motorized, target {WHEEL_MOTOR_TARGET_ANG_VEL:.1f} rad/s, "
      f"max impulse {WHEEL_MOTOR_MAX_IMPULSE:.3f})")
print("Hinges also hand-posable: Leg_Link_* / Wheel_* rotation X unlocked in viewport")
print("=" * 70)

if bpy.app.background:
    # Headless (render pipeline) run -- persist the build per the
    # model_<subject>.py contract in DESIGN.md. Skipped when run live via
    # run_blender_python_live so it never hijacks the GUI session's own
    # open file.
    bpy.ops.wm.save_as_mainfile(
        filepath="/home/pluto-atom-4/blender-workspace/blender-project/renders/pendulum.blend",
        check_existing=False,
    )
else:
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
