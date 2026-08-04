"""Export the armed inverted pendulum (issue #21, model_pendulum.py) to a
Wavefront OBJ mesh for import into Webots (issue #28, Phase 1).

Rebuilds the existing rig via model_pendulum.py (reused, not re-derived --
see PENDULUM.md for the dimension table) and exports the current selection
to blender-project/physics/worlds/meshes/pendulum.obj, the mesh referenced
by blender-project/physics/worlds/pendulum_world.wbt's Mesh node (Webots'
Mesh node supports DAE/STL/OBJ/FBX -- see
/usr/local/webots/resources/nodes/Mesh.wrl).

NOTE on format: the original plan called for bpy.ops.wm.collada_export
(.dae). This system's Blender package (Debian's blender 4.3.2+dfsg) does
not ship the Collada exporter -- io_scene_dae isn't bundled/enabled in the
"+dfsg" build (verified: bpy.ops.wm.collada_export raises "operator ...
could not be found"; bpy.ops.wm only exposes obj_export/ply_export/
stl_export, and bpy.ops.export_scene only fbx/gltf). OBJ is the closest
available equivalent Webots' Mesh node also accepts, so this exports OBJ
instead. global_scale=0.001 converts the model's millimeter-scale Blender
units (scale_length=0.001 per model_pendulum.py) to Webots' meters; the
exporter's default forward_axis='NEGATIVE_Z'/up_axis='Y' already matches
Webots' Y-up convention, so no extra rotation is needed in the world file.

Headless -- run via run_blender_python. The export only runs when
bpy.app.background is true (same guard model_pendulum.py uses for
save_as_mainfile), so accidentally running this against a live GUI session
never overwrites the exported mesh out from under the user.
"""

import bpy
import os

SCRIPTS_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/scripts"
OUTPUT_MESH = "/home/pluto-atom-4/blender-workspace/blender-project/physics/worlds/meshes/pendulum.obj"

exec(open(os.path.join(SCRIPTS_DIR, "model_pendulum.py")).read())

if bpy.app.background:
    os.makedirs(os.path.dirname(OUTPUT_MESH), exist_ok=True)

    # Select every mesh object in the rebuilt rig except Ground_Plane --
    # pendulum_world.wbt supplies its own floor (RectangleArena), so the
    # model's own ground mesh would just be a redundant duplicate sitting
    # at the same Z=0 plane.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.name != "Ground_Plane":
            obj.select_set(True)

    bpy.ops.wm.obj_export(
        filepath=OUTPUT_MESH,
        export_selected_objects=True,
        global_scale=0.001,  # mm (this model's units) -> m (Webots' units)
        forward_axis='NEGATIVE_Z',
        up_axis='Y',
        export_materials=True,
    )
    print(f"Exported pendulum mesh for Webots: {OUTPUT_MESH}")
else:
    print("Skipped mesh export -- not running headless (bpy.app.background is False); "
          "re-run via run_blender_python to actually export.")
