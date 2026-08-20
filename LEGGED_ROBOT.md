# Dual-Wheel Legged Balancing Robot (issue #23)

An XGO-style dual-wheel legged balancing robot — CNC-mm-accurate chassis,
STS3032 bus servos, a 4-bar leg linkage, and treaded/driven wheels —
procedurally generated and rigged in Blender. Built via PR #24 (commit
`4f7e8b2`), tracking issue #23. All dimensions are authored in millimeters
(1 Blender unit = 1 meter; scripts convert with `mm()`).

## FK instead of IK: why

Issue #23 asked for the robot to be built and rigged via the live/interactive
MCP bridge (`run_blender_python_live`), using bone IK constraints for the
hip/knee joints. In practice, live bone IK constraints didn't re-solve
correctly under this Blender build's live/headless evaluation. The leg
hinge is instead driven by **direct FK keyframes** on hip/knee joint
rotation — same strict parenting hierarchy, deterministic result, no
dependency on IK solver re-evaluation. As a consequence, the model was
ultimately built through the disposable headless `run_blender_python` path
rather than the live bridge the issue requested.

## Two script variants

| Script | Description |
|---|---|
| `model_dual_wheel_legged_robot.py` | Base model: chassis, STS3032 hip/knee servos, 4-bar leg linkage, wheel, electronics. Strict FK parenting hierarchy (Chassis → Hip Servo → Upper Leg → Knee Servo → Lower Leg → ...). |
| `model_dual_wheel_legged_robot_precise.py` | Higher-fidelity variant (per this repo's `_precise` naming convention — see `DESIGN.md`), refined against reference photos of the real hardware: sandwich CNC chassis stack and a true parallelogram 4-bar leg linkage. Kept as a separate script rather than overwriting the base model. |

Both scripts save their own `.blend` under `blender-project/renders/` when
run headless, guarded by `bpy.app.background` (so a live-GUI run never
overwrites or retargets whatever `.blend` the user has open, matching
`model_pendulum.py`'s existing convention). Neither has a separate
`render_<subject>*.py` script — unlike the Tamiya/armed-pendulum builds,
this feature's render preview (`model_dual_wheel_legged_robot_precise_preview.png`)
was produced without a dedicated tracked render script.

## Animation

- **Frames 1–120**: exploded-view assembly sequence.
- **Frames 121–250**: IMU-style balance micro-oscillation, crouch, jump,
  free-fall, and touchdown.

The balance/jump phase went through many iterative fixes across the PR
(see commit history in `git log 4f7e8b2` for the full sequence): easing
enums are ignored entirely by Blender under `BEZIER` interpolation
(discovered empirically), so explosive liftoff timing required passing
real interpolation modes (`QUAD`/`EXPO`) instead of relying on the
`easing=` argument; a `lock_wheels_to_floor()` helper re-derives the exact
chassis height every frame from the live FK pose (across the grounded
crouch/landing ranges) instead of hand-picked anchor keyframes, to keep
the wheels from sinking into or floating above the floor; and the jump
physics were reworked to derive apex height and ascent/descent timing from
the actual measured liftoff velocity of the crouch-to-push keyframes,
rather than an independently chosen apex height.

## Sandwich chassis / 4-bar parallelogram leg linkage (`_precise` variant)

`model_dual_wheel_legged_robot_precise.py` refines the base model against
reference photos of the real hardware:

- **Sandwich CNC chassis stack**: base plate, standoffs, PCB deck,
  sandwiched LiPo battery, and a white ATOM S3 controller housing with
  port cutouts.
- **4-bar leg linkage**: originally an independent parallelogram (two
  full-length links each separately spanning hip to a shared ankle block,
  with equal-length driven/follower plates keeping the ankle coupler level
  through the full range of motion, verified numerically). This was later
  restructured to match the reference hardware more closely: two thin
  plates sandwich the hip and knee pivots as a rigid doubled fork,
  converging at a single knee knuckle, then one sturdier plate continues
  from there down to the ankle/wheel. Kinematics are preserved with only
  the hip actuated — the knee knuckle is keyframed to the negative of the
  upper plates' angle so the lower plate/ankle/wheel subtree never
  accumulates net rotation, keeping the wheel level.
- **Inverted ankle-mounted wheel servo**, tilted inline with the linkage.

## Stance-overlap bug fix

The initial hip/rear-extension spacing let the wheels physically overlap:
wheel radius (`WHEEL_R` = 40mm) exceeded half the hip spacing, producing a
20mm overlap. Fixed by widening:

- `HIP_LATERAL`: 30mm → 50mm
- `REAR_EXT_W`: 36mm → 130mm

The legs were verified already-symmetric before this fix — the overlap was
a spacing bug, not an asymmetry bug.

## Horn-bracket and servo-body mirroring fixes

Two separate real mirroring bugs were found and fixed:

- `build_servo_horn_bracket`'s local +X offset wasn't sign-flipped between
  legs, so the bracket sat outward on the right leg but inward on the left
  (`hip_servo` itself is never rotated between sides, only translated).
- `build_servo`'s body pivot.x was fixed regardless of leg side, so the
  body mesh (offset from its own origin, not centered on it) always
  extended toward world -X — inward (correct, matching the reference
  hardware) for the right leg, but outward past its own pivot for the left
  leg, on both the hip servo and the ankle-mounted wheel servo. The
  spline nub's local offset had the same bug and was fixed the same way.

Both fixes were verified mirror-exact across explode, mid-animation, and
rest frames — the earlier symmetry checks in the branch had only compared
object origins (which stayed mirror-correct throughout), so the body-mesh
bug went undetected until actual mesh vertex extents in world space were
checked.

## Jump Behavior Simulation (issue #86)

The `legged_robot_jump` controller (issue #86) implements a coordinated
jump sequence via a state machine with position-controlled hip motors and
velocity-controlled wheel motors.

### Controller Timing

The jump cycle spans 2.0 seconds total:

| Phase | Time Window | Hip Angle Transition | Wheel Spin |
|---|---|---|---|
| **REST** | 0.0–0.2s | ~58° (1.012 rad, idle) | Off |
| **CROUCH** | 0.2–0.7s | 58° → 120° (1.012 → 2.094 rad) | Off |
| **PUSH** | 0.7–1.0s | 120° → 15° (2.094 → 0.262 rad) | Forward (2.0 rad/s) |
| **FLIGHT** | 1.0–1.2s | 15° (held), wheels inactive | Off |
| **LANDING** | 1.2–1.4s | 15° → 58° (0.262 → 1.012 rad) | Backward (−1.5 rad/s) |
| **SETTLE** | 1.4–2.0s | ~58° (idle, absorb impact) | Off |

**Easing profiles** (from Blender animation):
- CROUCH phase: exponential ease (smooth slow→fast→slow)
- PUSH phase: quadratic ease (sharp acceleration for explosive liftoff)

**Wheel motor control**:
- Forward spin (2.0 rad/s) during PUSH/LIFTOFF provides traction and assists
  upward momentum transfer (phase #41 future work: optimize grip strategy).
- Backward spin (−1.5 rad/s) during LANDING provides braking and impact
  absorption. Parameters are configurable, not hardcoded in the controller.

### Tuning Method

The jump controller profile was derived from Phase 1's Blender animation
keyframe timing and easing modes (see `model_dual_wheel_legged_robot_precise.py`
`build_balance_and_jump()`). Real tuning steps:

1. **Phase 0 feasibility gate** (`feasibility_phase0.py`):
   - Computed expected jump height (optimistic/pessimistic) from STS3032
     stall torque and stroke geometry: ~0.025–0.050 m range.
   - Provided upper and lower bounds for acceptance testing.

2. **Blender prototype animation**:
   - Keyframed hip angles and timing empirically against visual reference.
   - Derived liftoff velocity from measured Z-position derivative across
     the push phase.
   - Confirmed wheel contact and landing absorption feasibility.

3. **Webots sim validation** (issue #86):
   - Ran headless physics simulation with the jump controller and measured
     actual jump height/velocity/torque from telemetry.
   - Compared measured values against Phase 0 predictions to validate model
     fidelity and servo torque limits.
   - Acceptance gates: jump_height ≥ 5cm, takeoff_velocity ≥ 0.7 m/s,
     max_servo_torque ≤ 0.353 N·m (80% of 0.4413 stall).

**Servo torque margin**: The hip servo's stall torque is 0.4413 N·m; the
controller limits peak usage to 0.353 N·m (80% derate) for safety. If measured
torque approaches or exceeds this limit, reduce crouch/push duration or
increase LEVER_ARM (though real leverage is set by linkage geometry, not
configurable).

**Wheel spin tuning**: Forward/backward wheel speeds (2.0/−1.5 rad/s) are
placeholders tuned for visual plausibility during simulation. Real-world
validation will likely require adjustment based on actual tire friction and
impact response.

### Known Limitations

- **Mesh fidelity**: Collision bounding objects are coarse boxes/cylinders
  (see legged_robot_world.wbt comments). Real ankle-wheel contact is
  approximated; actual landing dynamics may differ.
- **Wheel contact model**: Webots default friction (coulombFriction 0.9)
  and no explicit slip model. Real treaded wheels have complex grip
  behavior not captured by this simple model.
- **Air resistance**: Zero drag; real jump arc is affected by air currents
  and pitch/roll instability.
- **Servo lag**: Hip motor response is instant (setPosition() applies
  immediately in Webots). Real STS3032 servo has ~100ms response time +
  load-dependent slew rate, not modeled.
- **Spring/damping**: Hip joint has a spring constant (0.1329 N·m/rad),
  but damping is zero. Real servo has internal friction and mechanical
  spring hysteresis not captured here.
- **Two-legged symmetry assumption**: Controller drives both hip motors
  in sync. Real impact can break symmetry; no active load-balancing is
  implemented.
- **Knee kinematic coupling**: Lower-leg angle is determined by hip angle
  (rigid 4-bar linkage, no active knee servo). If knee geometry ever
  becomes actuated (e.g., for improved stability), the controller will
  need update.

Related issues and cross-links:

- **Issue #25** (Phase 0/1/2): Original design and Phase 1 linkage geometry.
- **Issue #41** (Wheel traction strategy): Future work on grip optimization
  during launch/landing.
- **Issue #84** (Z-offset fix): Corrected ground-plane positioning before
  jump simulation; verified wheels land at floor level.
- **Issue #86** (Jump behavior): This controller and test harness.

## Known Limitations (general)

- Leg joints are FK, not IK — see "FK instead of IK: why" above.
- No dedicated `render_<subject>*.py` scripts exist for this feature; the
  model scripts persist their own `.blend` output directly.
