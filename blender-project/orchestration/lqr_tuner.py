"""LQR gain solver + Webots-driven tuning loop for the armed inverted
pendulum (issue #21 geometry, issue #28 Phase 1 -- trimmed scope).

Plain Python, no LangGraph/state-machine wrapper (deferred per the
architect-plan comment on issue #28). Three pieces:

  (a) solve_lqr_gain()        -- Riccati-equation LQR gain solve
                                  (scipy.linalg.solve_continuous_are).
  (b) run_webots_headless()   -- subprocess wrapper around the `webots`
                                  binary against pendulum_world.wbt, plus
                                  parse_telemetry() for its output.
  (c) tune_lqr()               -- a plain iteration loop that grows the
                                  tilt-angle cost term in Q until the
                                  closed-loop system clears a stability
                                  margin (or hits an iteration cap).

Telemetry status (read before relying on run_webots=True): pendulum_world.wbt
ships with `controller "<none>"` -- there is no Webots controller in this
repo yet that reads the Gyro/Accelerometer and writes a telemetry file.
Building that controller (and, more importantly, an articulated multi-body
Webots robot with real hinge joints matching model_pendulum.py's hip/wheel
rig, since the exported mesh today is a single static Shape) is follow-up
work, not part of this trimmed Phase 1 PR. run_webots_headless() and
parse_telemetry() are fully implemented and were exercised against the real
`webots` binary (R2025a, confirmed installed at /usr/local/bin/webots) in
this environment -- see the module's test/validation notes in WEBOTS.md --
but with no controller producing telemetry, parse_telemetry() will find no
file and return None. tune_lqr()'s convergence criterion is therefore based
on the analytic closed-loop eigenvalues of A - B@K (always available,
independent of Webots), not on parsed telemetry; the optional Webots run is
attempted per iteration for its own sake but does not gate convergence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from scipy.linalg import solve_continuous_are

# ---------------------------------------------------------------------------
# (a) LQR gain solver
# ---------------------------------------------------------------------------


def solve_lqr_gain(A, B, Q, R):
    """Solve the continuous-time algebraic Riccati equation and return the
    optimal state-feedback gain K for u = -Kx.

    Solves A^T S + S A - S B R^-1 B^T S + Q = 0 via
    scipy.linalg.solve_continuous_are, then K = R^-1 B^T S -- the standard
    closed-form LQR gain from S. Cross-checked in
    tests/test_lqr_tuner.py against the `control` library's own
    control.lqr(), which wraps the same Riccati solve.

    Returns (K, S, closed_loop_eigenvalues) where closed_loop_eigenvalues
    are the eigenvalues of (A - B @ K) -- all should have negative real
    parts for a stabilizing gain.
    """
    A = np.atleast_2d(np.asarray(A, dtype=float))
    B = np.atleast_2d(np.asarray(B, dtype=float))
    Q = np.atleast_2d(np.asarray(Q, dtype=float))
    R = np.atleast_2d(np.asarray(R, dtype=float))

    S = solve_continuous_are(A, B, Q, R)
    K = np.linalg.solve(R, B.T @ S)
    closed_loop_eigs = np.linalg.eigvals(A - B @ K)
    return K, S, closed_loop_eigs


def is_stable(eigenvalues: Sequence[complex], margin: float = 0.0) -> bool:
    """True if every closed-loop eigenvalue's real part is < -margin."""
    return bool(np.all(np.real(eigenvalues) < -margin))


# ---------------------------------------------------------------------------
# Linearized pendulum-on-cart model, approximating the armed inverted
# pendulum (model_pendulum.py / PENDULUM.md) for a first LQR pass.
# ---------------------------------------------------------------------------


@dataclass
class PendulumParams:
    """Approximate linearized cart-pole parameters for the armed inverted
    pendulum. This collapses the real two-leg, hinge-jointed rig (see
    PENDULUM.md) into the textbook single inverted-pendulum-on-a-cart used
    for a first LQR pass -- not a literal multi-body match. Mass figures
    mirror the placeholder rigid-body masses in model_pendulum.py (which
    PENDULUM.md itself calls out as "not pulled from a real BOM"); the
    pendulum length mirrors the model's own chassis-center height
    (CHASSIS_Z_CENTER = 99.5 mm, converted to meters).
    """

    cart_mass_kg: float = 0.15 + 2 * 0.03       # Chassis_Base_Plate + 2x Wheel_*
    pendulum_mass_kg: float = 2 * 0.02          # 2x Leg_Link_*
    pendulum_length_m: float = 0.0995           # CHASSIS_Z_CENTER (mm -> m)
    gravity_m_s2: float = 9.81


def pendulum_state_space(params: Optional[PendulumParams] = None):
    """Linearized state-space (A, B) for a cart-pole approximation of the
    armed inverted pendulum around the upright equilibrium (theta = 0).

    State x = [cart_pos, cart_vel, tilt_angle, tilt_rate] (tilt from
    vertical, small-angle linearization). Input u = force on the cart
    (stand-in for net wheel-drive force in the real rig).

    Standard cart-pole linearization (e.g. the classic single
    inverted-pendulum-on-cart derivation; M = cart mass, m = pendulum
    point mass, l = pendulum length, g = gravity):

        x'  = v
        v'  = -(m g / M) theta + u / M
        theta'  = omega
        omega'  = ((M + m) g / (M l)) theta - u / (M l)
    """
    p = params or PendulumParams()
    M, m, l, g = (
        p.cart_mass_kg,
        p.pendulum_mass_kg,
        p.pendulum_length_m,
        p.gravity_m_s2,
    )

    A = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, -(m * g) / M, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, ((M + m) * g) / (M * l), 0.0],
        ]
    )
    B = np.array([[0.0], [1.0 / M], [0.0], [-1.0 / (M * l)]])
    return A, B


# ---------------------------------------------------------------------------
# (b) Webots headless runner + telemetry parser
# ---------------------------------------------------------------------------

DEFAULT_WEBOTS_BINARY = "webots"
DEFAULT_WORLD_PATH = (
    Path(__file__).resolve().parents[1] / "physics" / "worlds" / "pendulum_world.wbt"
)

# Telemetry format: CSV (chosen over JSON for easy pandas/Excel inspection
# and append-per-timestep writing from a future Webots controller without
# holding the whole run in memory). Expected header:
#   time,gyro_x,gyro_y,gyro_z,accel_x,accel_y,accel_z,tilt_rad
# One row per controller timestep. A .json path (a list of such records) is
# also accepted -- see parse_telemetry().


def webots_available(webots_binary: str = DEFAULT_WEBOTS_BINARY) -> bool:
    """Cheap check for whether the `webots` binary is on PATH, so callers
    can skip run_webots_headless() gracefully in a headless/CI environment
    without it installed."""
    return shutil.which(webots_binary) is not None


@dataclass
class WebotsRunResult:
    returncode: Optional[int]
    timed_out: bool
    telemetry: Optional[pd.DataFrame]
    stdout: str
    stderr: str


def parse_telemetry(telemetry_path) -> Optional[pd.DataFrame]:
    """Load a telemetry file (CSV, or JSON list-of-records if the suffix is
    .json) into a DataFrame. Returns None (with a printed note, not an
    exception) if the file doesn't exist -- the expected case in this repo
    today, since no Webots controller yet writes one (see module docstring).
    """
    path = Path(telemetry_path)
    if not path.exists():
        print(
            f"[lqr_tuner] No telemetry file at {path} -- no Webots controller is "
            f"wired up yet to produce one (pendulum_world.wbt's Robot controller "
            f"is \"<none>\"); see WEBOTS.md."
        )
        return None
    if path.suffix.lower() == ".json":
        with open(path) as f:
            records = json.load(f)
        return pd.DataFrame(records)
    return pd.read_csv(path)


def run_webots_headless(
    world_path=DEFAULT_WORLD_PATH,
    duration_s: float = 10.0,
    telemetry_path=None,
    webots_binary: str = DEFAULT_WEBOTS_BINARY,
    extra_args: Optional[Sequence[str]] = None,
) -> WebotsRunResult:
    """Run Webots headlessly against world_path for up to duration_s
    seconds, then parse telemetry_path (see parse_telemetry) if given.

    Launches `webots --batch --mode=fast --minimize --stdout --stderr
    --no-rendering <world_path>` (no on-screen window; `--mode=fast`
    disables real-time throttling). Webots' own world/robot definition has
    no built-in "run for N seconds and exit" flag, so duration is enforced
    externally: the subprocess is given `duration_s` seconds via
    Popen.communicate(timeout=...), then terminated (SIGTERM, escalating to
    SIGKILL after a 5s grace period) if it's still running.

    Verified in this environment against the real webots R2025a binary and
    the actual pendulum_world.wbt (see WEBOTS.md) -- the world loads cleanly
    with `webots --batch --mode=fast --minimize --no-rendering
    pendulum_world.wbt` (exit 0, no errors/warnings once meshes/pendulum.obj
    exists). This function was exercised the same way as part of building
    this module; whether it was actually re-run end-to-end from this exact
    function (vs. the equivalent raw command) is noted in the PR report.
    """
    world_path = Path(world_path)
    if not world_path.exists():
        raise FileNotFoundError(f"Webots world not found: {world_path}")
    if not webots_available(webots_binary):
        raise FileNotFoundError(
            f"'{webots_binary}' not found on PATH -- install Webots or pass "
            f"webots_binary= explicitly."
        )

    args = [
        webots_binary,
        "--batch",
        "--mode=fast",
        "--minimize",
        "--stdout",
        "--stderr",
        "--no-rendering",
    ]
    if extra_args:
        args.extend(extra_args)
    args.append(str(world_path))

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=duration_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

    telemetry = parse_telemetry(telemetry_path) if telemetry_path is not None else None
    return WebotsRunResult(
        returncode=proc.returncode,
        timed_out=timed_out,
        telemetry=telemetry,
        stdout=stdout or "",
        stderr=stderr or "",
    )


# ---------------------------------------------------------------------------
# (c) Iteration loop -- adjust Q/R, re-evaluate, stop on stability or cap
# ---------------------------------------------------------------------------


@dataclass
class TuningResult:
    iterations: int
    gains: np.ndarray
    Q: np.ndarray
    R: np.ndarray
    closed_loop_eigs: np.ndarray
    stable: bool
    telemetry: Optional[pd.DataFrame] = None


def tune_lqr(
    A,
    B,
    Q0,
    R0,
    max_iterations: int = 15,
    stability_margin: float = 0.05,
    q_growth: float = 1.5,
    tilt_state_index: int = 2,
    run_webots: bool = False,
    world_path=DEFAULT_WORLD_PATH,
    duration_s: float = 5.0,
    telemetry_path=None,
    webots_binary: str = DEFAULT_WEBOTS_BINARY,
) -> TuningResult:
    """Plain iteration loop (not a state machine/LangGraph graph): solve the
    LQR gain for the current Q/R, check the closed-loop system's stability
    margin, and if it's not past `stability_margin` yet, scale up the
    tilt-angle cost term (Q[tilt_state_index, tilt_state_index]) by
    q_growth and try again, up to max_iterations.

    Stability margin is `-max(real(eigenvalues))` of the closed-loop system
    A - B@K -- how far the slowest-decaying mode sits into the stable
    (negative real part) half-plane. This is always computable analytically,
    so tuning converges even without a Webots controller producing
    telemetry yet (see module docstring). Pass run_webots=True to also
    attempt a headless Webots run + telemetry parse each iteration
    (best-effort, does not gate convergence, skipped automatically if the
    `webots` binary isn't on PATH).
    """
    Q = np.array(Q0, dtype=float)
    R = np.array(R0, dtype=float)
    result: Optional[TuningResult] = None

    for iteration in range(1, max_iterations + 1):
        K, _S, eigs = solve_lqr_gain(A, B, Q, R)
        worst_margin = -np.max(np.real(eigs))
        stable = worst_margin > stability_margin

        telemetry = None
        if run_webots:
            if not webots_available(webots_binary):
                print(
                    f"[lqr_tuner] iteration {iteration}: '{webots_binary}' not on "
                    f"PATH -- skipping Webots run, using analytic eigenvalues only."
                )
            else:
                run_result = run_webots_headless(
                    world_path=world_path,
                    duration_s=duration_s,
                    telemetry_path=telemetry_path,
                    webots_binary=webots_binary,
                )
                telemetry = run_result.telemetry

        result = TuningResult(
            iterations=iteration,
            gains=K,
            Q=Q.copy(),
            R=R.copy(),
            closed_loop_eigs=eigs,
            stable=stable,
            telemetry=telemetry,
        )
        print(
            f"[lqr_tuner] iteration {iteration}: worst_margin={worst_margin:.4f} "
            f"stable={stable} Q[{tilt_state_index},{tilt_state_index}]={Q[tilt_state_index, tilt_state_index]:.3f}"
        )
        if stable:
            break
        Q[tilt_state_index, tilt_state_index] *= q_growth

    assert result is not None
    return result


if __name__ == "__main__":
    # Plain demo run -- not a CLI (no argparse/entry point, per the
    # architect-plan's deferred-scope list). Solves the LQR gain for the
    # pendulum_state_space() model and iterates Q until stable, attempting a
    # real Webots run only if the binary is actually on PATH.
    A, B = pendulum_state_space()
    Q0 = np.diag([1.0, 1.0, 10.0, 1.0])
    R0 = np.array([[0.1]])

    tuning = tune_lqr(A, B, Q0, R0, run_webots=webots_available())

    print("=" * 70)
    print(f"Converged after {tuning.iterations} iteration(s), stable={tuning.stable}")
    print(f"Gain K = {tuning.gains}")
    print(f"Closed-loop eigenvalues = {tuning.closed_loop_eigs}")
