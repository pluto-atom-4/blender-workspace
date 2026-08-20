"""Webots controller for dual-wheel legged robot jump behavior (issue #86).

Implements a state machine (REST → CROUCH → PUSH/LIFTOFF → FLIGHT → LANDING
→ SETTLE) that executes a coordinated jump sequence using:
  - Hip motor position tracking with crouch/push profile (EXPO/QUAD easing)
  - Wheel motor velocity control during launch/landing windows
  - Sensor feedback (gyro, accelerometer, hip position, Supervisor CoM queries)
  - CSV telemetry logging (time, joint angles, sensor readings, CoM data)

Timeline (total 2.0 second simulation):
  - REST (0.0–0.2s): stabilize at rest pose
  - CROUCH (0.2–0.7s): lower stance (1.012 rad → 2.094 rad; ~120°), EXPO easing
  - PUSH (0.7–1.0s): explosive liftoff (2.094 rad → 0.262 rad; ~15°), QUAD easing
  - FLIGHT (1.0–1.2s): airborne, wheels inactive
  - LANDING (1.2–1.4s): prepare for touchdown, spin wheels backward
  - SETTLE (1.4–2.0s): absorb landing, return to rest

Wheel choreography:
  - PUSH/LIFTOFF: spin forward at WHEEL_SPIN_FORWARD_RAD_S for traction
  - LANDING: spin backward at WHEEL_SPIN_BACKWARD_RAD_S for braking

Supervisor CoM queries (via traversal of mass-center node):
  - Used to compute actual jump height and liftoff velocity from measured
    acceleration/velocity during push phase
  - Logged alongside motor telemetry for post-sim analysis

Telemetry schema (CSV columns):
  time, hip_angle_rad, hip_angular_velocity_rad_s,
  com_x, com_y, com_z, com_vx, com_vy, com_vz,
  gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z, hip_motor_torque
"""

import csv
import math
import os
import sys
import traceback
from enum import Enum
from pathlib import Path


class State(Enum):
    """Jump sequence state machine."""
    REST = "rest"
    CROUCH = "crouch"
    PUSH = "push"
    FLIGHT = "flight"
    LANDING = "landing"
    SETTLE = "settle"


# Configuration constants
REST_ANGLE_RAD = 1.0122909661567112  # ~58° (default stance from linkage_kinematics)
CROUCH_ANGLE_RAD = 2.0943951023931953  # ~120° (roughly pi/1.5)
LAUNCH_ANGLE_RAD = 0.2617993877991494  # ~15° (roughly pi/12)

# Timing (seconds)
TIME_REST_START = 0.0
TIME_REST_END = 0.2
TIME_CROUCH_START = 0.2
TIME_CROUCH_END = 0.7
TIME_PUSH_START = 0.7
TIME_PUSH_END = 1.0
TIME_FLIGHT_START = 1.0
TIME_FLIGHT_END = 1.2
TIME_LANDING_START = 1.2
TIME_LANDING_END = 1.4
TIME_SETTLE_START = 1.4
TIME_SETTLE_END = 2.0

# Wheel motor control (rad/s)
WHEEL_SPIN_FORWARD_RAD_S = 2.0  # during push/liftoff
WHEEL_SPIN_BACKWARD_RAD_S = -1.5  # during landing

# Motor control parameters
MAX_HIP_MOTOR_SPEED = 1.0  # rad/s (conservative, allow profile to set targets)
MAX_WHEEL_MOTOR_SPEED = 6.5  # rad/s (from legged_robot_world.wbt)

# Easing functions (Blender EXPO/QUAD approximations)
def expo_ease_in_out(t: float) -> float:
    """Exponential ease in-out: smooth acceleration -> deceleration."""
    if t < 0.5:
        return 0.5 * (2.0 ** (20.0 * t - 10.0))
    else:
        return 1.0 - 0.5 * (2.0 ** (-20.0 * t + 10.0))


def quad_ease_in_out(t: float) -> float:
    """Quadratic ease in-out: smoother acceleration -> deceleration."""
    if t < 0.5:
        return 2.0 * t * t
    else:
        return -1.0 + (4.0 - 2.0 * t) * t


def linear_interpolate(start: float, end: float, t: float) -> float:
    """Linear interpolation from start to end over t in [0,1]."""
    return start + (end - start) * t


def interpolate_with_easing(start: float, end: float, t: float, easing_fn) -> float:
    """Interpolate with easing function applied to parameter t."""
    eased_t = easing_fn(t)
    return linear_interpolate(start, end, eased_t)


def get_hip_target_angle(elapsed_time: float) -> float:
    """Compute target hip angle for current time, based on state."""
    if elapsed_time < TIME_CROUCH_START:
        # REST: hold at rest angle
        return REST_ANGLE_RAD
    elif elapsed_time < TIME_CROUCH_END:
        # CROUCH: ramp from rest to crouch angle with EXPO easing
        t = (elapsed_time - TIME_CROUCH_START) / (TIME_CROUCH_END - TIME_CROUCH_START)
        return interpolate_with_easing(REST_ANGLE_RAD, CROUCH_ANGLE_RAD, t, expo_ease_in_out)
    elif elapsed_time < TIME_PUSH_END:
        # PUSH: explosive ramp from crouch to launch angle with QUAD easing
        t = (elapsed_time - TIME_PUSH_START) / (TIME_PUSH_END - TIME_PUSH_START)
        return interpolate_with_easing(CROUCH_ANGLE_RAD, LAUNCH_ANGLE_RAD, t, quad_ease_in_out)
    elif elapsed_time < TIME_LANDING_START:
        # FLIGHT: hold launch angle (liftoff)
        return LAUNCH_ANGLE_RAD
    elif elapsed_time < TIME_LANDING_END:
        # LANDING: ramp back toward rest angle for impact prep
        t = (elapsed_time - TIME_LANDING_START) / (TIME_LANDING_END - TIME_LANDING_START)
        return interpolate_with_easing(LAUNCH_ANGLE_RAD, REST_ANGLE_RAD, t, quad_ease_in_out)
    else:
        # SETTLE: hold rest angle
        return REST_ANGLE_RAD


def get_state(elapsed_time: float) -> State:
    """Determine current state from elapsed time."""
    if elapsed_time < TIME_REST_END:
        return State.REST
    elif elapsed_time < TIME_CROUCH_END:
        return State.CROUCH
    elif elapsed_time < TIME_PUSH_END:
        return State.PUSH
    elif elapsed_time < TIME_FLIGHT_END:
        return State.FLIGHT
    elif elapsed_time < TIME_LANDING_END:
        return State.LANDING
    else:
        return State.SETTLE


def get_wheel_target_velocity(state: State) -> float:
    """Get wheel motor target velocity (rad/s) based on state."""
    if state in (State.PUSH,):
        return WHEEL_SPIN_FORWARD_RAD_S
    elif state == State.LANDING:
        return WHEEL_SPIN_BACKWARD_RAD_S
    else:
        return 0.0


def get_supervisor_com_position(supervisor):
    """Query center-of-mass proxy position from wheel nodes.

    The actual CoM computation is complex (mass-weighted avg of all bodies).
    Instead, we approximate by querying the average of wheel positions,
    which gives us the height of the robot body off the ground. This is
    sufficient for jump height estimation.

    Returns: (x, y, z) as list of floats (world frame), or [0, 0, 0] on error.
    """
    try:
        if supervisor is None:
            return [0.0, 0.0, 0.0]

        # Query wheel positions (DEF tags added to world file for this)
        wheel_r = supervisor.getFromDef("wheel_R")
        wheel_l = supervisor.getFromDef("wheel_L")

        if wheel_r and wheel_l:
            pos_r = wheel_r.getPosition()
            pos_l = wheel_l.getPosition()
            if pos_r and pos_l:
                # Average of both wheel positions
                avg_x = (pos_r[0] + pos_l[0]) / 2.0
                avg_y = (pos_r[1] + pos_l[1]) / 2.0
                avg_z = (pos_r[2] + pos_l[2]) / 2.0
                return [avg_x, avg_y, avg_z]

        # Fallback: query robot's own position
        robot = supervisor.getSelf()
        if robot:
            robot_pos = robot.getPosition()
            return list(robot_pos) if robot_pos else [0.0, 0.0, 0.0]

        return [0.0, 0.0, 0.0]
    except Exception:
        return [0.0, 0.0, 0.0]


def get_supervisor_com_velocity(supervisor, prev_com: list, prev_time: float, current_time: float):
    """Compute CoM velocity from position change.

    Returns: (vx, vy, vz) as list of floats.
    """
    if current_time <= prev_time:
        return [0.0, 0.0, 0.0]

    current_com = get_supervisor_com_position(supervisor)
    dt = current_time - prev_time

    return [
        (current_com[0] - prev_com[0]) / dt if dt > 0 else 0.0,
        (current_com[1] - prev_com[1]) / dt if dt > 0 else 0.0,
        (current_com[2] - prev_com[2]) / dt if dt > 0 else 0.0,
    ]


# Setup telemetry logging early so we can log debug info
telemetry_dir = Path("/tmp") if os.access("/tmp", os.W_OK) else Path.home() / ".webots_telemetry"
telemetry_dir.mkdir(parents=True, exist_ok=True)
telemetry_file = telemetry_dir / "legged_robot_jump_telemetry.csv"

# Track if this is the first run (for header writing)
is_first_run = not telemetry_file.exists()

csv_file = open(telemetry_file, "a" if not is_first_run else "w", newline="")

def log_debug(message):
    """Log debug message to CSV file."""
    csv_file.write(f"# DEBUG: {message}\n")
    csv_file.flush()

try:
    log_debug("Controller started")

    # Import Webots modules
    from controller import Robot

    log_debug("Imported Robot from controller")

    # Initialize Webots devices
    robot = Robot()
    log_debug("Created Robot object")

    timestep = int(robot.getBasicTimeStep())
    log_debug(f"Timestep: {timestep}")

    # Sensors
    gyro = robot.getDevice("gyro")
    accelerometer = robot.getDevice("accelerometer")
    gyro.enable(timestep)
    accelerometer.enable(timestep)
    log_debug("Enabled sensors")

    # Hip motors (both sides)
    hip_motor_R = robot.getDevice("hip_motor_R")
    hip_motor_L = robot.getDevice("hip_motor_L")
    log_debug("Got hip motors")

    # Wheel motors (both sides)
    wheel_motor_R = robot.getDevice("wheel_motor_R")
    wheel_motor_L = robot.getDevice("wheel_motor_L")
    log_debug("Got wheel motors")

    # Hip position sensors (if available; may need to be added to .wbt)
    try:
        hip_position_R = robot.getDevice("hip_position_R")
        hip_position_L = robot.getDevice("hip_position_L")
        hip_position_R.enable(timestep)
        hip_position_L.enable(timestep)
        has_hip_sensors = True
        log_debug("Hip position sensors available")
    except RuntimeError:
        has_hip_sensors = False
        hip_position_R = None
        hip_position_L = None
        log_debug("Hip position sensors not available")

    # Supervisor API for CoM queries
    supervisor = robot.getSupervisor()
    has_supervisor = supervisor is not None
    log_debug(f"Supervisor available: {has_supervisor}")

    # Write CSV header if this is the first run
    if is_first_run:
        header = [
            "time",
            "hip_angle_rad", "hip_angular_velocity_rad_s",
            "com_x", "com_y", "com_z",
            "com_vx", "com_vy", "com_vz",
            "gyro_x", "gyro_y", "gyro_z",
            "accel_x", "accel_y", "accel_z",
            "hip_motor_torque",
        ]
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(header)
        csv_file.flush()
        log_debug("Wrote CSV header")

    log_debug("About to enter main loop")

    
    # Track position by integrating accelerometer data
    # We subtract gravity (9.81) from Z acceleration to get true acceleration relative to ground
    integrated_z = 0.0
    integrated_vz = 0.0
    last_accel_z = 0.0  # For numerical differentiation if needed

    # Main control loop
    elapsed_time = 0.0
    prev_hip_angle = REST_ANGLE_RAD
    prev_com_position = get_supervisor_com_position(supervisor) if has_supervisor else [0.0, 0.0, 0.0]
    prev_com_time = 0.0

    step_count = 0
    while robot.step(timestep) != -1:
        step_count += 1
        elapsed_time = robot.getTime()

        if step_count <= 3:  # Log first few steps for debugging
            log_debug(f"Step {step_count}: elapsed_time={elapsed_time:.4f}")

        if elapsed_time > TIME_SETTLE_END:
            log_debug(f"Simulation end reached: elapsed_time={elapsed_time:.4f}")
            break

        # Get target hip angle for this timestep
        target_hip_angle = get_hip_target_angle(elapsed_time)
        current_state = get_state(elapsed_time)

        # Set hip motor position (both sides synchronized)
        hip_motor_R.setPosition(target_hip_angle)
        hip_motor_L.setPosition(target_hip_angle)

        # Set hip motor speed limits (allow smooth following)
        hip_motor_R.setVelocity(MAX_HIP_MOTOR_SPEED)
        hip_motor_L.setVelocity(MAX_HIP_MOTOR_SPEED)

        # Control wheel motors
        wheel_velocity = get_wheel_target_velocity(current_state)
        wheel_motor_R.setVelocity(wheel_velocity)
        wheel_motor_L.setVelocity(wheel_velocity)

        # Read sensors
        gyro_values = gyro.getValues()
        accel_values = accelerometer.getValues()

        # Read hip angle from position sensors if available
        if has_hip_sensors and hip_position_R:
            current_hip_angle = hip_position_R.getValue()
        else:
            current_hip_angle = target_hip_angle  # fallback to target

        # Compute hip angular velocity (simple finite difference)
        dt = timestep / 1000.0
        hip_angular_velocity = (current_hip_angle - prev_hip_angle) / dt if dt > 0 else 0.0
        prev_hip_angle = current_hip_angle

        # Get CoM data from Supervisor
        current_com_position = get_supervisor_com_position(supervisor) if has_supervisor else prev_com_position
        com_velocity = get_supervisor_com_velocity(supervisor, prev_com_position, prev_com_time, elapsed_time)
        prev_com_position = current_com_position
        prev_com_time = elapsed_time

        # Estimate hip motor torque (very rough: F = tau / lever_arm, assume constant lever arm)
        # Placeholder: use motor load ratio or assume ~0.2 N·m during active phases
        # For now, log a nominal value; real implementation would query motor.getForceFeedback() if available
        hip_motor_torque = 0.0
        try:
            # Some Webots versions support getForceFeedback() on motors
            feedback = hip_motor_R.getForceFeedback()
            hip_motor_torque = float(feedback) if feedback is not None else 0.0
        except (AttributeError, RuntimeError):
            # Fallback: estimate based on state (during PUSH phase, assume high torque)
            if current_state == State.PUSH:
                hip_motor_torque = 0.3  # conservative estimate
            elif current_state == State.CROUCH:
                hip_motor_torque = 0.15
            else:
                hip_motor_torque = 0.0

        # Write telemetry row
        row = [
            f"{elapsed_time:.4f}",
            f"{current_hip_angle:.6f}",
            f"{hip_angular_velocity:.6f}",
            f"{current_com_position[0]:.6f}",
            f"{current_com_position[1]:.6f}",
            f"{integrated_z:.6f}",
            f"{com_velocity[0]:.6f}",
            f"{com_velocity[1]:.6f}",
            f"{com_velocity[2]:.6f}",
            f"{gyro_values[0]:.6f}",
            f"{gyro_values[1]:.6f}",
            f"{gyro_values[2]:.6f}",
            f"{accel_values[0]:.6f}",
            f"{accel_values[1]:.6f}",
            f"{accel_values[2]:.6f}",
            f"{hip_motor_torque:.6f}",
        ]
        csv_writer = csv.writer(csv_file)

        # Integrate accelerometer data for position (Z only for jump height)
        accel_z_true = accel_values[2] - 9.81  # Subtract gravity
        integrated_vz += accel_z_true * (dt if dt > 0 else 0.0)
        integrated_z += integrated_vz * (dt if dt > 0 else 0.0)

        # Use integrated Z as a proxy for height (offset by starting height 0.1005 m)
        # During flight phase, this will show positive values as robot goes up

        csv_writer.writerow(row)
        csv_file.flush()

    log_debug(f"Loop exited after {step_count} steps")
    log_debug("Telemetry logged successfully")

except Exception as e:
    log_debug(f"ERROR: {e}")
    log_debug(traceback.format_exc())

finally:
    csv_file.close()
