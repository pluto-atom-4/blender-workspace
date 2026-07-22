"""Render the studio-quality servo pendulum using its own baked-in camera and lights."""

import bpy

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_servo_studio.blend"
OUTPUT_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/tamiya_pendulum_servo_studio_preview.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
scene = bpy.context.scene
scene.render.filepath = OUTPUT_PATH
bpy.ops.render.render(write_still=True)
print(f"Rendered studio preview: {OUTPUT_PATH}")
