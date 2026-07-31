"""
Shared mesh/animation primitives for the dual-wheel-legged-robot scripts
(model_dual_wheel_legged_robot.py and its _precise sibling). Extracted
after the same fcurve-filtering bug in kf_loc had to be independently
found and patched in both files (issue #23 code review) -- not meant to
be imported by unrelated scripts in this repo.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

MM = 0.001  # 1mm in Blender meters


def mm(*vals):
    if len(vals) == 1:
        return vals[0] * MM
    return tuple(v * MM for v in vals)


def mm_inv(vec):
    return (vec.x / MM, vec.y / MM, vec.z / MM)


AXIS_ROT = {
    'Z': None,
    'X': Matrix.Rotation(math.radians(90), 3, 'Y'),
    'Y': Matrix.Rotation(math.radians(90), 3, 'X'),
}


def _link(obj, collection):
    collection.objects.link(obj)
    return obj


def apply_transforms(obj):
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.select_set(False)


def shade_flat(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = False


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def make_box(name, collection, size_mm, pivot_mm=(0.0, 0.0, 0.0), location_mm=(0.0, 0.0, 0.0), material=None):
    """Box of size_mm (x,y,z), local origin offset by pivot_mm from geometric center.
    Scale is baked via bmesh construction directly, then transform_apply is
    still called right after creation (location=False) so any future
    rotation/scale edits on THIS object start from a clean identity basis --
    satisfies the "apply transforms right after creating each plate" brief."""
    sx, sy, sz = mm(*size_mm)
    px, py, pz = mm(*pivot_mm)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = v.co.x * sx - px
        v.co.y = v.co.y * sy - py
        v.co.z = v.co.z * sz - pz
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj, collection)
    obj.location = mm(*location_mm)
    shade_flat(obj)
    apply_transforms(obj)
    if material is not None:
        assign_material(obj, material)
    return obj


def make_cylinder(name, collection, radius_mm, depth_mm, axis='Z', segments=32,
                   pivot_mm=(0.0, 0.0, 0.0), location_mm=(0.0, 0.0, 0.0), cap=True, material=None):
    r = mm(radius_mm)
    d = mm(depth_mm)
    px, py, pz = mm(*pivot_mm)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments,
                           radius1=r, radius2=r, depth=d)
    rot = AXIS_ROT.get(axis)
    if rot is not None:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=rot)
    for v in bm.verts:
        v.co.x -= px
        v.co.y -= py
        v.co.z -= pz
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj, collection)
    obj.location = mm(*location_mm)
    shade_flat(obj)
    apply_transforms(obj)
    if material is not None:
        assign_material(obj, material)
    return obj


def merge_cutters(name, collection, cutter_specs):
    """cutter_specs: list of dicts {type:'box'|'cyl', size/radius/depth/axis, location(local mm)}.
    Builds ONE combined mesh so a single boolean modifier removes all of them."""
    bm = bmesh.new()
    for spec in cutter_specs:
        sub = bmesh.new()
        if spec['type'] == 'box':
            sx, sy, sz = mm(*spec['size'])
            bmesh.ops.create_cube(sub, size=1.0)
            for v in sub.verts:
                v.co.x *= sx
                v.co.y *= sy
                v.co.z *= sz
        else:
            r = mm(spec['radius'])
            d = mm(spec['depth'])
            bmesh.ops.create_cone(sub, cap_ends=True, cap_tris=False, segments=spec.get('segments', 24),
                                   radius1=r, radius2=r, depth=d)
            rot = AXIS_ROT.get(spec.get('axis', 'Z'))
            if rot is not None:
                bmesh.ops.rotate(sub, verts=sub.verts, cent=(0, 0, 0), matrix=rot)
        lx, ly, lz = mm(*spec['location'])
        for v in sub.verts:
            v.co.x += lx
            v.co.y += ly
            v.co.z += lz
        tmp_mesh = bpy.data.meshes.new("tmp_cutter")
        sub.to_mesh(tmp_mesh)
        sub.free()
        bm.from_mesh(tmp_mesh)
        bpy.data.meshes.remove(tmp_mesh)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj, collection)
    return obj


def boolean_diff_apply(target, cutter_obj):
    mod = target.modifiers.new(name="Cut", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter_obj
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mesh_data = cutter_obj.data
    bpy.data.objects.remove(cutter_obj, do_unlink=True)
    if mesh_data.users == 0:
        bpy.data.meshes.remove(mesh_data)
    shade_flat(target)


def set_ease(obj, easing='EASE_IN_OUT'):
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = easing


def animate_assembly(obj, assembled_loc_mm, explode_dir_mm, seat_frame=45, hold_frame=90):
    """Frame 1: exploded. seat_frame: seated. Holds static through hold_frame."""
    assembled = Vector(mm(*assembled_loc_mm))
    exploded = assembled + Vector(mm(*explode_dir_mm))

    obj.location = exploded
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location = assembled
    obj.keyframe_insert(data_path="location", frame=seat_frame)
    obj.keyframe_insert(data_path="location", frame=hold_frame)
    set_ease(obj, 'EASE_OUT')


def set_keyframe_shape(obj, data_path, frame, interp, easing, array_index=None):
    """Sets interpolation/easing on the keyframe point at `frame` matching
    data_path (and array_index, if given). Shared by every kf_* helper
    below instead of each re-walking fcurves itself -- was independently
    duplicated 4x before this (issue #23 code review).

    Finds the keyframe by ITS FRAME NUMBER, not by grabbing
    keyframe_points[-1] (array position) -- an earlier version of this
    code did that, which only happens to find the keyframe just inserted
    when every call across a curve's lifetime authors strictly in
    increasing-frame order. lock_wheels_to_floor breaks that assumption on
    purpose (it revisits early frames, like 90-168, AFTER later frames
    like 174/220 are already keyframed), so keyframe_points[-1] there
    silently grabbed the highest-FRAME-NUMBER keyframe on the curve --
    usually the final stand-frame -- instead of the one just touched. That
    bug was invisible as long as every caller used the same default shape
    anyway; it only became visible once a caller needed a *specific* frame
    to carry a different shape than its neighbors (issue #23 code review).

    NOTE: a keyframe's interpolation/easing governs the curve segment
    LEAVING that keyframe (toward the next one), not the segment arriving
    at it -- verified empirically. Set the shape on the EARLIER of two
    keyframes to control the segment between them.

    NOTE: Blender ignores the `easing` enum entirely when interpolation is
    'BEZIER' (the default here, and everywhere in this codebase) -- it
    only affects the primitive curve types (QUAD/CUBIC/EXPO/SINE/etc).
    Pass a real interp mode when `easing` needs to actually do something.
    """
    if not (obj.animation_data and obj.animation_data.action):
        return
    for fc in obj.animation_data.action.fcurves:
        if fc.data_path != data_path:
            continue
        if array_index is not None and fc.array_index != array_index:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                kp.interpolation = interp
                kp.easing = easing
                break


def kf_loc(obj, frame, loc_mm, interp='BEZIER', easing='EASE_IN_OUT'):
    obj.location = Vector(mm(*loc_mm))
    obj.keyframe_insert(data_path="location", frame=frame)
    set_keyframe_shape(obj, "location", frame, interp, easing)


def kf_loc_z(obj, frame, z_mm, interp='BEZIER', easing='EASE_IN_OUT'):
    """Keyframes only the Z channel of location, leaving X/Y fcurves (and
    their existing keyframes) untouched -- for dense per-frame correction
    passes like lock_wheels_to_floor, where re-inserting the full (x,y,z)
    vector every frame would triple the keyframe count for channels that
    never actually change."""
    obj.location.z = z_mm * MM
    obj.keyframe_insert(data_path="location", index=2, frame=frame)
    set_keyframe_shape(obj, "location", frame, interp, easing, array_index=2)


def kf_rot_x(obj, frame, deg, interp='BEZIER', easing='EASE_IN_OUT'):
    obj.rotation_euler.x = math.radians(deg)
    obj.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
    set_keyframe_shape(obj, "rotation_euler", frame, interp, easing, array_index=0)


def kf_rot_full(obj, frame, euler, interp='BEZIER', easing='EASE_IN_OUT'):
    """Keyframes all three rotation_euler channels at once from a given
    mathutils.Euler -- for rotations that don't decompose into a single
    meaningful channel (e.g. a wheel roll composed around a tipped local
    axis; see kf_wheel_spin in the _precise script)."""
    obj.rotation_euler = euler
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    set_keyframe_shape(obj, "rotation_euler", frame, interp, easing)


def lock_wheels_to_floor(root_obj, legs, floor_z, frame_ranges, boundary_shapes=None):
    """Densely re-keyframes root_obj's Z (every frame, in the given ranges
    only) so the wheel bottom sits exactly at floor_z throughout -- not
    just at hand-authored anchor frames, which bezier-interpolate through
    a nonlinear FK relationship and drift a few mm off the floor between
    them (issue #23: measured up to -4.9mm mid-crouch-ramp before this).

    Shared by both robot scripts (root_obj is base_plate/chassis
    respectively) -- moved here after the same "extend the range one
    frame into launch" fix had to be independently re-derived for each
    copy once already.

    Derived from the R wheel and applied to both via root_obj.z (shared by
    the whole rig) -- correct as long as the caller always drives L and R
    to identical angles, which both callers do. Asserted every sampled
    frame rather than assumed, so a future asymmetric gait change (turning,
    per-leg balance correction) fails loudly here instead of silently
    floating/sinking L.

    boundary_shapes: optional {frame: (interp, easing)} -- since a
    keyframe's shape governs the segment LEAVING it (see set_keyframe_
    shape), the LAST frame of a locked range still controls the very next
    (unlocked, airborne) segment even though its VALUE gets corrected
    here. Every frame's default BEZIER/EASE_IN_OUT shape is harmless for
    frames strictly inside a range (the next frame's own point makes the
    shape between them moot), but silently clobbering a deliberately-set
    non-BEZIER shape on a range's last frame breaks whatever curve the
    caller wanted for the segment after it (issue #23 code review: this
    is exactly how the "explosive ascent" shape at LAUNCH_FRAME was lost).
    Pass the desired shape for such frames here instead of relying on
    whatever kf_loc/kf_rot_* call set it earlier.

    One-shot bake computed from the pose at script-build time -- if a live
    session (run_blender_python_live) re-keyframes a leg angle inside these
    ranges afterward, this correction does NOT get re-run and the bake goes
    stale for that frame. Re-run the whole model script (or call this
    function again) after any such live edit.
    """
    scene = bpy.context.scene
    wheel_r = legs['R']['wheel']
    wheel_l = legs['L']['wheel']
    boundary_shapes = boundary_shapes or {}
    for start, end in frame_ranges:
        for f in range(start, end + 1):
            scene.frame_set(f)
            root_obj.location.z = 0.0
            bpy.context.view_layer.update()
            offset_r = min((wheel_r.matrix_world @ Vector(c)).z for c in wheel_r.bound_box)
            offset_l = min((wheel_l.matrix_world @ Vector(c)).z for c in wheel_l.bound_box)
            assert abs(offset_l - offset_r) < 0.001, (
                f"frame {f}: L/R wheel-bottom offsets diverged "
                f"({offset_l:.5f} vs {offset_r:.5f}) -- lock_wheels_to_floor "
                "assumes symmetric legs and only corrects against R"
            )
            needed_z_mm = (floor_z - offset_r) / MM
            interp, easing = boundary_shapes.get(f, ('BEZIER', 'EASE_IN_OUT'))
            kf_loc_z(root_obj, f, needed_z_mm, interp=interp, easing=easing)
