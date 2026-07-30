"""Pendulum stabilization controller for the armed inverted pendulum robot
(issue #21). Runs on top of the rig built by model_pendulum.py.

Keyframed fallback, not a live physics controller: Blender's rigid body
HINGE/MOTOR constraint angular motor (`use_motor_ang`) was verified
non-functional in this Blender 4.3.2 environment via isolated minimal
repros (anchor + single wheel + motor, both box and convex-hull shapes,
both HINGE's own motor and a dedicated MOTOR constraint, torque cap cranked
to 1000 -- all produced exactly zero rotation across 30+ simulated frames,
while plain gravity-driven translation on the same rig worked correctly).
So instead of driving Hinge_Wheel_*'s motor in real time, this script:

1. Strips the rigid_body / rigid_body_constraint data added by
   model_pendulum.py (it can't drive anything here) and deletes the now
   inert Hinge_* constraint-empty objects.
2. Adds a Balance_Pivot empty at wheel-axle height and reparents the
   chassis stack + both leg links under it -- rotating that pivot tips the
   whole upper body around the wheel axle, like a real two-wheel balancing
   robot, instead of spinning the chassis in place around its own center.
3. Runs the same PID balance math as before (Kp/Ki/Kd on tilt) as a plain
   Python simulation loop (not a live handler), and bakes the result to
   keyframes: Root Y-location (rolling), Balance_Pivot X-rotation (tip),
   Wheel_Left/Right X-rotation (spin).

Trades away real physical wheel-ground force interaction for a working,
visually-correct animated demonstration of the same control law. Run via
run_blender_python_live. Requires model_pendulum.py's rig to already exist.
"""

import bpy
import math

WHEEL_RADIUS = 32.5  # mm, matches model_pendulum.py's WHEEL_DIAMETER / 2

# PID gains on tilt (radians, 0 = upright) -- same values as the abandoned
# live physics controller and the reference sim in
# model_inverted_pendulum_simulation.py.
KP = 14.5
KI = 0.3
KD = 4.2
INTEGRAL_LIMIT = 2.0
CMD_LIMIT = 18.0

CONTROL_SIGN = 1.0
INITIAL_DISTURBANCE_DEG = 8.0

FPS = 24
TOTAL_FRAMES = 150
DT = 1.0 / FPS
SUB_STEPS = 10
S_DT = DT / SUB_STEPS

# Abstract pendulum length -- distance from wheel axle to the upper body's
# effective center of mass, roughly chassis hip height above the axle.
SIM_L = 0.067  # meters (~ 99.5mm - 32.5mm, HIP_Z - WHEEL_RADIUS, in m)
SIM_G = 9.81


def get_rig():
    names = ["Armed_Inverted_Pendulum", "Chassis_Base_Plate",
             "Leg_Link_Left", "Leg_Link_Right", "Wheel_Left", "Wheel_Right"]
    objs = {n: bpy.data.objects.get(n) for n in names}
    missing = [n for n, o in objs.items() if o is None]
    if missing:
        raise RuntimeError(f"Pendulum rig not found -- run model_pendulum.py first "
                            f"(missing: {missing}).")
    return objs


def strip_physics(objs):
    """Remove rigid_body/constraint data model_pendulum.py added -- it
    can't drive anything in this environment, and leaving it in place would
    fight the keyframes we're about to add."""
    for name in ["Ground_Plane", "Chassis_Base_Plate", "Leg_Link_Left",
                 "Leg_Link_Right", "Wheel_Left", "Wheel_Right"]:
        obj = bpy.data.objects.get(name)
        if obj and obj.rigid_body:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.ops.rigidbody.object_remove()

    for name in ["Hinge_Hip_Left", "Hinge_Hip_Right",
                 "Hinge_Wheel_Left", "Hinge_Wheel_Right"]:
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)


def set_parent_keep_transform(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def build_balance_pivot(objs):
    """Pivot at wheel-axle height (Z = WHEEL_RADIUS) -- rotating it tips
    the whole upper body around the axle line, not around the chassis's
    own center."""
    existing = bpy.data.objects.get("Balance_Pivot")
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.0, 0.0, WHEEL_RADIUS))
    pivot = bpy.context.active_object
    pivot.name = "Balance_Pivot"
    set_parent_keep_transform(pivot, objs["Armed_Inverted_Pendulum"])

    for name in ["Chassis_Base_Plate", "Leg_Link_Left", "Leg_Link_Right"]:
        obj = bpy.data.objects.get(name)
        set_parent_keep_transform(obj, pivot)

    return pivot


def simulate():
    s = {"x": 0.0, "v": 0.0, "theta": math.radians(INITIAL_DISTURBANCE_DEG),
         "omega": 0.0, "integral": 0.0}
    states = [dict(s)]
    for _ in range(TOTAL_FRAMES - 1):
        for _sub in range(SUB_STEPS):
            error = s["theta"]
            s["integral"] = max(-INTEGRAL_LIMIT, min(INTEGRAL_LIMIT,
                                 s["integral"] + error * S_DT))
            u = CONTROL_SIGN * (KP * error + KI * s["integral"] + KD * s["omega"])
            u = max(-CMD_LIMIT, min(CMD_LIMIT, u))

            theta_accel = (SIM_G * math.sin(s["theta"]) - math.cos(s["theta"]) * u) / SIM_L
            s["omega"] += theta_accel * S_DT
            s["theta"] += s["omega"] * S_DT

            s["v"] += u * S_DT - 0.4 * s["v"]
            s["x"] += s["v"] * S_DT

            if abs(s["theta"]) >= math.pi / 2:
                s["theta"] = math.copysign(math.pi / 2, s["theta"])
                s["omega"] = 0.0
        states.append(dict(s))
    return states


def set_linear(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    for fcurve in obj.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'LINEAR'


def bake_keyframes(objs, pivot, states):
    root = objs["Armed_Inverted_Pendulum"]
    wheel_l, wheel_r = objs["Wheel_Left"], objs["Wheel_Right"]

    root.location.y = 0.0
    root.rotation_euler.x = 0.0
    pivot.rotation_euler.x = 0.0
    wheel_l.rotation_euler.x = 0.0
    wheel_r.rotation_euler.x = 0.0

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = TOTAL_FRAMES
    scene.render.fps = FPS

    # x is in abstract sim meters; WHEEL_RADIUS (mm) / SIM_WHEEL_RADIUS (abstract
    # "meters", chosen as 0.03 here) converts to mm the same way
    # model_inverted_pendulum_simulation.py does.
    sim_wheel_radius = 0.03
    sim_to_mm = WHEEL_RADIUS / sim_wheel_radius

    for i, s in enumerate(states):
        frame = i + 1
        root.location.y = s["x"] * sim_to_mm
        root.keyframe_insert(data_path="location", index=1, frame=frame)

        pivot.rotation_euler.x = s["theta"]
        pivot.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)

        wheel_spin = s["x"] / sim_wheel_radius
        for wheel in (wheel_l, wheel_r):
            wheel.rotation_euler.x = wheel_spin
            wheel.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)

    for obj in (root, pivot, wheel_l, wheel_r):
        set_linear(obj)

    scene.frame_set(1)


objs = get_rig()
strip_physics(objs)
pivot = build_balance_pivot(objs)
states = simulate()
bake_keyframes(objs, pivot, states)

final_deg = math.degrees(states[-1]["theta"])
max_deg = max(abs(math.degrees(s["theta"])) for s in states)

print("=" * 70)
print("Keyframed pendulum balance animation baked (physics motor was a dead end --")
print("see this script's docstring for the isolated repro that proved it).")
print(f"Gains: Kp={KP} Ki={KI} Kd={KD} | initial disturbance {INITIAL_DISTURBANCE_DEG:.1f} deg")
print(f"Frames 1-{TOTAL_FRAMES} @ {FPS}fps | max tilt {max_deg:.2f} deg | final tilt {final_deg:.2f} deg")
print("RESULT:", "BALANCED (converges toward upright)" if abs(final_deg) < 2.0 else "NOT BALANCED")
print("Press Play in the live viewport to watch it (root translates, Balance_Pivot")
print("tips the chassis+legs, wheels spin) -- no rigid body simulation involved.")
print("=" * 70)

if not bpy.app.background:
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
