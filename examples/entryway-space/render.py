"""Render the Blocksmith CLI example with supplied equirectangular space skyboxes.

Run after the native CLI generation; this script only adds World, lights and cameras.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out-dir',type=Path,default=ROOT/'space-example')
parser.add_argument('--samples',type=int,default=48)
parser.add_argument('--preview',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
out=args.out_dir.resolve();out.mkdir(parents=True,exist_ok=True)
assert 1<=args.samples<=1024
scene=bpy.context.scene
meshes=[o for o in scene.objects if o.type=='MESH']
assert len(meshes)==196,('Expected the latest Blocksmith CLI construction',len(meshes))
def signature():
    return hashlib.sha256(repr([(o.name,[(tuple(v.co)) for v in o.data.vertices],
                                [tuple(p.vertices) for p in o.data.polygons],tuple(tuple(r) for r in o.matrix_world))
                               for o in meshes]).encode()).hexdigest()
before=signature()
for obj in list(scene.objects):
    if obj.type in {'CAMERA','LIGHT'}:bpy.data.objects.remove(obj,do_unlink=True)
for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=args.samples
scene.render.resolution_x=960 if args.preview else 1920
scene.render.resolution_y=540 if args.preview else 1080
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.render.image_settings.color_mode='RGB'

world=bpy.data.worlds.new('Space skybox');world.use_nodes=True;scene.world=world
nodes=world.node_tree.nodes;nodes.clear();links=world.node_tree.links
coord=nodes.new('ShaderNodeTexCoord');mapping=nodes.new('ShaderNodeMapping')
mapping.inputs['Rotation'].default_value[2]=math.radians(125)
env=nodes.new('ShaderNodeTexEnvironment');env.projection='EQUIRECTANGULAR'
background=nodes.new('ShaderNodeBackground');background.inputs['Strength'].default_value=.8
ambient=nodes.new('ShaderNodeBackground');ambient.inputs['Color'].default_value=(.32,.4,.6,1)
ambient.inputs['Strength'].default_value=.5
path=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader');output=nodes.new('ShaderNodeOutputWorld')
links.new(coord.outputs['Normal'],mapping.inputs['Vector'])
links.new(mapping.outputs['Vector'],env.inputs['Vector'])
links.new(env.outputs['Color'],background.inputs['Color'])
links.new(path.outputs['Is Camera Ray'],mix.inputs[0])
links.new(ambient.outputs['Background'],mix.inputs[1]);links.new(background.outputs['Background'],mix.inputs[2])
links.new(mix.outputs[0],output.inputs['Surface'])

def camera(name,position,target,lens):
    data=bpy.data.cameras.new(name);data.lens=lens;data.clip_end=1000
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=position
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    return obj
hero=camera('Overview - CLI build',(92,120,138),(0,0,1),40)
entry=camera('Entry hall - space sky',(11,-10,2.4),(11,-1,1.6),19)
stair=camera('Stair hall - space sky',(-15,-.4,2.15),(-15,12,.3),20)
for frame,cam in enumerate([hero,entry,stair],1):
    marker=scene.timeline_markers.new(cam.name,frame=frame);marker.camera=cam
scene.frame_start=1;scene.frame_end=3
sun_data=bpy.data.lights.new('Key sunlight','SUN');sun_data.energy=3;sun_data.angle=math.radians(12)
sun=bpy.data.objects.new('Key sunlight',sun_data);scene.collection.objects.link(sun)
sun.rotation_euler=(math.radians(28),math.radians(-20),math.radians(-25))
fill_data=bpy.data.lights.new('Large soft fill','AREA');fill_data.energy=6500;fill_data.shape='DISK';fill_data.size=50
fill=bpy.data.objects.new('Large soft fill',fill_data);scene.collection.objects.link(fill)
fill.location=(0,-15,45);fill.rotation_euler=(Vector((0,0,0))-fill.location).to_track_quat('-Z','Y').to_euler()
skyboxes={name:ROOT/'skyboxes'/f'skybox-space-{name}.png' for name in ['nebula','galaxy','day','dark','band']}
images={}
for name,file in skyboxes.items():
    assert file.is_file(),file
    img=bpy.data.images.load(str(file),check_existing=True)
    assert tuple(img.size)==(4096,2048),(file,tuple(img.size))
    images[name]=img
    env.image=img;scene.frame_set(2);scene.camera=entry
    scene.render.filepath=str(out/f'entry-{name}.png')
    bpy.ops.render.render(write_still=True)
env.image=images['galaxy'];env.image.pack()
if not args.preview:
    for frame,(cam,name) in enumerate([(hero,'overview'),(entry,'entry'),(stair,'stairs')],1):
        scene.frame_set(frame);scene.camera=cam;scene.render.filepath=str(out/f'{name}.png')
        if name=='entry':
            shutil.copyfile(out/'entry-galaxy.png',out/'entry.png')
            continue
        bpy.ops.render.render(write_still=True)
scene.camera=hero;scene.frame_set(1)
scene['example']='Doom II MAP01 Entryway reconstructed with Blocksmith native CLI tools'
scene['construction']='185 editable modules, 34 contour structures, 11 native CUT helpers'
scene['render_workflow']='CLI Python: equirectangular World skybox, cameras, lights, Eevee'
scene['skybox']='skybox-space-galaxy.png; supplied by the example author'
assert signature()==before,'Rendering must not alter construction meshes or their transforms'
metadata=dict(ok=True,geometry_unchanged=True,mesh_signature=before,visible_modules=185,cutters=11,
              render_engine='Eevee',samples=args.samples,resolution=[scene.render.resolution_x,scene.render.resolution_y],
              primary_skybox='galaxy',skyboxes=list(skyboxes),cli_generated=True,
              skybox_sha256={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in skyboxes.items()})
(out/'render-report.json').write_text(json.dumps(metadata,indent=2))
if not args.preview:
    for name,image in images.items():
        if name!='galaxy' and image.users==0:bpy.data.images.remove(image)
    for image in bpy.data.images:
        if image.packed_file:image.filepath='//packed/'+image.name
    env.image.filepath='//skyboxes/skybox-space-galaxy.png'
    assert env.image.packed_file and scene.render.engine=='BLENDER_EEVEE'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Entryway-Space.blend'))
print('SPACE EXAMPLE COMPLETE',json.dumps(metadata),flush=True)
