# SPDX-License-Identifier: GPL-3.0-or-later
"""Build shipped thumbnails from the actual preset geometry in a clean Blender process."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blocksmith as bs
from blocksmith.ui import apply_preset

bs.register()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=192; scene.render.resolution_y=144; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
shade=scene.display.shading; shade.light='STUDIO'; shade.color_type='MATERIAL'; shade.show_shadows=True
shade.show_cavity=True; shade.cavity_type='BOTH'; shade.background_type='WORLD'; scene.world.color=(.035,.045,.06)
bpy.ops.object.camera_add(); camera=bpy.context.object; scene.camera=camera; camera.data.type='ORTHO'
folder=Path(bs.__file__).parent/'assets'/'previews'; folder.mkdir(parents=True,exist_ok=True)
for identifier,label,group,kind,params in bs.PRESETS:
    obj=apply_preset(bpy.context,identifier)
    bpy.context.view_layer.update(); bb=bs.bounds(obj)
    low=Vector([min(v[i] for v in bb) for i in range(3)]); high=Vector([max(v[i] for v in bb) for i in range(3)])
    center=(low+high)/2; size=max(high-low)
    camera.location=center+Vector((1.4,-1.8,1.4))*max(1,size)
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=max(1,size)*1.65
    scene.render.filepath=str(folder/(identifier+'.png'))
    bpy.ops.render.render(write_still=True)
    mesh=obj.data; bpy.data.objects.remove(obj,do_unlink=True); bpy.data.meshes.remove(mesh)
bs.unregister()
print('PASS: rendered all preset thumbnails')
