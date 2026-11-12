# SPDX-License-Identifier: GPL-3.0-or-later
"""Add a readable overview and camera to the generated test level."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blocksmith as bs
bs.register()
folder=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else Path(__file__).resolve().parents[1]/'generated'/'doom-hangar'
bpy.ops.wm.open_mainfile(filepath=str(folder/'level.blend'))
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=1600; scene.render.resolution_y=1100; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
shade=scene.display.shading
shade.light='STUDIO'; shade.color_type='TEXTURE'; shade.show_shadows=True
shade.show_cavity=True; shade.cavity_type='BOTH'; shade.background_type='WORLD'
scene.world.color=(.035,.045,.055)
bpy.ops.object.camera_add()
camera=bpy.context.object; camera.name='Overview'; camera.data.type='ORTHO'; camera.data.ortho_scale=108
center=Vector((-8,.5,.4)); camera.location=center+Vector((18,-58,105))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler(); scene.camera=camera
for name,text,location,size in [
    ('Label_START','START',(-28,-5,.04),1),('Label_EXIT','EXIT',(24.5,-26,.04),.8),
    ('Label_HANGAR','H A N G A R',(-13,-32,.04),2),
]:
    curve=bpy.data.curves.new(name,'FONT'); curve.body=text; curve.size=size; curve.extrude=.005
    obj=bpy.data.objects.new(name,curve); scene.collection.objects.link(obj); obj.location=location
    obj.color=(1,.5,.15,1)
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        space=area.spaces.active; space.shading.type='SOLID'; space.shading.color_type='TEXTURE'
        space.shading.show_cavity=True; space.overlay.show_floor=False
        rv=space.region_3d; rv.view_location=center; rv.view_rotation=camera.rotation_euler.to_quaternion()
        rv.view_distance=85; rv.view_perspective='ORTHO'
for obj in bpy.context.selected_objects: obj.select_set(False)
bpy.context.view_layer.objects.active=None
scene.cursor.location=(-25,-4,0)
scene.bs.dimensions=False
scene.render.filepath=str(folder/'overview.png')
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'hangar.blend'))
print('PASS: Hangar overview and editable Blender scene saved')
bs.unregister()
