# SPDX-License-Identifier: GPL-3.0-or-later
"""Draft geometry, surface orientation and the same collision rules used by the CLI."""
import sys, math
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Vector
import blocksmith as bs
from blocksmith.drawing import parameters, layout, surface_frame, select_preset
from blocksmith.collision import Solid, overlaps

bs.register()
c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
s=c.scene.bs
for normal in [(0,0,1),(0,-1,0),(1,0,0),(.5,0,.866)]:
    frame,front=surface_frame(Vector(normal))
    assert frame.determinant()>.999
    p=parameters(c,'LADDER' if front else 'FLOOR','ladder' if front else 'floor_4')
    matrix=layout(p,Vector((0,0,0)),Vector((-2,0,3)) if front else Vector((-4,-3,0)),frame,front)
    mesh=bs.build(p); solid=Solid([matrix@Vector(v) for v in mesh.vertices],mesh.faces)
    assert solid is not None
    if front:
        assert abs(p.width-2)<1e-5 and abs(p.height-3)<1e-5 and abs(p.depth-.12)<1e-5
        assert (matrix.col[2].xyz-Vector((0,0,1))).length<1e-4
print('PASS: oriented surface frames and ladder/floor gestures preserve positive transforms')
for angle in [-135,-90,-45,0,45,90,135]:
    a=math.radians(angle); cut=.2*math.tan(a/2)
    p=parameters(c,'WALL','wall_4'); p.miter_end=-cut
    q=parameters(c,'WALL','wall_4'); q.miter_start=cut
    first=bs.build(p); second=bs.build(q)
    world=Matrix.Translation((4,0,0))@Matrix.Rotation(a,4,'Z')
    left=Solid(first.vertices,first.faces)
    right=Solid([world@Vector(v) for v in second.vertices],second.faces)
    assert not overlaps(left,right,c.scene),angle
    ends=[Vector((4,0,0)),Vector((4-cut,.2,0))]
    starts=[world@Vector((0,0,0)),world@Vector((cut,.2,0))]
    assert all((x-y).length<1e-5 for x,y in zip(ends,starts)),angle
print('PASS: both corner directions and oblique joins meet without volume overlap')
with bs.guard.transaction(c):
    left=bs.create(c,'WALL'); left.bs.width=4; left.bs.miter_end=-.2; left.location=(0,0,0)
    right=bs.create(c,'WALL'); right.bs.width=4; right.bs.miter_start=.2
    right.matrix_world=Matrix.Translation((4,0,0))@Matrix.Rotation(math.pi/2,4,'Z')
assert not bs.guard.audit(c.scene)
bpy.ops.blocksmith.opening(variant='DOOR')
assert right.bs.opening=='DOOR' and not bs.guard.audit(c.scene)
print('PASS: a joined wall remains editable as a doorway')
select_preset(s,'room_6')
assert s.shape=='ROOM' and s.draw_width==6 and s.draw_depth==6 and s.draw_height==3
s.shape='STAIRS'
assert s.preset=='stairs_1' and s.draw_height==1
p=parameters(c,'ROOM','room_6'); result=bs.build(p)
assert min(v[2] for v in result.vertices)<0 and max(v[2] for v in result.vertices)==3
# Invalid drafts must be red before placement; ordinary geometry is not an obstacle.
p=parameters(c,'BLOCK'); result=bs.build(p)
assert bs.guard.placement_error(c,result.vertices,result.faces,Matrix.Identity(4),'BLOCK')
bpy.ops.mesh.primitive_cube_add(location=(20,20,0))
assert not bs.guard.placement_error(c,result.vertices,result.faces,Matrix.Translation((20,20,0)),'BLOCK')
bs.unregister()
print('PASS: presets, complete room, collision preview and ordinary-model scope')
# Re-register to verify metric callbacks also survive addon reload.
bs.register()
from blocksmith.editing import metric_issues, reach
c.scene.cursor.location=(40,0,0)
player=bs.create(c,'PLAYER'); c.scene.bs.player_height=2.1; c.scene.bs.player_radius=.4
assert abs(player.bs.height-2.1)<1e-5 and abs(player.bs.width-.8)<1e-5
c.scene.cursor.location=(44,0,0)
ruler=bs.create(c,'JUMP_RULER'); c.scene.bs.jump_gap=4
assert abs(max(v.co.x for v in ruler.data.vertices)-4.02)<1e-4
p=parameters(c,'DOOR','door'); p.open_height=1.5
assert any('рост' in msg for msg in metric_issues(p,c.scene.bs))
c.scene.cursor.location=(50,0,0)
floor=bs.create(c,'FLOOR'); floor.bs.width=6; floor.bs.depth=6
with bs.guard.transaction(c):
    ledge=bs.create(c,'BLOCK'); ledge.location=(51,1,0); ledge.bs.width=1; ledge.bs.depth=1; ledge.bs.height=.5
c.view_layer.update()
base,top,height,_,_=reach(c,ledge)
assert abs(base)<1e-4 and abs(height-.5)<1e-4,(base,top,height)
# Shortening a mitered wall must clamp before its far face can reverse.
c.scene.cursor.location=(60,0,0)
joined=bs.create(c,'WALL')
with bs.guard.transaction(c): joined.bs.miter_start=.2; joined.bs.miter_end=-.2
joined.bs.width=.1
assert joined.bs.width>.4 and not bs.guard.audit(c.scene)
bpy.ops.blocksmith.opening(variant='DOOR')
joined.bs.width=.1
assert joined.bs.width>joined.bs.open_width+.4 and not bs.guard.audit(c.scene)
bs.unregister()
print('PASS: live reference metrics, clearance hints, supporting-surface height and minimum joined-wall length')
