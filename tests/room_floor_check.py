# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing a room rests its slab on the support instead of inside it."""
import sys, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Vector
import blocksmith as bs
from blocksmith.drawing import parameters, layout

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
floor=bs.create(c,'FLOOR'); floor.bs.width=floor.bs.depth=20
c.view_layer.update()
for thickness in (.2,.7):
    p=parameters(c,'ROOM','room_6'); p.thickness=thickness
    for end in ((8,8,0),(-4,-4,0)):
        world=layout(p,Vector((2,2,0)),Vector(end),Matrix.Identity(4))
        mesh=bs.build(p)
        assert abs(min((world@Vector(v)).z for v in mesh.vertices))<1e-5
        assert not bs.guard.placement_error(c,mesh.vertices,mesh.faces,world,'ROOM')
    p=parameters(c,'ROOM','room_6'); p.thickness=thickness
    frame=Matrix.Translation((3,3,5))@Matrix.Rotation(.3,4,'Z')
    world=layout(p,Vector(),Vector((6,6,0)),frame)
    assert abs(min((world@Vector(v)).z for v in bs.build(p).vertices)-5)<1e-5

p=parameters(c,'ROOM','room_6')
world=layout(p,Vector((2,2,0)),Vector((8,8,0)),Matrix.Identity(4))
with bs.guard.transaction(c):
    room=bs.create(c,'ROOM'); bs.BUSY=True
    try:
        for key in ('width','depth','height','thickness'): setattr(room.bs,key,getattr(p,key))
    finally: bs.BUSY=False
    bs.rebuild(room,True); room.matrix_world=world
assert not bs.guard.audit(c.scene)
c.scene.cursor.location=(14,2,0); wall=bs.create(c,'WALL')
world=layout(p,Vector((13,2,0)),Vector((19,8,0)),Matrix.Identity(4))
mesh=bs.build(p)
assert bs.guard.placement_error(c,mesh.vertices,mesh.faces,world,'ROOM'),'Walls must still block room placement'
bs.unregister()
print('PASS: room slab rests on floor, both drag directions, thick slabs, raised/rotated plane, actual placement and wall collision')
