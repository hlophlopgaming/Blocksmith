# SPDX-License-Identifier: GPL-3.0-or-later
"""Point and freehand contour tools; geometry stays in the normal shape lifecycle."""
import json
import math

import bpy
import gpu
from bpy.props import BoolProperty,EnumProperty
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix,Vector

from . import guard
from .outline_geometry import validate,extrude,simplify_stroke
from .translations import tr

KINDS={'POLY_FLOOR','POLY_BLOCK'}
ACTIVE=None


def contours(obj):
    loops=validate(json.loads(obj.bs.contours))
    xs=[p[0] for loop in loops for p in loop];ys=[p[1] for loop in loops for p in loop]
    sx=obj.bs.width/(max(xs)-min(xs));sy=obj.bs.depth/(max(ys)-min(ys))
    return [[(x*sx,y*sy) for x,y in loop] for loop in loops]


def create(context,loops,kind='POLY_FLOOR',height=.2,frame=None,obj=None):
    """One validated, undoable operation for drawing, point editing and scripts."""
    core=guard.core();loops=validate(loops)
    if kind not in KINDS:raise ValueError('Choose a contour floor or contour volume')
    if type(height) not in (int,float) or not math.isfinite(height) or not .01<=height<=10000:
        raise ValueError('Height must be between 0.01 and 10000 m')
    if obj is not None and (not obj.bs.enabled or obj.bs.kind not in KINDS or core.manual(obj)):
        raise ValueError('Select an unedited Blocksmith contour object')
    xs=[p[0] for loop in loops for p in loop];ys=[p[1] for loop in loops for p in loop]
    x0,y0=min(xs),min(ys);width,depth=max(xs)-x0,max(ys)-y0
    if min(width,depth)<.01:raise ValueError('The contour must be at least 1 cm wide and deep')
    loops=[[(x-x0,y-y0) for x,y in loop] for loop in loops]
    with guard.transaction(context):
        if obj is None:
            obj=core.create(context,kind)
            obj.name='Contour Floor' if kind=='POLY_FLOOR' else 'Contour Volume'
        frame=frame if frame is not None else Matrix.Identity(4)
        saved=core.BUSY;core.BUSY=True
        try:
            obj.bs.contours=json.dumps(loops);obj.bs.width=width;obj.bs.depth=depth;obj.bs.height=height
        finally:core.BUSY=saved
        core.rebuild(obj,True)
        pivot=Vector(obj.bs.pivot_offset)
        obj.matrix_world=frame@Matrix.Translation(Vector((x0,y0,0))+pivot)
        context.view_layer.update()
    return obj


class BS_OT_outline(bpy.types.Operator):
    bl_idname='blocksmith.outline';bl_label='Draw Contour';bl_options={'REGISTER','UNDO','BLOCKING'}
    kind: EnumProperty(name='Shape',items=[('POLY_FLOOR','Contour Floor',''),('POLY_BLOCK','Contour Volume','')])
    mode: EnumProperty(name='Input',items=[('POINTS','Points','Click snapped corners'),('FREEHAND','Freehand','Draw a closed stroke')])
    edit: BoolProperty(name='Edit Existing',default=False)

    @classmethod
    def poll(cls,context):
        from .drawing import ACTIVE as DRAW
        from .curves import ACTIVE as CURVE
        return (guard.enabled() and context.mode=='OBJECT' and context.area is not None and
                context.area.type=='VIEW_3D' and ACTIVE is None and DRAW is None and CURVE is None)

    def invoke(self,context,event):
        global ACTIVE
        from .drawing import leave_tool
        leave_tool(context)
        self.obj=context.active_object if self.edit else None
        if self.edit and (self.obj is None or not self.obj.bs.enabled or self.obj.bs.kind not in KINDS or guard.core().manual(self.obj)):
            self.report({'WARNING'},tr('Select an unedited contour object'));return {'CANCELLED'}
        self.area=context.area;self.window=context.window;self.scene=context.scene
        self.region=next(r for r in self.area.regions if r.type=='WINDOW')
        self.frame=None;self.loops=[];self.points=[];self.cursor=None;self.selected=None
        self.drag=False;self.moving=False;self.adjusting=False;self.closed=False;self.editing=self.edit
        self.lines=None;self.fill=None;self.dots=None;self.error=''
        if self.obj:
            self.kind=self.obj.bs.kind;self.height=self.obj.bs.height
            self.frame=self.obj.matrix_world@Matrix.Translation(-Vector(self.obj.bs.pivot_offset))
            self.loops=contours(self.obj)
        else:self.height=context.scene.bs.floor_thickness if self.kind=='POLY_FLOOR' else context.scene.bs.draw_height
        self.shader=gpu.shader.from_builtin('UNIFORM_COLOR')
        self.handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_preview,(),'WINDOW','POST_VIEW')
        self.window.cursor_modal_set('CROSSHAIR');ACTIVE=self
        context.window_manager.modal_handler_add(self);self.preview();return {'RUNNING_MODAL'}

    def finish(self,context,result):
        global ACTIVE
        if not self.closed:
            self.closed=True;self.result=result
            bpy.types.SpaceView3D.draw_handler_remove(self.handle,'WINDOW')
            self.area.header_text_set(None);self.window.cursor_modal_restore();self.area.tag_redraw()
        if ACTIVE is self:ACTIVE=None
        return result

    def cancel(self,context):self.finish(context,{'CANCELLED'})

    def draw_preview(self):
        if bpy.context.area!=self.area:return
        gpu.state.blend_set('ALPHA');gpu.state.depth_mask_set(False)
        try:
            self.shader.bind()
            if self.fill:
                self.shader.uniform_float('color',(.15,.7,1,.16));self.fill.draw(self.shader)
            self.shader.uniform_float('color',(1,.25,.15,1) if self.error else (.15,.8,1,1))
            if self.lines:self.lines.draw(self.shader)
            if self.dots:
                gpu.state.point_size_set(7);self.dots.draw(self.shader)
        finally:
            gpu.state.point_size_set(1);gpu.state.depth_mask_set(True);gpu.state.blend_set('NONE')

    def data(self):return self.loops+([self.points] if self.points else [])

    def preview(self):
        self.lines=self.fill=self.dots=None
        if self.frame is not None:
            loops=self.data();segments=[];dots=[]
            for loop in loops:
                dots.extend(self.frame@Vector((*p,0)) for p in loop)
                if len(loop)>1:
                    for a,b in zip(loop,loop[1:]+loop[:1]):segments.extend((self.frame@Vector((*a,0)),self.frame@Vector((*b,0))))
            if self.points and self.cursor and not self.editing:
                segments.extend((self.frame@Vector((*self.points[-1],0)),self.frame@Vector((*self.cursor,0))))
            if segments:self.lines=batch_for_shader(self.shader,'LINES',{'pos':segments})
            if dots:self.dots=batch_for_shader(self.shader,'POINTS',{'pos':dots})
            if loops and not self.drag:
                try:
                    vertices,faces=extrude(loops,self.height,self.kind=='POLY_FLOOR')
                    tris=[self.frame@Vector(vertices[j]) for face in faces for i in range(1,len(face)-1)
                          for j in (face[0],face[i],face[i+1])]
                    self.fill=batch_for_shader(self.shader,'TRIS',{'pos':tris});self.error=''
                except ValueError as exc:
                    if any(len(loop)>=3 for loop in loops):self.error=str(exc)
        helptext=tr('LMB: move point · I: insert · Del: delete point · X: remove hole' if self.editing else
                    'LMB: points' if self.mode=='POINTS' else 'Drag LMB: closed stroke')
        self.area.header_text_set(tr('Contour')+f' · {helptext} · H: {self.height:.2f} m · '+tr('O: hole · Tab: edit · Enter: finish · Esc: cancel')+
                                  (' · '+tr(self.error) if self.error else ''))
        self.area.tag_redraw()

    def nearest(self,event,edges=False):
        mouse=Vector((event.mouse_x-self.region.x,event.mouse_y-self.region.y));best=None;distance=12
        for i,loop in enumerate(self.loops):
            screen=[view3d_utils.location_3d_to_region_2d(self.region,self.area.spaces.active.region_3d,self.frame@Vector((*p,0))) for p in loop]
            for j,p in enumerate(screen):
                if p is None:continue
                if edges:
                    q=screen[(j+1)%len(screen)]
                    if q is None:continue
                    delta=q-p;t=max(0,min(1,(mouse-p).dot(delta)/max(delta.length_squared,1e-12)))
                    d=(p+delta*t-mouse).length
                else:d=(p-mouse).length
                if d<distance:distance=d;best=(i,j)
        return best

    def commit(self,context):
        try:create(context,self.data(),self.kind,self.height,self.frame,self.obj)
        except (ValueError,guard.ConstraintError) as exc:
            self.preview();self.error=str(exc);self.area.header_text_set(tr(str(exc)))
            self.report({'WARNING'},tr(str(exc)));return {'RUNNING_MODAL'}
        return self.finish(context,{'FINISHED'})

    def end_stroke(self,context):
        self.drag=False
        try:self.points=simplify_stroke(self.points,context.scene.bs.contour_tolerance)
        except ValueError as exc:self.error=str(exc)
        self.preview()

    def modal(self,context,event):
        try:return self.event(context,event)
        except Exception as exc:
            self.report({'WARNING'},tr('Contour drawing stopped: ')+str(exc))
            return self.finish(context,{'CANCELLED'})

    def event(self,context,event):
        from .drawing import surface_hit,point_on_plane,snap_point
        if self.closed:return self.result
        if context.scene!=self.scene or context.mode!='OBJECT' or event.type=='WINDOW_DEACTIVATE' or not guard.enabled():
            return self.finish(context,{'CANCELLED'})
        if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':return self.finish(context,{'CANCELLED'})
        if event.type in {'MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE','NDOF_MOTION'}:return {'PASS_THROUGH'}
        if event.type=='H' and event.value=='PRESS':
            self.adjusting=not self.adjusting;self.height_start=self.height;self.height_mouse=event.mouse_y;return {'RUNNING_MODAL'}
        if self.adjusting:
            if event.type=='MOUSEMOVE':
                self.height=max(.01,self.height_start+(event.mouse_y-self.height_mouse)*.01);self.preview()
            if event.type=='LEFTMOUSE' and event.value=='PRESS':self.adjusting=False
            return {'RUNNING_MODAL'}
        if event.type in {'RET','NUMPAD_ENTER'} and event.value=='PRESS':return self.commit(context)
        if event.type=='O' and event.value=='PRESS':
            try:
                self.loops=validate(self.data());self.points=[];self.editing=False;self.selected=None
                self.drag=False;self.moving=False
            except ValueError as exc:self.error=str(exc)
            self.preview();return {'RUNNING_MODAL'}
        if event.type=='TAB' and event.value=='PRESS':
            try:
                self.loops=validate(self.data());self.points=[];self.editing=True;self.drag=False;self.moving=False
            except ValueError as exc:self.error=str(exc)
            self.preview();return {'RUNNING_MODAL'}
        if event.type in {'BACK_SPACE','DEL'} and event.value=='PRESS':
            if self.editing and self.selected:
                i,j=self.selected
                if len(self.loops[i])>3:self.loops[i].pop(j);self.selected=None;self.moving=False
            elif self.points:self.points.pop()
            self.preview();return {'RUNNING_MODAL'}
        if event.type=='X' and event.value=='PRESS' and self.editing and self.selected and self.selected[0]>0:
            self.loops.pop(self.selected[0]);self.selected=None;self.moving=False;self.preview();return {'RUNNING_MODAL'}
        inside=self.region.x<=event.mouse_x<self.region.x+self.region.width and self.region.y<=event.mouse_y<self.region.y+self.region.height
        panel=any(r.type in {'UI','TOOLS','HEADER','TOOL_HEADER'} and r.width>1 and r.x<=event.mouse_x<r.x+r.width and r.y<=event.mouse_y<r.y+r.height for r in self.area.regions)
        if not inside or panel:
            if event.type=='LEFTMOUSE' and event.value=='RELEASE':
                if self.drag:self.end_stroke(context)
                self.moving=False
            return {'RUNNING_MODAL'}
        frame=self.frame
        if frame is None:
            hit=surface_hit(context,event)
            if hit is None:return {'RUNNING_MODAL'}
            original,front,_=hit
            normal=original.col[1 if front else 2].xyz.normalized()
            frame=normal.to_track_quat('Z','Y').to_matrix().to_4x4();frame.translation=original.translation
            point=frame.translation.copy()
        else:
            point=point_on_plane(context,event,frame.translation,frame.col[2].xyz)
            if point is None:return {'RUNNING_MODAL'}
        if context.scene.bs.object_snap and not event.ctrl and not (self.drag and self.mode=='FREEHAND'):
            point,_=snap_point(context,event,point,frame,objects=[o for o in context.visible_objects if o!=self.obj])
        local=frame.inverted()@point
        p=(local.x,local.y)
        if event.shift and self.points and self.mode=='POINTS':
            prev=self.points[-1]
            p=(p[0],prev[1]) if abs(p[0]-prev[0])>=abs(p[1]-prev[1]) else (prev[0],p[1])
        self.cursor=p
        if self.editing:
            if event.type=='I' and event.value=='PRESS':
                near=self.nearest(event,edges=True)
                if near:
                    i,j=near;self.loops[i].insert(j+1,p);self.selected=(i,j+1)
            if event.type=='LEFTMOUSE' and event.value=='PRESS':
                self.selected=self.nearest(event);self.moving=self.selected is not None
            if event.type=='MOUSEMOVE' and self.moving:
                i,j=self.selected;self.loops[i][j]=p
            if event.type=='LEFTMOUSE' and event.value=='RELEASE':self.moving=False
        else:
            if event.type=='LEFTMOUSE' and event.value=='PRESS':
                if self.frame is None:self.frame=frame
                if self.mode=='FREEHAND':self.points=[p];self.drag=True
                elif not self.points or math.dist(self.points[-1],p)>.001:self.points.append(p)
            if event.type=='MOUSEMOVE' and self.drag and math.dist(self.points[-1],p)>.005:
                if len(self.points)>=2048:
                    self.drag=False;self.points=[];self.error='Stroke too long; draw a shorter contour'
                    self.report({'WARNING'},tr(self.error))
                else:self.points.append(p)
            if event.type=='LEFTMOUSE' and event.value=='RELEASE' and self.drag:
                self.end_stroke(context)
        self.preview();return {'RUNNING_MODAL'}
