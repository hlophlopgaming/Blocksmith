"""Native Blender checks for contour geometry, guard rollback, persistence and export."""
import json
import struct
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import blocksmith as bs
from blocksmith.outlines import create,contours

bs.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
outer=[(0,0),(7,0),(7,6),(4,6),(4,4),(0,4)]
hole=[(1,1),(3,1),(3,3),(1,3)]
floor=create(bpy.context,[outer,hole],height=.2)
floor.name='ContourFloor'
block=create(bpy.context,[[(10,0),(13,0),(13,2),(12,3),(10,2)]],kind='POLY_BLOCK',height=2)
block.name='ContourVolume'
frame=Matrix.Translation((17,0,0))@Matrix.Rotation(1.5707963267948966,4,'X')
profile=create(bpy.context,[[(0,0),(4,0),(4,3),(2,4),(0,3)]],kind='POLY_BLOCK',height=.4,frame=frame)
profile.name='VerticalProfile'
assert not bs.guard.audit(scene)
for obj in (floor,block,profile):
    assert obj.bs.enabled and not bs.manual(obj) and obj.get('bs_managed')
    bm=bmesh.new();bm.from_mesh(obj.data)
    assert bm.calc_volume(signed=True)>0
    assert all(e.is_manifold and e.is_contiguous for e in bm.edges)
    assert all(f.calc_area()>1e-10 for f in bm.faces)
    bm.free()
floor.bs.height=.35
assert min(v.co.z for v in floor.data.vertices)<-.3499
floor.bs.width=14
assert max(v.co.x for v in floor.data.vertices)>13.999
assert len(contours(floor))==2 and not bs.manual(floor)
floor.bs.width=7
snapshot=(floor.bs.contours,bs.signature(floor.data),floor.matrix_world.copy())
try:
    create(bpy.context,[outer],height=.35,frame=Matrix.Translation((10,0,1)),obj=floor)
except bs.guard.ConstraintError:pass
else:raise AssertionError('A contour edit overlapping another protected object was accepted')
assert (floor.bs.contours,bs.signature(floor.data))==snapshot[:2]
assert floor.matrix_world==snapshot[2]
assert not bs.guard.audit(scene)
scene.bs.export_path='/tmp/blocksmith-outline-check';scene.bs.filename='outlines';scene.bs.export_format='GLB'
Path(scene.bs.export_path).mkdir(exist_ok=True)
export=Path(scene.bs.export_path)/'outlines.glb'
if export.exists():export.unlink()
assert bpy.ops.blocksmith.export()=={'FINISHED'}
blob=export.read_bytes();length,kind=struct.unpack_from('<II',blob,12)
document=json.loads(blob[20:20+length])
assert {n['name'].removesuffix('-col') for n in document['nodes'] if 'mesh' in n}>={'ContourFloor','ContourVolume','VerticalProfile'}
saved='/tmp/blocksmith-outline-check/persistence.blend'
bpy.ops.wm.save_as_mainfile(filepath=saved)
bpy.ops.wm.open_mainfile(filepath=saved)
obj=bpy.data.objects['ContourFloor'];assert len(json.loads(obj.bs.contours))==2
obj.bs.height=.4;assert min(v.co.z for v in obj.data.vertices)<-.3999
assert not bs.manual(obj) and not bs.guard.audit(bpy.context.scene)
print('OUTLINE NATIVE CHECK PASSED: concavity, holes, vertical profiles, resize, rollback, GLB and reload',flush=True)
