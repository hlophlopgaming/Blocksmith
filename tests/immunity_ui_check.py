# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blocksmith as bs
from blocksmith.ui import draw_main
bs.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
obj=bs.create(bpy.context,'BLOCK')
bpy.context.scene.cursor.location=(3,0,0)
neighbor=bs.create(bpy.context,'BLOCK')
neighbor.select_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
bpy.ops.object.mode_set(mode='EDIT')
seen=[]
class Layout:
    def label(self,**kw): pass
    def box(self): return self
    def row(self,**kw): return self
    def prop(self,data,name,**kw): seen.append((data,name))
    def operator(self,*args,**kw): return type('Op',(),{})()
draw_main(Layout(),bpy.context)
assert any(data==obj.bs and name=='free_placement' for data,name in seen), 'No persistent immunity switch is exposed in Edit Mode'
obj.bs.free_placement=True
bm=bmesh.from_edit_mesh(obj.data)
for vertex in bm.verts: vertex.co.x+=3
bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')
assert bs.guard.flush() and obj.bs.free_placement and not bs.guard.protected(obj)
stamp=bs.signature(obj.data)
obj.bs.free_placement=False
assert obj.bs.free_placement and bs.signature(obj.data)==stamp,'Restoring protection destroyed manual edits'
neighbor.scale.x=-1;bpy.context.view_layer.update()
assert not bs.guard.flush() and neighbor.scale.x==1
assert obj.bs.free_placement and bs.signature(obj.data)==stamp
bpy.ops.object.mode_set(mode='EDIT')
bm=bmesh.from_edit_mesh(obj.data)
for vertex in bm.verts: vertex.co.z+=.1
bmesh.update_edit_mesh(obj.data)
obj.bs.free_placement=False
bpy.ops.object.mode_set(mode='OBJECT')
changed=bs.signature(obj.data)
assert not bs.guard.flush()
assert obj.bs.free_placement and bs.signature(obj.data)==changed,'Deferred unmark discarded Edit Mode changes'
bs.unregister()
print('PASS: Edit Mode immunity switch, overlaps, reversed normals, protected neighbor and preserved manual edits on invalid unmark')
