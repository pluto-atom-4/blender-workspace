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

import linkage_kinematics  # noqa: E402
from linkage_kinematics import (  # noqa: E402
    ANKLE_DROP_MM,
    CROUCH_ANGLE_DEG,
    LAUNCH_ANGLE_DEG,
    LINEAR_VECTOR_MAX_DEVIATION_MM,
    LOWER_LEN_MM,
    UPPER_LEN_MM,
    ankle_position,
    derived_stroke_mm,
    horizontal_moment_arm_mm,
    max_chord_deviation_mm,
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


def test_max_chord_deviation_matches_measured_value():
    """Regression guard (issue #41): pins the current leg linkage's
    max_chord_deviation_mm() at the measured ~15.648mm figure the #41
    architect plan cited (and this module's own __main__ report prints).
    Guards against silent geometry drift changing the number the
    LINEAR_VECTOR_MAX_DEVIATION_MM gate is evaluated against."""
    dev_mm = max_chord_deviation_mm()

    assert dev_mm == pytest.approx(15.648, abs=0.01)


def test_max_chord_deviation_is_scale_invariant_under_upper_len():
    """Issue #41 finding: because ankle_position() is a pure circular arc
    of radius UPPER_LEN_MM (theta-sweep endpoints fixed), both the sampled
    curve and its chord scale linearly with UPPER_LEN_MM -- so
    max_chord_deviation_mm() at UPPER_LEN_MM=2R is (to within float noise)
    exactly 2x the deviation at UPPER_LEN_MM=R. This documents *why*
    increasing UPPER_LEN_MM does NOT fix the Linear Vector Rule gate (it
    makes the deviation worse, not better) -- a guard against someone later
    "fixing" issue #41 by just bumping UPPER_LEN_MM without re-reading the
    rationale in LINEAR_VECTOR_MAX_DEVIATION_MM's comment.

    Uses the same module-global-reassignment override mechanism
    model_leg_linkage_deviation.py (issue #42) uses for build_leg()'s
    UPPER_LEN/HIP_Z, since ankle_position() resolves UPPER_LEN_MM as a free
    variable from linkage_kinematics's own module globals at call time.
    Restores the original value afterward so no test order dependency is
    introduced.
    """
    original_upper_len_mm = linkage_kinematics.UPPER_LEN_MM
    try:
        linkage_kinematics.UPPER_LEN_MM = original_upper_len_mm
        dev_at_r = linkage_kinematics.max_chord_deviation_mm()

        linkage_kinematics.UPPER_LEN_MM = original_upper_len_mm * 2.0
        dev_at_2r = linkage_kinematics.max_chord_deviation_mm()
    finally:
        linkage_kinematics.UPPER_LEN_MM = original_upper_len_mm

    assert dev_at_2r == pytest.approx(2.0 * dev_at_r, rel=1e-9)
    # Sanity-check the override was actually restored, not just re-set to
    # the same numeric value coincidentally.
    assert linkage_kinematics.UPPER_LEN_MM == original_upper_len_mm


def test_linear_vector_rule_passes_with_resolved_threshold():
    """Confirms the module's own PASS/FAIL logic (mirrored from __main__)
    reports PASS with the issue #41-resolved 18mm gate against the
    measured ~15.648mm deviation -- i.e. LINEAR_VECTOR_MAX_DEVIATION_MM was
    actually raised, and the linkage's own already-shipped geometry clears
    it with the documented margin."""
    dev_mm = max_chord_deviation_mm()

    assert LINEAR_VECTOR_MAX_DEVIATION_MM == pytest.approx(18.0)
    assert dev_mm <= LINEAR_VECTOR_MAX_DEVIATION_MM
