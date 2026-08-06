"""Unit tests for the Phase 0 feasibility gate in feasibility_phase0.py
(issue #25, Phase 0).

Deliberately scoped to estimate_jump_height() plus the repo-constants case
-- pure arithmetic, no Blender/bpy/Webots dependency. Mirrors
test_lqr_tuner.py's existing pattern in this same orchestration subproject.
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feasibility_phase0 import (  # noqa: E402
    GRAVITY_M_S2,
    JUMP_HEIGHT_THRESHOLD_M,
    LEVER_ARM_M,
    STALL_TORQUE_N_M,
    STROKE_M,
    TORQUE_DERATE_FRACTION,
    TOTAL_MASS_KG,
    estimate_jump_height,
)


def test_estimate_jump_height_matches_closed_form_hand_computable_case():
    """Simple hand-computable case: torque=1 N*m, lever_arm=1m (F=1N),
    stroke=1m (W=1J), mass=2kg.

    v = sqrt(2 * 1 / 2) = sqrt(1) = 1 m/s
    dh = v^2 / (2 * 9.81) = 1 / 19.62 = 0.050968... m

    Verifies the energy-conservation algebra directly (F=tau/lever,
    W=F*stroke, v=sqrt(2W/m), dh=v^2/2g) rather than just calling the
    function and eyeballing the number.
    """
    torque_n_m = 1.0
    lever_arm_m = 1.0
    stroke_m = 1.0
    mass_kg = 2.0

    force_n = torque_n_m / lever_arm_m
    work_j = force_n * stroke_m
    expected_velocity = math.sqrt(2.0 * work_j / mass_kg)
    expected_height = (expected_velocity ** 2) / (2.0 * GRAVITY_M_S2)

    height_m = estimate_jump_height(torque_n_m, lever_arm_m, stroke_m, mass_kg)

    assert height_m == pytest.approx(expected_height, rel=1e-10)
    assert height_m == pytest.approx(1.0 / (2.0 * GRAVITY_M_S2), rel=1e-10)


def test_estimate_jump_height_scales_as_expected():
    """Doubling torque doubles force and work, so v scales by sqrt(2) and
    height (proportional to v^2) doubles -- a second, independent algebra
    check on top of the closed-form case above."""
    base_height = estimate_jump_height(1.0, 1.0, 1.0, 1.0)
    doubled_torque_height = estimate_jump_height(2.0, 1.0, 1.0, 1.0)

    assert doubled_torque_height == pytest.approx(2.0 * base_height, rel=1e-10)


def test_repo_constants_case_produces_positive_finite_height():
    """The real repo-constants case (STALL_TORQUE_N_M, LEVER_ARM_M,
    STROKE_M, TOTAL_MASS_KG, as used by the __main__ report) must produce a
    positive, finite apex height for both the optimistic and pessimistic
    (derated) torque cases."""
    optimistic_torque_n_m = STALL_TORQUE_N_M
    pessimistic_torque_n_m = STALL_TORQUE_N_M * (1.0 - TORQUE_DERATE_FRACTION)

    for torque_n_m in (optimistic_torque_n_m, pessimistic_torque_n_m):
        height_m = estimate_jump_height(torque_n_m, LEVER_ARM_M, STROKE_M, TOTAL_MASS_KG)
        assert math.isfinite(height_m)
        assert height_m > 0.0

    # Pessimistic (derated torque) must never exceed optimistic (stall
    # torque) -- less force in should never produce more height out.
    optimistic_height_m = estimate_jump_height(optimistic_torque_n_m, LEVER_ARM_M, STROKE_M, TOTAL_MASS_KG)
    pessimistic_height_m = estimate_jump_height(pessimistic_torque_n_m, LEVER_ARM_M, STROKE_M, TOTAL_MASS_KG)
    assert pessimistic_height_m < optimistic_height_m


def test_stall_torque_conversion_from_datasheet_kgf_cm():
    """STALL_TORQUE_N_M should match the datasheet's 4.5 kg-cm@6V figure
    converted via 1 kgf-cm = 0.0980665 N-m -- catches a unit-conversion
    slip independent of estimate_jump_height() itself."""
    assert STALL_TORQUE_N_M == pytest.approx(4.5 * 0.0980665, rel=1e-9)


def test_threshold_is_documented_20mm():
    """The proposed Phase 0 pass bar is 20mm (roughly half the chassis
    height) -- pin it so a silent edit to the constant doesn't quietly
    change the gate without review."""
    assert JUMP_HEIGHT_THRESHOLD_M == pytest.approx(0.020)
