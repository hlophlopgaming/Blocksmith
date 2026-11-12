# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared placement keeps floor thickness and centered shapes outside their support."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector,Matrix
import blocksmith as bs
from blocksmith import drawing
bs.register();c=bpy.context
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
with bs.guard.transaction(c):
 floor=bs.create(c,'FLOOR');floor.bs.width=floor.bs.depth=5;floor.location=(20,0,0)
 c.scene.cursor.location=(30,0,0);wall=bs.create(c,'WALL');wall.bs.width=4;wall.bs.depth=.2;wall.bs.height=4
c.view_layer.update()
def preview(kind,frame,front,end,target,normal):
 op=SimpleNamespace(params=drawing.parameters(c,kind),start=Vector(),end=Vector(end),frame=frame,front=front,turn=0,place_only=False,
                    previous=None,cut_target=None,access_target=None,support_target=target,support_normal=Vector(normal))
 op.pose=lambda:drawing.BS_OT_draw.pose(op)
 with patch.object(drawing.gpu.shader,'from_builtin',return_value=object()),patch.object(drawing,'batch_for_shader',return_value=object()):
  drawing.BS_OT_draw.update_preview(op,c)
 assert not op.error,op.error
 return op
op=preview('FLOOR',Matrix.Translation((21,1,0)),False,(2,2,0),floor,(0,0,1))
assert abs(op.matrix.translation.z-op.params.height)<1e-5 and op.clip_target is None
frame=Matrix.Diagonal((-1,-1,1,1));frame.translation=(32,0,0)
op=preview('CYLINDER',frame,True,(1,0,2),wall,(0,-1,0))
mesh=bs.build(op.params);points=[op.matrix@Vector(v) for v in mesh.vertices]
assert abs(max(v.y for v in points))<1e-5
assert abs(min(v.x for v in points)-31)<1e-5 and abs(max(v.x for v in points)-32)<1e-5
bs.unregister();print('PASS: floor stacks without burying itself; column keeps full shape and exact support contact')
