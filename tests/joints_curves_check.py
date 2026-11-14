# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Blender geometry: wall ends, native editable curves, rollback and export."""
import math, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Vector
import blocksmith as bs
from blocksmith.drawing import parameters
from blocksmith.joints import plan, apply
from blocksmith.curves import create, arc_points
from blocksmith.collision import Solid, overlaps

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False); bs.guard.reload_state(); bs.guard.flush()

def solid(p,matrix):
    mesh=bs.build(p)
    return Solid([matrix@Vector(v) for v in mesh.vertices],mesh.faces)

for angle in (-135,-90,-45,45,90,135):
    for depth in (.1,.2,.6):
        for reverse in (False,True):
            p=parameters(c,'WALL','wall_4'); q=parameters(c,'WALL','wall_4'); q.depth=depth
            a=Matrix.Identity(4); b=Matrix.Translation((4,0,0))@Matrix.Rotation(math.radians(angle),4,'Z')
            if reverse: b=b@Matrix.Translation((q.width,q.depth,0))@Matrix.Rotation(math.pi,4,'Z')
            (p,a),(q,b)=plan(p,a,q,b)
            assert not overlaps(solid(p,a),solid(q,b),c.scene),(angle,depth,reverse)
            left=[a@Vector(v) for v in bs.build(p).vertices]
            right=[b@Vector(v) for v in bs.build(q).vertices]
            assert sum(any((v-w).length<1e-4 for w in right) for v in left)>=4,(angle,depth,reverse)
print('PASS: miter corners both directions, unequal thickness and reversed endpoints')

for mode in ('BUTT','TRIM'):
    for angle in (45,90,135):
        p=parameters(c,'WALL','wall_4'); q=parameters(c,'WALL','wall_4')
        b=Matrix.Translation((2,-3,0))@Matrix.Rotation(math.radians(angle),4,'Z')
        # Aim a sufficiently long branch into the main wall; the outer end remains fixed.
        q.width=4
        if angle!=90: b.translation=Vector((2,0,0))-b.col[0].xyz*3
        old=b@Vector((0,0,0))
        (p,a),(q,b)=plan(p,Matrix.Identity(4),q,b,mode)
        assert not overlaps(solid(p,a),solid(q,b),c.scene),(mode,angle)
        assert (b@Vector((0,0,0))-old).length<1e-5
        if mode=='TRIM': assert p.width==4
print('PASS: butt and T junctions trim the branch to a face, preserve the other end')

with bs.guard.transaction(c):
    a=bs.create(c,'WALL'); a.bs.width=4; a.bs.depth=.2
    b=bs.create(c,'WALL'); b.bs.width=4; b.bs.depth=.4
    b.matrix_world=Matrix.Translation((4,0,0))@Matrix.Rotation(math.pi/2,4,'Z')
    for obj,(p,matrix) in zip((a,b),plan(a.bs,a.matrix_world,b.bs,b.matrix_world)): apply(obj,p,matrix)
assert not bs.guard.audit(c.scene)
for o in c.selected_objects: o.select_set(False)
a.select_set(True); b.select_set(True); c.view_layer.objects.active=a
assert bpy.ops.blocksmith.join(mode='MITER')=={'FINISHED'}
bpy.ops.blocksmith.opening(variant='DOOR')
assert a.bs.opening=='DOOR' and not bs.guard.audit(c.scene)
print('PASS: join operator and subsequent opening edit')

c.scene.bs.draw_depth=.3; c.scene.bs.draw_height=3
for i,mode in enumerate(('POINTS','FREEHAND','ARC')):
    obj=create(c,[(0,0,0),(2,1,0),(4,0,0)],mode,Matrix.Translation((20+i*10,0,0)))
    assert obj.type=='CURVE' and obj.data.use_fill_caps and obj.data.bevel_object
    assert obj.data.splines[0].type==('POLY' if mode=='ARC' else 'BEZIER')
    c.view_layer.update(); evaluated=obj.evaluated_get(c.evaluated_depsgraph_get()); mesh=evaluated.to_mesh()
    try:
        shape=Solid([obj.matrix_world@v.co for v in mesh.vertices],[tuple(f.vertices) for f in mesh.polygons])
        assert abs(min(v.co.z for v in mesh.vertices))<1e-5
        assert abs(max(v.co.z for v in mesh.vertices)-3)<1e-5
    finally: evaluated.to_mesh_clear()
    assert not bs.guard.audit(c.scene)
    obj.bs.height=4; obj.bs.depth=.4; c.view_layer.update()
    assert not bs.guard.audit(c.scene)
    assert abs(obj.dimensions.z-4)<1e-4
    print('PASS:',mode,'closed evaluated mesh, native handles, editable height/thickness')

# Native point editing must use the same protection as a mesh move.
curve=next(o for o in c.scene.objects if o.get('bs_curve_wall') and o.data.splines[0].type=='BEZIER'); old=curve.data.splines[0].bezier_points[0].co.copy()
curve.data.splines[0].bezier_points[0].co=(-20,0,0); c.view_layer.update()
assert not bs.guard.flush(),'Curve endpoint passed through an existing wall'
assert (curve.data.splines[0].bezier_points[0].co-old).length<1e-5
print('PASS: conflicting native point edit restored to a native curve')
for point in curve.data.splines[0].bezier_points: point.radius=0
c.view_layer.update()
assert not bs.guard.flush(),'Degenerate native curve radius accepted'
assert all(abs(point.radius-1)<1e-5 for point in curve.data.splines[0].bezier_points)
print('PASS: native radius changes restore even when control-point coordinates are unchanged')

profiles=sum('bs_curve_owner' in o for o in bpy.data.objects)
try: create(c,[(0,0,0),(2,1,0),(4,0,0)],'POINTS',Matrix.Translation((20,0,0)))
except bs.guard.ConstraintError: pass
else: raise AssertionError('Overlapping curve placement accepted')
assert sum('bs_curve_owner' in o for o in bpy.data.objects)==profiles
print('PASS: conflicting creation removes both curve and its hidden profile')

# A normal Shift+D copy must not resize its source through the bevel profile.
with bs.guard.transaction(c):
    copy=curve.copy(); copy.data=curve.data.copy(); c.scene.collection.objects.link(copy); copy.location.y+=15
copy.bs.height=5; c.view_layer.update()
assert abs(curve.dimensions.z-4)<1e-4 and abs(copy.dimensions.z-5)<1e-4
curve.bs.height=3; c.view_layer.update()
assert abs(copy.dimensions.z-5)<1e-4
print('PASS: duplicated curve profiles resize independently')

points=arc_points([(1,0,0),(0,1,0),(-1,0,0)])
assert all(abs(p.length-1)<1e-5 for p in points)
assert (points[0]-Vector((1,0,0))).length<1e-5 and (points[-1]-Vector((-1,0,0))).length<1e-5
try: arc_points([(0,0,0),(1,0,0),(2,0,0)])
except ValueError: pass
else: raise AssertionError('Collinear arc accepted')

folder=Path(tempfile.mkdtemp(prefix='blocksmith-070-'))
for o in c.selected_objects: o.select_set(False)
curve.select_set(True); c.view_layer.objects.active=curve
c.scene.bs.export_path=str(folder); c.scene.bs.export_scope='SELECTED'
assert bpy.ops.blocksmith.export()=={'FINISHED'}
assert (folder/'blockout.glb').stat().st_size>1000
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'curves.blend'))
bs.unregister(); bs.register(); assert bpy.data.objects.get(curve.name).type=='CURVE'
assert not bs.guard.audit(c.scene)
bs.unregister()
bpy.ops.wm.open_mainfile(filepath=str(folder/'curves.blend'))
bs.register(); c=bpy.context
assert len([o for o in c.scene.objects if o.get('bs_curve_wall')])==4
assert not bs.guard.audit(c.scene)
bs.unregister()
print('PASS: native curve GLB export, .blend save and addon re-registration',folder)
