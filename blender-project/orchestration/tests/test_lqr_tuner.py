"""Unit tests for the LQR gain solver in lqr_tuner.py (issue #28, Phase 1).

Deliberately scoped to solve_lqr_gain() / is_stable() only -- pure numeric
Riccati-solve, no Webots dependency. Anything that shells out to the real
`webots` binary belongs in a separate, explicitly-skippable integration
test (not written here; CI may not have Webots or a display -- see
run_webots_headless()'s docstring in lqr_tuner.py).
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lqr_tuner import is_stable, pendulum_state_space, solve_lqr_gain  # noqa: E402


def test_scalar_system_matches_closed_form():
    """Scalar system x' = a x + b u, cost x'Qx + u'Ru. The Riccati equation
    reduces to a quadratic in the scalar s: 2 a s - (b^2/r) s^2 + q = 0,
    which has a closed-form root -- cross-check scipy's solve against it by
    hand rather than against another library call.

    a=1, b=1, q=1, r=1 -> (1/r) b^2 s^2 - 2 a s - q = 0 -> s^2 - 2s - 1 = 0
    -> s = 1 + sqrt(2) (positive root, since S must be positive definite).
    k = (1/r) b s = 1 + sqrt(2).
    """
    A = [[1.0]]
    B = [[1.0]]
    Q = [[1.0]]
    R = [[1.0]]

    K, S, eigs = solve_lqr_gain(A, B, Q, R)

    expected_s = 1.0 + np.sqrt(2.0)
    expected_k = expected_s  # b=r=1, so k = s

    assert S[0, 0] == pytest.approx(expected_s, rel=1e-8)
    assert K[0, 0] == pytest.approx(expected_k, rel=1e-8)

    # Closed-loop pole: a - b*k = 1 - (1 + sqrt(2)) = -sqrt(2).
    assert eigs[0].real == pytest.approx(-np.sqrt(2.0), rel=1e-8)
    assert is_stable(eigs)


def test_scalar_system_matches_control_library():
    """Cross-check the same scalar system against the `control` package's
    own control.lqr(), which independently wraps the Riccati solve."""
    control = pytest.importorskip("control")

    A, B, Q, R = [[1.0]], [[1.0]], [[1.0]], [[1.0]]
    K, _S, _eigs = solve_lqr_gain(A, B, Q, R)

    K_ref, _S_ref, _E_ref = control.lqr(np.array(A), np.array(B), np.array(Q), np.array(R))

    assert K[0, 0] == pytest.approx(np.asarray(K_ref).item(), rel=1e-6)


def test_double_integrator_is_stabilized():
    """Double integrator (x'' = u): A = [[0,1],[0,0]], B = [[0],[1]] is a
    textbook LQR example -- unstable in open loop (a repeated eigenvalue at
    0), and any positive-definite Q, R must yield a stabilizing gain since
    (A, B) is controllable. Cross-checked against control.lqr() where
    available, and always checked against the closed-form stability
    definition (all closed-loop eigenvalues have negative real part).
    """
    A = [[0.0, 1.0], [0.0, 0.0]]
    B = [[0.0], [1.0]]
    Q = np.eye(2)
    R = [[1.0]]

    K, S, eigs = solve_lqr_gain(A, B, Q, R)

    # S must be symmetric positive definite for a valid Riccati solution.
    assert S == pytest.approx(S.T, abs=1e-8)
    assert np.all(np.linalg.eigvalsh(S) > 0)

    assert is_stable(eigs)
    assert is_stable(eigs, margin=0.1)

    control = pytest.importorskip("control")
    K_ref, _S_ref, _E_ref = control.lqr(np.array(A), np.array(B), Q, np.array(R))
    assert np.allclose(K, np.asarray(K_ref), rtol=1e-6)


def test_pendulum_state_space_is_controllable_and_stabilizable():
    """The linearized pendulum-on-cart model used by tune_lqr() (see
    pendulum_state_space()) should be controllable (classic cart-pole
    result), and a modest default Q/R should produce a stabilizing gain --
    this is the same model tune_lqr()'s __main__ demo solves."""
    A, B = pendulum_state_space()

    # Controllability matrix [B, AB, A^2 B, A^3 B] must be full rank (4)
    # for this 4-state system.
    n = A.shape[0]
    ctrb_blocks = [B]
    power = B
    for _ in range(1, n):
        power = A @ power
        ctrb_blocks.append(power)
    ctrb = np.hstack(ctrb_blocks)
    assert np.linalg.matrix_rank(ctrb) == n

    Q = np.diag([1.0, 1.0, 10.0, 1.0])
    R = np.array([[0.1]])
    _K, _S, eigs = solve_lqr_gain(A, B, Q, R)
    assert is_stable(eigs)


def test_is_stable_rejects_unstable_eigenvalues():
    assert not is_stable([1.0 + 0j, -1.0 + 0j])
    assert not is_stable([-0.001 + 0j], margin=0.01)
    assert is_stable([-5.0 + 0j, -0.2 + 1j, -0.2 - 1j])
