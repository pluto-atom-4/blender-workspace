# blender-project/

The operational workspace: automation scripts in, `.blend`/render outputs
out (see [`AGENTS.md`](../AGENTS.md#project-layout) and
[`DESIGN.md`](../DESIGN.md#overview) at the repo root for the high-level
split between this directory and the `blender-mcp/` server). This README is
the detailed companion for what's actually inside `blender-project/` —
including a few directories the root docs don't mention.

## Directory rundown

| Directory | Tracked in git? | What it is |
|---|---|---|
| `scripts/` | Yes | Generative Python automations (models, renders, exports). Run via the `blender-local-agent` MCP tools. See [Naming convention](#naming-convention) below and [`SKILLS.md`](../SKILLS.md) for the full inventory. |
| `renders/` | `.blend` files only (`*.png`, `*.mp4`, `*.blend1` are gitignored) | Build artifacts — `.blend` source files, preview PNGs, and the occasional simulation MP4. Regenerate via `scripts/`, don't hand-edit. |
| `orchestration/` | Yes | Standalone `uv` subproject (own `pyproject.toml`/`uv.lock`, mirroring `blender-mcp/`'s pattern) for the Webots/LQR pipeline: `lqr_tuner.py` plus `tests/`. See [`WEBOTS.md`](../WEBOTS.md) and `orchestration/README.md`. |
| `physics/` | Yes | `worlds/` holds the Webots world (`pendulum_world.wbt`) and exported mesh assets (`meshes/pendulum.obj`, `.mtl`) consumed by that world. Produced by `scripts/export_pendulum_to_webots.py`. |
| `assets/` | Yes (path is gitignored, but `hq720.jpg` and `inverted_pendulum_simulation.py` are explicitly excepted with `!` rules in `.gitignore`) | Reference material actually used by the build scripts: `hq720.jpg` (photo reference for the Tamiya and armed-inverted-pendulum builds, see [`PENDULUM.md`](../PENDULUM.md)) and `inverted_pendulum_simulation.py`, a standalone matplotlib GIF storyboard generator — not a `bpy`/Blender script, not part of the `scripts/` inventory in `SKILLS.md`, but the documented source `model_inverted_pendulum_simulation.py` was ported from. |
| `images/` | No (untracked, gitignored) | Stale. Contains 8 PNGs, all 8 byte-identical duplicates of files already in `renders/`. No script writes here — `render_*` scripts all target `renders/`. Leftover output location from before `renders/` became the single PNG destination. Cleanup (delete the directory) tracked in [issue #31](https://github.com/pluto-atom-4/blender-workspace/issues/31). |
| `anime/` | No (untracked) | One file, `anime.gif`. No script in `scripts/` or `assets/` writes to this path or filename — `assets/inverted_pendulum_simulation.py` saves its output as `inverted_pendulum.gif` in whatever directory it's run from, not `anime/anime.gif`. Provenance looks manual/external (the generator script's docstring links to a note.com article and an `InvertedPendulumSim.tsx` component outside this repo). Not reproducible from anything currently in this repo — untracked via `git rm --cached` so the existing `.gitignore` rule now actually applies. |
| `work/` | No (untracked) | One file, `pendulum-spinning.blend` (plus its gitignored `.blend1` backup). Hand-edited in the Blender GUI directly (see its commit history — "Add centered camera, light, and exponential spin animation") rather than produced by a script. Scratch/manual-session space, distinct from `renders/`'s "regenerate via scripts" contract — untracked via `git rm --cached` so the existing `.gitignore` rule now actually applies. |
| `issue-content.json` (file, not a dir) | Yes | Raw GitHub issue #1 body, imported verbatim. Not consumed by any script. |

## Naming convention

Scripts in `scripts/` follow the pattern documented in
[`DESIGN.md`](../DESIGN.md#script-conventions):

- `model_<subject>.py` — builds the scene/mesh and saves a `.blend`.
- `render_<subject>.py` / `render_<subject>_<angle>.py` — loads or rebuilds
  the scene and renders a preview PNG from a specific viewpoint (`front`,
  `side`, `top`).
- A `_precise` suffix marks a higher-fidelity variant built from more exact
  reference measurements, kept alongside the original rather than replacing
  it.

## Per-feature writeups

| Doc | Covers |
|---|---|
| [`PENDULUM.md`](../PENDULUM.md) | Armed inverted pendulum robot (issue #21): two-wheel-leg self-balancing build, rigid-body physics, PID balance controller. |
| [`LEGGED_ROBOT.md`](../LEGGED_ROBOT.md) | Dual-wheel legged balancing robot (issue #23): CNC-accurate chassis, 4-bar leg linkage, FK-keyframed rig. |
| [`WEBOTS.md`](../WEBOTS.md) | Webots physics export & LQR tuning (issue #28, Phase 1): Blender-to-Webots geometry export plus a standalone LQR gain solver — what's built and what's explicitly deferred. |

For the full script-by-script inventory (including the base/precise Tamiya
pendulum scripts not tied to a specific issue), see
[`SKILLS.md`](../SKILLS.md).
