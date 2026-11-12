# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression cases for actual operator and native-transform constraint paths."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Vector
import blocksmith as bs
from blocksmith import guard
from blocksmith.editing import resize

bs.register()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
c=bpy.context; c.view_layer.update(); guard.flush()

def cube(x,y,z=0,**sizes):
    c.scene.cursor.location=(x,y,z)
    with guard.transaction(c):
        o=bs.create(c,'BLOCK')
        for key,value in sizes.items(): setattr(o.bs,key,value)
    return o

a=cube(0,0); b=cube(3,0)
try: cube(0,0)
except guard.ConstraintError: pass
else: raise AssertionError('Duplicate placement was accepted')
assert len([o for o in c.scene.objects if o.type=='MESH'])==2
b.location.x=1; c.view_layer.update()
assert not guard.flush() and abs(b.location.x-3)<1e-6,'Native G was not rejected'
b.scale.x=-1; c.view_layer.update()
assert not guard.flush() and b.scale.x==1,'Negative scale accepted'
b.scale.z=0; c.view_layer.update()
assert not guard.flush() and b.scale.z==1,'Zero scale accepted'
# RNA update callbacks cannot leave conflicting parameters behind.
a.bs.width=4
assert a.bs.width==2,'Parameter growth was accepted'
try: resize(b,'width',4,side=-1)
except guard.ConstraintError: pass
else: raise AssertionError('Negative-face resize passed through neighbor')
assert b.bs.width==2 and abs(b.location.x-3)<1e-6
b.location.x=2; c.view_layer.update(); assert guard.flush(),'Touching faces rejected'
print('PASS: duplicate, native move/scale, parameter resize, anchoring; touching faces allowed')
try: cube(.5,.5,.5,width=.2,depth=.2,height=.2)
except guard.ConstraintError: pass
else: raise AssertionError('Full containment accepted')
with guard.transaction(c):
    wall=cube(0,10,width=4,depth=.2); wall.rotation_euler.z=.785398
with guard.transaction(c):
    wall2=cube(0,11,width=4,depth=.2); wall2.rotation_euler.z=.785398
assert guard.flush(),'Separated rotated walls rejected by AABB'
with guard.transaction(c):
    c.scene.cursor.location=(10,10,0); door=bs.create(c,'DOOR')
inside=cube(10.7,9.9,width=.4,depth=.4,height=1)
assert guard.flush(),'Object in door opening rejected'
print('PASS: containment detected; rotated separation and door clearance accepted')
original=bs.signature(b.data); material=b.data.materials[0]
bm=bmesh.new(); bm.from_mesh(b.data); bmesh.ops.reverse_faces(bm,faces=list(bm.faces)); bm.to_mesh(b.data); bm.free()
c.view_layer.update(); assert not guard.flush(),'Reversed normals accepted'
assert bs.signature(b.data)==original and b.data.materials[0]==material and b.data.uv_layers
print('PASS: flipped mesh normals restored with UVs and materials')
# Real boolean holes are tested with Blender Exact, rather than a convex hull.
with guard.transaction(c):
    outer=cube(20,0,width=4,depth=4,height=3)
    cutter=cube(21,1,-.1,width=2,depth=2,height=4)
    for o in c.selected_objects: o.select_set(False)
    outer.select_set(True); cutter.select_set(True); c.view_layer.objects.active=outer
    assert bpy.ops.blocksmith.tool(action='CUT')=={'FINISHED'}
hole=cube(21.5,1.5,width=.5,depth=.5,height=1)
assert guard.flush(),'Boolean hole treated as solid'
print('PASS: cutter exception and evaluated concave boolean opening')
# Hidden objects and parent transforms cannot bypass the same constraints.
b.hide_set(True); b.location.x=1; c.view_layer.update()
assert not guard.flush() and abs(b.location.x-2)<1e-6,'Hidden obstacle bypassed guard'
b.hide_set(False)
parent=bpy.data.objects.new('Parent',None); c.scene.collection.objects.link(parent); b.parent=parent
c.view_layer.update(); guard.flush()
parent.scale.x=-1; c.view_layer.update()
assert not guard.flush() and parent.scale.x==1 and b.scale.x>0,'Parent reflection bypassed guard'
# Baking a reference/volume preserves its semantic exemption, not its editable parameters.
c.scene.cursor.location=(.2,.2,1); water=bs.create(c,'WATER')
for o in c.selected_objects: o.select_set(False)
water.select_set(True); c.view_layer.objects.active=water
assert bpy.ops.blocksmith.tool(action='BAKE')=={'FINISHED'}
assert not water.bs.enabled and guard.excluded(water,c.scene)
# A conversion keeps the original as an excluded archive, without deleting the user's mesh.
bpy.ops.mesh.primitive_cube_add(size=2,location=(60,0,0)); original=c.active_object
assert bpy.ops.blocksmith.tool(action='CONVERT')=={'FINISHED'}
assert original.name in bpy.data.objects and original.hide_get() and guard.excluded(original,c.scene)
print('PASS: hidden meshes, parent reflection, baking volumes and keeping source archives')
guard.require_valid(c.scene)
print('PASS: strict export audit clean')
bs.unregister()
