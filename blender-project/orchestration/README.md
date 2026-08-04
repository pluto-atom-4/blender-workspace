# orchestration

Isolated `uv` subproject: LQR gain solver + Webots headless-run/tuning loop
for the armed inverted pendulum (issue #28, Phase 1). Mirrors the sibling
`blender-mcp/` subproject's pattern (own `pyproject.toml`, own `uv.lock`)
rather than a monolithic root `pyproject.toml`, so this PR's dependency
footprint stays isolated from `blender-mcp/`'s FastMCP server deps.

Scope is deliberately trimmed to gain-solving and a headless Webots
subprocess runner. LangGraph orchestration, the `langchain-openai`
"designer agent" node, PlatformIO/ESP32 firmware, the hardware-in-the-loop
bridge, CLI entry points, and the Dash dashboard are all deferred to later
PRs — none of that is installed or wired up here. See [WEBOTS.md](../../WEBOTS.md)
at the repo root for the full pipeline writeup (Blender export, the Webots
world file, and — importantly — the "What isn't validated end-to-end"
section, which this README does not repeat).

## Install

```bash
cd blender-project/orchestration
uv sync --extra test
```

`requires-python = ">=3.12"`. Core deps: `numpy`, `scipy`, `control`,
`pandas`. The `test` extra adds `pytest`.

## Tests

```bash
uv run --extra test pytest
```

`tests/test_lqr_tuner.py` covers `solve_lqr_gain()` / `is_stable()` only —
pure numeric Riccati-solve, no Webots dependency (CI may not have Webots or
a display). It checks a scalar system against a closed-form solution, cross-checks
against the `control` package's own `control.lqr()`, verifies a double
integrator gets stabilized, and confirms `pendulum_state_space()`'s
linearized model is controllable and yields a stabilizing gain under a
default Q/R.

## Usage

`lqr_tuner.py` exposes:

- `solve_lqr_gain(A, B, Q, R)` — solves the continuous-time algebraic
  Riccati equation (`scipy.linalg.solve_continuous_are`) and returns
  `(K, S, closed_loop_eigenvalues)` for `u = -Kx`.
- `pendulum_state_space(params: Optional[PendulumParams] = None)` — a
  linearized cart-pole approximation of the armed inverted pendulum
  (state `[cart_pos, cart_vel, tilt_angle, tilt_rate]`), returning `(A, B)`.
- `run_webots_headless(world_path, duration_s, telemetry_path, webots_binary, extra_args)`
  — runs `webots --batch --mode=fast --minimize --no-rendering <world>` as a
  subprocess, enforcing `duration_s` externally, and parses telemetry if a
  path is given. Returns a `WebotsRunResult`.
- `parse_telemetry(telemetry_path)` — reads a CSV or `.json` telemetry file
  into a pandas `DataFrame`; returns `None` if the file doesn't exist (the
  expected case today — no Webots controller in this repo writes one yet).
- `tune_lqr(A, B, Q0, R0, max_iterations=15, stability_margin=0.05, q_growth=1.5, tilt_state_index=2, run_webots=False, ...)`
  — plain iteration loop (not a state machine): solves the LQR gain, checks
  the closed-loop stability margin, and scales up the tilt-angle cost term
  in `Q` until the margin clears or `max_iterations` is hit. Convergence is
  gated on the analytic closed-loop eigenvalues, not on Webots telemetry —
  `run_webots=True` attempts a headless run per iteration best-effort only.

Demo run (solves the pendulum model and iterates `Q` until stable):

```bash
uv run python lqr_tuner.py
```

## Limitations

No Webots controller exists yet to produce telemetry, so `run_webots=True`
and `run_webots_headless()` exercise the real `webots` binary and world file
but `parse_telemetry()` will always return `None` in this repo today. See
[WEBOTS.md](../../WEBOTS.md)'s "What isn't validated end-to-end" and "Known
limitations / next steps" sections for the full picture (placeholder
mass/length parameters, no `HingeJoint`s in the exported mesh, coarse
bounding box, etc.).
