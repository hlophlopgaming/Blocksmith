# SPDX-License-Identifier: GPL-3.0-or-later
"""Editable through-cuts for meshes without replacing their source geometry."""
import bpy
import bmesh
from mathutils import Matrix
from .geometry import Mesh, arch_top

WALLS={'WALL','DOOR','WINDOW','ARCH','ROOM'}
VARIANTS=[('DOOR','Дверь',''),('WINDOW','Окно',''),('ARCH','Арка',''),('ARCH_WINDOW','Арочное окно',''),('NONE','Убрать проём','')]


def native(obj):
    from . import manual
    return obj.bs.enabled and obj.bs.kind in WALLS and not manual(obj)


def modifier(obj):
    return next((m for m in obj.modifiers if m.type=='BOOLEAN' and m.object and m.object.get('bs_opening')),None)


def update(obj,context):
    """Keep one private cutter per target, including native Blender duplicates."""
    from . import signature
    p=obj.bs; mod=modifier(obj)
    if mod is None and p.opening=='NONE': return
    evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
    vertices=evaluated.data.vertices
    if not vertices: raise ValueError('В выбранном меше нет геометрии')
    low=[min(v.co[i] for v in vertices) for i in range(3)]
    high=[max(v.co[i] for v in vertices) for i in range(3)]
    axis='XYZ'.index(p.cut_axis); horizontal=1 if axis==0 else 0; vertical=1 if axis==2 else 2
    width=high[horizontal]-low[horizontal]; height=high[vertical]-low[vertical]
    if min(width,height,high[axis]-low[axis])<1e-5: raise ValueError('Для проёма нужен объёмный меш')
    margin=max(.01,(high[axis]-low[axis])*.01)
    shape=Mesh()
    if p.opening=='NONE':
        shape.box(high[0]+margin,high[1]+margin,high[2]+margin,.01,.01,.01)
    else:
        ow=min(p.open_width,width*.95); oh=min(p.open_height,height*.98)
        count=max(1,min(p.count,int(width/(ow+.02))))
        gap=(width-count*ow)/(count+1); offset=max(-gap*.95,min(gap*.95,p.offset))
        sill=min(p.sill,max(0,height-oh-.01)) if p.opening in {'WINDOW','ARCH_WINDOW'} else 0
        bottom=low[vertical]+sill if p.opening in {'WINDOW','ARCH_WINDOW'} else low[vertical]-margin
        for i in range(count):
            x=low[horizontal]+gap*(i+1)+ow*i+offset
            top=low[vertical]+sill+oh
            profile=[(x,bottom),(x+ow,bottom)]
            if p.opening in {'ARCH','ARCH_WINDOW'}:
                profile += [(x+ow*f,arch_top(f,ow,oh,low[vertical]+sill,p.arch_style))
                            for f in (j/p.segments for j in range(p.segments,-1,-1))]
            else: profile += [(x+ow,top),(x,top)]
            shape.prism(profile,high[axis]-low[axis]+2*margin,low[axis]-margin)
        if axis==0: shape.vertices=[(y,x,z) for x,y,z in shape.vertices]
        elif axis==2: shape.vertices=[(x,z,y) for x,y,z in shape.vertices]
    if mod is None:
        mesh=bpy.data.meshes.new('BS_Opening')
        cutter=bpy.data.objects.new(obj.name+' • проём',mesh)
        context.collection.objects.link(cutter)
        cutter['bs_opening']=True; cutter['bs_cutter']=True; cutter['bs_managed']=True
        mod=obj.modifiers.new('BS_Opening','BOOLEAN'); mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter
    else:
        cutter=mod.object
        if cutter.parent!=obj or cutter.data.users>1:
            cutter=cutter.copy(); cutter.data=cutter.data.copy(); context.collection.objects.link(cutter); mod.object=cutter
    cutter.parent=obj; cutter.matrix_parent_inverse=Matrix.Identity(4); cutter.matrix_basis=Matrix.Identity(4)
    cutter.hide_render=True; cutter.hide_set(True)
    mesh=cutter.data; mesh.clear_geometry(); mesh.from_pydata(shape.vertices,[],shape.faces); mesh.update()
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh)
    finally: bm.free()
    cutter['bs_signature']=signature(mesh)


def set_variant(context,obj,variant):
    import sys
    from . import rebuild
    core=sys.modules[__package__]; p=obj.bs
    saved=core.BUSY; core.BUSY=True
    try:
        if native(obj):
            if p.kind!='ROOM': p.kind='WALL'
            p.opening=variant
            rebuild(obj)
        else:
            if modifier(obj) is None and variant!='NONE':
                evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
                coords=[v.co for v in evaluated.data.vertices]
                if not coords: raise ValueError('В выбранном меше нет геометрии')
                size=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)]
                if min(size)<1e-5: raise ValueError('Для проёма нужен объёмный меш')
                axis=min(range(3),key=lambda i:size[i]); p.cut_axis='XYZ'[axis]
                w=size[1 if axis==0 else 0]; h=size[1 if axis==2 else 2]
                p.open_width=min(context.scene.bs.door_width,w*.45)
                p.open_height=min(context.scene.bs.door_height,h*.6)
                p.sill=h*.2; p.offset=0; p.count=1
            p.opening=variant
            update(obj,context)
    finally: core.BUSY=saved


def surface(context,event):
    """Pick a face and its first exit, so a room cut never reaches the opposite wall."""
    from .drawing import surface_hit
    from .geometry import REFERENCES
    from mathutils import Vector
    from mathutils.geometry import closest_point_on_tri
    target=surface_hit(context,event,force_surfaces=True)
    if target is None:raise ValueError('Начните рисовать на стене или меше')
    picked,front,obj=target
    if obj is None or obj.type!='MESH' or obj.get('bs_cutter') or (obj.bs.enabled and obj.bs.kind in REFERENCES):
        raise ValueError('Начните рисовать на стене или меше')
    point=picked.translation.copy();normal=picked.col[1 if front else 2].xyz.normalized()
    world=obj.matrix_world; inv=world.inverted()
    normal.normalize(); up=Vector((0,0,1)); vertical=up-normal*up.dot(normal)
    if vertical.length<.01: vertical=Vector((0,1,0))
    vertical.normalize(); horizontal=normal.cross(vertical).normalized(); vertical=horizontal.cross(normal)
    frame=Matrix((horizontal,normal,vertical)).transposed().to_4x4(); frame.translation=point
    evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
    # Nudge into a real triangle so a cut can start exactly at an existing edge.
    mesh=evaluated.data;mesh.calc_loop_triangles(); normals=inv.to_3x3().transposed()
    centres=[]
    for triangle in mesh.loop_triangles:
        face=mesh.polygons[triangle.polygon_index]
        if (normals@face.normal).normalized().dot(normal)<.9999:continue
        a,b,c=(world@mesh.vertices[i].co for i in triangle.vertices)
        if (closest_point_on_tri(point,a,b,c)-point).length<1e-4:centres.append((a+b+c)/3)
    inside=point.lerp(min(centres,key=lambda v:(v-point).length_squared),.001) if centres else point
    hit,back,back_normal,_=evaluated.ray_cast(inv@(inside-normal*.0001),(inv.to_3x3()@(-normal)).normalized())
    from . import manual
    if obj.bs.enabled and obj.bs.kind=='ROOM' and not manual(obj):
        local=inv.to_3x3()@normal
        thickness=obj.bs.thickness if abs(local.normalized().z)>.7 else min(obj.bs.thickness,obj.bs.width/3,obj.bs.depth/3)
        depth=thickness/local.length
    else:
        if not hit or (inv.to_3x3().transposed()@back_normal).normalized().dot(normal)>-.01:
            raise ValueError('Начните внутри грани объёмного меша')
        depth=(inside-world@back).dot(normal)
    # shortcut: depth follows this face; redraw after changing the wall thickness.
    if depth<.0001: raise ValueError('У поверхности нет толщины для выреза')
    return obj,frame,depth


def drawn_mesh(kind,start,end,depth):
    """The drag rectangle is the hole, rather than a new wall containing a hole."""
    left,right=sorted((start.x,end.x)); bottom,top=sorted((start.z,end.z))
    if right-left<.01 or top-bottom<.01: raise ValueError('Протяните ширину и высоту проёма')
    shape=Mesh(); profile=[(left,bottom),(right,bottom)]
    if kind=='ARCH':
        profile += [(left+(right-left)*j/32,arch_top(j/32,right-left,top-bottom,bottom,'ROUND')) for j in range(32,-1,-1)]
    else: profile += [(right,top),(left,top)]
    shape.prism(profile,depth+.002,-depth-.001)
    return shape


def apply_drawn(context,obj,shape,frame):
    """Add an independent cut; retain the target and all earlier openings."""
    context.view_layer.update()
    from . import signature
    mesh=bpy.data.meshes.new('BS_DrawnOpening')
    mesh.from_pydata(shape.vertices,[],shape.faces); mesh.update()
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh)
    finally: bm.free()
    cutter=bpy.data.objects.new(obj.name+' • проём',mesh); context.collection.objects.link(cutter)
    cutter['bs_drawn_opening']=True; cutter['bs_cutter']=True; cutter['bs_managed']=True
    cutter['bs_signature']=signature(mesh)
    cutter.parent=obj; cutter.matrix_parent_inverse=Matrix.Identity(4)
    cutter.matrix_basis=obj.matrix_world.inverted()@frame
    cutter.hide_render=True; cutter.hide_set(True)
    mod=obj.modifiers.new('BS_DrawnOpening','BOOLEAN'); mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.use_self=True; mod.object=cutter
    for selected in context.selected_objects: selected.select_set(False)
    obj.select_set(True); context.view_layer.objects.active=obj
