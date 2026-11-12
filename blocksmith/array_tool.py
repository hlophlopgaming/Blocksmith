# SPDX-License-Identifier: GPL-3.0-or-later
"""A mouse-driven row backed by Blender's editable Array modifier."""
from .translations import tr
import bpy
from bpy.props import BoolProperty,IntProperty
from mathutils import Vector,Matrix
from . import guard

ACTIVE=None


def opening_source(obj):
    return next((m.object for m in reversed(obj.modifiers) if m.type=='BOOLEAN' and m.object
                 and m.object.parent==obj and (m.object.get('bs_drawn_opening') or (m.object.get('bs_opening') and obj.bs.opening!='NONE'))),None)


def array_modifier(obj,count,delta):
    bpy.context.view_layer.update()
    mod=obj.modifiers.new('BS_Row','ARRAY')
    mod.use_relative_offset=False; mod.use_constant_offset=True; mod.count=count
    mod.constant_offset_displace=obj.matrix_world.to_3x3().inverted()@delta/(count-1)
    return mod


def spacing_error(source,count,delta):
    length=delta.length
    if length<.01:return 'Specify the end of the row'
    axis=delta/length
    points=[source.matrix_world@Vector(v) for v in source.bound_box]
    size=max(v.dot(axis) for v in points)-min(v.dot(axis) for v in points)
    return 'Reduce the repeat count or extend the row' if length/(count-1)<size-1e-5 else ''


class BS_OT_row(bpy.types.Operator):
    bl_idname='blocksmith.row'; bl_label='Draw Row'; bl_options={'REGISTER','UNDO','BLOCKING'}
    opening: BoolProperty(name='Opening',default=False)
    count: IntProperty(name='Count',default=5,min=2,max=100)
    @classmethod
    def poll(cls,context):
        o=context.active_object
        return context.mode=='OBJECT' and context.area and context.area.type=='VIEW_3D' and o is not None and o.type=='MESH' and not o.get('bs_cutter')
    def invoke(self,context,event):
        global ACTIVE
        from .drawing import ACTIVE as DRAW
        from .curves import ACTIVE as CURVE
        if ACTIVE is not None or DRAW is not None or CURVE is not None:return {'CANCELLED'}
        self.owner=context.active_object; self.source=opening_source(self.owner) if self.opening else self.owner
        if self.source is None:
            self.report({'WARNING'},tr('Draw the first opening on the object'));return {'CANCELLED'}
        if abs(self.source.matrix_world.determinant())<1e-12:return {'CANCELLED'}
        self.area=context.area;self.window=context.window;self.scene=context.scene
        self.region=next(r for r in self.area.regions if r.type=='WINDOW')
        self.hidden=self.owner.hide_get();self.closed=False;self.delta=Vector();self.error='Specify the end of the row'
        self.temporary=[]
        try:
            self.preview=self.copy(context,self.source)
            if not self.preview.data.vertices:raise ValueError('The selected object has no geometry')
            self.mod=array_modifier(self.preview,self.count,Vector())
            if self.opening:
                self.preview.hide_set(True)
                self.result=self.copy(context,self.owner)
                mod=self.result.modifiers.new('Row preview','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.use_self=True;mod.object=self.preview
                self.owner.hide_set(True)
            else:
                self.result=self.preview;self.preview.display_type='WIRE';self.preview.show_in_front=True
            box=[self.source.matrix_world@Vector(v) for v in self.source.bound_box]
            self.anchor=sum(box,Vector())/8
            self.normal=(self.source.matrix_world.to_3x3().inverted().transposed()@Vector((0,1,0))).normalized() if self.opening else Vector((0,0,1))
            self.workspace=context.workspace
            self.workspace.status_text_set(tr('Row · mouse: length and direction · wheel: count · LMB: create · Esc / RMB: cancel'))
            self.hud=bpy.types.SpaceView3D.draw_handler_add(self.draw_hud,(),'WINDOW','POST_PIXEL')
            context.window_manager.modal_handler_add(self); ACTIVE=self
            return {'RUNNING_MODAL'}
        except Exception as exc:
            self.cleanup();self.report({'WARNING'},tr(str(exc)));return {'CANCELLED'}
    def copy(self,context,source):
        mesh=bpy.data.meshes.new_from_object(source.evaluated_get(context.evaluated_depsgraph_get()))
        obj=bpy.data.objects.new('__BS_row_preview',mesh);obj['bs_guard_temp']=True
        context.scene.collection.objects.link(obj);obj.matrix_world=source.matrix_world.copy();obj.color=source.color;obj.hide_render=True
        self.temporary.append(obj);return obj
    def move(self,context,event):
        from .drawing import point_on_plane
        point=point_on_plane(context,event,self.anchor,self.normal)
        if point is None:return
        self.delta=point-self.anchor
        self.delta-=self.normal*self.normal.dot(self.delta)
        if context.scene.bs.object_snap and not event.ctrl:
            frame=self.source.matrix_world.to_3x3().normalized().to_4x4() if self.opening else Matrix.Identity(4)
            local=frame.inverted().to_3x3()@self.delta
            for i in ((0,2) if self.opening else (0,1)):local[i]=round(local[i]/context.scene.bs.grid)*context.scene.bs.grid
            self.delta=frame.to_3x3()@local
        if event.shift:
            frame=self.source.matrix_world.to_3x3().normalized() if self.opening else Matrix.Identity(3)
            local=frame.inverted()@self.delta; axes=(0,2) if self.opening else (0,1)
            keep=max(axes,key=lambda i:abs(local[i]))
            for i in axes:
                if i!=keep:local[i]=0
            self.delta=frame@local
        self.update_preview(context)
    def update_preview(self,context):
        self.mod.count=self.count
        self.mod.constant_offset_displace=self.source.matrix_world.to_3x3().inverted()@self.delta/(self.count-1)
        context.view_layer.update()
        self.error=spacing_error(self.source,self.count,self.delta)
        if self.opening and not self.error:
            owner=[self.owner.matrix_world@Vector(v) for v in self.owner.bound_box]
            repeated=[self.preview.matrix_world@Vector(v) for v in self.preview.bound_box]
            for i in (0,2):
                axis=self.source.matrix_world.col[i].xyz.normalized()
                if (min(v.dot(axis) for v in repeated)<min(v.dot(axis) for v in owner)-1e-4 or
                    max(v.dot(axis) for v in repeated)>max(v.dot(axis) for v in owner)+1e-4):
                    self.error='The opening row extends outside the object';break
        if not self.error and guard.protected(self.owner):
            evaluated=self.result.evaluated_get(context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:
                kind=self.owner.bs.kind if self.owner.bs.enabled else self.owner.get('bs_role','BLOCK')
                self.error=guard.placement_error(context,[v.co[:] for v in mesh.vertices],[p.vertices[:] for p in mesh.polygons],self.result.matrix_world,kind,{self.owner:None})
            finally:evaluated.to_mesh_clear()
        self.area.header_text_set(tr('Row: {0} objects · length {1:.2f} m').format(self.count,self.delta.length)+(' · '+self.error if self.error else ''))
        self.area.tag_redraw()
    def draw_hud(self):
        if bpy.context.area!=self.area:return
        import blf
        blf.size(0,16);blf.color(0,1,.3,.2,1) if self.error else blf.color(0,.3,.8,1,1)
        blf.position(0,30,60,0);blf.draw(0,self.error or tr('{0} repeats · {1:.2f} m').format(self.count,self.delta.length))
    def cleanup(self):
        global ACTIVE
        if getattr(self,'closed',True):return
        self.closed=True
        if hasattr(self,'hud'):bpy.types.SpaceView3D.draw_handler_remove(self.hud,'WINDOW')
        if hasattr(self,'workspace'):self.workspace.status_text_set(None)
        try:self.owner.hide_set(self.hidden)
        except ReferenceError:pass
        for obj in reversed(self.temporary):
            mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
            if not mesh.users:bpy.data.meshes.remove(mesh)
        self.area.header_text_set(None);self.area.tag_redraw()
        if ACTIVE is self:ACTIVE=None
    def finish(self,context):
        self.update_preview(context)
        if self.error:
            self.report({'WARNING'},tr(self.error));return {'RUNNING_MODAL'}
        self.cleanup()
        mod=None
        try:
            with guard.transaction(context):
                mod=array_modifier(self.source,self.count,self.delta)
                context.view_layer.update()
        except guard.ConstraintError as exc:
            if mod is not None:
                try:self.source.modifiers.remove(mod)
                except ReferenceError:pass
            self.report({'WARNING'},tr(str(exc)));return {'CANCELLED'}
        return {'FINISHED'}
    def modal(self,context,event):
        if self.closed:return {'CANCELLED'}
        try:
            if context.scene!=self.scene or context.mode!='OBJECT' or event.type in {'ESC','RIGHTMOUSE','WINDOW_DEACTIVATE'}:
                self.cleanup();return {'CANCELLED'}
            inside=self.region.x<=event.mouse_x<self.region.x+self.region.width and self.region.y<=event.mouse_y<self.region.y+self.region.height
            panel=any(r.type in {'UI','TOOLS','HEADER','TOOL_HEADER'} and r.width>1 and r.x<=event.mouse_x<r.x+r.width and r.y<=event.mouse_y<r.y+r.height for r in self.area.regions)
            if not inside or panel:
                if event.type=='LEFTMOUSE':self.cleanup();return {'CANCELLED','PASS_THROUGH'}
                return {'PASS_THROUGH'}
            if event.type=='MOUSEMOVE':self.move(context,event)
            elif event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
                self.count=max(2,min(100,self.count+(1 if event.type=='WHEELUPMOUSE' else -1)));self.update_preview(context)
            elif event.type=='LEFTMOUSE' and event.value=='PRESS':return self.finish(context)
            elif event.type=='MIDDLEMOUSE':return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}
        except Exception as exc:
            self.cleanup();self.report({'WARNING'},tr(str(exc)));return {'CANCELLED'}
    def cancel(self,context):self.cleanup()
