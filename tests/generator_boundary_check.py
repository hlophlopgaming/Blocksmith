# SPDX-License-Identifier: GPL-3.0-or-later
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy,bmesh
import blocksmith as bs
from blocksmith.drawing import parameters
bs.register();out=[]
for preset in bs.PRESETS:
 try:
  p=parameters(bpy.context,preset[3],preset[0]);raw=bs.raw_build(p);clean=bs.build(p)
  mesh=bpy.data.meshes.new('audit');mesh.from_pydata(clean.vertices,[],clean.faces);mesh.update()
  assert all(abs(min(v[i] for v in raw.vertices)-min(v[i] for v in clean.vertices))<1e-5 and abs(max(v[i] for v in raw.vertices)-max(v[i] for v in clean.vertices))<1e-5 for i in range(3)),preset[0]
  bm=bmesh.new();bm.from_mesh(mesh)
  before=len(bm.verts);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
  bad=sum(not e.is_manifold for e in bm.edges)
  out.append(dict(preset=preset[0],raw_faces=len(raw.faces),faces=len(clean.faces),bad_edges_after_weld=bad,merged_vertices=before-len(bm.verts)))
  bm.free();bpy.data.meshes.remove(mesh)
 except Exception as e:out.append(dict(preset=preset[0],error=str(e)))
print('AUDIT',len(out),'presets;',sum(r.get('raw_faces',0) for r in out),'raw faces ->',sum(r.get('faces',0) for r in out),'boundary faces');Path('/tmp/blocksmith-generator-audit.json').write_text(json.dumps(out,indent=2))
assert not any(r.get('error') or r.get('bad_edges_after_weld') for r in out), 'Generator audit failed'
for kind in ('STAIRS','L_STAIRS','U_STAIRS','SPIRAL_STAIRS','CURVED_WALL'):
 for solid in (False,True):
  for angle in (90,180,360,540,720,1440):
   p=parameters(bpy.context,kind);p.solid=solid;p.angle=angle;p.height=2.37;p.max_step=.23
   clean=bs.build(p);mesh=bpy.data.meshes.new('variant');mesh.from_pydata(clean.vertices,[],clean.faces);mesh.update()
   bm=bmesh.new();bm.from_mesh(mesh)
   assert all(e.is_manifold for e in bm.edges) and bm.calc_volume()>0,(kind,solid,angle)
   bm.free();bpy.data.meshes.remove(mesh)
print('PASS: all presets retain bounds, welded boundaries, positive volume; solid/open stairs and partial/full curves')
bs.unregister()
