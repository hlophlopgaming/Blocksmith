# SPDX-License-Identifier: GPL-3.0-or-later
"""Positive-volume intersection. Touching faces and points are allowed."""
from dataclasses import dataclass
import math
import bpy
from mathutils import Vector

EPS=1e-5  # meters; avoids rejecting adjoining modules due to float round-off


class GeometryError(ValueError): pass


def bounds(vertices):
    return tuple((min(v[i] for v in vertices),max(v[i] for v in vertices)) for i in range(3))


def bounds_overlap(a,b):
    return all(min(a[i][1],b[i][1])-max(a[i][0],b[i][0])>EPS for i in range(3))


def unique_axes(vectors):
    result={}
    for v in vectors:
        if v.length_squared<1e-16: continue
        v=v.normalized()
        if next((x for x in v if abs(x)>1e-7),1)<0: v=-v
        result.setdefault(tuple(round(x,5) for x in v),v)
    return list(result.values())


@dataclass
class Part:
    vertices: list
    faces: list
    bounds: tuple
    normals: list
    edges: list
    convex: bool


class Solid:
    def __init__(self,vertices,faces):
        self.vertices=[Vector(v) for v in vertices]; self.faces=[tuple(f) for f in faces]
        if not self.vertices or not self.faces: raise GeometryError('Empty geometry')
        if not all(math.isfinite(x) for v in self.vertices for x in v): raise GeometryError('Nonfinite coordinates')
        self.bounds=bounds(self.vertices)
        roots=list(range(len(vertices)))
        def root(i):
            while roots[i]!=i:
                roots[i]=roots[roots[i]]; i=roots[i]
            return i
        for face in faces:
            for v in face[1:]: roots[root(v)]=root(face[0])
        groups={}
        for face in faces: groups.setdefault(root(face[0]),[]).append(face)
        self.parts=[]
        for group in groups.values():
            ids=sorted({i for f in group for i in f}); remap={v:i for i,v in enumerate(ids)}
            points=[self.vertices[i] for i in ids]
            polygons=[tuple(remap[i] for i in f) for f in group]
            directed={}; normals=[]; edges=[]; planes=[]; volume=0
            origin=points[0]
            for face in polygons:
                a=points[face[0]]; normal=Vector((0,0,0))
                for j,i in enumerate(face):
                    k=face[(j+1)%len(face)]; edge=tuple(sorted((i,k)))
                    count,sign=directed.get(edge,(0,0)); directed[edge]=(count+1,sign+(1 if i<k else -1))
                    edges.append(points[k]-points[i]); normal+=(points[i]-a).cross(points[k]-a)
                if normal.length_squared>1e-18:
                    normal.normalize(); normals.append(normal); planes.append((normal,a))
                for j in range(1,len(face)-1):
                    volume+=(a-origin).dot((points[face[j]]-origin).cross(points[face[j+1]]-origin))/6
            if any(count!=2 or sign!=0 for count,sign in directed.values()):
                raise GeometryError('Open mesh or inconsistent normals')
            if volume<=1e-12: raise GeometryError('Inverted or degenerate geometry')
            convex=all(n.dot(v-a)<=EPS for n,a in planes for v in points)
            self.parts.append(Part(points,polygons,bounds(points),unique_axes(normals),unique_axes(edges),convex))

    @classmethod
    def from_object(cls,obj,depsgraph=None):
        if depsgraph is not None and obj.modifiers:
            evaluated=obj.evaluated_get(depsgraph); mesh=evaluated.to_mesh()
            try: return cls([obj.matrix_world@v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
            finally: evaluated.to_mesh_clear()
        return cls([obj.matrix_world@v.co for v in obj.data.vertices],[tuple(p.vertices) for p in obj.data.polygons])


def convex_overlap(a,b):
    if not bounds_overlap(a.bounds,b.bounds): return False
    for axis in a.normals+b.normals+[u.cross(v) for u in a.edges for v in b.edges]:
        if axis.length_squared<1e-14: continue
        axis=axis.normalized()
        left=[v.dot(axis) for v in a.vertices]; right=[v.dot(axis) for v in b.vertices]
        if min(max(left),max(right))-max(min(left),min(right))<=EPS: return False
    return True


def exact_overlap(a,b,scene):
    """Blender's Exact boolean handles a manually edited or modifier-produced concave solid."""
    import bmesh
    objects=[]; meshes=[]
    try:
        for solid in (a,b):
            mesh=bpy.data.meshes.new('__BS_guard'); meshes.append(mesh)
            mesh.from_pydata(solid.vertices,[],solid.faces); mesh.update()
            obj=bpy.data.objects.new('__BS_guard',mesh); objects.append(obj)
            obj['bs_guard_temp']=True; scene.collection.objects.link(obj); obj.hide_render=True; obj.hide_set(True)
        mod=objects[0].modifiers.new('__BS_intersection','BOOLEAN')
        mod.operation='INTERSECT'; mod.solver='EXACT'; mod.use_self=True; mod.object=objects[1]
        dg=bpy.context.evaluated_depsgraph_get(); evaluated=objects[0].evaluated_get(dg); mesh=evaluated.to_mesh()
        try:
            bm=bmesh.new()
            try:
                bm.from_mesh(mesh)
                volume=abs(bm.calc_volume(signed=True)); area=sum(f.calc_area() for f in bm.faces)
                # Match the linear contact tolerance used by SAT, including thin boolean slivers.
                return volume>EPS*area/2
            finally: bm.free()
        finally: evaluated.to_mesh_clear()
    finally:
        for obj in objects: bpy.data.objects.remove(obj,do_unlink=True)
        for mesh in meshes:
            if mesh.users==0: bpy.data.meshes.remove(mesh)


def overlaps(a,b,scene=None):
    if not bounds_overlap(a.bounds,b.bounds): return False
    if not all(p.convex for p in a.parts+b.parts):
        if scene is None: raise GeometryError('Exact checking of a nonconvex mesh requires a scene')
        return exact_overlap(a,b,scene)
    return any(convex_overlap(p,q) for p in a.parts for q in b.parts if bounds_overlap(p.bounds,q.bounds))
