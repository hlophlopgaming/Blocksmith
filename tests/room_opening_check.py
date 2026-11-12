# SPDX-License-Identifier: GPL-3.0-or-later
"""Room openings must cut only the chosen wall and keep the room editable."""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Vector
import blocksmith as bs
from blocksmith.editing import metric_issues

bs.register()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
c=bpy.context
room=bs.create(c,'ROOM')
with bs.guard.transaction(c):
    room.bs.width=8; room.bs.depth=6; room.bs.height=3; room.bs.thickness=.3
    room.location=(12,-5,2); room.rotation_euler.z=math.radians(37)
c.view_layer.update()
bs.set_pivot(room,room.matrix_world@Vector((4,3,0)))
matrix=room.matrix_world.copy(); pivot=tuple(room.bs.pivot_offset)

def wall_hit(side,z,x=None):
    p=room.bs; w,d=p.width,p.depth
    center=(w if side in {'FRONT','BACK'} else d)/2 if x is None else x
    origin,direction={'FRONT':((center,-1,z),(0,1,0)),
                      'BACK':((center,d+1,z),(0,-1,0)),
                      'LEFT':((-1,center,z),(1,0,0)),
                      'RIGHT':((w+1,center,z),(-1,0,0))}[side]
    return room.ray_cast(Vector(origin)-Vector(pivot),Vector(direction),distance=1+min(p.thickness,w/3,d/3)+.01)[0]

for thickness in (.3,2.28):
    room.bs.thickness=thickness
    for side in ('FRONT','BACK','LEFT','RIGHT'):
        # Changing sides moves the opening; it must restore the previous wall.
        room.bs.room_wall=side
        for variant in ('DOOR','WINDOW','ARCH','NONE'):
            assert bpy.ops.blocksmith.opening(variant=variant)=={'FINISHED'}
            c.view_layer.update()
            assert room.bs.kind=='ROOM' and room.matrix_world==matrix
            assert tuple(room.bs.pivot_offset)==pivot
            assert (room.bs.width,room.bs.depth,room.bs.height)==(8,6,3)
            z=1.5 if variant=='WINDOW' else .5
            for other in ('FRONT','BACK','LEFT','RIGHT'):
                assert wall_hit(other,z)==(other!=side or variant=='NONE'),(thickness,side,variant,other)
            if variant=='WINDOW': assert wall_hit(side,.25),'Window lost its sill'
            assert wall_hit(side,2.99),'Opening removed the lintel'
            bm=bmesh.new(); bm.from_mesh(room.data)
            assert all(e.is_manifold for e in bm.edges),(side,variant)
            assert bm.calc_volume()>0
            bm.free()
            assert not bs.manual(room) and not bs.guard.audit(c.scene)
print('PASS: doors/windows/arches on all four room walls, thick walls, intact lintels, closed meshes, unchanged transforms/pivot')

room.bs.thickness=.3; room.bs.room_wall='FRONT'
bpy.ops.blocksmith.opening(variant='DOOR')
room.bs.offset=.4; room.bs.open_width=1.4
c.view_layer.update()
assert not wall_hit('FRONT',1,4.4) and wall_hit('FRONT',1,.5)
room.bs.count=2; c.view_layer.update()
gap=(8-2*1.4)/3
for index in range(2): assert not wall_hit('FRONT',1,gap*(index+1)+1.4*index+.4+.7)
assert wall_hit('FRONT',1,4.4),'Space between doors disappeared'
# Side-wall clearance must use depth and its scale, rather than the room's width.
room.bs.room_wall='LEFT'; room.bs.open_width=.4
assert any('ширина' in issue for issue in metric_issues(room.bs,c.scene.bs))
room.bs.count=1; room.bs.room_wall='FRONT'; room.bs.open_width=1.4
# A resized room keeps an actual hole in the selected wall.
room.bs.width=10; c.view_layer.update()
assert not wall_hit('FRONT',1,5.4) and wall_hit('BACK',1)
room.bs.width=8
print('PASS: opening width/offset/count, room resize and side-wall clearance warnings')

# Closing a doorway must respect a managed object that now occupies the opening.
with bs.guard.transaction(c):
    blocker=bs.create(c,'BLOCK')
    blocker.bs.width=.2; blocker.bs.depth=.1; blocker.bs.height=.4
    blocker.matrix_world=room.matrix_world.copy()
    blocker.matrix_world.translation=room.matrix_world@(Vector((4.4,.1,.3))-Vector(pivot))
c.view_layer.update()
stamp=bs.signature(room.data)
room.bs.opening='NONE'
assert room.bs.opening=='DOOR' and bs.signature(room.data)==stamp
bpy.data.objects.remove(blocker,do_unlink=True)
c.view_layer.objects.active=room
c.view_layer.update(); bs.guard.flush()
print('PASS: closing the room doorway cannot overlap a managed object')

folder=Path(tempfile.mkdtemp(prefix='blocksmith-room-door-'))
s=c.scene.bs; s.export_path=str(folder); s.filename='room'; s.export_scope='SELECTED'
room.select_set(True)
assert bpy.ops.blocksmith.export()=={'FINISHED'}
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'room.blend'))
bs.unregister(); bs.register()
assert room.bs.kind=='ROOM' and room.bs.opening=='DOOR' and room.bs.room_wall=='FRONT'
assert bs.rebuild(room) and not bs.manual(room)
assert not wall_hit('FRONT',1,4.4)
print('PASS: room opening GLB export, saved parameters and addon reload')
print('ROOM_EXPORT',json.dumps(str(folder)))
Path('/tmp/blocksmith-room-door-export.txt').write_text(str(folder))
bs.unregister()
