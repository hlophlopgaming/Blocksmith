# SPDX-License-Identifier: GPL-3.0-or-later
"""Run: blender -b --factory-startup --python-exit-code 1 --python tests/blender_check.py"""
import sys
from pathlib import Path
import tempfile
import struct
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blocksmith as bs
from mathutils import Vector

bs.register()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
ctx=bpy.context
for i,kind in enumerate(bs.SHAPES):
    ctx.scene.cursor.location=(i%7*8,i//7*8,0)
    obj=bs.create(ctx,kind)
    assert obj.data.vertices and obj.data.polygons,kind
    bm=bmesh.new(); bm.from_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges),kind
    assert abs(bm.calc_volume())>1e-7,kind
    bm.free()
    assert not bs.manual(obj),kind
    obj.bs.height+=.25
    assert not bs.manual(obj),kind
    assert obj.data.uv_layers.active
print('PASS: all shapes, closed meshes, parameters, UVs')
ctx.scene.cursor.location=(80,0,0)
obj=bs.create(ctx,'BLOCK'); obj.bs.width=4
assert abs(max(v.co.x for v in obj.data.vertices)-4)<1e-5
before=[obj.matrix_world@v.co for v in obj.data.vertices]
bs.set_pivot(obj,obj.matrix_world@Vector((2,1,1)))
ctx.view_layer.update()
assert all((a-obj.matrix_world@v.co).length<1e-5 for a,v in zip(before,obj.data.vertices))
obj.bs.height=3
assert abs(min(v.co.x for v in obj.data.vertices)+2)<1e-5
obj.data.vertices[0].co.x+=.125
edited=obj.data.vertices[0].co.copy(); obj.bs.width=5
assert (obj.data.vertices[0].co-edited).length<1e-6 and bs.manual(obj)
assert bpy.ops.blocksmith.tool(action='RESET')=={'FINISHED'}
assert not bs.manual(obj)
print('PASS: pivot and manual edit protection')
# Baked water retains its role even if its display tag changes.
ctx.scene.cursor.location=(90,0,0)
water=bs.create(ctx,'WATER'); water.name='BakedWater'
assert bpy.ops.blocksmith.tool(action='BAKE')=={'FINISHED'}
bs.tag_object(water,'PROP')
assert bs.guard.excluded(water,ctx.scene)
temp=water.copy(); temp.data=water.data.copy(); temp.name='GuardTemporary'
ctx.scene.collection.objects.link(temp); temp['bs_guard_temp']=True
folder=Path(tempfile.mkdtemp(prefix='blocksmith-check-'))
s=ctx.scene.bs; s.export_path=str(folder); s.filename='blockout'; s.export_scope='COLLECTION'
source_names=set(bpy.data.objects.keys()); selected=list(ctx.selected_objects); active=ctx.active_object
assert bpy.ops.blocksmith.export()=={'FINISHED'}
assert set(bpy.data.objects.keys())==source_names
assert list(ctx.selected_objects)==selected and ctx.active_object==active
raw=(folder/'blockout.glb').read_bytes(); assert raw[:4]==b'glTF'
length,kind=struct.unpack_from('<II',raw,12); data=json.loads(raw[20:20+length])
names=[node.get('name','') for node in data['nodes']]
assert any(name.endswith('-col') for name in names),names
assert not any('Player' in name or 'Ruler' in name or 'Crouch' in name or 'Clearance' in name for name in names),names
assert any('Water' in name and not name.endswith('-col') for name in names),names
assert any(name.startswith('BakedWater') for name in names),names
assert not any('Water' in name and name.endswith('-col') for name in names),names
assert not any('GuardTemporary' in name for name in names),names
assert data.get('images') and data.get('textures')
print('PASS: GLB collision suffix, water, references, textures, scene restoration')
Path('/tmp/blocksmith-export-folder.txt').write_text(str(folder))
ctx.scene.bs.dimensions=False
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'demo.blend'))
bs.unregister(); bs.register(); bs.unregister()
print('PASS: save, unregister and register')
