# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw native Blender curves with a rectangular wall profile."""
import math
import bpy
import gpu
from bpy.props import EnumProperty
from mathutils import Vector, Matrix
from gpu_extras.batch import batch_for_shader
from . import guard

MODES=[('POINTS','Точки / Безье','ЛКМ ставит точки; Enter завершает; ручки доступны в Tab'),
       ('FREEHAND','Свободная линия','Протяните ЛКМ, чтобы нарисовать стену'),
       ('ARC','Дуга по 3 точкам','Начало, точка на дуге, конец')]
ACTIVE=None


def arc_points(points,steps=48):
    a,b,c=(Vector(p) for p in points)
    u=b-a; v=c-a; det=2*(u.x*v.y-u.y*v.x)
    if abs(det)<1e-6: raise ValueError('Три точки дуги не должны лежать на одной прямой')
    center=a+Vector(((v.y*u.length_squared-u.y*v.length_squared)/det,
                     (u.x*v.length_squared-v.x*u.length_squared)/det,0))
    start=math.atan2(a.y-center.y,a.x-center.x)
    middle=(math.atan2(b.y-center.y,b.x-center.x)-start)%(2*math.pi)
    end=(math.atan2(c.y-center.y,c.x-center.x)-start)%(2*math.pi)
    sweep=end if middle<end else end-2*math.pi
    radius=(a-center).length
    if radius>10000: raise ValueError('Слишком большой радиус дуги')
    return [center+Vector((radius*math.cos(start+sweep*i/steps),radius*math.sin(start+sweep*i/steps),0)) for i in range(steps+1)]


def signature(data):
    return repr((data.resolution_u,data.use_fill_caps,
        [(s.type,s.use_cyclic_u,[(tuple(p.co),tuple(p.handle_left),tuple(p.handle_right),p.handle_left_type,p.handle_right_type)
          for p in s.bezier_points] if s.type=='BEZIER' else [tuple(p.co) for p in s.points]
         ) for s in data.splines],
        [[tuple(p.co) for p in s.points] for s in data.bevel_object.data.splines] if data.bevel_object else None))


def update_profile(obj):
    profile=obj.data.bevel_object
    shared=profile is not None and any(o!=obj and o.type=='CURVE' and o.get('bs_curve_wall') and o.data.bevel_object==profile for o in bpy.data.objects)
    if profile is None or profile.get('bs_curve_owner')!=obj or shared:
        data=bpy.data.curves.new('BS_Wall_Profile','CURVE'); data.dimensions='2D'
        profile=bpy.data.objects.new('BS_Wall_Profile',data); profile['bs_guard_temp']=True; profile['bs_curve_owner']=obj
        # A linked hidden profile stays available to Blender's curve evaluator and .blend saves.
        helpers=bpy.data.collections.get('Blocksmith Profiles')
        if helpers is None:
            helpers=bpy.data.collections.new('Blocksmith Profiles'); bpy.context.scene.collection.children.link(helpers)
        helpers.objects.link(profile); profile.hide_render=True; profile.hide_viewport=True
        obj.data.bevel_mode='OBJECT'; obj.data.bevel_object=profile
        spline=data.splines.new('POLY'); spline.points.add(3); spline.use_cyclic_u=True
    d,h=obj.bs.depth,obj.bs.height
    for point,co in zip(profile.data.splines[0].points,((-d/2,0,0,1),(-d/2,h,0,1),(d/2,h,0,1),(d/2,0,0,1))): point.co=co
    profile.data.update_tag(); obj.data.update_tag()


@guard.checked
def resize_profile(obj):
    update_profile(obj)


@guard.checked
def create(context,points,mode,frame=None):
    from . import collection
    from .materials import apply_texture
    points=[Vector(p) for p in points]
    if mode not in {item[0] for item in MODES}: raise ValueError('Неизвестный режим кривой')
    if any(not math.isfinite(v) or abs(v)>10000 for p in points for v in p): raise ValueError('Недопустимые координаты кривой')
    if len(points)<2 or all((p-points[0]).length<.01 for p in points[1:]):
        raise ValueError('Нужны хотя бы две различные точки')
    if len(points)>512: raise ValueError('Не более 512 точек на одну кривую')
    if mode=='ARC': points=arc_points(points)
    data=bpy.data.curves.new('BS_Curve','CURVE'); data.dimensions='3D'; data.resolution_u=12
    data.twist_mode='Z_UP'; data.use_fill_caps=True
    spline=data.splines.new('POLY' if mode=='ARC' else 'BEZIER')
    if spline.type=='BEZIER':
        spline.bezier_points.add(len(points)-1)
        for point,co in zip(spline.bezier_points,points):
            point.co=co; point.handle_left_type=point.handle_right_type='AUTO'
    else:
        spline.points.add(len(points)-1)
        for point,co in zip(spline.points,points): point.co=(*co,1)
    obj=bpy.data.objects.new('Кривая стена',data); collection(context).objects.link(obj)
    obj.bs.depth=context.scene.bs.draw_depth; obj.bs.height=context.scene.bs.draw_height
    obj.bs.tag='WALL'; obj.bs.use_kenney=True; obj.bs.palette=context.scene.bs.palette; obj.bs.texture=context.scene.bs.texture
    obj['bs_curve_wall']=True; obj['bs_role']='WALL'
    update_profile(obj); apply_texture(obj)
    # Blender duplicates cap vertices; Weld keeps the exported wall watertight.
    weld=obj.modifiers.new('Замкнуть торцы','WELD'); weld.merge_threshold=1e-5
    obj.matrix_world=frame if frame is not None else Matrix.Identity(4)
    for selected in context.selected_objects: selected.select_set(False)
    obj.select_set(True); context.view_layer.objects.active=obj; context.view_layer.update()
    return obj


class BS_OT_curve(bpy.types.Operator):
    bl_idname='blocksmith.curve'; bl_label='Нарисовать кривую стену'; bl_options={'REGISTER','UNDO','BLOCKING'}
    mode: EnumProperty(items=MODES)
    @classmethod
    def poll(cls,context):
        from .drawing import ACTIVE as DRAWING
        return context.mode=='OBJECT' and context.area and context.area.type=='VIEW_3D' and ACTIVE is None and DRAWING is None
    def invoke(self,context,event):
        global ACTIVE
        from .drawing import leave_tool
        leave_tool(context)
        self.area=context.area; self.window=context.window; self.scene=context.scene
        self.region=next(r for r in self.area.regions if r.type=='WINDOW')
        self.points=[]; self.cursor=None; self.frame=None; self.drag=False; self.batch=None; self.closed=False
        self.shader=gpu.shader.from_builtin('UNIFORM_COLOR')
        self.handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_preview,(),'WINDOW','POST_VIEW')
        self.window.cursor_modal_set('CROSSHAIR'); context.window_manager.modal_handler_add(self); ACTIVE=self
        self.area.header_text_set('Кривая · ЛКМ: точки / протянуть · Enter: готово · Backspace: удалить · Esc: отмена')
        return {'RUNNING_MODAL'}
    def draw_preview(self):
        if self.batch is None or bpy.context.area!=self.area: return
        gpu.state.blend_set('ALPHA')
        try:
            self.shader.bind(); self.shader.uniform_float('color',(.2,.75,1,1)); self.batch.draw(self.shader)
        finally: gpu.state.blend_set('NONE')
    def finish(self,context,result):
        global ACTIVE
        if not self.closed:
            self.closed=True; bpy.types.SpaceView3D.draw_handler_remove(self.handle,'WINDOW')
            self.area.header_text_set(None); self.window.cursor_modal_restore(); self.area.tag_redraw()
        if ACTIVE is self: ACTIVE=None
        return result
    def cancel(self,context): self.finish(context,{'CANCELLED'})
    def commit(self,context):
        try: create(context,self.points,self.mode,self.frame)
        except (ValueError,guard.ConstraintError) as exc:
            self.report({'WARNING'},str(exc)); return {'RUNNING_MODAL'}
        return self.finish(context,{'FINISHED'})
    def modal(self,context,event):
        try: return self.handle_event(context,event)
        except Exception as exc:
            self.report({'WARNING'},'Рисование кривой остановлено: '+str(exc))
            return self.finish(context,{'CANCELLED'})
    def handle_event(self,context,event):
        from .drawing import surface_hit,point_on_plane,snap_point
        if self.closed: return {'CANCELLED'}
        if context.scene!=self.scene or context.mode!='OBJECT' or event.type=='WINDOW_DEACTIVATE': return self.finish(context,{'CANCELLED'})
        if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS': return self.finish(context,{'CANCELLED'})
        if event.type in {'RET','NUMPAD_ENTER'} and event.value=='PRESS': return self.commit(context)
        if event.type=='BACK_SPACE' and event.value=='PRESS':
            if self.points: self.points.pop()
        inside=self.region.x<=event.mouse_x<self.region.x+self.region.width and self.region.y<=event.mouse_y<self.region.y+self.region.height
        panel=any(r.type in {'UI','TOOLS','HEADER','TOOL_HEADER'} and r.width>1 and r.x<=event.mouse_x<r.x+r.width and r.y<=event.mouse_y<r.y+r.height for r in self.area.regions)
        if not inside or panel:
            if event.type=='LEFTMOUSE' and event.value=='RELEASE' and self.drag:
                self.drag=False; return self.commit(context)
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE','NDOF_MOTION'}: return {'PASS_THROUGH'}
        if self.frame is None:
            target=surface_hit(context,event)
            if target is not None:
                # Wall height follows the supporting plane's normal.
                frame,_=target[:2]
                point=frame.translation.copy()
            else: return {'RUNNING_MODAL'}
        else:
            frame=self.frame; point=point_on_plane(context,event,frame.translation,frame.col[2].xyz)
            if point is None: return {'RUNNING_MODAL'}
        if self.mode!='FREEHAND' and context.scene.bs.object_snap and not event.ctrl:
            point,_=snap_point(context,event,point,frame)
        local=frame.inverted()@point; local.z=0
        self.cursor=local
        if event.type=='LEFTMOUSE' and event.value=='PRESS':
            if self.frame is None: self.frame=frame
            if not self.points or (local-self.points[-1]).length>.01: self.points.append(local.copy())
            self.drag=self.mode=='FREEHAND'
            if self.mode=='ARC' and len(self.points)==3: return self.commit(context)
        if event.type=='MOUSEMOVE' and self.drag:
            if (local-self.points[-1]).length>max(.05,context.scene.bs.draw_depth/2):
                if len(self.points)>=512: self.points=self.points[::2]
                self.points.append(local.copy())
        if event.type=='LEFTMOUSE' and event.value=='RELEASE' and self.drag:
            self.drag=False
            if (local-self.points[-1]).length>.01: self.points.append(local.copy())
            return self.commit(context)
        preview=self.points+([local] if self.points and (local-self.points[-1]).length>.001 else [])
        if self.mode=='ARC' and len(preview)==3:
            try: preview=arc_points(preview)
            except ValueError: pass
        self.batch=batch_for_shader(self.shader,'LINE_STRIP',{'pos':[frame@p for p in preview]}) if len(preview)>1 else None
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}
