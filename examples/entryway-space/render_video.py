"""Render an eight-second Eevee showcase from the supplied packed example.

Run in Blender, then encode the PNG sequence with the README's ffmpeg command.
"""
import argparse
import hashlib
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out-dir', type=Path, required=True)
parser.add_argument('--preview', action='store_true', help='Render one frame per shot')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = args.out_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == 'MESH']
assert len(meshes) == 196, 'Open the supplied Entryway-Space.blend first'

def signature():
    return hashlib.sha256(repr([
        (o.name, [tuple(v.co) for v in o.data.vertices],
         [tuple(p.vertices) for p in o.data.polygons], tuple(tuple(r) for r in o.matrix_world))
        for o in meshes
    ]).encode()).hexdigest()

before = signature()
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 32
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.fps = 24
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.frame_start = 1
scene.frame_end = 192
for marker in list(scene.timeline_markers):
    scene.timeline_markers.remove(marker)
camera = scene.objects['Overview - CLI build']
scene.camera = camera
camera.data.lens = 40
for frame in ([1, 121, 157] if args.preview else range(1, 193)):
    scene.frame_set(frame)
    if frame <= 120:
        angle = math.radians(42 + 32 * (frame - 1) / 119)
        position = (151 * math.cos(angle), 151 * math.sin(angle), 138)
        target = (0, 0, 1)
        camera.data.lens = 40
    elif frame <= 156:
        position = (11, -10 + 2 * (frame - 121) / 35, 2.4)
        target = (11, -1, 1.6)
        camera.data.lens = 19
    else:
        position = (-15, -.4 + 2 * (frame - 157) / 35, 2.15)
        target = (-15, 12, .3)
        camera.data.lens = 20
    camera.location = position
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / f'{frame:04d}.png')
    bpy.ops.render.render(write_still=True)
assert signature() == before, 'Presentation must preserve the construction meshes'
assert all((out / f'{f:04d}.png').is_file()
           for f in ([1, 121, 157] if args.preview else range(1, 193)))
print('VIDEO FRAMES COMPLETE: Eevee, 1280x720, 24 fps; construction meshes unchanged', flush=True)
