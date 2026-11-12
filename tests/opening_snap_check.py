# SPDX-License-Identifier: GPL-3.0-or-later
"""All shapes can start on an evaluated cut sill whose elevation is off the grid."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector,Matrix
import blocksmith as bs
from blocksmith import drawing,openings
bs.register();c=bpy.context
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
with bs.guard.transaction(c):
 room=bs.create(c,'ROOM');room.bs.width=7;room.bs.depth=12.5;room.bs.height=3;room.location=(-4,-5.5,.2)
 frame=Matrix(((0,1,0,3),(-1,0,0,-5),(0,0,1,.234524),(0,0,0,1)))
 openings.apply_drawn(c,room,openings.drawn_mesh('WINDOW',Vector((-10,0,0)),Vector((0,0,2.5)),.2),frame)
c.view_layer.update();sill=.234524
# A view from outside: the ray falls just inside the opening; the visible cut edge is within 12 px.
region=SimpleNamespace(type='WINDOW',x=0,y=0)
ctx=SimpleNamespace(scene=c.scene,visible_objects=c.visible_objects,area=SimpleNamespace(regions=[region]),
 space_data=SimpleNamespace(region_3d=None),evaluated_depsgraph_get=c.evaluated_depsgraph_get)
event=SimpleNamespace(mouse_x=0,mouse_y=round((sill+.01)*100),ctrl=False)
with patch.object(drawing,'ray',return_value=(Vector((6,0,sill+.01)),Vector((-1,0,0)))),patch.object(drawing.view3d_utils,'location_3d_to_region_2d',side_effect=lambda r,rv,v:Vector((v.y*100,v.z*100))):
 frame,front,owner=drawing.surface_hit(ctx,event)
 assert abs(frame.translation.z-sill)<1e-5,('Sill missed by shared surface picker',tuple(frame.translation))
 assert owner==room
# Every generated shape enters through this picker; no per-shape grid fallback may lose the sill.
for kind in bs.SHAPES:
    p=drawing.parameters(c,kind)
    op=SimpleNamespace(params=p,default=SimpleNamespace(**vars(p)),place_only=False,previous=None,
        frame=Matrix.Identity(4),front=False,start=Vector(),end=Vector(),cut_target=None,
        support_target=None,support_normal=Vector((0,0,1)))
    op.update_preview=lambda context:None
    op.move=lambda context,event:drawing.BS_OT_draw.move(op,context,event)
    event.shift=False
    with patch.object(drawing,'ray',return_value=(Vector((6,0,sill+.01)),Vector((-1,0,0)))),patch.object(drawing.view3d_utils,'location_3d_to_region_2d',side_effect=lambda r,rv,v:Vector((v.y*100,v.z*100))):
        drawing.BS_OT_draw.begin(op,ctx,event)
    assert op.phase=='BASE' and abs(op.frame.translation.z-sill)<1e-5,(kind,tuple(op.frame.translation))
    if kind in {'DOOR','WINDOW','ARCH'}:assert abs(op.cut_depth-.2)<.001,(kind,op.cut_depth)
print('PASS: all',len(bs.SHAPES),'shape tools share the evaluated off-grid edge anchor')
# A single wall has no rear surface: an empty ray through the hole must still find its visible edge.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
with bs.guard.transaction(c):
    wall=bs.create(c,'WALL');wall.bs.width=4;wall.bs.depth=.2;wall.bs.height=3
    openings.apply_drawn(c,wall,openings.drawn_mesh('WINDOW',Vector((-3,0,sill)),Vector((-1,0,sill+2)),.2),Matrix.Diagonal((-1,-1,1,1)))
c.view_layer.update();ctx.visible_objects=c.visible_objects;event.mouse_x=200
with patch.object(drawing,'ray',return_value=(Vector((2,-3,sill+.01)),Vector((0,1,0)))),patch.object(drawing.view3d_utils,'location_3d_to_region_2d',side_effect=lambda r,rv,v:Vector((v.x*100,v.z*100))):
    target=drawing.surface_hit(ctx,event)
    assert target is not None and target[2]==wall and abs(target[0].translation.z-sill)<1e-5
print('PASS: empty ray through a standalone opening still snaps to the visible cut edge')
bs.unregister();print('PASS: evaluated Boolean sill snapped exactly off-grid for shared shape placement')
