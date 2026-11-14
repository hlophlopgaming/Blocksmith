# SPDX-License-Identifier: GPL-3.0-or-later
"""A saved file pause permits sculpting and never restores stale geometry on resume."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blocksmith as bs

bs.register(); c=bpy.context; g=bs.guard
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
obj=bs.create(c,'BLOCK'); obj.name='Sculpted'
c.scene.cursor.location=(4,0,0)
neighbor=bs.create(c,'BLOCK'); neighbor.name='ProtectedNeighbor'
c.scene.cursor.location=(20,0,0)
player=bs.create(c,'PLAYER'); player.name='Player'
player_height=player.bs.height
second=bpy.data.scenes.new('Other scene')
folder=Path(tempfile.mkdtemp(prefix='blocksmith-file-pause-'))
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'enabled.blend'))
before={o.name:bs.signature(o.data) for o in c.scene.objects if o.type=='MESH'}
c.scene.bs.file_enabled=False
assert not g.enabled() and not second.bs.file_enabled
assert all(not item.active for _,item in bs.KEYMAPS)
assert not g._states and not g._backups
assert {o.name:bs.signature(o.data) for o in c.scene.objects if o.type=='MESH'}==before

# Pausing removes background capture, property rebuilds, material changes and snap updates.
capture=g.capture
def unexpected_capture(*args,**kwargs): raise AssertionError('Paused file still captures meshes')
g.capture=unexpected_capture
try:
    assert g.tick()==.5
    c.view_layer.objects.active=obj
    for other in c.selected_objects: other.select_set(False)
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='SCULPT')
    obj.data.vertices[0].co.z+=.375
    obj.data.update(); c.view_layer.update()
    assert g.flush()
    bpy.ops.object.mode_set(mode='OBJECT')
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm,faces=list(bm.faces)); bm.to_mesh(obj.data); bm.free()
    obj.location.x=4; obj.scale.x=-1
    stamp=bs.signature(obj.data)
    material=obj.data.materials[0]
    obj.bs.width=5; obj.bs.palette='Red'
    assert bs.signature(obj.data)==stamp and obj.data.materials[0]==material
    c.scene.bs.player_height=2.5
    assert player.bs.height==player_height
    view=next(a.spaces.active for a in c.window_manager.windows[0].screen.areas if a.type=='VIEW_3D')
    snap=c.scene.tool_settings.use_snap; scale=view.overlay.grid_scale
    c.scene.bs.move_snap=not snap; c.scene.bs.grid=.125
    assert c.scene.tool_settings.use_snap==snap
    assert view.overlay.grid_scale==scale
    assert g.flush() and g.tick()==.5 and not g.audit(c.scene)
    assert not g.protected(obj) and not g._states and not g._backups
    assert bs.create(c,'BLOCK') is None
    assert not bs.ui.BS_GGT_resize.poll(c) and not bs.BS_PT_tools.poll(c)
    bs.draw_dimensions()
finally: g.capture=capture
print('PASS: all scenes paused; sculpt/manual edits, overlap and reflection survive; no background captures or property side effects')

bpy.ops.wm.save_as_mainfile(filepath=str(folder/'paused.blend'))
bpy.ops.wm.open_mainfile(filepath=str(folder/'enabled.blend'))
assert g.enabled(); g.tick()
assert all(item.active for _,item in bs.KEYMAPS)
bpy.ops.wm.open_mainfile(filepath=str(folder/'paused.blend'))
assert not g.enabled(); g.tick()
assert all(not item.active for _,item in bs.KEYMAPS)
obj=c.scene.objects['Sculpted']; neighbor=c.scene.objects['ProtectedNeighbor']
assert bs.signature(obj.data)==stamp and obj.location.x==4 and obj.scale.x==-1
# Newly added scenes do not escape the paused file; resume from any scene works.
third=bpy.data.scenes.new('Added while paused')
assert not g.enabled()
g.tick(); assert not third.bs.file_enabled
third.bs.file_enabled=True
assert g.enabled() and all(scene.bs.file_enabled for scene in bpy.data.scenes)
assert bs.signature(obj.data)==stamp and obj.location.x==4 and obj.scale.x==-1 and bs.manual(obj)
neighbor.scale.y=-1; c.view_layer.update()
assert not g.flush() and neighbor.scale.y==1
assert bs.signature(obj.data)==stamp and obj.scale.x==-1
print('PASS: pause saved per file, loading another file resumes tools, manual/sculpt edits preserved on resume, protection returns for new changes')
bs.unregister()
