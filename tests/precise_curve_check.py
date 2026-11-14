"""Exact curve segments on a supporting mesh and editable placed cutters."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix,Vector
import blocksmith as bs
from blocksmith import curves,openings
bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
floor=bs.create(c,'FLOOR'); floor.bs.width=10; floor.bs.depth=10
wall=curves.create(c,[(1,1,0),(5,1,0),(5,5,0)],'POLY')
assert wall.data.splines[0].type=='POLY'
assert [tuple(p.co)[:3] for p in wall.data.splines[0].points]==[(1,1,0),(5,1,0),(5,5,0)]
c.view_layer.update(); assert not bs.guard.audit(c.scene)
evaluated=wall.evaluated_get(c.evaluated_depsgraph_get()); mesh=evaluated.to_mesh()
try: assert abs(min((wall.matrix_world@v.co).z for v in mesh.vertices))<1e-5
finally: evaluated.to_mesh_clear()
try: curves.arc_points([(0,0,0),(1,0,0)])
except ValueError: pass
else: raise AssertionError('Incomplete arc accepted')
c.scene.cursor.location=(20,0,0); target=bs.create(c,'BLOCK')
shape=openings.drawn_mesh('DOOR',Vector((.5,0,0)),Vector((1.5,0,1.5)),2)
frame=Matrix.Translation((20,2,0))
with bs.guard.transaction(c): openings.apply_drawn(c,target,shape,frame)
cutter=next(m.object for m in target.modifiers if m.type=='BOOLEAN')
original=bs.signature(target.data)
cutter.location.x+=.25; cutter.scale.x=1.25
c.view_layer.update(); assert bs.guard.flush()
assert bs.signature(target.data)==original and cutter.parent==target
bs.unregister()
print('PASS: exact snapped-segment coordinates on a support; incomplete arcs rejected; placed opening moves/resizes without replacing target')
