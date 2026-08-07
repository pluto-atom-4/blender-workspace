"""Phase 0 feasibility gate: back-of-envelope jump-height estimate for the
dual-wheel legged robot's STS3032 hip servo (issue #25, Phase 0).

Before investing in the full 4-bar linkage/spring design (Phase 1+), this
is a cheap check on whether STS3032's torque ceiling (4.5kg-cm@6V stall,
25g each) can plausibly produce a meaningful jump height at all, given the
existing rig's real geometry constants (read from
model_dual_wheel_legged_robot_precise.py, the "_precise" variant --
LEGGED_ROBOT.md already references it, not the base
model_dual_wheel_legged_robot.py).

Deliberately coarse physics -- that is the point of a Phase 0 gate, not a
bug:

  1. Force from torque:    F = tau / lever_arm
  2. Work over stroke:     W = F * stroke
  3. Liftoff velocity:     v = sqrt(2 W / m)      (energy conservation, no losses)
  4. Apex height:          dh = v^2 / (2 g)

Two cases are reported, not one: OPTIMISTIC uses STS3032's published stall
torque as-is (an upper bound -- real delivered torque falls as angular
speed rises); PESSIMISTIC derates that torque (see TORQUE_DERATE_FRACTION)
since STS3032 has no published continuous/non-stall rating at all, so the
actually-safe sustained torque is unknown and could be meaningfully lower.
Reporting a range, not a single flattering number, is the explicit intent
per the Phase 0 implementation plan (issue #25 comment).

Single function (estimate_jump_height) plus named constants for every
assumption, so swapping in a real BOM mass or Phase 1's actual
linkage-derived lever arm later is a one-line edit, not a rewrite.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Reference geometry constants -- read directly from
# model_dual_wheel_legged_robot_precise.py (confirmed current as of issue
# #25 Phase 0; re-check that file if this module and the model ever drift).
# ---------------------------------------------------------------------------

UPPER_LEN_MM = 40.0
LOWER_LEN_MM = 30.0
ANKLE_DROP_MM = 10.0
WHEEL_R_MM = 40.0
HIP_LATERAL_MM = 50.0
BASE_W_MM, BASE_L_MM, BASE_T_MM = 90.0, 70.0, 3.0

# ---------------------------------------------------------------------------
# Mass estimate -- no mass constant exists anywhere in
# model_dual_wheel_legged_robot_precise.py or model_dual_wheel_legged_robot.py.
# This is a PLACEHOLDER pending a real BOM, matching this repo's existing
# convention for placeholder masses (see PENDULUM.md: "Mass and impulse
# values are placeholders sized for a small robot, not pulled from a real
# BOM -- tune them against actual part weights before trusting the sim's
# dynamics quantitatively.").
#
# Built from:
#   4 x STS3032 (2 hip + 2 wheel) @ 25g  = 100g
#   Aluminum base plate (90x70x3mm @ ~2.7 g/cm^3) ~= 51g
#   Leg plates (4 small CNC links, rough estimate)  ~= 40g
#   LiPo + ATOM S3 + PCB deck (order-of-magnitude placeholder) ~= 109g
#   -----------------------------------------------------------
#   Total                                            ~= 300g
# Picked as the midpoint of the issue's proposed ~250-350g range.
TOTAL_MASS_KG = 0.300  # PLACEHOLDER -- not sourced from a real BOM, see above

# ---------------------------------------------------------------------------
# Actuator constants -- Feetech STS3032 datasheet: 4.5 kg-cm stall torque
# @ 6V. 1 kgf-cm = 0.0980665 N-m.
# ---------------------------------------------------------------------------

STALL_TORQUE_KGF_CM = 4.5
KGF_CM_TO_N_M = 0.0980665
STALL_TORQUE_N_M = STALL_TORQUE_KGF_CM * KGF_CM_TO_N_M  # ~0.4413 N-m

# STS3032 has no published continuous (non-stall) torque rating -- only the
# stall figure above appears in the datasheet. Derating by 50% for the
# pessimistic case is a judgment call standing in for that missing number,
# not a spec value: it is roughly in line with the general 1.5-3x
# peak-over-continuous safety margins commonly recommended for balancing
# robots (see the architect-assessment comment on issue #25), landing near
# the conservative end of that range.
TORQUE_DERATE_FRACTION = 0.5

# Lever arm: UPPER_LEN as a first-pass stand-in for the hip servo's
# effective moment arm. Real mechanical-advantage geometry isn't finalized
# until Phase 1's linkage design -- this is deliberately the simplest
# possible assumption, not a linkage-accurate one.
LEVER_ARM_M = UPPER_LEN_MM / 1000.0  # 0.04 m

# Stroke: real vertical (Z) travel of the ankle between CROUCH_ANGLE
# (120deg) and LAUNCH_ANGLE (15deg), derived from Phase 1's
# linkage_kinematics.py (ankle_position()-based FK, not this file's old
# "half of total leg reach" guess -- see that module's derived_stroke_mm()
# for the calculation). Also matches
# model_dual_wheel_legged_robot_precise.py's own CROUCH_ANGLE/LAUNCH_ANGLE
# comment, which independently cites ~59mm from an empirical per-frame
# chassis-Z sweep.
STROKE_M = 0.058637  # 58.637mm, from linkage_kinematics.derived_stroke_mm()

GRAVITY_M_S2 = 9.81

# Pass bar: roughly half the rig's chassis height. Proposed, not asserted
# final -- see the issue #25 Phase 0 comment.
JUMP_HEIGHT_THRESHOLD_M = 0.020  # 20mm


def estimate_jump_height(torque_n_m: float, lever_arm_m: float, stroke_m: float, mass_kg: float) -> float:
    """Coarse energy-conservation jump-height estimate, in meters.

    F = torque_n_m / lever_arm_m           (force from torque)
    W = F * stroke_m                       (work over stroke)
    v = sqrt(2 W / mass_kg)                (liftoff velocity, no losses)
    dh = v^2 / (2 * GRAVITY_M_S2)          (apex height)

    Deliberately coarse (see module docstring): constant torque across the
    full stroke, zero mechanical losses, no accounting for the actual 4-bar
    linkage kinematics. This is a Phase 0 feasibility gate, not a final
    performance prediction.
    """
    force_n = torque_n_m / lever_arm_m
    work_j = force_n * stroke_m
    liftoff_velocity_m_s = math.sqrt(2.0 * work_j / mass_kg)
    apex_height_m = (liftoff_velocity_m_s ** 2) / (2.0 * GRAVITY_M_S2)
    return apex_height_m


if __name__ == "__main__":
    optimistic_torque_n_m = STALL_TORQUE_N_M
    pessimistic_torque_n_m = STALL_TORQUE_N_M * (1.0 - TORQUE_DERATE_FRACTION)

    optimistic_height_m = estimate_jump_height(optimistic_torque_n_m, LEVER_ARM_M, STROKE_M, TOTAL_MASS_KG)
    pessimistic_height_m = estimate_jump_height(pessimistic_torque_n_m, LEVER_ARM_M, STROKE_M, TOTAL_MASS_KG)

    print("=" * 70)
    print("Phase 0 feasibility gate: STS3032 jump-height estimate (issue #25)")
    print("=" * 70)
    print(f"Mass estimate (placeholder): {TOTAL_MASS_KG * 1000:.0f}g")
    print(f"Lever arm: {LEVER_ARM_M * 1000:.0f}mm    Stroke: {STROKE_M * 1000:.0f}mm")
    print(f"Threshold: {JUMP_HEIGHT_THRESHOLD_M * 1000:.0f}mm")
    print("-" * 70)
    for label, torque_n_m, height_m in (
        ("OPTIMISTIC (stall torque)", optimistic_torque_n_m, optimistic_height_m),
        (f"PESSIMISTIC ({TORQUE_DERATE_FRACTION * 100:.0f}% derated)", pessimistic_torque_n_m, pessimistic_height_m),
    ):
        verdict = "PASS" if height_m >= JUMP_HEIGHT_THRESHOLD_M else "FAIL"
        print(
            f"{label}: torque={torque_n_m:.4f} N*m  "
            f"apex_height={height_m * 1000:.1f}mm  -> {verdict}"
        )
    print("=" * 70)
