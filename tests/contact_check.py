# SPDX-License-Identifier: GPL-3.0-or-later
"""Off-grid draft endpoints and face contact use actual transformed geometry."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Vector
import blocksmith as bs
from blocksmith import drawing

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
with bs.guard.transaction(c):
    floor=bs.create(c,'FLOOR'); floor.bs.width=4.37; floor.bs.depth=4
c.view_layer.update()
region=SimpleNamespace(type='WINDOW',x=0,y=0)
context=SimpleNamespace(scene=c.scene,visible_objects=c.visible_objects,
    area=SimpleNamespace(regions=[region]),space_data=SimpleNamespace(region_3d=None),
    evaluated_depsgraph_get=c.evaluated_depsgraph_get)
p=Vector((4.37,2,0)); event=SimpleNamespace(mouse_x=437,mouse_y=200,ctrl=False,shift=False)
op=SimpleNamespace(frame=Matrix.Identity(4),front=False,start=Vector(),params=drawing.parameters(c,'FLOOR'),update_preview=lambda _:None)
with patch.object(drawing,'ray',side_effect=lambda ctx,e:(Vector((e.mouse_x/100,e.mouse_y/100,10)),Vector((0,0,-1)))), patch.object(drawing,'point_on_plane',return_value=p), patch.object(drawing.view3d_utils,'location_3d_to_region_2d',side_effect=lambda r,rv,v:Vector((v.x*100,v.y*100))):
    drawing.BS_OT_draw.move(op,context,event)
    assert (op.end-p).length<1e-5,('Off-grid floor edge missed',tuple(op.end),tuple(p))
    event.ctrl=True; drawing.BS_OT_draw.move(op,context,event)
    assert (op.end-p).length<1e-5
    event.ctrl=False; event.mouse_x=200; event.mouse_y=200
    with patch.object(drawing,'point_on_plane',return_value=Vector((2.12,2.13,0))):
        drawing.BS_OT_draw.move(op,context,event)
        assert (op.end-Vector((2,2,0))).length<1e-5
print('PASS: real drawing move snaps off-grid edges; Ctrl and grid fallback work')
# Same placement as the screenshot: a +90 degree wall sits 0.5 m outside the floor.
with bs.guard.transaction(c):
    c.scene.cursor.location=(-.5,0,0); wall=bs.create(c,'WALL')
    wall.bs.width=4; wall.bs.depth=.5; wall.rotation_euler.z=__import__('math').pi/2
c.view_layer.update()
for o in c.selected_objects: o.select_set(False)
wall.select_set(True); floor.select_set(True); c.view_layer.objects.active=floor
assert bpy.ops.blocksmith.attach(axis='X',direction=-1)=={'FINISHED'}
c.view_layer.update()
assert abs(max(v.x for v in bs.bounds(wall)))<1e-5
assert abs(wall.bs.depth-.5)<1e-5 and not bs.guard.audit(c.scene)
print('PASS: rotated wall contacts floor without changing geometry or relaxing collision checks')
# A wall crossing the draft plane supplies exact intersection points, even without vertices there.
with bs.guard.transaction(c): wall.location.z=-1
c.view_layer.update()
context.visible_objects=[wall]
p=Vector((0,0,0)); event.mouse_x=event.mouse_y=0
with patch.object(drawing,'ray',side_effect=lambda ctx,e:(Vector((e.mouse_x/100,e.mouse_y/100,10)),Vector((0,0,-1)))), patch.object(drawing,'point_on_plane',return_value=p), patch.object(drawing.view3d_utils,'location_3d_to_region_2d',side_effect=lambda r,rv,v:Vector((v.x*100,v.y*100))):
    drawing.BS_OT_draw.move(op,context,event)
    assert op.end.length<1e-5

# Each external face works in a rotated, scaled, shifted-pivot target frame.
from blocksmith.editing import attach
from math import radians
for axis in 'XYZ':
    for direction in (-1,1):
        bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
        bs.guard.reload_state()
        with bs.guard.transaction(c):
            c.scene.cursor.location=(0,0,0); target=bs.create(c,'FLOOR')
            target.bs.width=6; target.bs.depth=5; target.bs.height=.37
            target.matrix_world=Matrix.Translation((7,-3,2))@Matrix.Rotation(radians(37),4,'Z')@Matrix.Diagonal((1.2,.8,1.5,1))
            c.view_layer.update(); bs.set_pivot(target,target.matrix_world@Vector((2,1,0)))
            c.scene.cursor.location=(30,30,10); source=bs.create(c,'BLOCK')
            source.bs.width=source.bs.depth=source.bs.height=.2
            source.rotation_euler.z=radians(-23)
        c.view_layer.update()
        # Parent transform must not turn a world move into a local move.
        parent=bpy.data.objects.new('Parent',None); c.collection.objects.link(parent)
        parent.matrix_world=Matrix.Translation((1,2,0))@Matrix.Rotation(.3,4,'Z')
        world=source.matrix_world.copy(); source.parent=parent; source.matrix_world=world
        c.view_layer.update()
        original=source.matrix_world.to_3x3().copy()
        normal=target.matrix_world.to_3x3().inverted().transposed()@Vector(tuple(direction if a==axis else 0 for a in 'XYZ'))
        normal.normalize()
        attach(c,source,target,axis,direction); c.view_layer.update()
        assert source.matrix_world.to_3x3()==original
        left=min(normal.dot(v) for v in bs.bounds(source)); right=max(normal.dot(v) for v in bs.bounds(target))
        assert abs(left-right)<1e-5,(axis,direction,left,right)
        assert not bs.guard.audit(c.scene)
print('PASS: six faces, rotated/scaled targets, shifted pivots and parented source')

# Evaluated modifiers determine contact, not the original mesh or its object origin.
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False); bs.guard.reload_state()
with bs.guard.transaction(c):
    c.scene.cursor.location=(0,0,0); target=bs.create(c,'BLOCK'); target.bs.width=2
    c.scene.cursor.location=(10,0,0); source=bs.create(c,'BLOCK'); source.bs.width=1
    displace=target.modifiers.new('Move mesh','DISPLACE'); displace.direction='X'; displace.strength=-2; displace.mid_level=0
c.view_layer.update()
attach(c,source,target,'X',-1); c.view_layer.update()
assert abs(max(v.x for v in bs.bounds(source))+2)<1e-5

# A third module still blocks the move; both pieces keep their accepted transforms.
with bs.guard.transaction(c):
    c.scene.cursor.location=(5,0,0); obstacle=bs.create(c,'BLOCK')
    obstacle.bs.width=1; obstacle.bs.depth=2; obstacle.bs.height=2
    source.location=(10,0,0)
c.view_layer.update(); original=source.matrix_world.copy()
# The evaluated right target face is x=0; attached source would occupy x=0..1.
with bs.guard.transaction(c): obstacle.location.x=0
try: attach(c,source,target,'X',1)
except bs.guard.ConstraintError: pass
else: raise AssertionError('A third module did not block attachment')
c.view_layer.update()
assert (source.matrix_world.translation-original.translation).length<1e-5
assert not bs.guard.audit(c.scene)
print('PASS: evaluated modifiers and collision rollback')
bs.unregister()
