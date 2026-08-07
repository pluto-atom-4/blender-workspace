"""Phase 1 linkage verification: 4-bar leg kinematics for the dual-wheel
legged robot's hip/knee linkage (issue #25, Phase 1).

Phase 0 (feasibility_phase0.py) confirmed via a coarse energy calc that the
STS3032 hip actuator isn't obviously too weak. Phase 1 verifies the
EXISTING leg linkage geometry -- already built in
model_dual_wheel_legged_robot_precise.py's build_leg() -- against two
design rules, rather than designing a new linkage:

  1. Linear Vector Rule: as the hip sweeps its full operational range, the
     ankle/ground-contact point should trace a path close to a straight
     line (so the ground-reaction-force vector direction stays close to
     constant through the stroke), and that line should pass close to the
     robot's CoM horizontal position (so the thrust doesn't induce an
     unwanted horizontal moment).
  2. Variable Mechanical Advantage: the leg's force-multiplication should
     increase toward full extension (LAUNCH_ANGLE) so the servo's limited
     torque produces a bigger push right when it matters for liftoff.

Both checks are against PROPOSED thresholds (explicitly not final, same
convention as feasibility_phase0.py's own JUMP_HEIGHT_THRESHOLD_M) -- see
the issue #25 Phase 1 comment for the full rationale.

This module also (a) re-derives feasibility_phase0.py's STROKE_M placeholder
from real kinematics instead of the old "half of total leg reach" guess
(Task 3), and (b) sizes a first-pass PEA (parallel elastic actuation)
spring constant from the gravitational torque at rest stance (Task 4).

Pure Python, no bpy dependency -- same subproject as feasibility_phase0.py
(numpy/scipy/pandas/pytest available via pyproject.toml, though this module
only actually needs math/dataclasses from the stdlib).
"""

from __future__ import annotations

import math

from feasibility_phase0 import BASE_L_MM, GRAVITY_M_S2 as PHASE0_GRAVITY_M_S2, TOTAL_MASS_KG

# ---------------------------------------------------------------------------
# Reference geometry constants -- read directly from
# model_dual_wheel_legged_robot_precise.py's build_leg()/kf_leg_angle()
# (confirmed current as of issue #25 Phase 1; re-check that file if this
# module and the model ever drift). See that file's build_leg() (~line 295)
# and the CROUCH_ANGLE/LAUNCH_ANGLE/DEFAULT_HIP_ANGLE comments (~line
# 499-514) for the source of these numbers.
# ---------------------------------------------------------------------------

UPPER_LEN_MM = 40.0   # upper_plate_front/back length, hip pivot to knee knuckle
LOWER_LEN_MM = 30.0   # lower_plate length, knee knuckle to ankle_block
ANKLE_DROP_MM = 10.0  # ankle_block center to wheel_servo/wheel axle, below lower_plate's tail
HIP_LATERAL_MM = 50.0
HIP_Z_MM = 20.0

CROUCH_ANGLE_DEG = 120.0   # deep crouch (kf_leg_angle load phase)
LAUNCH_ANGLE_DEG = 15.0    # explosive extension (kf_leg_angle push phase)
DEFAULT_HIP_ANGLE_DEG = 58.0  # resting stance

# model_dual_wheel_legged_robot_precise.py's own module-level GRAVITY is 9.8,
# not feasibility_phase0.py's GRAVITY_M_S2=9.81 -- both are reasonable g
# approximations (negligible practical difference) but Task 4's PEA spring
# sizing reuses the model script's own constant for consistency with the
# geometry/animation source of truth it's derived alongside.
GRAVITY_M_S2 = 9.8

assert PHASE0_GRAVITY_M_S2 == 9.81  # documents the (intentional, harmless) mismatch noted above


# ---------------------------------------------------------------------------
# Task 1/2: ankle kinematics
# ---------------------------------------------------------------------------

def ankle_position(hip_angle_deg: float) -> tuple[float, float]:
    """Ankle/ground-contact position (x_mm, z_mm) in the hip-local frame,
    for a given hip_angle_deg (the same value kf_leg_angle() keyframes onto
    hip_servo/upper_plate_front/back's rotation_euler.x).

    x is the horizontal axis within the leg's sagittal sweep plane (the
    model's world Y, since the hip rotates about world/local X -- see
    build_leg()'s hip_world Y-component and kf_leg_angle's rotation_euler.x
    usage); z is vertical, positive up, both relative to the hip pivot at
    the origin.

    Matches build_leg()'s actual linkage: upper_plate_front/back sweep
    hip_angle_deg around the hip pivot, so the knee knuckle (their tip)
    traces a circular arc of radius UPPER_LEN_MM centered on the hip pivot.
    knee_knuckle is then keyframed to the exact negative of the hip angle
    (see kf_leg_angle), which cancels upper_plate's rotation for everything
    it parents (lower_plate, ankle_block, wheel) -- net rotation of that
    subtree is zero, i.e. it stays level, so the ankle sits a CONSTANT
    (LOWER_LEN_MM + ANKLE_DROP_MM) straight below the arc point regardless
    of hip_angle_deg.

    Verified against build_balance_and_jump()'s own sampled-Z-table
    comment (needed base_plate.z at 5deg steps: 15->+17.4, 38->+10.3,
    58->0, 90->-21.2, 120->-41.2): the needed chassis Z at each angle is
    -(ankle_z(angle) - ankle_z(58)) if the ankle is pinned to the floor,
    and that reproduces all five sampled values from this formula to
    within 0.01mm.
    """
    theta = math.radians(hip_angle_deg)
    arc_x_mm = UPPER_LEN_MM * math.sin(theta)
    arc_z_mm = -UPPER_LEN_MM * math.cos(theta)
    x_mm = arc_x_mm
    z_mm = arc_z_mm - (LOWER_LEN_MM + ANKLE_DROP_MM)
    return (x_mm, z_mm)


def horizontal_moment_arm_mm(hip_angle_deg: float) -> float:
    """Horizontal (perpendicular-to-gravity) distance from the hip rotation
    axis to the ankle/ground-contact point -- the moment arm r such that a
    vertical force F at the ankle produces hip torque tau = F * r (and,
    equivalently, tau at the hip produces vertical force F = tau / r: the
    "vertical-force-to-hip-torque ratio", 1/r, is what Task 2 calls the
    mechanical advantage MA)."""
    x_mm, _z_mm = ankle_position(hip_angle_deg)
    return abs(x_mm)


# ---------------------------------------------------------------------------
# Task 1: Linear Vector Rule
# ---------------------------------------------------------------------------

# Sample every 1deg across the real operational sweep (LAUNCH_ANGLE to
# CROUCH_ANGLE) -- fine enough for a smooth curve, well beyond the 5
# already-known comment samples (15/38/58/90/120) used above just to
# cross-check the formula.
SAMPLE_STEP_DEG = 1.0

# Proposed, not final (same convention as feasibility_phase0.py's
# JUMP_HEIGHT_THRESHOLD_M) -- see issue #25 Phase 1 comment.
LINEAR_VECTOR_MAX_DEVIATION_MM = 8.0

# Proposed tolerance for the chord-vs-CoM horizontal check below --
# informational context for the Linear Vector Rule, not one of the two
# named PASS/FAIL gate thresholds this module reports (deviation and MA
# ratio are; see module docstring).
COM_OFFSET_TOLERANCE_MM = 15.0

# First-pass CoM horizontal-offset estimate, reusing feasibility_phase0.py's
# placeholder mass breakdown as a simplified two-bucket model (that file has
# no per-component POSITION data, only masses, so this is a documented
# simplification, not a real CoM calc):
#   - hip-servo mass (2 x STS3032 @ 25g, from feasibility_phase0.py's own
#     mass-breakdown comment) sits AT the hip pivot -> 0mm horizontal offset.
#   - everything else (base plate, battery, deck/ATOM S3, remaining leg
#     plates, wheel servos) is treated as concentrated at the chassis's own
#     geometric center, which sits BASE_L_MM/2 forward of the hip pivot
#     (hip_world's Y is -BASE_L/2 - REAR_EXT_T in the model script; ignoring
#     the small REAR_EXT_T=3mm here is itself a further simplification).
# Weighted average of those two buckets gives a rough forward-of-hip CoM
# offset -- explicitly first-pass, not a real BOM-based CoM.
HIP_SERVO_MASS_KG = 2 * 0.025  # 2 hip servos only (of the 4 STS3032 total), 25g each
CHASSIS_CENTER_OFFSET_FROM_HIP_MM = BASE_L_MM / 2.0
REMAINDER_MASS_KG = TOTAL_MASS_KG - HIP_SERVO_MASS_KG
COM_HORIZONTAL_OFFSET_FROM_HIP_MM = (
    REMAINDER_MASS_KG * CHASSIS_CENTER_OFFSET_FROM_HIP_MM + HIP_SERVO_MASS_KG * 0.0
) / TOTAL_MASS_KG


def sampled_ankle_positions(step_deg: float = SAMPLE_STEP_DEG) -> list[tuple[float, float, float]]:
    """List of (hip_angle_deg, x_mm, z_mm) across [LAUNCH_ANGLE_DEG,
    CROUCH_ANGLE_DEG] at step_deg increments (endpoints always included)."""
    samples = []
    angle = LAUNCH_ANGLE_DEG
    while angle < CROUCH_ANGLE_DEG:
        x_mm, z_mm = ankle_position(angle)
        samples.append((angle, x_mm, z_mm))
        angle += step_deg
    x_mm, z_mm = ankle_position(CROUCH_ANGLE_DEG)
    samples.append((CROUCH_ANGLE_DEG, x_mm, z_mm))
    return samples


def max_chord_deviation_mm(samples: list[tuple[float, float, float]] | None = None) -> float:
    """Max perpendicular distance (mm) of the sampled ankle-position curve
    from the straight chord connecting its LAUNCH_ANGLE_DEG and
    CROUCH_ANGLE_DEG endpoints."""
    if samples is None:
        samples = sampled_ankle_positions()
    x1, z1 = samples[0][1], samples[0][2]
    x2, z2 = samples[-1][1], samples[-1][2]
    dx, dz = x2 - x1, z2 - z1
    chord_len = math.hypot(dx, dz)
    max_dev = 0.0
    for _angle, x, z in samples:
        # 2D cross product magnitude / chord length = perpendicular distance
        cross = abs(dx * (z - z1) - dz * (x - x1))
        dev = cross / chord_len
        max_dev = max(max_dev, dev)
    return max_dev


def chord_mean_horizontal_mm(samples: list[tuple[float, float, float]] | None = None) -> float:
    """Mean of the chord endpoints' x (horizontal) coordinates -- used as
    the chord's representative horizontal position for the CoM-offset
    tolerance check."""
    if samples is None:
        samples = sampled_ankle_positions()
    x1 = samples[0][1]
    x2 = samples[-1][1]
    return (x1 + x2) / 2.0


# ---------------------------------------------------------------------------
# Task 2: Variable Mechanical Advantage
# ---------------------------------------------------------------------------

# Proposed, not final -- see issue #25 Phase 1 comment.
MECHANICAL_ADVANTAGE_MIN_RATIO = 1.3


def mechanical_advantage_ratio() -> float:
    """MA(LAUNCH_ANGLE_DEG) / MA(CROUCH_ANGLE_DEG), where MA(angle) =
    1 / horizontal_moment_arm_mm(angle) is the vertical-force-to-hip-torque
    ratio (bigger MA = more force out per unit of hip torque in). Since MA
    is inversely proportional to the moment arm, this ratio equals
    moment_arm(CROUCH_ANGLE_DEG) / moment_arm(LAUNCH_ANGLE_DEG) -- expected
    to be > 1 (leverage/force-multiplication increasing toward full
    extension at LAUNCH_ANGLE_DEG, where the moment arm is smallest)."""
    r_launch = horizontal_moment_arm_mm(LAUNCH_ANGLE_DEG)
    r_crouch = horizontal_moment_arm_mm(CROUCH_ANGLE_DEG)
    return r_crouch / r_launch


# ---------------------------------------------------------------------------
# Task 3: stroke derivation (corrects feasibility_phase0.py's STROKE_M)
# ---------------------------------------------------------------------------

def derived_stroke_mm() -> float:
    """Real vertical (Z) travel of the ankle between CROUCH_ANGLE_DEG and
    LAUNCH_ANGLE_DEG, from ankle_position() -- replaces
    feasibility_phase0.py's old STROKE_M placeholder ("half of total leg
    reach", a guess) with a value actually derived from the leg's FK
    geometry. Expected to land close to the ~59mm the model script's own
    CROUCH_ANGLE/LAUNCH_ANGLE comment already mentions (empirically swept
    chassis-Z, not this formula) -- this independently re-derives that
    number rather than copying it."""
    _x_launch, z_launch = ankle_position(LAUNCH_ANGLE_DEG)
    _x_crouch, z_crouch = ankle_position(CROUCH_ANGLE_DEG)
    return abs(z_launch - z_crouch)


# ---------------------------------------------------------------------------
# Task 4: PEA spring stiffness sizing
# ---------------------------------------------------------------------------

def gravitational_torque_at_rest_n_m() -> float:
    """Gravitational torque (N*m) about the hip axis at DEFAULT_HIP_ANGLE_DEG
    (rest stance), using the ankle's own horizontal offset from the hip at
    that angle as the effective lever arm for the robot's weight.

    First-pass simplification: in standing balance the ground-reaction
    force acts (approximately) through the ankle/wheel contact point, so
    the horizontal offset between that contact point and the hip axis --
    the same horizontal_moment_arm_mm() used for Task 2 -- doubles as the
    lever arm for the body-weight torque the hip must resist at rest,
    rather than a separately-modeled CoM position. TOTAL_MASS_KG is
    imported directly from feasibility_phase0.py (not replicated) so the
    two Phase 0/1 modules can't silently drift on the placeholder mass."""
    lever_arm_m = horizontal_moment_arm_mm(DEFAULT_HIP_ANGLE_DEG) / 1000.0
    return TOTAL_MASS_KG * GRAVITY_M_S2 * lever_arm_m


# Engagement-angle assumption: the PEA spring is at its natural (unloaded)
# length when the leg is at LAUNCH_ANGLE_DEG (full extension) -- a plausible
# "relaxed" reference pose for a parallel elastic element -- and stretches
# as the hip bends toward DEFAULT_HIP_ANGLE_DEG (rest stance). The angular
# deflection from natural length to rest angle is therefore
# (DEFAULT_HIP_ANGLE_DEG - LAUNCH_ANGLE_DEG), converted to radians. This is
# a first-pass sizing assumption, not a final spring design -- a different
# natural-length pose would change the target constant.
PEA_ENGAGEMENT_DEFLECTION_DEG = DEFAULT_HIP_ANGLE_DEG - LAUNCH_ANGLE_DEG


def pea_spring_constant_n_m_per_rad() -> float:
    """Target PEA spring constant (N*m/rad): gravitational torque at rest
    stance divided by the assumed angular deflection from the spring's
    natural length (LAUNCH_ANGLE_DEG) to the rest angle
    (DEFAULT_HIP_ANGLE_DEG) -- see PEA_ENGAGEMENT_DEFLECTION_DEG's comment.
    Per the issue's Counter-Balance Rule: sized so the spring's torque at
    58deg matches/supports the gravitational torque, freeing the servo's
    torque budget for the push."""
    torque_n_m = gravitational_torque_at_rest_n_m()
    deflection_rad = math.radians(PEA_ENGAGEMENT_DEFLECTION_DEG)
    return torque_n_m / deflection_rad


if __name__ == "__main__":
    samples = sampled_ankle_positions()

    max_dev_mm = max_chord_deviation_mm(samples)
    chord_x_mm = chord_mean_horizontal_mm(samples)
    com_dev_mm = abs(chord_x_mm - COM_HORIZONTAL_OFFSET_FROM_HIP_MM)

    ma_ratio = mechanical_advantage_ratio()
    stroke_mm = derived_stroke_mm()
    gravity_torque_n_m = gravitational_torque_at_rest_n_m()
    spring_k = pea_spring_constant_n_m_per_rad()

    print("=" * 70)
    print("Phase 1 linkage verification (issue #25, Phase 1)")
    print("=" * 70)
    print(f"Sampled {len(samples)} points, {LAUNCH_ANGLE_DEG:.0f}deg to "
          f"{CROUCH_ANGLE_DEG:.0f}deg, every {SAMPLE_STEP_DEG:.0f}deg")
    print("-" * 70)
    print("Task 1: Linear Vector Rule")
    print(f"  Max perpendicular deviation from chord: {max_dev_mm:.3f}mm")
    print(f"  Threshold (proposed): <= {LINEAR_VECTOR_MAX_DEVIATION_MM:.1f}mm")
    verdict1 = "PASS" if max_dev_mm <= LINEAR_VECTOR_MAX_DEVIATION_MM else "FAIL"
    print(f"  -> {verdict1}")
    print(f"  Chord mean horizontal position: {chord_x_mm:.2f}mm from hip")
    print(f"  First-pass CoM horizontal offset estimate: {COM_HORIZONTAL_OFFSET_FROM_HIP_MM:.2f}mm from hip")
    com_verdict = "within" if com_dev_mm <= COM_OFFSET_TOLERANCE_MM else "OUTSIDE"
    print(f"  Chord vs CoM deviation: {com_dev_mm:.2f}mm ({com_verdict} "
          f"proposed {COM_OFFSET_TOLERANCE_MM:.1f}mm tolerance) [informational]")
    print("-" * 70)
    print("Task 2: Variable Mechanical Advantage")
    print(f"  Moment arm at {LAUNCH_ANGLE_DEG:.0f}deg: {horizontal_moment_arm_mm(LAUNCH_ANGLE_DEG):.3f}mm")
    print(f"  Moment arm at {CROUCH_ANGLE_DEG:.0f}deg: {horizontal_moment_arm_mm(CROUCH_ANGLE_DEG):.3f}mm")
    print(f"  MA({LAUNCH_ANGLE_DEG:.0f}deg) / MA({CROUCH_ANGLE_DEG:.0f}deg) ratio: {ma_ratio:.3f}x")
    print(f"  Threshold (proposed): >= {MECHANICAL_ADVANTAGE_MIN_RATIO:.1f}x")
    verdict2 = "PASS" if ma_ratio >= MECHANICAL_ADVANTAGE_MIN_RATIO else "FAIL"
    print(f"  -> {verdict2}")
    print("-" * 70)
    print("Task 3: Stroke derivation (feasibility_phase0.py STROKE_M correction)")
    print(f"  Derived vertical stroke ({CROUCH_ANGLE_DEG:.0f}deg -> {LAUNCH_ANGLE_DEG:.0f}deg): {stroke_mm:.3f}mm")
    print("-" * 70)
    print("Task 4: PEA spring stiffness sizing")
    print(f"  Horizontal moment arm at rest ({DEFAULT_HIP_ANGLE_DEG:.0f}deg): "
          f"{horizontal_moment_arm_mm(DEFAULT_HIP_ANGLE_DEG):.3f}mm")
    print(f"  Gravitational torque at rest stance: {gravity_torque_n_m:.4f} N*m")
    print(f"  Assumed engagement deflection (natural length at {LAUNCH_ANGLE_DEG:.0f}deg "
          f"-> rest {DEFAULT_HIP_ANGLE_DEG:.0f}deg): {PEA_ENGAGEMENT_DEFLECTION_DEG:.1f}deg")
    print(f"  Target spring constant: {spring_k:.4f} N*m/rad")
    print("=" * 70)
