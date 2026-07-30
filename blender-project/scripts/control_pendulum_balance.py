"""Pendulum stabilization controller for the armed inverted pendulum robot
(issue #21). Runs on top of the rig built by model_pendulum.py -- reads the
live rigid-body chassis tilt each frame and drives Hinge_Wheel_Left/Right's
angular motor target velocity to catch it, exactly like a real self-balancing
robot's wheel-speed loop.

Looks objects up by name rather than holding references from the build
script, so it survives being run in a separate live call. Re-running this
script is safe -- it replaces its own frame_change_pre handler instead of
stacking a second one.

Run via run_blender_python_live. Requires model_pendulum.py's rig (chassis +
Hinge_Wheel_Left/Right with use_motor_ang already enabled) to already exist
in the scene.
"""

import bpy
import math

HANDLER_TAG = "pendulum_balance_controller"

# PID gains on chassis pitch (rotation_euler.x, radians -- 0 is upright).
# Same structure as the reference sim in model_inverted_pendulum_simulation.py.
KP = 14.5
KI = 0.3
KD = 4.2
INTEGRAL_LIMIT = 2.0          # anti-windup clamp on the accumulated error
WHEEL_CMD_LIMIT = 20.0        # rad/s, clamps the motor target velocity output

# Flip if live testing shows the robot driving away from vertical instead of
# catching itself -- sign depends on the hinge/motor axis convention, which
# isn't verified against a running sim from script authoring alone.
CONTROL_SIGN = 1.0

INITIAL_DISTURBANCE_DEG = 8.0  # starting lean applied once, at setup time


def get_rig():
    chassis = bpy.data.objects.get("Chassis_Base_Plate")
    hinge_left = bpy.data.objects.get("Hinge_Wheel_Left")
    hinge_right = bpy.data.objects.get("Hinge_Wheel_Right")
    if not (chassis and hinge_left and hinge_right):
        raise RuntimeError(
            "Pendulum rig not found -- run model_pendulum.py first "
            "(need Chassis_Base_Plate, Hinge_Wheel_Left, Hinge_Wheel_Right)."
        )
    return chassis, hinge_left, hinge_right


_state = {"integral": 0.0, "prev_theta": 0.0, "prev_frame": None}


def _make_handler(chassis, hinge_left, hinge_right, fps):
    def pendulum_balance_controller(scene, depsgraph=None):
        frame = scene.frame_current
        if _state["prev_frame"] is not None and frame == _state["prev_frame"]:
            return
        dt = 1.0 / fps if _state["prev_frame"] is None else max(1, frame - _state["prev_frame"]) / fps
        _state["prev_frame"] = frame

        theta = chassis.rotation_euler.x
        _state["integral"] = max(-INTEGRAL_LIMIT, min(INTEGRAL_LIMIT,
                                  _state["integral"] + theta * dt))
        derivative = (theta - _state["prev_theta"]) / dt
        _state["prev_theta"] = theta

        u = CONTROL_SIGN * (KP * theta + KI * _state["integral"] + KD * derivative)
        u = max(-WHEEL_CMD_LIMIT, min(WHEEL_CMD_LIMIT, u))

        hinge_left.rigid_body_constraint.motor_ang_target_velocity = u
        hinge_right.rigid_body_constraint.motor_ang_target_velocity = u

    pendulum_balance_controller.__name__ = HANDLER_TAG
    return pendulum_balance_controller


def install_controller():
    chassis, hinge_left, hinge_right = get_rig()

    for handler_list in (bpy.app.handlers.frame_change_pre,):
        for h in list(handler_list):
            if getattr(h, "__name__", "") == HANDLER_TAG:
                handler_list.remove(h)

    _state["integral"] = 0.0
    _state["prev_theta"] = math.radians(INITIAL_DISTURBANCE_DEG)
    _state["prev_frame"] = None

    scene = bpy.context.scene
    fps = scene.render.fps if scene.render.fps else 24
    bpy.app.handlers.frame_change_pre.append(_make_handler(chassis, hinge_left, hinge_right, fps))

    # Apply the initial lean and rewind so playback starts from a disturbed
    # pose the controller has to correct -- and invalidate any stale bake so
    # the sim recomputes from this new starting state.
    chassis.rotation_euler.x = math.radians(INITIAL_DISTURBANCE_DEG)
    scene.frame_set(scene.frame_start)
    try:
        bpy.ops.ptcache.free_bake_all()
    except RuntimeError:
        pass
    scene.frame_set(scene.frame_start)

    return chassis, hinge_left, hinge_right


chassis, hinge_left, hinge_right = install_controller()

print("=" * 70)
print("Pendulum stabilization controller installed (frame_change_pre handler).")
print(f"Gains: Kp={KP} Ki={KI} Kd={KD} | wheel cmd limit +/-{WHEEL_CMD_LIMIT} rad/s")
print(f"Initial disturbance: {INITIAL_DISTURBANCE_DEG:.1f} deg lean on Chassis_Base_Plate")
print("Press Play in the live viewport to watch it recover -- both wheel hinge")
print("motors are driven from Chassis_Base_Plate pitch (rotation_euler.x) each frame.")
print("If it drives away from vertical instead of catching itself, flip CONTROL_SIGN")
print("in control_pendulum_balance.py and re-run.")
print("=" * 70)

bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
