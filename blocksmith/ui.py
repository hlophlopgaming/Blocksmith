# SPDX-License-Identifier: GPL-3.0-or-later
"""Module picker and direct editing in the viewport."""
from pathlib import Path
from types import SimpleNamespace
import math
import bpy
import bpy.utils.previews
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector
from .presets import PRESETS, BY_ID
from . import guard
from .editing import resize
from .array_tool import BS_OT_row
from .materials import apply_texture, ROOT as TEXTURES

PREVIEWS=None


@guard.checked
def apply_preset(context,identifier):
    from . import create, rebuild
    from . import __name__ as package
    import sys
    core=sys.modules[package]
    preset=BY_ID[identifier]
    obj=create(context,preset[3]); core.BUSY=True
    try:
        for key,value in preset[4].items(): setattr(obj.bs,key,value)
    finally: core.BUSY=False
    rebuild(obj,True); obj['bs_preset']=identifier
    obj.name=preset[1]
    return obj


def icon(identifier):
    return PREVIEWS[identifier].icon_id if PREVIEWS and identifier in PREVIEWS else 0


def texture_view(context):
    if context.screen:
        for area in context.screen.areas:
            if area.type=='VIEW_3D':
                shade=area.spaces.active.shading; shade.type='SOLID'; shade.color_type='TEXTURE'; shade.show_cavity=True


class BS_OT_preset(bpy.types.Operator):
    bl_idname='blocksmith.preset'; bl_label='Выбрать модуль'; bl_options={'REGISTER','UNDO'}
    identifier: StringProperty(default='wall_4')
    action: EnumProperty(items=[('SELECT','Выбрать',''),('ADD','Добавить у курсора',''),('PLACE','Разместить мышью',''),('STAMP','Серия копий',''),('DRAW','Рисовать',''),('NATIVE','Add Cube','')])
    @guard.checked
    def execute(self,context):
        if self.identifier not in BY_ID: return {'CANCELLED'}
        from .drawing import select_preset
        s=context.scene.bs; select_preset(s,self.identifier)
        if self.action=='ADD':
            apply_preset(context,self.identifier); texture_view(context)
        elif self.action in {'PLACE','STAMP'}:
            return bpy.ops.blocksmith.draw('INVOKE_DEFAULT',use_preset=True,place_only=True,repeat=self.action=='STAMP')
        elif self.action in {'NATIVE','DRAW'}:
            return bpy.ops.blocksmith.activate()
        if context.area: context.area.tag_redraw()
        return {'FINISHED'}


class BS_OT_step(bpy.types.Operator):
    bl_idname='blocksmith.step'; bl_label='Изменить на шаг сетки'; bl_options={'REGISTER','UNDO'}
    key: EnumProperty(items=[(k,k,'') for k in ('width','depth','height')])
    direction: IntProperty(default=1)
    @classmethod
    def poll(cls,context):
        from . import manual
        o=context.active_object
        return context.mode=='OBJECT' and o is not None and o.type=='MESH' and o.bs.enabled and not manual(o)
    @guard.checked
    def execute(self,context):
        from . import manual
        targets=context.selected_objects if self.all_selected else [context.active_object]
        for o in targets:
            if o.type=='MESH' and o.bs.enabled and not manual(o):
                resize(o,self.key,getattr(o.bs,self.key)+self.direction*context.scene.bs.grid)
                context.view_layer.update()
        return {'FINISHED'}
    all_selected: BoolProperty(default=False,options={'SKIP_SAVE'})
    def invoke(self,context,event):
        self.all_selected=event.alt
        return self.execute(context)


class BS_OT_free_placement(bpy.types.Operator):
    bl_idname='blocksmith.free_placement'; bl_label='Свободное размещение'; bl_options={'REGISTER','UNDO'}
    bl_description='Добавить или снять метку свободного размещения у выделенных мешей'
    enabled: BoolProperty(default=True)
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and any(o.type=='MESH' and o.is_editable for o in context.selected_objects)
    @guard.checked
    def execute(self,context):
        for obj in context.selected_objects:
            if obj.type=='MESH' and obj.is_editable: obj.bs.free_placement=self.enabled
        return {'FINISHED'}


class BS_OT_attach(bpy.types.Operator):
    bl_idname='blocksmith.attach'; bl_label='Пристыковать к грани'; bl_options={'REGISTER','UNDO'}
    bl_description='Переместить соседнюю деталь к внешней грани активной, сохраняя форму и поворот; оси основной детали'
    axis: EnumProperty(items=[(a,a,'Ось основной детали') for a in 'XYZ'])
    direction: IntProperty(default=1,min=-1,max=1)
    @classmethod
    def poll(cls,context):
        objects=context.selected_objects
        return (context.mode=='OBJECT' and len(objects)==2 and context.active_object in objects
                and all(o.type=='MESH' for o in objects))
    @guard.checked
    def execute(self,context):
        from .editing import attach
        target=context.active_object; obj=next(o for o in context.selected_objects if o!=target)
        try: attach(context,obj,target,self.axis,-1 if self.direction<0 else 1)
        except ValueError as exc:
            self.report({'WARNING'},str(exc)); return {'CANCELLED'}
        context.view_layer.update()
        return {'FINISHED'}


class BS_OT_texture(bpy.types.Operator):
    bl_idname='blocksmith.texture'; bl_label='Применить Kenney к выделенным'; bl_options={'REGISTER','UNDO'}
    @guard.checked
    def execute(self,context):
        for obj in context.selected_objects:
            if obj.type!='MESH' and not obj.get('bs_curve_wall'): continue
            p=obj.bs; p.use_kenney=True; p.palette=context.scene.bs.palette; p.texture=context.scene.bs.texture
            apply_texture(obj)
        texture_view(context)
        return {'FINISHED'}


class BS_OT_resize(bpy.types.Operator):
    bl_idname='blocksmith.resize'; bl_label='Потянуть размер'; bl_options={'REGISTER','UNDO','BLOCKING'}
    key: EnumProperty(items=[(k,k,'') for k in ('width','depth','height')])
    side: IntProperty(default=1)
    @classmethod
    def poll(cls,context): return BS_OT_step.poll(context)
    def invoke(self,context,event):
        self.obj=context.active_object; self.value=getattr(self.obj.bs,self.key)
        self.location=self.obj.location.copy(); self.world=self.obj.matrix_world.copy()
        self.mouse=Vector((event.mouse_x,event.mouse_y))
        self.index=('width','depth','height').index(self.key)
        box=[Vector(v) for v in self.obj.bound_box]
        low=Vector([min(v[i] for v in box) for i in range(3)]); high=Vector([max(v[i] for v in box) for i in range(3)])
        self.fixed=low[self.index] if self.side>0 else high[self.index]
        self.span=high[self.index]-low[self.index]
        raw=[v.co[self.index] for v in self.obj.data.vertices]
        from . import raw_build
        values=guard.props(self.obj.bs);step=max(.001,abs(self.value)*.001)
        def span(props):
            mesh=raw_build(SimpleNamespace(**props))
            return max(v[self.index] for v in mesh.vertices)-min(v[self.index] for v in mesh.vertices)
        base=span(values);values[self.key]+=step
        derivative=(span(values)-base)/step
        self.geometric=abs(derivative)>1e-6
        self.parameter_scale=derivative if self.geometric else 1
        self.parameter_offset=self.value-(max(raw)-min(raw))/self.parameter_scale
        face=(low+high)/2;face[self.index]=high[self.index] if self.side>0 else low[self.index]
        self.face=self.world@face
        axis='XYZ'[('width','depth','height').index(self.key)]
        direction=self.world.to_3x3()@Vector(tuple(1 if a==axis else 0 for a in 'XYZ'))
        region=context.region; rv=context.space_data.region_3d
        center=self.world.translation
        a=view3d_utils.location_3d_to_region_2d(region,rv,center)
        b=view3d_utils.location_3d_to_region_2d(region,rv,center+direction*self.side)
        self.screen_axis=(b-a) if a is not None and b is not None else Vector((0,50))
        if self.screen_axis.length<1: self.screen_axis=Vector((0,50))
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set('Тяните к ребру или вершине · Ctrl: без привязки · Esc: отменить')
        return {'RUNNING_MODAL'}
    @guard.checked
    def modal(self,context,event):
        if event.type in {'ESC','RIGHTMOUSE'}:
            setattr(self.obj.bs,self.key,self.value); self.obj.location=self.location
            context.area.header_text_set(None); return {'CANCELLED'}
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':
            context.area.header_text_set(None); return {'FINISHED'}
        if event.type=='MOUSEMOVE':
            movement=Vector((event.mouse_x,event.mouse_y))-self.mouse
            delta=movement.dot(self.screen_axis)/self.screen_axis.length_squared
            value=(self.span+delta)/self.parameter_scale+self.parameter_offset
            snapped=None
            if not event.ctrl and context.scene.bs.object_snap and self.geometric:
                from .drawing import snap_point
                point=self.face+self.world.col[self.index].xyz*self.side*delta
                hidden=self.obj.hide_get()
                try:
                    self.obj.hide_set(True);context.view_layer.update()
                    candidates=[o for o in context.visible_objects if o!=self.obj and o not in self.obj.children_recursive]
                    point,snapped=snap_point(context,event,point,Matrix.Translation(point),objects=candidates,mode='SPACE')
                finally:self.obj.hide_set(hidden)
                if snapped is not None:
                    local=self.world.inverted()@point
                    value=(local[self.index]-self.fixed)*self.side/self.parameter_scale+self.parameter_offset
            if not event.ctrl and snapped is None:value=round(value/context.scene.bs.grid)*context.scene.bs.grid
            # Rebase each event so opposing-face anchoring is independent of event count.
            setattr(self.obj.bs,self.key,self.value); self.obj.location=self.location.copy()
            context.view_layer.update()
            resize(self.obj,self.key,value,self.side); context.view_layer.update(); context.area.tag_redraw()
        return {'RUNNING_MODAL'}


class BS_GGT_resize(bpy.types.GizmoGroup):
    bl_idname='BS_GGT_resize'; bl_label='Blocksmith resize'
    bl_space_type='VIEW_3D'; bl_region_type='WINDOW'; bl_options={'3D','PERSISTENT'}
    @classmethod
    def poll(cls,context):
        return context.scene.bs.handles and BS_OT_step.poll(context)
    def setup(self,context):
        self.arrows=[]
        for index,key in enumerate(('width','depth','height')):
            for side in (-1,1):
                arrow=self.gizmos.new('GIZMO_GT_arrow_3d'); arrow.draw_style='BOX'
                arrow.color=(1,.55,.1); arrow.alpha=.65; arrow.color_highlight=(1,.85,.25); arrow.alpha_highlight=1
                arrow.scale_basis=.7
                props=arrow.target_set_operator('blocksmith.resize'); props.key=key; props.side=side
                self.arrows.append((arrow,index,side))
    def draw_prepare(self,context):
        obj=context.active_object; bb=[Vector(v) for v in obj.bound_box]
        low=Vector([min(v[i] for v in bb) for i in range(3)])
        high=Vector([max(v[i] for v in bb) for i in range(3)])
        for arrow,index,side in self.arrows:
            pos=(low+high)/2; pos[index]=high[index] if side>0 else low[index]
            direction=obj.matrix_world.to_3x3()@Vector(tuple(side if i==index else 0 for i in range(3)))
            basis=direction.to_track_quat('Z','Y').to_matrix().to_4x4()
            basis.translation=obj.matrix_world@pos
            arrow.matrix_basis=basis


class BS_PT_catalog(bpy.types.Panel):
    bl_label='Готовые модули'; bl_idname='BS_PT_catalog'; bl_space_type='VIEW_3D'; bl_region_type='WINDOW'
    bl_ui_units_x=24
    def draw(self,context):
        s=context.scene.bs; l=self.layout
        l.prop(s,'preset_group',text='Раздел')
        grid=l.grid_flow(columns=4,even_columns=True,align=True)
        for identifier,label,group,kind,params in PRESETS:
            if group!=s.preset_group: continue
            col=grid.column(align=True); box=col.box()
            if icon(identifier): box.template_icon(icon_value=icon(identifier),scale=4)
            op=col.operator('blocksmith.preset',text=label,depress=s.preset==identifier)
            op.identifier=identifier; op.action='SELECT'


def size_row(layout,p,key,label):
    row=layout.row(align=True)
    op=row.operator('blocksmith.step',text='',icon='REMOVE'); op.key=key; op.direction=-1
    row.prop(p,key,text=label)
    op=row.operator('blocksmith.step',text='',icon='ADD'); op.key=key; op.direction=1


def draw_creation(l,context):
    s=context.scene.bs
    box=l.column()
    box.prop(s,'shape',text='Форма')
    if s.shape in {'DOOR','WINDOW','ARCH','STAIRS','RAMP'}:
        row=box.row(align=True)
        row.prop(s,'object_snap',text='Привязка',toggle=True)
        row.prop(s,'keep_drawing',text='Повторять',toggle=True)
        return
    row=box.row(align=True)
    row.prop(s,'draw_height',text='Высота')
    row.prop(s,'draw_depth',text='Толщина' if s.shape in {'WALL','DOOR','WINDOW','ARCH'} else 'Глубина')
    box.prop(s,'draw_width',text='Длина при щелчке')
    row=box.row(align=True)
    row.prop(s,'keep_drawing',text='Повторять',toggle=True)
    row.prop(s,'surfaces',text='На поверхности',toggle=True)
    row.prop(s,'object_snap',text='Привязка',toggle=True)
    if s.shape=='WALL':
        box.prop(s,'draw_chain',text='Соединять стены в цепочку')
        if s.draw_chain: box.prop(s,'joint_mode',text='Стык')
    header,curves=l.panel('blocksmith_curves',default_closed=True)
    header.label(text='Кривые стены',icon='CURVE_BEZCURVE')
    if curves:
        from .curves import MODES
        for mode,label,_ in MODES: curves.operator('blocksmith.curve',text=label).mode=mode
    row=box.row(align=True)
    row.operator('blocksmith.grid',text='÷2').factor=.5
    row.prop(s,'grid',text='Сетка'); row.operator('blocksmith.grid',text='×2').factor=2
    if not s.surfaces: box.prop(s,'draw_plane_z',text='Уровень основания')


def draw_tools(l,context):
    for choices in ((('WALL','Стена'),('FLOOR','Пол'),('ROOM','Комната')),
                    (('STAIRS','Лестница'),('RAMP','Пандус'),('BLOCK','Блок')),
                    (('DOOR','Дверь'),('WINDOW','Окно'),('ARCH','Арка'))):
        row=l.row(align=True)
        for kind,label in choices:
            op=row.operator('blocksmith.activate',text=label,depress=context.scene.bs.shape==kind)
            op.kind=kind
    kind=context.scene.bs.shape
    text=('Протяните проём прямо на стене' if kind in {'DOOR','WINDOW','ARCH'} else
          'От нижнего пола к верхнему краю' if kind in {'STAIRS','RAMP'} else 'Протяните конструкцию в сцене')
    l.label(text=text,icon='MOUSE_LMB')


def draw_main(l,context):
    from . import manual
    s=context.scene.bs
    if context.mode!='OBJECT':
        l.label(text='Tab → режим объектов',icon='INFO'); return
    from .drawing import ACTIVE, TOOL_ID
    tool=context.workspace.tools.from_space_view3d_mode('OBJECT',create=False)
    active=tool is not None and tool.idname==TOOL_ID
    row=l.row(align=True); row.scale_y=1.5
    row.operator('blocksmith.activate',text='Рисовать конструкции',icon='GREASEPENCIL',depress=active)
    if active or ACTIVE is not None: row.operator('blocksmith.stop',text='',icon='CANCEL')
    draw_tools(l,context)
    if BS_OT_row.poll(context):
        row=l.row(align=True)
        row.operator('blocksmith.row',text='Ряд объектов',icon='MOD_ARRAY')
        from .array_tool import opening_source
        if opening_source(context.active_object):row.operator('blocksmith.row',text='Ряд проёмов').opening=True
    preset=BY_ID.get(s.preset)
    row=l.row(align=True)
    if preset and icon(preset[0]): row.template_icon(icon_value=icon(preset[0]),scale=3)
    col=row.column(align=True)
    if preset: col.label(text=preset[1])
    col.popover(panel='BS_PT_catalog',text='Объекты с превью',icon='ASSET_MANAGER')
    header,body=l.panel('blocksmith_create',default_closed=context.active_object is not None)
    header.label(text='Следующая конструкция',icon='ADD')
    if body: draw_creation(body,context)
    if active:
        l.label(text='Протяните ЛКМ · Esc / ПКМ: выделение')
        if s.shape not in {'DOOR','WINDOW','ARCH','STAIRS','RAMP'}: l.label(text='H: высота · Ctrl: без привязки')
    warning=guard.message(context.scene)
    if warning:
        row=l.row(); row.alert=True; row.label(text=warning,icon='ERROR')
    obj=context.active_object
    if obj and obj.type=='MESH':
        box=l.box(); box.label(text='Свободное размещение',icon='UNLOCKED' if obj.bs.free_placement else 'LOCKED')
        row=box.row(align=True)
        row.operator('blocksmith.free_placement',text='Добавить метку').enabled=True
        row.operator('blocksmith.free_placement',text='Снять метку').enabled=False
        if obj.bs.free_placement: box.label(text='Метка включена · ограничения отключены')
    if BS_OT_attach.poll(context):
        contact=l.box(); contact.label(text='К грани: '+obj.name)
        contact.label(text='Оси основной детали; соседняя перемещается')
        for axis in 'XYZ':
            row=contact.row(align=True)
            for direction in (-1,1):
                op=row.operator('blocksmith.attach',text=('−' if direction<0 else '+')+axis)
                op.axis=axis; op.direction=direction
    walls=[o for o in context.selected_objects if o.type=='MESH' and o.bs.enabled and o.bs.kind in {'WALL','DOOR','WINDOW','ARCH'}]
    if len(walls)==2 and len(context.selected_objects)==2:
        joints=l.box(); joints.label(text='Стыки выделенных стен')
        joints.label(text='Основная: '+context.active_object.name)
        from .joints import MODES
        for mode,label,_ in MODES: joints.operator('blocksmith.join',text=label).mode=mode
    if obj and obj.type=='CURVE' and obj.get('bs_curve_wall'):
        box=l.box(); box.label(text=obj.name,icon='CURVE_BEZCURVE')
        box.prop(obj.bs,'depth',text='Толщина'); box.prop(obj.bs,'height',text='Высота')
        box.prop(obj.data,'resolution_u',text='Плавность')
        box.operator('object.mode_set',text='Редактировать точки и ручки (Tab)').mode='EDIT'
    if obj and obj.type=='MESH' and obj.bs.enabled:
        p=obj.bs; box=l.box(); box.label(text='Выбранный объект',icon='EDITMODE_HLT'); box.label(text=obj.name)
        if s.show_metrics:
            from .editing import metric_issues
            for issue in metric_issues(p,s,obj.matrix_world.to_scale()):
                row=box.row(); row.alert=True; row.label(text=issue,icon='ERROR')
        if manual(obj):
            box.label(text='Ручная правка меша — размеры защищены',icon='LOCKED')
            box.operator('blocksmith.tool',text='Сохранить как меш').action='BAKE'
            box.operator('blocksmith.tool',text='Сбросить ручные правки').action='RESET'
        else:
            for key,label in [('width','Длина'),('depth','Глубина'),('height','Высота')]: size_row(box,p,key,label)
            box.prop(s,'handles',text='Тянуть размеры в сцене')
            if 'STAIRS' in p.kind:
                box.prop(p,'auto_steps',text='Автоматические ступени')
                box.prop(p,'max_step' if p.auto_steps else 'steps',text='Высота шага' if p.auto_steps else 'Ступеней')
                box.prop(p,'flip',text='Развернуть')
                if p.kind in {'L_STAIRS','U_STAIRS'}: box.prop(p,'flight_width',text='Ширина марша')
            if p.kind=='ROOM': box.prop(p,'thickness',text='Пол и стены')
            if p.kind in {'CURVED_WALL','SPIRAL_STAIRS'}: box.prop(p,'angle',text='Угол поворота')
            if p.kind=='RAILING': box.prop(p,'spacing',text='Шаг стоек'); box.prop(p,'rails',text='Перекладины')
            if p.kind=='LADDER': box.prop(p,'spacing',text='Шаг перекладин')
            if p.kind=='ROOF': box.prop(p,'roof',text='Тип крыши')
            row=box.row(align=True)
            for axis in 'XY':
                op=row.operator('blocksmith.tool',text='Копия +'+axis); op.action='EXTEND'; op.axis=axis; op.direction=1
            box.label(text='Alt + кнопка ±: все выделенные',icon='INFO')
    elif not (obj and (obj.type=='MESH' or obj.get('bs_curve_wall'))): l.label(text='Выберите меш для проёма или редактирования',icon='INFO')
    row=l.row(align=True)
    row.operator('blocksmith.view',text='Текстуры',icon='TEXTURE').mode='TEXTURE'
    row.operator('blocksmith.view',text='Теги',icon='COLOR').mode='OBJECT'


class BS_OT_opening(bpy.types.Operator):
    bl_idname='blocksmith.opening'; bl_label='Изменить проём'; bl_options={'REGISTER','UNDO'}
    from .openings import VARIANTS
    variant: EnumProperty(items=VARIANTS)
    @classmethod
    def poll(cls,context):
        obj=context.active_object
        return context.mode=='OBJECT' and obj is not None and obj.type=='MESH' and obj.is_editable and not obj.get('bs_cutter')
    @guard.checked
    def execute(self,context):
        from .openings import set_variant
        try: set_variant(context,context.active_object,self.variant)
        except ValueError as exc:
            self.report({'WARNING'},str(exc)); return {'CANCELLED'}
        context.view_layer.update()
        return {'FINISHED'}


class BS_OT_view(bpy.types.Operator):
    bl_idname='blocksmith.view'; bl_label='Вид прототипа'
    mode: EnumProperty(items=[('TEXTURE','Текстуры',''),('OBJECT','Цветовые теги','')])
    @guard.checked
    def execute(self,context):
        texture_view(context)
        for area in context.screen.areas:
            if area.type=='VIEW_3D': area.spaces.active.shading.color_type=self.mode
        return {'FINISHED'}


class BS_PT_surface(bpy.types.Panel):
    bl_options={'DEFAULT_CLOSED'}
    bl_label='Текстуры Kenney'; bl_idname='BS_PT_surface'; bl_parent_id='BS_PT_main'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Blocksmith'
    def draw(self,context):
        s=context.scene.bs; l=self.layout
        l.prop(s,'palette',text='Цвет')
        l.template_icon_view(s,'texture',show_labels=True,scale=3,scale_popup=4)
        l.operator('blocksmith.texture',text='Применить к выделенным',icon='MATERIAL')
        obj=context.active_object
        if obj and obj.type=='MESH' and obj.bs.enabled:
            l.prop(obj.bs,'uv_tile',text='Размер плитки, м')
        l.label(text='Kenney · CC0 · сохраняется в GLB')


class BS_OT_audit(bpy.types.Operator):
    bl_idname='blocksmith.audit'; bl_label='Проверить геометрию'
    def execute(self,context):
        errors=guard.audit(context.scene)
        if errors:
            for obj in context.selected_objects: obj.select_set(False)
            for a,b,_ in errors:
                for obj in (a,b):
                    if obj is not None: obj.select_set(True)
            self.report({'WARNING'},'; '.join(e[2] for e in errors[:3]))
        else: self.report({'INFO'},'Пересечений и инверсии нет')
        return {'FINISHED'}


class BS_OT_activate(bpy.types.Operator):
    bl_idname='blocksmith.activate'; bl_label='Рисовать конструкции'
    bl_description='Протяните выбранную конструкцию в сцене. Esc / ПКМ — вернуться к выделению'
    kind: StringProperty(default='')
    @classmethod
    def poll(cls,context): return context.mode=='OBJECT' and context.area and context.area.type=='VIEW_3D'
    def execute(self,context):
        from .drawing import TOOL_ID
        if self.kind: context.scene.bs.shape=self.kind
        context.window_manager.keyconfigs.update()
        result=bpy.ops.wm.tool_set_by_id(name=TOOL_ID)
        context.workspace.tools.from_space_view3d_mode('OBJECT',create=False).refresh_from_context()
        context.area.tag_redraw()
        return result


class BS_OT_native_tool(bpy.types.Operator):
    # Keep the old operator name for saved shortcuts.
    bl_idname='blocksmith.native_tool'; bl_label='Рисовать конструкции'
    @classmethod
    def poll(cls,context): return BS_OT_activate.poll(context)
    def execute(self,context): return bpy.ops.blocksmith.activate()


class BS_OT_stop(bpy.types.Operator):
    bl_idname='blocksmith.stop'; bl_label='Вернуться к выделению'
    def execute(self,context):
        from .drawing import ACTIVE, leave_tool
        from .curves import ACTIVE as CURVE
        if CURVE is not None: CURVE.finish(context,{'CANCELLED'})
        if ACTIVE is not None: ACTIVE.stop_requested=True
        else: leave_tool(context)
        return {'FINISHED'}


UI_CLASSES=(BS_OT_row,BS_OT_activate,BS_OT_native_tool,BS_OT_stop,BS_OT_audit,BS_OT_preset,BS_OT_step,BS_OT_free_placement,BS_OT_attach,BS_OT_texture,BS_OT_resize,BS_GGT_resize,BS_PT_catalog,
            BS_OT_opening,BS_OT_view,BS_PT_surface)


def register_ui():
    global PREVIEWS
    PREVIEWS=bpy.utils.previews.new()
    folder=Path(__file__).parent/'assets'/'previews'
    for preset in PRESETS:
        path=folder/(preset[0]+'.png')
        if path.is_file(): PREVIEWS.load(preset[0],str(path),'IMAGE')
    for path in TEXTURES.glob('*/*.png'):
        PREVIEWS.load('tex_'+path.parent.name+'_'+path.stem[-2:],str(path),'IMAGE')
    from .drawing import BS_WST_draw
    bpy.utils.register_tool(BS_WST_draw,after={'builtin.primitive_cube_add'},separator=True)


def unregister_ui():
    global PREVIEWS
    from .array_tool import ACTIVE as ROW
    if ROW is not None:ROW.cleanup()
    from .drawing import ACTIVE
    from .curves import ACTIVE as CURVE
    if CURVE is not None: CURVE.finish(bpy.context,{'CANCELLED'})
    if ACTIVE is not None: ACTIVE.finish(bpy.context)
    from .drawing import BS_WST_draw, CHAIN, TOOL_ID
    for window in bpy.context.window_manager.windows:
        area=next((a for a in window.screen.areas if a.type=='VIEW_3D'),None)
        tool=window.workspace.tools.from_space_view3d_mode('OBJECT',create=False)
        if area and tool and tool.idname==TOOL_ID:
            with bpy.context.temp_override(window=window,area=area): bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
    bpy.utils.unregister_tool(BS_WST_draw)
    CHAIN.clear()
    if PREVIEWS: bpy.utils.previews.remove(PREVIEWS); PREVIEWS=None
