# SPDX-License-Identifier: GPL-3.0-or-later
"""Run in a separate Blender: free placement, guard restoration and export."""
import json
from pathlib import Path
import struct
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Matrix
import blocksmith as bs

bs.register(); c=bpy.context; g=bs.guard
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
g.flush()

def cube(name,x):
    c.scene.cursor.location=(x,0,0)
    obj=bs.create(c,'BLOCK'); obj.name=name
    return obj

def select(*objects):
    for obj in c.selected_objects: obj.select_set(False)
    for obj in objects: obj.select_set(True)
    c.view_layer.objects.active=objects[-1]

left=cube('Protected',0); free=cube('Free',4); right=cube('ProtectedRight',8)
select(free)
assert not free.bs.free_placement
assert bpy.ops.blocksmith.free_placement(enabled=True)=={'FINISHED'}
free.location.x=1; free.scale.x=-1
c.view_layer.update(); assert g.flush() and free.bs.free_placement
assert free.location.x==1 and free.scale.x==-1 and not g.audit(c.scene)
shape=bs.build(free.bs)
assert not g.placement_error(c,shape.vertices,shape.faces,Matrix.Translation((-2,0,0)),'BLOCK')
assert g.placement_error(c,shape.vertices,shape.faces,Matrix.Identity(4),'BLOCK')

# Removing the mark must restore the mark, not move or delete the mesh.
assert bpy.ops.blocksmith.free_placement(enabled=False)=={'CANCELLED'}
assert free.bs.free_placement and free.location.x==1 and free.scale.x==-1
free.scale.x=1; c.view_layer.update(); assert g.flush()
assert bpy.ops.blocksmith.free_placement(enabled=False)=={'CANCELLED'}
assert free.bs.free_placement and free.location.x==1

# Exemption applies in both directions; unrelated rollback keeps the free edit.
left.location.x=1; c.view_layer.update(); assert g.flush()
left.location.x=8; free.location.y=1
c.view_layer.update(); assert not g.flush()
assert left.location.x==1 and free.location.y==1
free.bs.height=3; assert free.bs.height==3 and not bs.manual(free)
bm=bmesh.new(); bm.from_mesh(free.data)
bmesh.ops.reverse_faces(bm,faces=list(bm.faces)); bm.to_mesh(free.data); bm.free()
c.view_layer.update(); assert g.flush(),'Flipped normals rolled back on a free mesh'
free.scale.x=-1; c.view_layer.update(); assert g.flush()

# Duplicates, baking and the saved scene retain the mark.
copy=free.copy(); copy.data=free.data.copy(); c.collection.objects.link(copy)
c.view_layer.update(); assert g.flush() and copy.bs.free_placement
bpy.data.objects.remove(copy,do_unlink=True)
select(free)
assert bpy.ops.blocksmith.tool(action='BAKE')=={'FINISHED'}
assert not free.bs.enabled and free.bs.free_placement and not g.excluded(free,c.scene,include_water=True)
with tempfile.TemporaryDirectory(prefix='blocksmith-free-') as folder:
    c.scene.bs.export_scope='SELECTED'; c.scene.bs.export_path=folder
    assert bpy.ops.blocksmith.export()=={'FINISHED'}
    raw=Path(folder,'blockout.glb').read_bytes()
    size=struct.unpack_from('<I',raw,12)[0]
    gltf=json.loads(raw[20:20+size])
    assert any(n.get('name','').startswith('Free') for n in gltf['nodes'])
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(folder,'free.blend')))
    bpy.ops.wm.open_mainfile(filepath=str(Path(folder,'free.blend')))
    free=c.scene.objects['Free']; left=c.scene.objects['Protected']; right=c.scene.objects['ProtectedRight']
    assert free.bs.free_placement and not free.bs.enabled and free.scale.x==-1
    g.flush()

# Restore valid geometry, then remove the mark and confirm protection returns.
free.scale.x=1; free.location=(20,0,0)
bm=bmesh.new(); bm.from_mesh(free.data)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(free.data); bm.free()
c.view_layer.update(); assert g.flush()
select(free,right)
assert bpy.ops.blocksmith.free_placement(enabled=True)=={'FINISHED'}
assert free.bs.free_placement and right.bs.free_placement
assert bpy.ops.blocksmith.free_placement(enabled=False)=={'FINISHED'}
assert not free.bs.free_placement and not right.bs.free_placement
free.location.x=1; c.view_layer.update(); assert not g.flush() and free.location.x==20
right.scale.x=-1; c.view_layer.update(); assert not g.flush() and right.scale.x==1

# The property participates in the same history validation used by Undo/Redo.
select(free)
assert bpy.ops.blocksmith.free_placement(enabled=True)=={'FINISHED'}
free.location.x=1; c.view_layer.update(); assert g.flush()
bpy.ops.ed.undo_push(message='Free placement')
bs.BUSY=True
try: free.bs.free_placement=False
finally: bs.BUSY=False
bpy.ops.ed.undo_push(message='Unmarked invalid history')
free.bs.free_placement=True
bpy.ops.ed.undo_push(message='Marked again')
assert g.flush()
g._messages.clear()
bpy.ops.ed.undo()
g.check_history(c.scene)
assert g.message(c.scene).startswith('Intersection:'),'History ignored removal of the mark'
assert c.scene.objects['Free'].bs.free_placement,'Invalid Undo did not restore the mark'

bs.unregister(); bs.register(); bs.unregister()
print('PASS: free transforms/overlap/normals, scoped rollback, safe unmarking, copies, bake, save/reload, export and history validation')
