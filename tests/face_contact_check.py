# SPDX-License-Identifier: GPL-3.0-or-later
"""Screenshot regression: a stair as wide as its landing must fit both edge corners."""
import sys, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Vector
import blocksmith as bs
from blocksmith.editing import attach
bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
with bs.guard.transaction(c):
    tower=bs.create(c,'BLOCK'); tower.bs.width=4.5; tower.bs.depth=1.5; tower.bs.height=8.5; tower.location=(-6.5,5.5,0)
    stair=bs.create(c,'STAIRS'); stair.bs.width=stair.bs.depth=1.5; stair.bs.height=3.1654434204101562
    stair.matrix_world=Matrix.Translation((-.5,6.75,5.334556579589844))@Matrix.Rotation(math.pi,4,'Z')
c.view_layer.update()
attach(c,stair,tower,'X',1); c.view_layer.update()
ys=[v.y for v in bs.bounds(stair)]
assert abs(min(ys)-5.5)<1e-5 and abs(max(ys)-7)<1e-5,('One corner still overhangs',min(ys),max(ys))
assert abs(min(v.x for v in bs.bounds(stair))+2)<1e-5
assert not bs.guard.audit(c.scene)
from blocksmith import drawing
lower=Vector((-.5,6,5.334556579589844)); upper=Vector((-2,6,8.5))
for kind in ('STAIRS','RAMP'):
    low,high,width=drawing.landing_points(c,tower,lower,upper,1.5)
    assert abs(low.y-6.25)<1e-5 and abs(high.y-6.25)<1e-5 and abs(width-1.5)<1e-5
    p=drawing.parameters(c,kind); p.depth=width
    matrix=drawing.layout(p,low,high,Matrix.Identity(4))
    shape=bs.build(p)
    top=[matrix@Vector((p.width,y,p.height)) for y in (0,p.depth)]
    assert all(abs(v.x+2)<1e-5 and 5.5-1e-5<=v.y<=7+1e-5 for v in top)
tri=tower.modifiers.new('Triangulated surface','TRIANGULATE'); c.view_layer.update()
low,high,width=drawing.landing_points(c,tower,lower,upper,1.5)
assert abs(width-1.5)<1e-5 and abs(high.y-6.25)<1e-5
# A narrower target automatically limits the new stair width, preserving both supporting corners.
with bs.guard.transaction(c):
    stair.location.x+=5
    tower.bs.depth=1
low,high,width=drawing.landing_points(c,tower,lower,upper,1.5)
assert abs(width-1)<1e-5 and abs(high.y-6)<1e-5
bs.unregister(); print('PASS: actual screenshot dimensions; both upper corners fit without changing stair dimensions')
