# SPDX-License-Identifier: GPL-3.0-or-later
"""A staircase endpoint must not snap through the visible landing to a hidden mesh."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector, Matrix
import blocksmith as bs
from blocksmith import drawing
bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1)
front=c.active_object; front.name='Visible landing'
front.data.transform(Matrix.Translation((2,.5,2))@Matrix.Diagonal((4,1,4,1)))
bpy.ops.mesh.primitive_cube_add(size=1)
back=c.active_object; back.name='Hidden landing'
back.data.transform(Matrix.Translation((2.5,4.5,1.5))@Matrix.Diagonal((1,1,1,1)))
c.view_layer.update()
c.scene.bs.object_snap=True
region=SimpleNamespace(type='WINDOW',x=0,y=0)
ctx=SimpleNamespace(scene=c.scene,visible_objects=c.visible_objects,area=SimpleNamespace(regions=[region]),
 space_data=SimpleNamespace(region_3d=None),evaluated_depsgraph_get=c.evaluated_depsgraph_get)
event=SimpleNamespace(mouse_x=200,mouse_y=100,ctrl=False)
with patch.object(drawing,'ray',return_value=(Vector((2,-20,1)),Vector((0,1,0)))),patch.object(drawing.view3d_utils,'location_3d_to_region_2d',side_effect=lambda r,rv,v:Vector((v.x*100,v.z*100))):
 frame,_,target=drawing.surface_hit(ctx,event,force_surfaces=True,access=True)
 assert target==front and abs(frame.translation.y)<1e-5,('Snapped through visible landing',target.name,tuple(frame.translation))
# Clicking a visible side or underside resolves to the walkable top, never to that face's height.
c.scene.bs.object_snap=False
for eye,direction in ((Vector((2,-20,1)),Vector((0,1,0))),(Vector((2,.5,-1)),Vector((0,0,1)))):
    with patch.object(drawing,'ray',return_value=(eye,direction)):
        frame,_,target=drawing.surface_hit(c,event,force_surfaces=True,access=True)
        assert target==front and abs(frame.translation.z-4)<1e-5,tuple(frame.translation)
bs.unregister()
print('PASS: occluded vertices and edges cannot steal the landing endpoint')
