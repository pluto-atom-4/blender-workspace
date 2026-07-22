"""Render the inverted pendulum simulation.

Three modes (set RENDER_MODE below):
- 'preview': single-frame viewport PNG, fast sanity check.
- 'sequence': renders FRAME_START..FRAME_END as a numbered PNG sequence
  into renders/inverted_pendulum_frames/ -- run this in a few chunks
  covering 1-144 rather than one long call, then combine with ffmpeg.
- (combine step is a separate ffmpeg command, not part of this script)
"""

import bpy

BLEND_PATH = "/home/pluto-atom-4/blender-workspace/blender-project/renders/inverted_pendulum_simulation.blend"
PREVIEW_OUTPUT = "/home/pluto-atom-4/blender-workspace/blender-project/renders/inverted_pendulum_simulation_preview.png"
FRAMES_DIR = "/home/pluto-atom-4/blender-workspace/blender-project/renders/inverted_pendulum_frames/"

RENDER_MODE = "sequence"  # 'preview' or 'sequence'
PREVIEW_FRAME = 100
FRAME_START = 109
FRAME_END = 144

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
scene = bpy.context.scene

# EEVEE Next on this box's GPU (nouveau) segfaults deterministically at
# sample 25/64 regardless of frame -- a driver/sandbox resource issue, not
# scene content. Cycles/CPU sidesteps the GPU driver entirely.
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32 if RENDER_MODE == "preview" else 16
scene.cycles.use_denoising = False
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200

if RENDER_MODE == "preview":
    scene.frame_set(PREVIEW_FRAME)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = PREVIEW_OUTPUT
    bpy.ops.render.render(write_still=True)
    print(f"Rendered preview (frame {PREVIEW_FRAME}): {PREVIEW_OUTPUT}")
else:
    import os
    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = FRAMES_DIR + "frame_"
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    bpy.ops.render.render(animation=True)
    print(f"Rendered frames {FRAME_START}-{FRAME_END} to: {FRAMES_DIR}")
