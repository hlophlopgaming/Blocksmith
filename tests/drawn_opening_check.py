# SPDX-License-Identifier: GPL-3.0-or-later
"""A face gesture subtracts only the clicked wall, including rooms and transformed meshes."""
import sys, math
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector, Matrix
import blocksmith as bs
from blocksmith import drawing, openings

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
room=bs.create(c,'ROOM'); room.bs.width=6; room.bs.depth=6; room.bs.height=4
stamp=bs.signature(room.data)

def gesture(obj,a,b,kind='ARCH',normal=(0,-1,0)):
    c.view_layer.update(); world=obj.matrix_world
    point=world@Vector(a); normal=(world.to_3x3().inverted().transposed()@Vector(normal)).normalized()
    with patch.object(drawing,'ray',return_value=(point+normal*3,-normal)):
        target,frame,depth=openings.surface(c,SimpleNamespace(ctrl=True))
    assert target==obj
    shape=openings.drawn_mesh(kind,Vector(),frame.inverted()@(world@Vector(b)),depth)
    with bs.guard.transaction(c): openings.apply_drawn(c,target,shape,frame)
    c.view_layer.update()
    return depth

depth=gesture(room,(1,0,1),(3,0,3))
assert abs(depth-room.bs.thickness)<1e-4,depth
assert bs.signature(room.data)==stamp and room.bs.kind=='ROOM'
def ray(x,z): return room.evaluated_get(c.evaluated_depsgraph_get()).ray_cast(Vector((x,-1,z)),Vector((0,1,0)))
assert ray(2,2)[0] and ray(2,2)[1].y>5,'The opposite room wall was cut'
assert ray(1.05,2.95)[1].y<.01,'Arch corners were cut as a rectangle'
assert ray(.5,2)[1].y<.01
assert not bs.guard.audit(c.scene)
gesture(room,(5,0,2),(4,0,.5),'WINDOW')
assert ray(4.5,1)[1].y>5 and ray(2,2)[1].y>5
assert len([m for m in room.modifiers if m.type=='BOOLEAN'])==2
assert all(m.object.hide_get() and m.object.parent==room for m in room.modifiers)
assert len([o for o in c.visible_objects if o.type=='MESH'])==1
assert not bs.guard.audit(c.scene)
print('PASS: drawn arch and reversed window on a room, intact opposite wall and original mesh, independent holes, no facade objects')

bpy.ops.mesh.primitive_cube_add(size=1)
obj=c.active_object; obj.data.transform(Matrix.Translation((3,.5,2))@Matrix.Diagonal((6,1,4,1)))
obj.matrix_world=Matrix.Translation((20,0,0))@Matrix.Rotation(.6,4,'Z')@Matrix.Diagonal((1.3,.8,1.1,1))
stamp=bs.signature(obj.data); world=obj.matrix_world.copy()
assert abs(gesture(obj,(1,0,.2),(3,0,2.5),'WINDOW')-.8)<1e-4
hit,_,_,_=obj.evaluated_get(c.evaluated_depsgraph_get()).ray_cast(Vector((2,-1,1)),Vector((0,1,0)))
assert not hit and obj.matrix_world==world and bs.signature(obj.data)==stamp
print('PASS: arbitrary mesh, rotation, nonuniform scale and automatic face thickness')
# A side wall uses the hit normal, without selecting a room side or an axis.
gesture(room,(0,1,1),(0,3,2.5),'WINDOW',(-1,0,0))
evaluated=room.evaluated_get(c.evaluated_depsgraph_get())
assert evaluated.ray_cast(Vector((-1,2,1.5)),Vector((1,0,0)))[1].x>5
assert len(room.modifiers)==3 and not bs.guard.audit(c.scene)

import tempfile, json, struct
folder=Path(tempfile.mkdtemp(prefix='blocksmith-drawn-opening-'))
for selected in c.selected_objects: selected.select_set(False)
room.select_set(True); c.view_layer.objects.active=room
c.scene.bs.export_scope='SELECTED'; c.scene.bs.export_path=str(folder)
assert bpy.ops.blocksmith.export()=={'FINISHED'}
raw=(folder/'blockout.glb').read_bytes(); length=struct.unpack_from('<I',raw,12)[0]
gltf=json.loads(raw[20:20+length]); assert len(gltf['meshes'])==1
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'drawn.blend'))
bs.unregister(); bs.register()
assert len(room.modifiers)==3 and all(m.object.get('bs_drawn_opening') for m in room.modifiers)
assert ray(2,2)[1].y>5 and not bs.guard.audit(c.scene)
print('PASS: side wall from hit normal, evaluated GLB without cutters, saved openings and addon reload')

bs.unregister()
