# SPDX-License-Identifier: GPL-3.0-or-later
"""Union generated solid pieces before previews, editing and export share the mesh."""
from functools import lru_cache
import bpy
import bmesh
from .geometry import Mesh


def clean(shape):
    roots=list(range(len(shape.vertices)))
    def root(i):
        while roots[i]!=i: roots[i]=roots[roots[i]]; i=roots[i]
        return i
    for face in shape.faces:
        for i in face[1:]: roots[root(i)]=root(face[0])
    if len({root(i) for face in shape.faces for i in face})<=1: return shape
    vertices,faces=union(tuple(shape.vertices),tuple(shape.faces))
    result=Mesh(); result.vertices=list(vertices); result.faces=list(faces)
    return result


@lru_cache(maxsize=128)
def union(vertices,faces):
    meshes=[]; objects=[]
    try:
        for name in ('__BS_union','__BS_union_operand'):
            mesh=bpy.data.meshes.new(name); meshes.append(mesh)
            mesh.from_pydata(vertices,[],faces); mesh.update()
            obj=bpy.data.objects.new(name,mesh); objects.append(obj)
            obj['bs_guard_temp']=True; bpy.context.scene.collection.objects.link(obj)
            obj.hide_render=True; obj.hide_set(True)
        mod=objects[0].modifiers.new('Union','BOOLEAN')
        mod.operation='UNION'; mod.solver='EXACT'; mod.use_self=True; mod.object=objects[1]
        evaluated=objects[0].evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh=evaluated.to_mesh()
        try:
            bm=bmesh.new()
            try:
                bm.from_mesh(mesh)
                bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
                bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-8)
                bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
                if not all(e.is_manifold for e in bm.edges): raise ValueError('The generator produced an open union')
                bm.verts.ensure_lookup_table(); bm.verts.index_update()
                return tuple(tuple(v.co) for v in bm.verts),tuple(tuple(v.index for v in f.verts) for f in bm.faces)
            finally: bm.free()
        finally: evaluated.to_mesh_clear()
    finally:
        for obj in objects: bpy.data.objects.remove(obj,do_unlink=True)
        for mesh in meshes:
            if not mesh.users: bpy.data.meshes.remove(mesh)
