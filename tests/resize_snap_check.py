# SPDX-License-Identifier: GPL-3.0-or-later
"""A size handle must snap to an evaluated opening edge, not only the 0.5 m grid."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix,Vector
import blocksmith as bs
from blocksmith import drawing,openings,ui
bs.register();c=bpy.context
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sill=.234524
with bs.guard.transaction(c):
 room=bs.create(c,'ROOM');room.bs.width=7;room.bs.depth=12.5;room.bs.height=3;room.location=(-4,-5.5,.2)
 frame=Matrix(((0,1,0,3),(-1,0,0,-5),(0,0,1,sill),(0,0,0,1)))
 openings.apply_drawn(c,room,openings.drawn_mesh('WINDOW',Vector((-10,0,0)),Vector((0,0,2.5)),.2),frame)
 c.scene.cursor.location=(3,-5.5,0);block=bs.create(c,'BLOCK');block.bs.width=1;block.bs.depth=12.5;block.bs.height=.5
c.view_layer.update()
region=SimpleNamespace(type='WINDOW',x=0,y=0)
area=SimpleNamespace(regions=[region],header_text_set=lambda _:None,tag_redraw=lambda:None)
ctx=SimpleNamespace(scene=c.scene,view_layer=c.view_layer,active_object=block,visible_objects=c.visible_objects,
 area=area,region=region,space_data=SimpleNamespace(region_3d=None),window_manager=SimpleNamespace(modal_handler_add=lambda _:None),
 evaluated_depsgraph_get=c.evaluated_depsgraph_get)
op=SimpleNamespace(key='height',side=1)
projection=lambda r,rv,v:Vector((v.y*100,v.z*100))
with patch.object(ui.view3d_utils,'location_3d_to_region_2d',side_effect=projection):
 ui.BS_OT_resize.invoke(op,ctx,SimpleNamespace(mouse_x=0,mouse_y=50))
 with patch.object(drawing,'ray',return_value=(Vector((0,0,sill)),Vector((1,0,0)))):
  ui.BS_OT_resize.modal(op,ctx,SimpleNamespace(type='MOUSEMOVE',mouse_x=0,mouse_y=24,ctrl=False))
assert abs(block.bs.height-sill)<1e-5,('Handle missed sill',block.bs.height)
assert abs(min((block.matrix_world@v.co).z for v in block.data.vertices))<1e-5
c.scene.cursor.location=(20,0,0);curve=bs.create(c,'CURVED_WALL');curve.bs.angle=90;c.view_layer.update()
ctx.active_object=curve;ctx.visible_objects=c.visible_objects
curved=SimpleNamespace(key='width',side=1)
with patch.object(ui.view3d_utils,'location_3d_to_region_2d',side_effect=projection):
    ui.BS_OT_resize.invoke(curved,ctx,SimpleNamespace(mouse_x=0,mouse_y=0))
assert abs(curved.parameter_scale-.5)<1e-5,'Arc diameter must map to its actual face displacement'
bs.unregister();print('PASS: size handle snaps exactly to the cut sill and preserves its opposite face')
