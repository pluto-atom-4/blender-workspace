# Armed Inverted Pendulum Robot (issue #21)

A compact two-wheel-leg self-balancing robot, built and rigged live in
Blender via the `blender-local-agent` MCP server. Reference image:
`blender-project/assets/hq720.jpg`. Issue: #21.

## Component specs

| Component | Part | Dimensions |
|---|---|---|
| Hip actuator | Feetech STS3032 bus servo | 32 x 12 x 27.5 mm (L x W x H) |
| Leg link | Custom bracket, hip pivot to wheel actuator | 50 mm long, 12 mm wide |
| Wheel actuator | Robotis Dynamixel XL330 | 20 x 34 x 26 mm (W x H x D) |
| Wheel | Slim large-diameter cylinder | 65 mm diameter, 8 mm width |
| Chassis base plate | Mounting platform | 60 x 45 x 5 mm (W x D x H) |
| Battery | 2S LiPo, slim block | 46 x 30 x 7 mm |
| PCBs | ESP32 controller + servo driver | ~40 x 30 mm, stacked on 8 mm standoffs |
| IMU | Top sensor cube | 8 mm cube, white |

All dimensions are authored in millimeters (`scale_length = 0.001`, 1
Blender unit = 1 mm) across every script in this build.

## Object hierarchy

```
Armed_Inverted_Pendulum (root empty, static)
├─ Chassis_Base_Plate (ACTIVE rigid body: box)
│  ├─ Battery_2S_LiPo, PCB_ESP32_Controller, PCB_Servo_Driver, IMU_Sensor
│  ├─ Standoff_Battery_PCB1_0..3, Standoff_PCB1_PCB2_0..3
│  └─ STS3032_Hip_Left/Right (fixed; origin = output-shaft axis)
│     └─ STS3032_Hip_*_Horn
├─ Leg_Link_Left/Right (ACTIVE rigid body: box; flat-parented to root)
│  └─ XL330_Wheel_Left/Right (fixed, rides on the leg)
│     └─ XL330_Wheel_*_Horn
├─ Wheel_Left/Right (ACTIVE rigid body: convex hull; flat-parented to root)
├─ Hinge_Hip_Left/Right (constraint empty: Chassis <-> Leg_Link, +/-45 deg)
├─ Hinge_Wheel_Left/Right (constraint empty: Leg_Link <-> Wheel, motorized)
└─ Ground_Plane (PASSIVE rigid body: mesh)
```

`Leg_Link_*` and `Wheel_*` are parented flat to the root rather than nested
under the parts they visually hang from -- Blender rigid-body objects must
not sit under another *dynamic* parent, so the physical joints are wired
with `HINGE` rigid_body_constraint empties instead of the object hierarchy.
Purely cosmetic parts (battery, PCBs, IMU, servo horns, the XL330 bodies)
stay ordinary parented children and just ride along.

Hinge axis is world **X** everywhere (wheel axle direction), since nothing
upstream in the build is rotated. `STS3032_Hip_*` and `Wheel_*` have their
object origin shifted onto that axis (`set_origin_to_point`), and
`Leg_Link_*` / `Wheel_*` are left fully unlocked so they can also be
hand-posed directly in the viewport outside of simulation.

This is the hierarchy as built by `model_pendulum.py`. Running
`control_pendulum_balance.py` afterward mutates it further: the `Hinge_*`
constraint empties are deleted, rigid-body data is stripped from
`Chassis_Base_Plate`/`Leg_Link_*`/`Wheel_*`, and a new `Balance_Pivot` empty
is inserted between the root and `Chassis_Base_Plate`/`Leg_Link_*` -- see
Stabilization controller below.

## Physics

- Rigid body world auto-created if missing (`ensure_rigid_body_world`).
- `Ground_Plane`: PASSIVE, mesh shape, friction 0.9.
- `Chassis_Base_Plate`: ACTIVE, box shape, mass 0.15 kg, friction 0.5.
- `Leg_Link_Left/Right`: ACTIVE, box shape, mass 0.02 kg, friction 0.5.
- `Wheel_Left/Right`: ACTIVE, convex hull shape (mesh is a cylinder rotated
  onto X, so the axis-aligned `CYLINDER` shape would be mis-sized), mass
  0.03 kg, friction 1.2.
- `Hinge_Hip_*`: angular limit +/-45 deg, unmotorized (passive hip swing).
- `Hinge_Wheel_*`: no angle limit, angular motor enabled
  (`use_motor_ang`), target 9.4 rad/s (XL330 rated no-load speed),
  `motor_ang_max_impulse = 0.05` as a placeholder torque cap -- raise it if
  the wheels stall/slip in sim, lower it to soften acceleration.
- The whole assembly is lifted so the wheel bottoms sit exactly on the
  `Z = 0` ground plane (`CHASSIS_Z_BOTTOM` is solved algebraically from leg
  length + actuator height + wheel radius, not hand-tuned).

Mass and impulse values are placeholders sized for a small robot, not
pulled from a real BOM -- tune them against actual part weights before
trusting the sim's dynamics quantitatively.

**The `Hinge_Wheel_*` angular motor does not work.** Verified via isolated
minimal repros in this Blender 4.3.2 environment (anchor + single wheel +
motor, both box and convex-hull collision shapes, both `HINGE`'s own motor
and a dedicated `MOTOR` constraint, `motor_ang_max_impulse` swept from 0.05
to 1000) -- all produced exactly zero rotation across 30+ simulated frames,
while plain gravity-driven translation on the same rig worked correctly. So
this rigid-body/hinge/motor setup is left in place as a structurally correct
rig (correct joint pivots, masses, hinge limits) that can still be
hand-posed or used for a passive drop/settle test, but it is **not** what
drives the balance demo -- see below.

## Stabilization controller

`control_pendulum_balance.py` does not use the rigid-body motor above (it
can't drive anything). Instead it:

1. Strips the `rigid_body` / `rigid_body_constraint` data `model_pendulum.py`
   added and deletes the now-inert `Hinge_*` constraint-empty objects.
2. Adds a `Balance_Pivot` empty at wheel-axle height (`Z = WHEEL_RADIUS`) and
   reparents `Chassis_Base_Plate` + both `Leg_Link_*` under it, so rotating
   the pivot tips the whole upper body around the wheel axle like a real
   two-wheel balancing robot, instead of spinning the chassis in place.
3. Runs the PID balance law as a plain Python simulation loop (not a live
   frame handler):

   ```
   u = Kp*theta + Ki*integral(theta) + Kd*d(theta)/dt
   ```

   Gains: `Kp=14.5 Ki=0.3 Kd=4.2`, integral clamped to +/-2.0, output
   clamped to +/-18. Starts from an 8 deg initial lean.
4. Bakes the result to keyframes (`LINEAR` interpolation): `Armed_Inverted_Pendulum`
   Y-location (rolling), `Balance_Pivot` X-rotation (tip), `Wheel_Left`/`Wheel_Right`
   X-rotation (spin) -- 150 frames at 24fps.

Re-running the script re-strips/re-builds `Balance_Pivot` and re-bakes from
scratch each time, so it's safe to run repeatedly (e.g. after changing gains).

This trades away real physical wheel-ground force interaction for a working,
visually-correct animation of the same control law -- there is no Bullet
simulation involved once this script runs.

`CONTROL_SIGN` (top of the script) flips the sign of the control law.
Verified against the baked sim: default value converges the initial 8 deg
lean to -0.35 deg by frame 150 (`RESULT: BALANCED`, printed by the script).

## Running the scripts

All scripts live in `blender-project/scripts/`.

| Script | Tool | Purpose |
|---|---|---|
| `model_pendulum.py` | `run_blender_python_live` | Build/rebuild the full rig in the open Blender GUI. Clears prior mesh/empty objects, keeps camera/lights. |
| `control_pendulum_balance.py` | `run_blender_python_live` | Strip the rig's (non-functional) physics, add `Balance_Pivot`, run the PID sim, bake keyframes 1-150. Press Play in the viewport afterward. |
| `render_pendulum.py` | `run_blender_python` (headless) | Rebuild the rig in a disposable process, save `renders/pendulum.blend`, render the default 3/4 view. Run this first. |
| `render_pendulum_front.py` / `_side.py` / `_top.py` | `run_blender_python` (headless) | Load `renders/pendulum.blend` and render that angle. Run after `render_pendulum.py`. |

`model_pendulum.py` only calls `save_as_mainfile` when `bpy.app.background`
is true (i.e. running headless) -- live GUI runs never overwrite or retarget
whatever `.blend` you currently have open.

Typical live-editing session:
1. `check_blender_live_status` to confirm the MCP Live Bridge addon is
   reachable.
2. `run_blender_python_live` with `model_pendulum.py` to (re)build the rig.
3. `run_blender_python_live` with `control_pendulum_balance.py` to attach
   the balance controller.
4. Press Play in the Blender viewport to watch it stabilize.

Typical render/deliverable pass (headless, doesn't touch the live session):
1. `render_pendulum.py`
2. `render_pendulum_front.py`, `render_pendulum_side.py`, `render_pendulum_top.py`

## Outputs

`blender-project/renders/`:
- `pendulum.blend` — rebuildable source, produced by `render_pendulum.py`.
- `pendulum_preview.png` — default 3/4 view.
- `pendulum_preview_front.png`, `pendulum_preview_side.png`,
  `pendulum_preview_top.png` — orthographic angle previews.

## Known limitations / next steps

- The balance demo is keyframed, not physically simulated -- no real
  wheel-ground force interaction, no reaction to external pushes/collisions,
  because `use_motor_ang` (Blender's rigid-body angular motor) does not
  produce rotation in this Blender 4.3.2 environment. See Physics above for
  the repro that confirmed this; revisit if a Blender/engine update fixes it.
- Hip joints have no control loop -- only the wheel-balance/tip loop is
  modeled (as `Balance_Pivot` rotation); leg swing is not separately driven.
- No differential (per-wheel) drive for turning -- both wheels always get
  the same keyframed spin.
- Rigid body masses/friction and the PID gains are placeholders/tuned by eye,
  not sourced from real part weights or a torque datasheet.
