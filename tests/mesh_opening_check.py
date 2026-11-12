# SPDX-License-Identifier: GPL-3.0-or-later
"""Openings preserve arbitrary source meshes and remain editable, exportable and guarded."""
import sys, math, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector, Matrix
import blocksmith as bs
from blocksmith.openings import modifier

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1)
obj=c.active_object; obj.data.transform(Matrix.Diagonal((6,.6,4,1)))
obj.matrix_world=Matrix.Translation((4,-2,1))@Matrix.Rotation(.4,4,'Z')@Matrix.Diagonal((1.2,.8,1.1,1))
original=bs.signature(obj.data); transform=obj.matrix_world.copy()

def hit(x,z):
    c.view_layer.update()
    evaluated=obj.evaluated_get(c.evaluated_depsgraph_get())
    return evaluated.ray_cast(Vector((x,-2,z)),Vector((0,1,0)))[0]

for variant in ('DOOR','WINDOW','ARCH','ARCH_WINDOW','NONE'):
    assert bpy.ops.blocksmith.opening(variant=variant)=={'FINISHED'}
    assert bs.signature(obj.data)==original and obj.matrix_world==transform
    assert not obj.bs.enabled and obj.type=='MESH'
    if variant=='NONE': assert hit(0,-.5)
    else:
        assert not hit(0,-.5),variant
        assert hit(2.9,0),variant
        assert hit(0,1.99),'Lintel disappeared'
        assert hit(0,-1.9)==(variant in {'WINDOW','ARCH_WINDOW'}),variant
        if 'ARCH' in variant:
            top=-2+(obj.bs.sill if variant=='ARCH_WINDOW' else 0)+obj.bs.open_height
            assert not hit(0,top-.05) and hit(obj.bs.open_width*.49,top-.05),variant
    assert modifier(obj).object.parent==obj and modifier(obj).object.hide_render
print('PASS: all five variants on an ordinary rotated/scaled mesh; untouched source, through-cuts, sills and arch profiles')

bpy.ops.blocksmith.opening(variant='WINDOW')
obj.bs.open_width=1.5; obj.bs.open_height=1; obj.bs.sill=.5; obj.bs.offset=.7
assert not hit(.7,-1) and hit(-.7,-1)
obj.bs.count=2; obj.bs.offset=0
assert hit(0,-1) and not hit(-1.25,-1) and not hit(1.25,-1)
assert bs.signature(obj.data)==original
cutter=modifier(obj).object
assert bs.guard.excluded(cutter,c.scene,include_water=True)
# Copies must not edit the original opening when their parameters change.
copy=obj.copy(); copy.data=obj.data.copy(); c.collection.objects.link(copy); copy.location.x+=20
copy.bs.open_width=.5; c.view_layer.update()
assert modifier(copy).object!=cutter and modifier(copy).object.parent==copy
assert abs(obj.bs.open_width-1.5)<1e-5
print('PASS: live width/height/sill/offset/count and private cutters on duplicates')

# Z-directed cuts work on slabs; the automatic axis chooses the thin dimension.
c.scene.cursor.location=(40,0,0); floor=bs.create(c,'FLOOR'); floor.bs.width=6; floor.bs.depth=4
c.view_layer.update(); stamp=bs.signature(floor.data)
assert bpy.ops.blocksmith.opening(variant='WINDOW')=={'FINISHED'}
assert floor.bs.kind=='FLOOR' and floor.bs.cut_axis=='Z' and bs.signature(floor.data)==stamp
c.view_layer.update(); evaluated=floor.evaluated_get(c.evaluated_depsgraph_get())
assert not evaluated.ray_cast(Vector((3,1.4,2)),Vector((0,0,-1)))[0]
assert evaluated.ray_cast(Vector((.1,.1,2)),Vector((0,0,-1)))[0]
assert not bs.guard.audit(c.scene)

# An ordinary curved mesh with an existing modifier also keeps its original vertices.
bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=2,location=(80,0,2))
sphere=c.active_object; raw=bs.signature(sphere.data)
sub=sphere.modifiers.new('Existing subdivision','SUBSURF'); sub.levels=1
assert bpy.ops.blocksmith.opening(variant='ARCH_WINDOW')=={'FINISHED'}
sphere.bs.cut_axis='Y'; c.view_layer.update()
evaluated=sphere.evaluated_get(c.evaluated_depsgraph_get())
assert not evaluated.ray_cast(Vector((0,-3,-.5)),Vector((0,1,0)))[0]
assert evaluated.ray_cast(Vector((1.5,-3,-.5)),Vector((0,1,0)))[0]
assert bs.signature(sphere.data)==raw and sphere.modifiers.get(sub.name)==sub
print('PASS: curved ordinary mesh with an existing subdivision modifier')

# Hand edits stay intact; closing cannot fill space occupied by a protected block.
c.scene.cursor.location=(60,0,0); obj=bs.create(c,'WALL'); obj.bs.width=6; obj.bs.depth=.5; obj.bs.height=4
obj.data.vertices[0].co.x+=.05; c.view_layer.update(); bs.guard.flush()
stamp=bs.signature(obj.data)
assert bpy.ops.blocksmith.opening(variant='DOOR')=={'FINISHED'}
assert bs.signature(obj.data)==stamp and bs.manual(obj)
with bs.guard.transaction(c):
    c.scene.cursor.location=(62.8,.1,.1); blocker=bs.create(c,'BLOCK')
    blocker.bs.width=.2; blocker.bs.depth=.2; blocker.bs.height=.3
obj.select_set(True); c.view_layer.objects.active=obj
before=bs.signature(modifier(obj).object.data)
assert bpy.ops.blocksmith.opening(variant='NONE')=={'CANCELLED'}
assert obj.bs.opening=='DOOR' and bs.signature(modifier(obj).object.data)==before
assert not bs.guard.audit(c.scene)
print('PASS: slab cuts, hand-edited walls and collision-safe closing rollback')

# Export uses the evaluated hole and excludes its helper; save/re-register keeps controls.
for o in c.selected_objects: o.select_set(False)
obj.select_set(True); c.view_layer.objects.active=obj
folder=Path(tempfile.mkdtemp(prefix='blocksmith-mesh-opening-'))
c.scene.bs.export_scope='SELECTED'; c.scene.bs.export_path=str(folder)
assert bpy.ops.blocksmith.export()=={'FINISHED'}
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'openings.blend'))
bs.unregister(); bs.register()
assert modifier(obj) and obj.bs.opening=='DOOR' and bs.signature(obj.data)==stamp
bs.unregister()
print('PASS: GLB export, saved controls and addon reload')
