# SPDX-License-Identifier: GPL-3.0-or-later
"""Dragging from a lower floor to a landing sets run/rise without numeric fields."""
import sys, math
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
c.scene.bs.surfaces=False; c.scene.bs.object_snap=False
with bs.guard.transaction(c):
    floor=bs.create(c,'FLOOR'); floor.bs.width=20; floor.bs.depth=20; floor.location=(-5,-10,0)
    c.scene.cursor.location=(6,-2,2.75); landing=bs.create(c,'FLOOR'); landing.bs.width=4; landing.bs.depth=4
c.view_layer.update()
a=Vector((0,0,0)); b=Vector((6,0,2.75))
for kind in ('STAIRS','RAMP'):
    for start,end in ((a,b),(b,a)):
        p=drawing.parameters(c,kind,'stairs_1' if kind=='STAIRS' else 'ramp')
        op=SimpleNamespace(params=p,default=SimpleNamespace(**vars(p)),place_only=False,frame=Matrix.Identity(4),front=False,
                           start=Vector(),end=Vector(),previous=None,cut_target=None)
        def preview(context): op.matrix=drawing.layout(op.params,op.start,op.end,op.frame,op.front)
        op.update_preview=preview; op.move=lambda ctx,event:drawing.BS_OT_draw.move(op,ctx,event)
        event=SimpleNamespace(ctrl=False,shift=False,mouse_x=0,mouse_y=0)
        with patch.object(drawing,'ray',return_value=(start+Vector((0,0,5)),Vector((0,0,-1)))):
            drawing.BS_OT_draw.begin(op,c,event)
        with patch.object(drawing,'ray',return_value=(end+Vector((0,0,5)),Vector((0,0,-1)))):
            drawing.BS_OT_draw.move(op,c,event)
        assert op.access_target==landing,'The upper support must be used in both drag directions'
        assert abs(p.width-6)<1e-5 and abs(p.height-2.75)<1e-5,(kind,start,end,p)
        assert (op.matrix@Vector((p.width,p.depth/2,p.height))-b).length<1e-5
        assert (op.matrix@Vector((0,p.depth/2,0))-a).length<1e-5
        mesh=bs.build(p)
        assert not bs.guard.placement_error(c,mesh.vertices,mesh.faces,op.matrix,kind)
        if kind=='STAIRS':
            steps=math.ceil(p.height/p.max_step)
            assert abs(max(v[2] for v in mesh.vertices)-2.75)<1e-5 and p.height/steps<=c.scene.bs.max_step+1e-5
        # Shift preserves the measured rise while constraining the horizontal direction.
        event.shift=True
        with patch.object(drawing,'ray',return_value=(end+Vector((0,0,5)),Vector((0,0,-1)))):
            drawing.BS_OT_draw.move(op,c,event)
        assert abs(p.height-2.75)<1e-5
print('PASS: real surface picking, both drag directions, automatic height/run/steps, exact floor/landing contact and Shift')

# Pointing well inside the upper platform still ends at the approached edge, both ways.
for kind in ('STAIRS','RAMP'):
    inside=Vector((8,0,2.75))
    for start,end in ((a,inside),(inside,a)):
        p=drawing.parameters(c,kind,'stairs_1' if kind=='STAIRS' else 'ramp')
        op=SimpleNamespace(params=p,default=SimpleNamespace(**vars(p)),place_only=False,frame=Matrix.Identity(4),front=False,
                           start=Vector(),end=Vector(),previous=None,cut_target=None)
        op.update_preview=lambda context:None
        op.move=lambda ctx,event:drawing.BS_OT_draw.move(op,ctx,event)
        event=SimpleNamespace(ctrl=False,shift=False,mouse_x=0,mouse_y=0)
        with patch.object(drawing,'ray',return_value=(start+Vector((0,0,5)),Vector((0,0,-1)))):
            drawing.BS_OT_draw.begin(op,c,event)
        with patch.object(drawing,'ray',return_value=(end+Vector((0,0,5)),Vector((0,0,-1)))):
            drawing.BS_OT_draw.move(op,c,event)
        matrix=drawing.layout(p,op.start,op.end,op.frame)
        assert abs(p.width-6)<1e-4 and abs(p.height-2.75)<1e-4
        mesh=bs.build(p)
        assert not bs.guard.placement_error(c,mesh.vertices,mesh.faces,matrix,kind)
print('PASS: interior landing clicks stop at the approached edge, in both drag directions')

# Oriented runs remain centered and land at their endpoint; module stamps stay centered too.
for angle in (0,.4,math.pi/2,-2.1):
    p=drawing.parameters(c,'STAIRS','stairs_1')
    low=Vector((3,-7,2)); high=low+Vector((6*math.cos(angle),6*math.sin(angle),3.17))
    matrix=drawing.layout(p,low,high,Matrix.Identity(4))
    assert (matrix@Vector((p.width,p.depth/2,p.height))-high).length<1e-5
    assert abs(p.height-3.17)<1e-5
p=drawing.parameters(c,'STAIRS','stairs_1')
op=SimpleNamespace(params=p,start=Vector((-p.width/2,-p.depth/2,0)),end=Vector((p.width/2,-p.depth/2,0)),
                   frame=Matrix.Identity(4),front=False,place_only=True,turn=0)
pose=drawing.BS_OT_draw.pose(op)
assert (pose@Vector((p.width/2,p.depth/2,0))).length<1e-5
# Pixel-sized yaw and oblique approaches still meet the landing without disabling collision checks.
for kind in ('STAIRS','RAMP'):
    p=drawing.parameters(c,kind,'stairs_1' if kind=='STAIRS' else 'ramp')
    for y in (.02,.8,-1.2):
        high=Vector((6,y,2.75)); matrix=drawing.layout(p,a,high,Matrix.Identity(4))
        raw=bs.build(p)
        assert bs.guard.placement_error(c,raw.vertices,raw.faces,matrix,kind)
        trimmed=drawing.fit_landing(c,raw,matrix,landing)
        assert not bs.guard.placement_error(c,trimmed.vertices,trimmed.faces,matrix,kind)
        assert not any(o.get('bs_guard_temp') for o in c.scene.objects),'Preview helper leaked'
# The trim preserves blocking geometry between the two endpoints.
with bs.guard.transaction(c):
    c.scene.cursor.location=(2,-.2,0); obstacle=bs.create(c,'BLOCK')
    obstacle.bs.width=.5; obstacle.bs.depth=.4; obstacle.bs.height=.5
p=drawing.parameters(c,'STAIRS','stairs_1'); matrix=drawing.layout(p,a,Vector((6,.02,2.75)),Matrix.Identity(4))
trimmed=drawing.fit_landing(c,bs.build(p),matrix,landing)
assert bs.guard.placement_error(c,trimmed.vertices,trimmed.faces,matrix,'STAIRS')
print('PASS: automatic landing trim for pixel yaw and oblique stairs/ramps; third-object collision still blocks')

# A placed parametric module keeps the same trim when exported without its landing selected.
bpy.data.objects.remove(obstacle,do_unlink=True); c.view_layer.update(); bs.guard.flush()
with bs.guard.transaction(c):
    source=bs.create(c,'STAIRS')
    bs.BUSY=True
    try:
        for key in ('width','depth','height','max_step'): setattr(source.bs,key,getattr(p,key))
    finally: bs.BUSY=False
    bs.rebuild(source,True); source.matrix_world=matrix
    drawing.landing_modifier(source,landing)
assert not bs.guard.audit(c.scene)
import tempfile
folder=Path(tempfile.mkdtemp(prefix='blocksmith-access-'))
for selected in c.selected_objects: selected.select_set(False)
source.select_set(True); c.view_layer.objects.active=source
c.scene.bs.export_scope='SELECTED'; c.scene.bs.export_path=str(folder)
assert bpy.ops.blocksmith.export()=={'FINISHED'} and (folder/'blockout.glb').stat().st_size>100
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'stairs.blend'))
bs.unregister(); bs.register()
assert source.bs.kind=='STAIRS' and source.modifiers['BS_Landing'].object==landing
assert not bs.guard.audit(c.scene)
print('PASS: parametric landing trim survives GLB export, saved .blend and addon reload')

bs.unregister()
print('PASS: oblique/rotated runs, off-grid landing height and unchanged stamp pivot')
