"""Standalone 3D visualization of the Linear Vector Rule leg-linkage
deviation finding (issue #42, supporting the #41 decision).

#41 found the dual-wheel legged robot's leg linkage FAILs the Linear
Vector Rule (15.648mm max deviation vs a proposed 8mm threshold), tracked
in orchestration/linkage_kinematics.py as a printed mm figure only. This
script makes that bulge, the reference chord, the 8mm tolerance band, and
the CoM horizontal-offset comparison actually visible -- alongside a
placeholder "candidate" geometry overlay -- so a human can make #41's
UPPER_LEN/HIP_Z call with a picture instead of only a number.

Per the export_pendulum_to_webots.py / WEBOTS.md exec() reuse pattern,
this drives the REAL build_leg()/kf_leg_angle() from
model_dual_wheel_legged_robot_precise.py rather than reimplementing the
FK trig a third time (linkage_kinematics.py already reimplemented it once,
purely for fast numeric iteration outside Blender -- this script's own
console cross-check confirms the two haven't drifted apart).

Two things exec()'ing the production script implies, both accepted as
harmless per existing precedent (export_pendulum_to_webots.py accepts the
same category of side effect against model_pendulum.py):

1. It reruns the ENTIRE production main() -- rebuilds both legs, the full
   chassis, the exploded-view assembly, and the crouch/jump animation
   (the dense per-frame lock_wheels_to_floor pass), and unconditionally
   re-saves renders/model_dual_wheel_legged_robot_precise.blend. Wasted
   but deterministic work.
2. `legs`/`base_plate` built by that main() do NOT leak into this script's
   namespace (they're local to main(), which returns before exec()
   finishes) -- only top-level defs/constants do (build_leg, kf_leg_angle,
   clear_previous, UPPER_LEN, HIP_Z, LAUNCH_ANGLE, CROUCH_ANGLE,
   DEFAULT_HIP_ANGLE, BASE_L, mm, MM, ...). This script therefore calls
   build_leg() itself for each pass rather than reading back the
   production build's own legs.

UPPER_LEN/HIP_Z override mechanism: build_leg()'s body references those
names as free variables, resolved via build_leg.__globals__ at CALL time.
Because exec(open(...).read()) (no explicit globals dict) runs using this
script's own globals(), build_leg.__globals__ IS this module's namespace
-- reassigning UPPER_LEN/HIP_Z here before calling build_leg() again
genuinely changes what it builds. No changes to
model_dual_wheel_legged_robot_precise.py itself.

Run via the run_blender_python MCP tool (disposable headless) -- no live
GUI interaction required for building/saving this diagnostic scene.

Cross-check finding (see main()'s console report for the live numbers):
sampling ankle_block (as specified) reproduces linkage_kinematics.py's
max_chord_deviation_mm() EXACTLY (both report 15.648mm for the current
geometry) -- but the raw per-sample (x_mm, z_mm) points differ from
ankle_position()'s closed-form output by a CONSTANT offset at every single
angle: +PLATE_GAP/2 in the Y-equivalent axis (ankle_block descends through
upper_plate_front specifically, which sits PLATE_GAP/2 off
linkage_kinematics.py's single-centerline 2D model) and +ANKLE_DROP in Z
(ankle_position()'s own formula already subtracts ANKLE_DROP, i.e. it
actually models the wheel-axle point, not ankle_block). Both are exact,
angle-independent constants -- confirmed by direct inspection, not
approximated -- so the two sampled curves have IDENTICAL SHAPE, just
different origins; max_chord_deviation_mm() is invariant under a rigid
translation of the whole curve, which is exactly why the number that
actually gates PASS/FAIL agrees exactly despite this. Documented here
per the issue's own instruction not to silently absorb a cross-check
discrepancy -- this one is real, fully explained, and does not affect
the PASS/FAIL verdict.
"""

import sys
import bpy
import math
from mathutils import Vector

SCRIPTS_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/scripts"
ORCHESTRATION_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/orchestration"
OUTPUT_BLEND = "/home/pluto-atom-4/blender-workspace/blender-project/renders/leg_linkage_deviation.blend"

# ---------------------------------------------------------------------------
# 1. Pull in the real build_leg()/kf_leg_angle()/clear_previous() and the
#    UPPER_LEN/HIP_Z/LAUNCH_ANGLE/CROUCH_ANGLE/DEFAULT_HIP_ANGLE/BASE_L/mm/MM
#    module-level names via exec() -- reruns main() as a side effect (see
#    module docstring), legs/base_plate do not leak out, only top-level
#    defs/constants do.
# ---------------------------------------------------------------------------
exec(open(f"{SCRIPTS_DIR}/model_dual_wheel_legged_robot_precise.py").read())

# ---------------------------------------------------------------------------
# 2. linkage_kinematics.py -- source of truth for the thresholds/constants
#    this visualization must stay consistent with, and for the cross-check.
# ---------------------------------------------------------------------------
if ORCHESTRATION_DIR not in sys.path:
    sys.path.insert(0, ORCHESTRATION_DIR)
import linkage_kinematics as lk  # noqa: E402

# NOTE on naming: this script shares ONE global namespace with the exec()'d
# model_dual_wheel_legged_robot_precise.py (exec() with no explicit globals
# dict runs using this module's own globals()). That module defines its own
# module-level COLLECTION_NAME/PREFIX/_MAT_CACHE/get_material, referenced as
# free variables by its OWN clear_previous()/get_material()/build_servo()
# etc. -- which this script calls again later (clear_previous() directly,
# get_material() transitively via build_leg()->build_servo()->MAT_BLACK()
# and friends). Reusing those exact names here would silently OVERWRITE the
# production script's globals with incompatible values/signatures (verified
# empirically: an earlier draft that reused `get_material`/`PREFIX` broke
# clear_previous() -- it uses COLLECTION_NAME as a free variable resolved at
# CALL time, so overwriting it before calling clear_previous() makes it look
# for the WRONG collection name and silently no-op instead of clearing the
# production build -- and broke build_servo()'s MAT_BLACK()/MAT_METAL()
# lambdas, which resolve get_material() the same way and got a
# signature-incompatible replacement, raising "sequences of dimension 0
# should contain 4 items, not 5"). Every name below is therefore deliberately
# LLD_-prefixed/unique, not just this script's own object-naming prefix.
LLD_COLLECTION_NAME = "LegLinkageDeviation"
LLD_MAT_PREFIX = "LLD_"

_LLD_MAT_CACHE = {}


def get_lld_material(name, rgba, alpha=1.0):
    key = (name, rgba, alpha)
    if key in _LLD_MAT_CACHE:
        return _LLD_MAT_CACHE[key]
    mat = bpy.data.materials.get(LLD_MAT_PREFIX + name) or bpy.data.materials.new(LLD_MAT_PREFIX + name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgba, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.4
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = 'BLEND'
    _LLD_MAT_CACHE[key] = mat
    return mat


# ---------------------------------------------------------------------------
# 3. Direct-assignment leg-angle setter -- replicates kf_leg_angle()'s
#    4-line rotation_euler.x assignment body without its keyframe_insert
#    calls. No animation/timeline semantics apply to a static per-sample
#    pose evaluation; using the real kf_leg_angle() would work too (106
#    calls landing on the same frame just overwrite one keyframe per
#    channel) but is needless overhead and leaves stray keyframe data in a
#    diagnostic .blend with no timeline purpose.
# ---------------------------------------------------------------------------
def _set_leg_angle(leg, angle_deg):
    rad = math.radians(angle_deg)
    leg['hip_servo'].rotation_euler.x = rad
    leg['upper_plate_front'].rotation_euler.x = rad
    leg['upper_plate_back'].rotation_euler.x = rad
    leg['knee_knuckle'].rotation_euler.x = -rad


def _sample_leg(leg, hip_world):
    """Sweep LAUNCH_ANGLE->CROUCH_ANGLE at lk.SAMPLE_STEP_DEG, same loop
    shape as linkage_kinematics.sampled_ankle_positions() so the two
    sample grids line up 1:1 for the cross-check. Returns a list of
    (angle_deg, world_translation, x_mm, z_mm) -- x_mm/z_mm converted to
    ankle_position()'s hip-local convention."""
    samples = []
    angle = LAUNCH_ANGLE
    while angle < CROUCH_ANGLE:
        _set_leg_angle(leg, angle)
        bpy.context.view_layer.update()
        t = leg['ankle_block'].matrix_world.translation.copy()
        x_mm = (t.y - hip_world[1] * MM) / MM
        z_mm = (t.z - hip_world[2] * MM) / MM
        samples.append((angle, t, x_mm, z_mm))
        angle += lk.SAMPLE_STEP_DEG
    _set_leg_angle(leg, CROUCH_ANGLE)
    bpy.context.view_layer.update()
    t = leg['ankle_block'].matrix_world.translation.copy()
    x_mm = (t.y - hip_world[1] * MM) / MM
    z_mm = (t.z - hip_world[2] * MM) / MM
    samples.append((CROUCH_ANGLE, t, x_mm, z_mm))
    return samples


def _make_poly_curve(name, collection, points_mm, bevel_mm=0.0, material=None):
    """points_mm: list of (x, y, z) in mm. Builds one POLY-spline curve
    object with one point per entry."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    spline = curve.splines.new('POLY')
    spline.points.add(len(points_mm) - 1)
    for i, (x, y, z) in enumerate(points_mm):
        spline.points[i].co = (x * MM, y * MM, z * MM, 1.0)
    if bevel_mm > 0.0:
        curve.bevel_depth = bevel_mm * MM
        curve.bevel_resolution = 2
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def _make_text(name, collection, text, location_mm, size_mm=8.0, material=None):
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body = text
    curve.size = size_mm * MM
    obj = bpy.data.objects.new(name, curve)
    obj.location = mm(*location_mm)
    collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def _make_sphere(name, collection, radius_mm, location_mm, material=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius_mm * MM)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj.location = mm(*location_mm)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def build_deviation_curve(collection, upper_len, hip_z, label, x_offset_mm=0.0):
    """Builds one leg at (upper_len, hip_z) via the real build_leg(), plus
    its ankle-path curve, chord, 8mm tolerance envelope, CoM markers, and
    PASS/FAIL text label -- laterally offset by x_offset_mm (world X, outside
    the Y-Z sweep plane) so multiple passes don't overlap in the 3/4
    perspective view while collapsing to nothing (exact overlay) in the
    orthographic side view.

    Overrides UPPER_LEN/HIP_Z as module globals before calling build_leg()
    -- see module docstring for why this is the real parameterization
    mechanism, not a hypothetical build_leg() argument.
    """
    global UPPER_LEN, HIP_Z
    UPPER_LEN, HIP_Z = upper_len, hip_z

    anchor = bpy.data.objects.new(f"{label}_Anchor", None)
    anchor.location = (x_offset_mm * MM, 0.0, 0.0)
    collection.objects.link(anchor)

    leg = build_leg('R', collection, anchor)
    hip_world = leg['hip_world']

    samples = _sample_leg(leg, hip_world)

    max_dev_mm = lk.max_chord_deviation_mm([(a, x, z) for a, _t, x, z in samples])
    chord_x_mm = lk.chord_mean_horizontal_mm([(a, x, z) for a, _t, x, z in samples])
    com_dev_mm = abs(chord_x_mm - lk.COM_HORIZONTAL_OFFSET_FROM_HIP_MM)
    verdict = "PASS" if max_dev_mm <= lk.LINEAR_VECTOR_MAX_DEVIATION_MM else "FAIL"
    com_verdict = "within" if com_dev_mm <= lk.COM_OFFSET_TOLERANCE_MM else "OUTSIDE"

    curve_color = (0.15, 0.85, 0.2) if verdict == "PASS" else (0.9, 0.15, 0.1)
    curve_mat = get_lld_material(f"{label}_path", curve_color)

    # Ankle path -- world-space points, offset by x_offset_mm on X (the
    # anchor already offsets build_leg()'s own geometry there, but the
    # sampled world translation already includes that offset since it was
    # read from matrix_world after building on the offset anchor).
    path_points_mm = [(t.x / MM, t.y / MM, t.z / MM) for _a, t, _x, _z in samples]
    _make_poly_curve(f"{label}_AnklePath", collection, path_points_mm,
                      bevel_mm=1.5, material=curve_mat)

    # Chord -- straight line between the first and last sample (identical
    # definition to linkage_kinematics.max_chord_deviation_mm()'s chord).
    p1_mm = path_points_mm[0]
    p2_mm = path_points_mm[-1]
    chord_mat = get_lld_material(f"{label}_chord", (0.7, 0.7, 0.7))
    _make_poly_curve(f"{label}_Chord", collection, [p1_mm, p2_mm],
                      bevel_mm=0.6, material=chord_mat)

    # 8mm tolerance envelope -- two lines parallel to the chord, offset
    # +/-LINEAR_VECTOR_MAX_DEVIATION_MM perpendicular to the chord's Y-Z
    # direction (mathematically exact match to what max_chord_deviation_mm()
    # measures: perpendicular distance from the straight chord in the Y-Z
    # sweep plane). p1/p2 are (x, y, z) in world mm; the chord's own X is
    # constant (== x_offset_mm) since the sweep plane is Y-Z, so the
    # perpendicular direction is entirely within Y-Z too.
    dy = p2_mm[1] - p1_mm[1]
    dz = p2_mm[2] - p1_mm[2]
    chord_len = math.hypot(dy, dz)
    if chord_len > 1e-9:
        perp_y, perp_z = -dz / chord_len, dy / chord_len
    else:
        perp_y, perp_z = 1.0, 0.0
    band_mm = lk.LINEAR_VECTOR_MAX_DEVIATION_MM
    band_mat = get_lld_material("band", (0.9, 0.8, 0.1), alpha=0.35)
    for sign in (1.0, -1.0):
        off_y = perp_y * band_mm * sign
        off_z = perp_z * band_mm * sign
        band_p1 = (p1_mm[0], p1_mm[1] + off_y, p1_mm[2] + off_z)
        band_p2 = (p2_mm[0], p2_mm[1] + off_y, p2_mm[2] + off_z)
        _make_poly_curve(f"{label}_Band_{'pos' if sign > 0 else 'neg'}", collection,
                          [band_p1, band_p2], bevel_mm=0.3, material=band_mat)

    # CoM horizontal-offset markers: one at hip-local
    # (x=COM_HORIZONTAL_OFFSET_FROM_HIP_MM, z=chord mean Z), one at the
    # chord's own mean-horizontal position (chord_x_mm) -- both at the same
    # world Z (chord mean) and world X (x_offset_mm), varying only in the
    # sweep-plane "x" (world Y) axis per ankle_position()'s convention.
    hip_world_y_mm = hip_world[1]
    hip_world_z_mm = hip_world[2]
    com_marker_loc = (x_offset_mm, hip_world_y_mm + lk.COM_HORIZONTAL_OFFSET_FROM_HIP_MM,
                       (p1_mm[2] + p2_mm[2]) / 2.0)
    chord_marker_loc = (x_offset_mm, hip_world_y_mm + chord_x_mm,
                         (p1_mm[2] + p2_mm[2]) / 2.0)
    com_mat = get_lld_material("com_marker", (0.2, 0.4, 0.95))
    chord_marker_mat = get_lld_material("chord_marker", (0.9, 0.5, 0.1))
    _make_sphere(f"{label}_CoMMarker", collection, 3.0, com_marker_loc, material=com_mat)
    _make_sphere(f"{label}_ChordMarker", collection, 3.0, chord_marker_loc, material=chord_marker_mat)

    label_text = (f"{label}: {max_dev_mm:.1f}mm dev ({verdict}, "
                  f"<={lk.LINEAR_VECTOR_MAX_DEVIATION_MM:.0f}mm) | "
                  f"CoM delta {com_dev_mm:.1f}mm ({com_verdict} "
                  f"{lk.COM_OFFSET_TOLERANCE_MM:.0f}mm)")
    text_mat = get_lld_material(f"{label}_text", curve_color)
    text_loc = (x_offset_mm, hip_world_y_mm, hip_world_z_mm + 30.0)
    _make_text(f"{label}_Label", collection, label_text, text_loc,
               size_mm=6.0, material=text_mat)

    return {
        'leg': leg,
        'samples': samples,
        'max_dev_mm': max_dev_mm,
        'chord_x_mm': chord_x_mm,
        'com_dev_mm': com_dev_mm,
        'verdict': verdict,
        'com_verdict': com_verdict,
        'hip_world': hip_world,
    }


def _clear_default_scene_objects():
    """Removes Blender's leftover startup Cube/Light/Camera. Found
    empirically, in two stages: a first render came back dominated by a
    giant dark shape, which turned out to be the default 2x2x2 METER Cube
    sitting at the origin -- a first fix that only checked
    bpy.context.scene.collection.objects (the scene's ROOT collection,
    direct members only) did NOT remove it, because Blender's own startup
    scene actually links Cube/Light/Camera into a CHILD collection (named
    "Collection"), not the root directly -- confirmed by inspecting the
    saved .blend, where scene.collection.objects was empty but
    scene.objects (recursive) still listed all three. Fixed by walking
    bpy.context.scene.objects (recursive over every collection) instead of
    just the root. model_pendulum.py has its own
    clear_scene_preserve_camera_lights() for the general problem;
    model_dual_wheel_legged_robot_precise.py's clear_previous() does NOT
    (it only clears its own named "DualWheelLeggedRobotPrecise" collection),
    so this diagnostic script -- which must not modify that production file
    -- does its own equivalent cleanup here. Safe to remove everything
    still in the scene at this point: clear_previous() has already run, and
    this script's OWN collection doesn't exist yet (built right after this
    call), so nothing legitimate can still be present."""
    meshes_to_check = []
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH' and obj.data:
            meshes_to_check.append(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)
    for m in meshes_to_check:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    # Also drop any now-empty leftover collections (e.g. the default
    # "Collection") so they don't clutter the outliner -- purely cosmetic,
    # doesn't affect rendering.
    for coll in list(bpy.data.collections):
        if coll.name not in (LLD_COLLECTION_NAME,) and len(coll.objects) == 0 and coll.users == 0:
            bpy.data.collections.remove(coll)


def main():
    clear_previous()
    _clear_default_scene_objects()
    collection = bpy.data.collections.new(LLD_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)

    current = build_deviation_curve(collection, UPPER_LEN, HIP_Z, "current", x_offset_mm=0.0)
    candidate = build_deviation_curve(collection, UPPER_LEN + 10.0, HIP_Z, "candidate", x_offset_mm=180.0)

    # Cross-check against linkage_kinematics.py's own closed-form curve, for
    # the CURRENT geometry only (candidate uses a placeholder UPPER_LEN that
    # linkage_kinematics.py's module-level constants don't track -- the
    # cross-check is only meaningful where both sides model the same
    # geometry).
    lk_samples = lk.sampled_ankle_positions()
    lk_max_dev = lk.max_chord_deviation_mm(lk_samples)

    blender_points = [(a, x, z) for a, _t, x, z in current['samples']]
    max_point_delta = 0.0
    dx_values, dz_values = [], []
    for (a1, x1, z1), (a2, x2, z2) in zip(blender_points, lk_samples):
        assert abs(a1 - a2) < 1e-6, f"sample grids desynced at angle {a1} vs {a2}"
        dx, dz = x2 - x1, z2 - z1
        dx_values.append(dx)
        dz_values.append(dz)
        d = math.hypot(dx, dz)
        max_point_delta = max(max_point_delta, d)
    dx_spread = max(dx_values) - min(dx_values)
    dz_spread = max(dz_values) - min(dz_values)

    print("=" * 70)
    print("Leg linkage deviation visualization (issue #42, supports #41)")
    print("=" * 70)
    for pass_name, result in (("current", current), ("candidate", candidate)):
        print("-" * 70)
        print(f"Pass: {pass_name} (UPPER_LEN override used to build this pass)")
        print(f"  Max perpendicular deviation from chord: {result['max_dev_mm']:.3f}mm")
        print(f"  Threshold (proposed): <= {lk.LINEAR_VECTOR_MAX_DEVIATION_MM:.1f}mm")
        print(f"  -> {result['verdict']}")
        print(f"  Chord mean horizontal position: {result['chord_x_mm']:.2f}mm from hip")
        print(f"  CoM horizontal offset estimate: {lk.COM_HORIZONTAL_OFFSET_FROM_HIP_MM:.2f}mm from hip")
        print(f"  Chord vs CoM deviation: {result['com_dev_mm']:.2f}mm "
              f"({result['com_verdict']} {lk.COM_OFFSET_TOLERANCE_MM:.1f}mm tolerance) [informational]")
    print("-" * 70)
    print("Cross-check: Blender-sampled 'current' curve vs linkage_kinematics.py closed form")
    print(f"  linkage_kinematics.py max_chord_deviation_mm(): {lk_max_dev:.3f}mm")
    print(f"  Blender-sampled 'current' max_chord_deviation_mm(): {current['max_dev_mm']:.3f}mm")
    dev_agreement = abs(lk_max_dev - current['max_dev_mm'])
    print(f"  max_chord_deviation_mm() agreement (the number that gates PASS/FAIL): "
          f"{dev_agreement:.6f}mm {'OK' if dev_agreement <= 0.05 else '** DISCREPANCY **'}")
    print(f"  Max per-sample point distance (raw x,z, NOT translation-corrected): {max_point_delta:.4f}mm")
    print(f"  Per-sample dx spread: {dx_spread:.4f}mm | dz spread: {dz_spread:.4f}mm "
          f"(near-zero spread => the per-sample delta is a CONSTANT offset, i.e. the two "
          f"curves have the identical SHAPE, just different origins)")
    if max_point_delta > 0.05:
        if dx_spread < 0.05 and dz_spread < 0.05:
            print(f"  ** Per-sample points differ by a CONSTANT ({dx_values[0]:.4f}mm, "
                  f"{dz_values[0]:.4f}mm) offset, not a shape mismatch. Root cause: "
                  f"ankle_block (sampled here, per the spec) descends through "
                  f"upper_plate_front, which sits +PLATE_GAP/2 ({PLATE_GAP / 2:.1f}mm) off "
                  f"linkage_kinematics.py's single-centerline model in Y; and ankle_block "
                  f"itself sits ANKLE_DROP ({ANKLE_DROP:.1f}mm) mm ABOVE (less negative Z "
                  f"than) the point ankle_position()'s formula actually models (that formula's "
                  f"z_mm already subtracts ANKLE_DROP, i.e. it models the wheel-axle point, not "
                  f"ankle_block). Because max_chord_deviation_mm() is a perpendicular-distance-"
                  f"from-chord measurement, it is exactly invariant under this kind of rigid "
                  f"constant-offset translation of the whole sampled curve -- which is exactly "
                  f"why the actual PASS/FAIL-gating number above agrees to within float noise "
                  f"despite this. Flagging explicitly per the issue's own instruction not to "
                  f"silently absorb a discrepancy > 0.05mm -- this one is real, understood, and "
                  f"does not affect the PASS/FAIL verdict.")
        else:
            print(f"  ** DISCREPANCY > 0.05mm with non-trivial dx/dz SPREAD -- this looks like "
                  f"an actual shape mismatch, not just a constant offset. Investigate before "
                  f"trusting the PASS/FAIL verdict. **")
    else:
        print("  Within float/interpolation noise -- OK.")
    print("=" * 70)

    if bpy.app.background:
        bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND, check_existing=False)
        print(f"Saved: {OUTPUT_BLEND}")
    else:
        print("Skipped save -- not running headless (bpy.app.background is False); "
              "re-run via run_blender_python to persist the .blend, matching the "
              "existing model_<subject>.py save-guard convention (see e.g. "
              "model_dual_wheel_legged_robot_precise.py's main()).")


main()
