# SPDX-License-Identifier: GPL-3.0-or-later
"""Preset fidelity, direct resize anchoring, texture export and input lifecycle."""
import sys
from pathlib import Path
import tempfile
import struct
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import blocksmith as bs
from blocksmith.ui import apply_preset
from blocksmith.editing import resize
from blocksmith.drawing import parameters
from mathutils import Vector

bs.register()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
c=bpy.context
assert len(bs.PRESETS)==32 and len(bs.BY_ID)==32
for i,preset in enumerate(bs.PRESETS):
    c.scene.cursor.location=(i%8*14,i//8*14,0)
    obj=apply_preset(c,preset[0]); c.view_layer.update()
    for key,value in preset[4].items():
        actual=getattr(obj.bs,key)
        assert abs(actual-value)<1e-5 if isinstance(value,(float,int)) else actual==value,(preset[0],key)
    preview=parameters(c,obj.bs.kind,preset[0]); geometry=bs.build(preview)
    assert len(geometry.vertices)==len(obj.data.vertices),preset[0]
    assert obj.data.materials[0].name.startswith('BS_Kenney_')
print('PASS: 32 presets match meshes and drawing parameters')
for i,kind in enumerate(['BLOCK','FLOOR','CYLINDER','STAIRS']):
    c.scene.cursor.location=(140,i*30,0)
    obj=bs.create(c,kind); obj.rotation_euler.z=.7; c.view_layer.update()
    for key,index in [('width',0),('depth',1),('height',2)]:
        if kind=='CYLINDER' and key=='depth': continue
        for side in (-1,1):
            local=[Vector(v) for v in obj.bound_box]
            edge=min(v[index] for v in local) if side>0 else max(v[index] for v in local)
            point=Vector((0,0,0)); point[index]=edge
            before=obj.matrix_world@point
            resize(obj,key,getattr(obj.bs,key)+.5,side); c.view_layer.update()
            coords=[v.co[index] for v in obj.data.vertices]
            point[index]=min(coords) if side>0 else max(coords)
            assert (obj.matrix_world@point-before).length<1e-4,(kind,key,side)
print('PASS: both resize directions preserve opposite faces, including floor and rotated objects')
c.scene.cursor.location=(180,0,0)
obj=apply_preset(c,'door'); bpy.ops.blocksmith.opening(variant='ARCH')
assert obj.bs.kind=='WALL' and obj.bs.opening=='ARCH'
obj.data.vertices[0].co.x+=.1
assert not bpy.ops.blocksmith.step.poll(), 'manual edit protection lost'
c.scene.cursor.location=(200,0,0)
obj=apply_preset(c,'wall_4'); c.scene.bs.palette='Orange'; c.scene.bs.texture='07'
bpy.ops.blocksmith.texture()
assert 'Orange_07' in obj.data.materials[0].name
folder=Path(tempfile.mkdtemp(prefix='blocksmith-ui-export-'))
c.scene.bs.export_scope='SELECTED'; c.scene.bs.export_path=str(folder)
bpy.ops.blocksmith.export()
raw=(folder/'blockout.glb').read_bytes(); n=struct.unpack_from('<I',raw,12)[0]
gltf=json.loads(raw[20:20+n]); assert gltf['images'] and gltf['textures']
assert any('Orange_07' in m.get('name','') for m in gltf['materials'])
bs.unregister(); bs.register(); bs.unregister()
print('PASS: opening conversion, protected manual edits, Kenney GLB textures, clean re-registration')
