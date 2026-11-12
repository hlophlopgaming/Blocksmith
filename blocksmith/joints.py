# SPDX-License-Identifier: GPL-3.0-or-later
"""Plan wall ends before changing either mesh; active wall has priority."""
from types import SimpleNamespace
import bpy
from bpy.props import EnumProperty
from mathutils import Vector
from . import guard
from .geometry import wall_min_width

MODES=[('MITER','Под углом','Общая подрезка двух стен, включая разную толщину'),
       ('BUTT','Встык','Прямой торец основной стены, соседняя подрезается к её грани'),
       ('TRIM','Т-стык / подрезка','Подрезать соседнюю стену к грани основной, основную не менять')]


def plan(p,world,q,other,mode='MITER'):
    from . import build
    p=SimpleNamespace(**guard.props(p)) if isinstance(p,bpy.types.PropertyGroup) else SimpleNamespace(**vars(p))
    q=SimpleNamespace(**guard.props(q)) if isinstance(q,bpy.types.PropertyGroup) else SimpleNamespace(**vars(q))
    world=world.copy(); other=other.copy()
    for params,matrix in ((p,world),(q,other)):
        if params.kind not in {'WALL','DOOR','WINDOW','ARCH'} or params.flip:
            raise ValueError('Выберите две прямые стены без отражения')
        if any(abs(v-1)>1e-4 for v in matrix.to_scale()) or matrix.determinant()<0:
            raise ValueError('Перед стыковкой примените масштаб стен')
    x,y,z=(world.col[i].xyz.normalized() for i in range(3))
    u,v,n=(other.col[i].xyz.normalized() for i in range(3))
    origin=world@(-Vector(getattr(p,'pivot_offset',(0,0,0)))); start=other@(-Vector(getattr(q,'pivot_offset',(0,0,0))))
    if z.dot(n)<.9999 or abs(z.dot(start-origin))>1e-4:
        raise ValueError('Основания стен должны лежать в одной плоскости')
    denominator=z.dot(x.cross(u))
    if abs(denominator)<.02: raise ValueError('Для стыка нужны непараллельные стены')
    def crossing(a,b):
        return a+x*(z.dot((b-a).cross(u))/denominator)
    hit=crossing(origin,start)
    a=x.dot(hit-origin); b=u.dot(hit-start)
    end_p=a>p.width/2; end_q=b>q.width/2
    def end(params,matrix,last,near,far):
        if last:
            params.width=near; params.miter_end=far-near
        else:
            params.width-=near; params.miter_start=far-near
            matrix.translation+=matrix.col[0].xyz*near
        if params.width<wall_min_width(params)-1e-5:
            raise ValueError('Недостаточно длины стены для стыка и проёма')
        build(params)
    if mode=='MITER':
        # Two starts/two ends meet opposite sides; an end/start meets like sides.
        swapped=end_p==end_q
        near=crossing(origin,start+v*(q.depth if swapped else 0))
        far=crossing(origin+y*p.depth,start+v*(0 if swapped else q.depth))
        end(p,world,end_p,x.dot(near-origin),x.dot(far-origin))
        qnear,qfar=(far,near) if swapped else (near,far)
        end(q,other,end_q,u.dot(qnear-start),u.dot(qfar-start))
    else:
        far_end=start+u*(0 if end_q else q.width)
        side=y.dot(far_end-origin)
        if -.0001<=side<=p.depth+.0001:
            raise ValueError('Свободный конец соседней стены находится внутри основной')
        face=origin+y*(0 if side<0 else p.depth)
        near=crossing(face,start); far=crossing(face,start+v*q.depth)
        if mode=='BUTT':
            outer=crossing(origin,start+v*q.depth)
            limit=max(a,x.dot(outer-origin)) if end_p else min(a,x.dot(outer-origin))
            end(p,world,end_p,limit,limit)
        elif (min(x.dot(near-origin),x.dot(far-origin))<(0 if side<0 else p.miter_start)-.0001 or
              max(x.dot(near-origin),x.dot(far-origin))>p.width+(0 if side<0 else p.miter_end)+.0001):
            raise ValueError('Т-стык должен попадать в длину основной стены')
        end(q,other,end_q,u.dot(near-start),u.dot(far-start))
    return (p,world),(q,other)


def apply(obj,params,world):
    import sys
    core=sys.modules[__package__]; saved=core.BUSY; core.BUSY=True
    try:
        for key in ('width','miter_start','miter_end'): setattr(obj.bs,key,getattr(params,key))
    finally: core.BUSY=saved
    core.rebuild(obj,True); obj.matrix_world=world


class BS_OT_join(bpy.types.Operator):
    bl_idname='blocksmith.join'; bl_label='Состыковать стены'; bl_options={'REGISTER','UNDO'}
    mode: EnumProperty(items=MODES)
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and len(context.selected_objects)==2 and context.active_object in context.selected_objects
    @guard.checked
    def execute(self,context):
        from . import manual
        target=context.active_object; branch=next(o for o in context.selected_objects if o!=target)
        if any(o.type!='MESH' or not o.bs.enabled or manual(o) or o.modifiers for o in (target,branch)):
            self.report({'WARNING'},'Выберите две параметрические стены без модификаторов'); return {'CANCELLED'}
        try: result=plan(target.bs,target.matrix_world,branch.bs,branch.matrix_world,self.mode)
        except ValueError as exc:
            self.report({'WARNING'},str(exc)); return {'CANCELLED'}
        for obj,(params,world) in zip((target,branch),result): apply(obj,params,world)
        context.view_layer.update()
        return {'FINISHED'}
