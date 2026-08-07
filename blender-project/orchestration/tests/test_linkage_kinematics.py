"""Unit tests for the Phase 1 linkage verification in linkage_kinematics.py
(issue #25, Phase 1).

Pure arithmetic, no Blender/bpy/Webots dependency. Mirrors
test_feasibility_phase0.py's existing pattern in this same orchestration
subproject.
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from linkage_kinematics import (  # noqa: E402
    ANKLE_DROP_MM,
    CROUCH_ANGLE_DEG,
    LAUNCH_ANGLE_DEG,
    LOWER_LEN_MM,
    UPPER_LEN_MM,
    ankle_position,
    derived_stroke_mm,
    horizontal_moment_arm_mm,
    mechanical_advantage_ratio,
    pea_spring_constant_n_m_per_rad,
)


def test_ankle_position_at_zero_degrees_matches_hand_computed_trig():
    """At hip_angle=0deg the leg hangs straight down: sin(0)=0, cos(0)=1,
    so x=0 exactly (directly below the hip) and z=-(UPPER_LEN + LOWER_LEN +
    ANKLE_DROP) exactly (full straight-line reach below the hip pivot)."""
    x_mm, z_mm = ankle_position(0.0)

    assert x_mm == pytest.approx(0.0, abs=1e-9)
    assert z_mm == pytest.approx(-(UPPER_LEN_MM + LOWER_LEN_MM + ANKLE_DROP_MM), rel=1e-9)


def test_ankle_position_at_ninety_degrees_matches_hand_computed_trig():
    """At hip_angle=90deg: sin(90)=1, cos(90)=0, so x=UPPER_LEN exactly (the
    arc point is level with the hip) and z=-(LOWER_LEN + ANKLE_DROP) exactly
    (only the constant below-arc-point offset remains)."""
    x_mm, z_mm = ankle_position(90.0)

    assert x_mm == pytest.approx(UPPER_LEN_MM, rel=1e-9)
    assert z_mm == pytest.approx(-(LOWER_LEN_MM + ANKLE_DROP_MM), rel=1e-9)


def test_ankle_position_reproduces_model_script_sampled_z_table():
    """model_dual_wheel_legged_robot_precise.py's CROUCH_ANGLE/LAUNCH_ANGLE
    comment reports the empirically-swept needed base_plate.z (mm) at 5deg
    steps: 15->+17.4, 38->+10.3, 58->0, 90->-21.2, 120->-41.2 (chassis Z
    needed to keep the ankle pinned to the floor, relative to 58deg). If the
    ankle is pinned to a fixed floor height, the needed chassis Z shift
    equals -(ankle_z(angle) - ankle_z(58)). Cross-checks ankle_position()
    against that independently-derived (simulation-swept, not formula-
    derived) reference table."""
    _x58, z58 = ankle_position(58.0)
    expected = {15.0: 17.4, 38.0: 10.3, 90.0: -21.2, 120.0: -41.2}

    for angle_deg, expected_chassis_dz_mm in expected.items():
        _x, z = ankle_position(angle_deg)
        chassis_dz_mm = -(z - z58)
        assert chassis_dz_mm == pytest.approx(expected_chassis_dz_mm, abs=0.05)


def test_horizontal_moment_arm_range_and_launch_vs_crouch_relationship():
    """The horizontal moment arm isn't monotonic across the full
    [LAUNCH_ANGLE_DEG, CROUCH_ANGLE_DEG] sweep (it's UPPER_LEN_MM*sin(theta),
    which peaks at 90deg, inside that range) -- so this checks the range
    stays bounded by UPPER_LEN_MM (the arc radius) rather than asserting
    naive monotonicity, plus the specific launch-vs-crouch relationship the
    Variable Mechanical Advantage rule (Task 2) depends on: the moment arm
    at LAUNCH_ANGLE_DEG (near-straight leg) must be smaller than at
    CROUCH_ANGLE_DEG (bent leg) -- smaller moment arm there is what gives
    higher force output (MA = 1/r) right at full extension."""
    r_launch = horizontal_moment_arm_mm(LAUNCH_ANGLE_DEG)
    r_crouch = horizontal_moment_arm_mm(CROUCH_ANGLE_DEG)
    r_peak = horizontal_moment_arm_mm(90.0)

    for angle_deg in range(int(LAUNCH_ANGLE_DEG), int(CROUCH_ANGLE_DEG) + 1, 5):
        r = horizontal_moment_arm_mm(float(angle_deg))
        assert 0.0 <= r <= UPPER_LEN_MM + 1e-9

    assert r_launch < r_crouch
    assert r_peak == pytest.approx(UPPER_LEN_MM, rel=1e-9)
    assert r_peak >= r_launch and r_peak >= r_crouch


def test_mechanical_advantage_ratio_favors_launch_angle():
    """MA(15deg)/MA(120deg) should exceed 1.0 -- more force multiplication
    (mechanical advantage) at full extension than at deep crouch -- and
    specifically match moment_arm(crouch)/moment_arm(launch), the algebraic
    identity mechanical_advantage_ratio() relies on (MA = 1/r)."""
    ratio = mechanical_advantage_ratio()
    r_launch = horizontal_moment_arm_mm(LAUNCH_ANGLE_DEG)
    r_crouch = horizontal_moment_arm_mm(CROUCH_ANGLE_DEG)

    assert ratio > 1.0
    assert ratio == pytest.approx(r_crouch / r_launch, rel=1e-9)


def test_derived_stroke_is_positive_and_in_sane_range():
    """The derived stroke should be positive and land in a physically sane
    range for this leg's scale (a few tens of mm, not near-zero and not
    larger than the leg's total possible reach) -- 30-100mm brackets the
    model script's own ~59mm comment estimate with headroom."""
    stroke_mm = derived_stroke_mm()

    assert stroke_mm > 0.0
    assert 30.0 <= stroke_mm <= 100.0


def test_derived_stroke_close_to_model_script_comment_estimate():
    """Independently cross-checks derived_stroke_mm() against the ~59mm
    figure model_dual_wheel_legged_robot_precise.py's own comments already
    mention (from an empirical per-frame chassis-Z sweep) -- this module
    derives that number from ankle_position() directly rather than copying
    it, so the two should agree closely."""
    stroke_mm = derived_stroke_mm()

    assert stroke_mm == pytest.approx(59.0, abs=1.0)


def test_pea_spring_constant_is_positive_and_finite():
    """The first-pass PEA spring constant sizing should produce a positive,
    finite N*m/rad figure -- a sanity check on the torque/deflection
    algebra, not a claim about the "right" spring."""
    k = pea_spring_constant_n_m_per_rad()

    assert math.isfinite(k)
    assert k > 0.0
