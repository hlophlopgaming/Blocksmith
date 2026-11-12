# SPDX-License-Identifier: GPL-3.0-or-later
"""Blocksmith: editable blockouts for Blender 5 and Godot."""
import bpy
import bmesh
import blf
import gpu
import math
import os
from pathlib import Path
from mathutils import Vector, Matrix
from bpy.props import (BoolProperty, FloatProperty, IntProperty, StringProperty,
                       EnumProperty, PointerProperty, FloatVectorProperty)
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from .geometry import build as raw_build, SHAPES, REFERENCES, wall_min_width
from . import guard
from .presets import PRESETS, BY_ID, GROUPS
from .editing import metric_issues, sync_references, reach
from .materials import PALETTES, PATTERNS, apply_texture, texture_changed, texture_items
from .joints import MODES as JOINT_MODES, BS_OT_join
from .curves import BS_OT_curve

bl_info = {'name':'Blocksmith','author':'Blocksmith contributors','version':(0,8,2),
           'blender':(5,0,0),'location':'View3D > Sidebar > Blocksmith','category':'Object'}
TAGS = {'BLOCKOUT':(.55,.55,.55,1),'WALKABLE':(.25,.65,.35,1),'WALL':(.55,.65,.8,1),
        'COVER':(.7,.5,.2,1),'CLIMBABLE':(.9,.65,.15,1),'INTERACTIVE':(.3,.8,.9,1),
        'HAZARD':(.85,.15,.12,1),'TRIGGER':(.7,.2,.8,1),'PROP':(.6,.4,.2,1),
        'OUT_OF_BOUNDS':(.15,.15,.2,1),'WATER':(.1,.4,.85,.45)}
SHAPE_LABELS=dict(zip(SHAPES,('Блок','Стена','Дверь','Окно','Арка','Пол','Лестница','Пандус','Цилиндр',
    'Угол','Лестница L','Лестница U','Дуговая стена','Винтовая лестница','Крыша','Низкое укрытие',
    'Высокое укрытие','Приставная лестница','Перила','Вода','Комната','Игрок','Игрок присев',
    'Линейка роста','Линейка прыжка','Габарит прохода')))
SHAPE_ITEMS=[(k,SHAPE_LABELS[k],'') for k in SHAPES]
BUSY=False
KEYMAPS=[]
DRAW_HANDLE=None


def build(p):
    from .mesh_cleanup import clean
    return clean(raw_build(p))


def signature(mesh):
    if isinstance(mesh,bpy.types.Curve):
        from .curves import signature as curve_signature
        return curve_signature(mesh)
    # Coordinates and topology detect manual changes, including same-size edits.
    import hashlib
    return hashlib.sha256(repr(([(tuple(v.co)) for v in mesh.vertices],
                               [tuple(f.vertices) for f in mesh.polygons])).encode()).hexdigest()


def manual(obj):
    return obj.bs.enabled and obj.get('bs_signature') != signature(obj.data)


def tag_object(obj, tag):
    obj.bs.tag=tag
    obj.color=TAGS[tag]
    if obj.bs.enabled and obj.bs.use_kenney:
        apply_texture(obj); return
    if obj.data.materials and not all(m and m.name.startswith('BS_') for m in obj.data.materials):
        return
    mat=bpy.data.materials.get('BS_'+tag)
    if not mat:
        mat=bpy.data.materials.new('BS_'+tag)
        mat.diffuse_color=TAGS[tag]
        mat.use_nodes=True
        nodes=mat.node_tree.nodes; links=mat.node_tree.links
        shader=nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value=TAGS[tag]
        shader.inputs['Roughness'].default_value=.8
        # UV grid survives glTF export; shader nodes themselves do not.
        image=bpy.data.images.get('BS_Grid')
        if not image:
            image=bpy.data.images.new('BS_Grid',width=128,height=128,alpha=True)
            pixels=[]
            for y in range(128):
                for x in range(128):
                    pixels.extend((.25,.25,.25,1) if min(x,y)<2 else (1,1,1,1))
            image.pixels=pixels; image.pack()
        tex=nodes.new('ShaderNodeTexImage'); tex.image=image; tex.interpolation='Closest'
        # Tint grid pixels per tag, using an ordinary texture supported by glTF.
        tinted=bpy.data.images.new('BS_Grid_'+tag,width=128,height=128,alpha=True)
        source=list(image.pixels); color=TAGS[tag]
        tinted.pixels=[source[i]*color[i%4] for i in range(len(source))]
        tinted.pack(); tex.image=tinted
        links.new(tex.outputs['Color'],shader.inputs['Base Color'])
        if tag=='WATER':
            shader.inputs['Alpha'].default_value=.45
            mat.surface_render_method='DITHERED'
    obj.data.materials.clear(); obj.data.materials.append(mat)


@guard.checked
def rebuild(obj, force=False):
    global BUSY
    if obj.mode!='OBJECT' or (not force and manual(obj)):
        return False
    p=obj.bs
    if not force and p.width<wall_min_width(p):
        saved=BUSY; BUSY=True
        try: p.width=wall_min_width(p)
        finally: BUSY=saved
    result=build(p)
    mesh=obj.data
    mesh.clear_geometry(); mesh.from_pydata(result.vertices,[],result.faces); mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    # Keep custom pivots through every parameter rebuild.
    for v in mesh.vertices:
        v.co-=Vector(p.pivot_offset)
    uv=mesh.uv_layers.new(name='UVMap') if not mesh.uv_layers else mesh.uv_layers.active
    for face in mesh.polygons:
        axis=max(range(3),key=lambda i:abs(face.normal[i]))
        axes=[i for i in range(3) if i!=axis]
        for li in face.loop_indices:
            co=mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv=(co[axes[0]]/p.uv_tile,co[axes[1]]/p.uv_tile)
    mesh.update(); obj['bs_signature']=signature(mesh)
    return True


def changed(self,context):
    if BUSY or not isinstance(self.id_data,bpy.types.Object): return
    obj=self.id_data
    from .openings import modifier, update
    try:
        with guard.transaction(context):
            if obj.get('bs_curve_wall'):
                from .curves import resize_profile
                resize_profile(obj)
            elif self.enabled: rebuild(obj)
            if modifier(obj): update(obj,context)
    except guard.ConstraintError: pass
    except ValueError as exc:
        if context.workspace: context.workspace.status_text_set('Blocksmith: '+str(exc))


def enum(items):
    return [(v,v.replace('_',' ').title(),'') for v in items]


class BSShape(bpy.types.PropertyGroup):
    enabled: BoolProperty(default=False)
    free_placement: BoolProperty(name='Свободное размещение',default=False,
        description='Разрешить пересечения, отражения и ручные правки без отката защитой Blocksmith')
    kind: EnumProperty(items=SHAPE_ITEMS,update=changed)
    tag: EnumProperty(items=enum(TAGS))
    width: FloatProperty(name='Width / Run',default=2,min=.01,max=10000,unit='LENGTH',update=changed)
    depth: FloatProperty(name='Depth / Flight',default=2,min=.01,max=10000,unit='LENGTH',update=changed)
    height: FloatProperty(name='Height',default=2,min=.01,max=10000,unit='LENGTH',update=changed)
    thickness: FloatProperty(default=.2,min=.005,max=100,unit='LENGTH',update=changed)
    open_width: FloatProperty(name='Opening Width',default=1,min=.01,unit='LENGTH',update=changed)
    open_height: FloatProperty(name='Opening Height',default=2.1,min=.01,unit='LENGTH',update=changed)
    sill: FloatProperty(default=1,min=0,unit='LENGTH',update=changed)
    offset: FloatProperty(default=0,unit='LENGTH',update=changed)
    miter_start: FloatProperty(default=0,min=-1000,max=1000,unit='LENGTH',update=changed)
    miter_end: FloatProperty(default=0,min=-1000,max=1000,unit='LENGTH',update=changed)
    count: IntProperty(name='Opening Count',default=1,min=1,max=100,update=changed)
    opening: EnumProperty(items=enum(['NONE','DOOR','WINDOW','ARCH','ARCH_WINDOW']),update=changed)
    cut_axis: EnumProperty(name='Направление выреза',items=enum(['X','Y','Z']),default='Y',update=changed)
    room_wall: EnumProperty(name='Стена комнаты',items=[('FRONT','Передняя (−Y)',''),('BACK','Задняя (+Y)',''),
        ('LEFT','Левая (−X)',''),('RIGHT','Правая (+X)','')],update=changed)
    arch_style: EnumProperty(items=[('ROUND','Полукруг',''),('SEGMENTAL','Пологая',''),('POINTED','Стрельчатая','')],update=changed)
    steps: IntProperty(default=12,min=1,max=512,update=changed)
    auto_steps: BoolProperty(name='Automatic Steps',default=True,update=changed)
    max_step: FloatProperty(name='Max Step',default=.25,min=.01,unit='LENGTH',update=changed)
    solid: BoolProperty(default=True,update=changed)
    flip: BoolProperty(default=False,update=changed)
    flight_width: FloatProperty(default=1,min=.1,unit='LENGTH',update=changed)
    angle: FloatProperty(name='Turn (degrees)',default=180,min=1,max=1440,update=changed)
    inner_radius: FloatProperty(default=.3,min=.01,unit='LENGTH',update=changed)
    column: BoolProperty(default=True,update=changed)
    segments: IntProperty(default=32,min=8,max=128,update=changed)
    roof: EnumProperty(items=enum(['GABLE','SHED']),update=changed)
    spacing: FloatProperty(default=.3,min=.05,unit='LENGTH',update=changed)
    rails: IntProperty(default=2,min=1,max=12,update=changed)
    use_kenney: BoolProperty(default=False)
    texture: EnumProperty(items=PATTERNS,default='13',update=texture_changed)
    palette: EnumProperty(items=PALETTES,default='Light',update=texture_changed)
    uv_tile: FloatProperty(default=1,min=.01,unit='LENGTH',update=changed)
    pivot_offset: FloatVectorProperty(size=3)
    player_height: FloatProperty(default=1.8)
    player_radius: FloatProperty(default=.3)
    crouch_height: FloatProperty(default=1.1)
    jump_height: FloatProperty(default=1)
    jump_gap: FloatProperty(default=3)
    low_cover: FloatProperty(default=1)
    high_cover: FloatProperty(default=1.7)


def grid_update(self,context):
    if context.screen and self.sync_grid:
        for area in context.screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.overlay.grid_scale=self.grid
    if context.scene:
        ts=context.scene.tool_settings
        ts.use_snap=self.move_snap; ts.snap_elements={'INCREMENT'}
        ts.use_snap_grid_absolute=True


def draw_shape_changed(self,context):
    from .drawing import shape_changed
    shape_changed(self,context)


class BSSettings(bpy.types.PropertyGroup):
    shape: EnumProperty(items=SHAPE_ITEMS,default='WALL',update=draw_shape_changed)
    preset: StringProperty(default='wall_4')
    preset_group: EnumProperty(items=GROUPS)
    handles: BoolProperty(name='Ручки размеров',default=True)
    palette: EnumProperty(items=PALETTES,default='Light')
    texture: EnumProperty(items=texture_items,default=12)
    grid: FloatProperty(default=.5,min=.001,max=1000,unit='LENGTH',update=grid_update)
    sync_grid: BoolProperty(default=True,update=grid_update)
    move_snap: BoolProperty(name='Move Snapping',default=False,update=grid_update)
    surfaces: BoolProperty(name='On Surfaces',default=True)
    object_snap: BoolProperty(name='Snap to Vertices',default=True)
    keep_drawing: BoolProperty(default=True)
    draw_width: FloatProperty(name='Длина',default=4,min=.01,max=10000,unit='LENGTH')
    draw_depth: FloatProperty(name='Глубина / толщина',default=.2,min=.01,max=10000,unit='LENGTH')
    draw_height: FloatProperty(name='Высота',default=3,min=.01,max=10000,unit='LENGTH')
    draw_plane_z: FloatProperty(name='Уровень основания',default=0,min=-10000,max=10000,unit='LENGTH')
    draw_chain: BoolProperty(name='Цепочка стен',default=False)
    joint_mode: EnumProperty(name='Стык стен',items=JOINT_MODES)
    dimensions: BoolProperty(default=True)
    show_metrics: BoolProperty(name='Подсказки масштаба',default=True)
    wall_height: FloatProperty(default=3,min=.1,unit='LENGTH')
    wall_thickness: FloatProperty(default=.2,min=.01,unit='LENGTH')
    floor_thickness: FloatProperty(default=.2,min=.01,unit='LENGTH')
    door_width: FloatProperty(default=1,min=.1,unit='LENGTH')
    door_height: FloatProperty(default=2.1,min=.1,unit='LENGTH')
    water_depth: FloatProperty(default=1,min=.01,unit='LENGTH')
    player_height: FloatProperty(default=1.8,min=.1,unit='LENGTH',update=sync_references)
    player_radius: FloatProperty(default=.3,min=.05,unit='LENGTH',update=sync_references)
    crouch_height: FloatProperty(default=1.1,min=.1,unit='LENGTH',update=sync_references)
    max_step: FloatProperty(default=.25,min=.01,unit='LENGTH',update=sync_references)
    jump_height: FloatProperty(default=1,min=.01,unit='LENGTH',update=sync_references)
    jump_gap: FloatProperty(default=3,min=.01,unit='LENGTH',update=sync_references)
    max_slope: FloatProperty(default=45,min=1,max=89)
    low_cover: FloatProperty(default=1,min=.01,unit='LENGTH',update=sync_references)
    high_cover: FloatProperty(default=1.7,min=.01,unit='LENGTH',update=sync_references)
    max_wade: FloatProperty(default=.5,min=0,unit='LENGTH')
    min_swim: FloatProperty(default=1.2,min=.01,unit='LENGTH')
    export_format: EnumProperty(items=enum(['GLB','FBX']))
    collision: BoolProperty(name='Godot Collision (-col)',default=True)
    export_scope: EnumProperty(items=enum(['COLLECTION','SELECTED','VISIBLE']))
    per_object: BoolProperty(default=False)
    center: BoolProperty(name='Center Individual Pieces',default=True)
    export_path: StringProperty(subtype='DIR_PATH',default='//export/')
    filename: StringProperty(default='blockout')
    prefix: StringProperty(default='')


def collection(context):
    coll=context.scene.collection.children.get('Blocksmith')
    if not coll:
        coll=bpy.data.collections.new('Blocksmith'); context.scene.collection.children.link(coll)
    return coll


@guard.checked
def create(context,kind):
    global BUSY
    s=context.scene.bs
    obj=bpy.data.objects.new('BS_'+kind.title(),bpy.data.meshes.new('BS_Mesh'))
    collection(context).objects.link(obj)
    obj['bs_managed']=True
    p=obj.bs
    BUSY=True
    try:
        p.enabled=True; p.kind=kind
        for key in ('player_height','player_radius','crouch_height','max_step','jump_height',
                    'jump_gap','low_cover','high_cover'):
            setattr(p,key,getattr(s,key))
        p.height=s.wall_height
        p.thickness=s.wall_thickness
        p.open_width=s.door_width; p.open_height=s.door_height
        if kind in {'WALL','DOOR','WINDOW','ARCH','RAILING','LADDER'}: p.depth=s.wall_thickness
        if kind=='FLOOR': p.height=s.floor_thickness
        if kind=='WATER': p.height=s.water_depth
        if kind=='WINDOW': p.open_height=1
        if kind=='LOW_COVER': p.height=s.low_cover
        if kind=='HIGH_COVER': p.height=s.high_cover
        if kind in {'PLAYER','CROUCH'}:
            p.width=p.depth=s.player_radius*2
            p.height=s.player_height if kind=='PLAYER' else s.crouch_height
        if kind=='HEIGHT_RULER': p.height=s.player_height
        tag=('WALL' if kind in {'WALL','DOOR','WINDOW','ARCH','CORNER','CURVED_WALL'} else
             'WALKABLE' if kind in {'FLOOR','STAIRS','L_STAIRS','U_STAIRS','SPIRAL_STAIRS','RAMP'} else
             'COVER' if kind.endswith('COVER') else 'CLIMBABLE' if kind=='LADDER' else
             'WATER' if kind=='WATER' else 'BLOCKOUT')
        tag_object(obj,tag)
    finally: BUSY=False
    rebuild(obj,True)
    p.use_kenney=True; p.palette=s.palette; p.texture=s.texture
    apply_texture(obj)
    obj.location=context.scene.cursor.location
    for other in context.selected_objects: other.select_set(False)
    obj.select_set(True); context.view_layer.objects.active=obj
    return obj


class BS_OT_add(bpy.types.Operator):
    bl_idname='blocksmith.add'
    bl_label='Add Blocksmith Shape'
    bl_options={'REGISTER','UNDO'}
    kind: EnumProperty(items=SHAPE_ITEMS)
    @guard.checked
    def execute(self,context):
        create(context,self.kind); return {'FINISHED'}


def bounds(obj):
    return [obj.matrix_world@Vector(v) for v in obj.bound_box]


@guard.checked
def set_pivot(obj,world):
    edited=manual(obj)
    local=obj.matrix_world.inverted()@world
    obj.data.transform(Matrix.Translation(-local))
    obj.matrix_world=obj.matrix_world@Matrix.Translation(local)
    obj.bs.pivot_offset=Vector(obj.bs.pivot_offset)+local
    if not edited: obj['bs_signature']=signature(obj.data)


class BS_OT_tool(bpy.types.Operator):
    bl_idname='blocksmith.tool'
    bl_label='Blocksmith Tool'
    bl_options={'REGISTER','UNDO'}
    action: EnumProperty(items=enum(['SNAP','FIT','BAKE','RESET','CUT','ASSET','APPLY_SCALE',
                                   'PIVOT','PIVOT_CURSOR','CURSOR_PIVOT','EXTEND','CONVERT','METRICS','VIEW']))
    axis: EnumProperty(items=enum(['X','Y','Z']))
    direction: IntProperty(default=1,min=-1,max=1)
    count: IntProperty(default=1,min=1,max=100)
    gap: FloatProperty(default=0,unit='LENGTH')
    pivot: FloatVectorProperty(default=(.5,.5,0),size=3,min=0,max=1)

    @classmethod
    def poll(cls,context): return context.mode=='OBJECT'

    @guard.checked
    def execute(self,context):
        global BUSY
        objects=list(context.selected_objects); active=context.active_object
        s=context.scene.bs; g=s.grid
        if self.action=='VIEW':
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type=='VIEW_3D':
                        shade=area.spaces.active.shading
                        shade.type='SOLID'; shade.color_type='OBJECT'; shade.show_cavity=True
            return {'FINISHED'}
        if self.action=='METRICS':
            targets=objects or [o for o in context.visible_objects if o.type=='MESH']
            failures=[]
            for o in targets:
                if o.type!='MESH' or not o.bs.enabled: continue
                problems=metric_issues(o.bs,s,o.matrix_world.to_scale())
                o.select_set(bool(problems))
                if problems: failures.append(o.name+': '+', '.join(problems))
            self.report({'WARNING'} if failures else {'INFO'},'; '.join(failures[:4]) or 'Metrics OK')
            return {'FINISHED'}
        if self.action=='CUT':
            if not active or active.type!='MESH': return {'CANCELLED'}
            for o in objects:
                if o==active or o.type!='MESH': continue
                if active in list(o.children_recursive):
                    self.report({'ERROR'},'Cannot use an ancestor as a cutter'); return {'CANCELLED'}
                mod=active.modifiers.new('BS_Cut','BOOLEAN'); mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=o
                o['bs_cutter']=True; o.display_type='WIRE'; o.hide_render=True
                world=o.matrix_world.copy(); o.parent=active; o.matrix_world=world
            return {'FINISHED'}
        for obj in objects:
            if obj.type!='MESH' or obj.mode!='OBJECT': continue
            p=obj.bs
            if self.action in {'SNAP','FIT'}:
                if self.action=='FIT' and p.enabled and not manual(obj):
                    BUSY=True
                    try:
                        for key in ('width','depth','height'):
                            value=getattr(p,key)
                            if value>=g: setattr(p,key,max(g,round(value/g)*g))
                    finally: BUSY=False
                    rebuild(obj)
                for i in range(3):
                    obj.location[i]=round(obj.location[i]/g)*g
                    obj.rotation_euler[i]=round(obj.rotation_euler[i]/(math.pi/2))*(math.pi/2)
            elif self.action=='RESET' and p.enabled: rebuild(obj,True)
            elif self.action=='BAKE':
                mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(context.evaluated_depsgraph_get()))
                old=obj.data; obj.modifiers.clear(); obj.data=mesh
                if p.enabled and p.kind in REFERENCES|{'WATER'}: obj['bs_role']=p.kind
                p.enabled=False
                if not old.users: bpy.data.meshes.remove(old)
            elif self.action=='APPLY_SCALE':
                if p.enabled and (any(x<=0 for x in obj.scale) or obj.data.users>1 or manual(obj)):
                    self.report({'WARNING'},'Apply Scale requires an unedited, single-user shape with positive scale'); continue
                if p.enabled:
                    # Nonuniform scale cannot preserve curved/arch profiles parametrically.
                    if max(obj.scale)-min(obj.scale)>1e-5:
                        self.report({'WARNING'},'Use uniform scale, or bake before applying nonuniform scale'); continue
                    BUSY=True
                    try:
                        f=obj.scale.x
                        for key in ('width','depth','height','thickness','open_width','open_height','sill','offset',
                                    'flight_width','inner_radius','spacing','max_step'):
                            setattr(p,key,getattr(p,key)*f)
                        p.pivot_offset=Vector(p.pivot_offset)*f
                    finally: BUSY=False
                    obj.scale=(1,1,1); rebuild(obj,True)
            elif self.action in {'PIVOT','PIVOT_CURSOR'}:
                if obj.data.users>1: obj.data=obj.data.copy()
                if self.action=='PIVOT_CURSOR': point=context.scene.cursor.location.copy()
                else:
                    bb=bounds(obj)
                    point=Vector([min(v[i] for v in bb)+(max(v[i] for v in bb)-min(v[i] for v in bb))*self.pivot[i] for i in range(3)])
                set_pivot(obj,point)
            elif self.action=='CURSOR_PIVOT': context.scene.cursor.location=obj.matrix_world.translation
            elif self.action=='ASSET' and not obj.get('bs_cutter') and p.kind not in REFERENCES:
                obj.asset_mark(); obj.asset_data.description='Blocksmith '+p.kind
                for name in ('Blocksmith',p.kind,p.tag): obj.asset_data.tags.new(name)
                obj.asset_generate_preview()
            elif self.action=='EXTEND':
                index='XYZ'.index(self.axis); bb=bounds(obj)
                length=max(v[index] for v in bb)-min(v[index] for v in bb)+self.gap
                for n in range(1,self.count+1):
                    copy=obj.copy(); copy.data=obj.data.copy()
                    context.collection.objects.link(copy)
                    copy.location[index]+=length*n*self.direction
                    for child in obj.children:
                        if not child.get('bs_cutter'): continue
                        cutter=child.copy(); cutter.data=child.data.copy(); context.collection.objects.link(cutter)
                        cutter.parent=copy
                        for mod in copy.modifiers:
                            if mod.type=='BOOLEAN' and mod.object==child: mod.object=cutter
            elif self.action=='CONVERT':
                bb=bounds(obj); low=Vector([min(v[i] for v in bb) for i in range(3)])
                high=Vector([max(v[i] for v in bb) for i in range(3)])
                new=create(context,'BLOCK'); BUSY=True
                try: new.bs.width,new.bs.depth,new.bs.height=high-low
                finally: BUSY=False
                new.location=low; rebuild(new,True); obj.hide_set(True); obj.hide_render=True
                obj['bs_source_backup']=True; new['bs_source']=obj
        return {'FINISHED'}


class BS_OT_tag(bpy.types.Operator):
    bl_idname='blocksmith.tag'; bl_label='Set Gameplay Tag'; bl_options={'REGISTER','UNDO'}
    tag: EnumProperty(items=enum(TAGS))
    select: BoolProperty(default=False)
    @guard.checked
    def execute(self,context):
        for o in context.visible_objects if self.select else context.selected_objects:
            if o.type!='MESH': continue
            if self.select: o.select_set(o.bs.tag==self.tag)
            else: tag_object(o,self.tag)
        return {'FINISHED'}


class BS_OT_grid(bpy.types.Operator):
    bl_idname='blocksmith.grid'; bl_label='Change Grid'; bl_options={'UNDO'}
    factor: FloatProperty(default=2)
    @guard.checked
    def execute(self,context):
        context.scene.bs.grid=max(.001,min(1000,context.scene.bs.grid*self.factor))
        return {'FINISHED'}


def pick(context,event):
    from .drawing import surface_hit
    target=surface_hit(context,event)
    return target[0].translation.copy() if target is not None else None


from .drawing import BS_OT_draw


class BS_OT_export(bpy.types.Operator):
    bl_idname='blocksmith.export'; bl_label='Export for Godot'; bl_options={'REGISTER'}
    @guard.checked
    def execute(self,context):
        s=context.scene.bs
        try: guard.require_valid(context.scene)
        except guard.ConstraintError as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}
        if s.export_path.startswith('//') and not bpy.data.filepath:
            self.report({'ERROR'},'Save the .blend or choose an absolute export folder'); return {'CANCELLED'}
        folder=Path(bpy.path.abspath(s.export_path)).expanduser()
        source=(context.selected_objects if s.export_scope=='SELECTED' else
                collection(context).all_objects if s.export_scope=='COLLECTION' else context.visible_objects)
        source=[o for o in source if (o.type=='MESH' or (o.type=='CURVE' and o.get('bs_curve_wall'))) and o.visible_get() and not guard.excluded(o,context.scene,include_water=True)]
        if not source:
            self.report({'ERROR'},'Nothing to export'); return {'CANCELLED'}
        selected=list(context.selected_objects); active=context.view_layer.objects.active
        temp=bpy.data.collections.new('BS_Export_Temp'); context.scene.collection.children.link(temp)
        copies=[]
        try:
            folder.mkdir(parents=True,exist_ok=True)
            for o in selected: o.select_set(False)
            for original in source:
                mesh=bpy.data.meshes.new_from_object(original.evaluated_get(context.evaluated_depsgraph_get()))
                # Temporary copies: exported naming, transforms and collision never alter the source.
                role=original.bs.kind if original.bs.enabled else original.get('bs_role')
                copy=bpy.data.objects.new(original.name+('-col' if s.collision and original.bs.tag!='WATER' and role!='WATER' else ''),mesh)
                temp.objects.link(copy); copy.matrix_world=original.matrix_world.copy(); copies.append(copy)
            groups=[[o] for o in copies] if s.per_object else [copies]
            used=set()
            for group in groups:
                for o in copies: o.select_set(o in group)
                if s.per_object and s.center: group[0].location=(0,0,0)
                name=s.prefix+(source[copies.index(group[0])].name if s.per_object else s.filename)
                name=bpy.path.clean_name(name).strip('.') or 'blockout'
                if name in used: raise ValueError('Export filenames collide after sanitizing: '+name)
                used.add(name)
                path=str(folder/(name+'.'+s.export_format.lower()))
                if os.path.exists(path):
                    raise FileExistsError('Export exists; choose another filename or folder: '+path)
                if s.export_format=='GLB':
                    bpy.ops.export_scene.gltf(filepath=path,export_format='GLB',use_selection=True,
                                              export_apply=True,export_animations=False,export_extras=True)
                else:
                    bpy.ops.export_scene.fbx(filepath=path,use_selection=True,object_types={'MESH'},
                                             axis_forward='-Z',axis_up='Y',bake_anim=False)
        except Exception as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}
        finally:
            for o in copies:
                mesh=o.data; bpy.data.objects.remove(o,do_unlink=True)
                if not mesh.users: bpy.data.meshes.remove(mesh)
            bpy.data.collections.remove(temp)
            for o in selected: o.select_set(True)
            context.view_layer.objects.active=active
        self.report({'INFO'},'Exported to '+str(folder)); return {'FINISHED'}


class BS_MT_add(bpy.types.Menu):
    bl_idname='BS_MT_add'; bl_label='Blocksmith'
    def draw(self,context):
        for key,label,_ in SHAPE_ITEMS:
            self.layout.operator('blocksmith.add',text=label).kind=key


class BS_MT_pie(bpy.types.Menu):
    bl_idname='BS_MT_pie'; bl_label='Blocksmith'
    def draw(self,context):
        pie=self.layout.menu_pie()
        pie.operator('blocksmith.activate',text='Рисовать конструкции')
        for key in ('BLOCK','WALL','FLOOR','STAIRS','RAMP','ROOM'):
            pie.operator('blocksmith.activate',text=SHAPE_LABELS[key]).kind=key
        pie.operator('blocksmith.export',text='Export GLB')


class BS_PT_main(bpy.types.Panel):
    bl_label='Blocksmith'; bl_idname='BS_PT_main'; bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Blocksmith'
    def draw(self,context):
        from .ui import draw_main
        draw_main(self.layout,context)


class BS_PT_tools(bpy.types.Panel):
    bl_label='Дополнительные инструменты'; bl_idname='BS_PT_tools'; bl_parent_id='BS_PT_main'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Blocksmith'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        l=self.layout
        box=l.box(); box.label(text='Инструменты выделенных объектов')
        box.operator('blocksmith.audit',text='Проверить геометрию',icon='VIEWZOOM')
        for key,label in [('SNAP','Snap to Grid'),('FIT','Fit Size to Grid'),('APPLY_SCALE','Apply Uniform Scale'),
                          ('CUT','Cut Active with Selected'),('BAKE','Bake to Mesh'),('CONVERT','Make Editable Block'),
                          ('ASSET','Mark as Asset'),('METRICS','Check Metrics'),('PIVOT_CURSOR','Pivot to Cursor'),
                          ('CURSOR_PIVOT','Cursor to Pivot')]:
            box.operator('blocksmith.tool',text=label).action=key
        row=box.row(align=True)
        for z,label in [(0,'Bottom'),(.5,'Center'),(1,'Top')]:
            op=row.operator('blocksmith.tool',text=label); op.action='PIVOT'; op.pivot=(.5,.5,z)
        for axis in 'XYZ':
            row=box.row(align=True)
            for sign in (-1,1):
                op=row.operator('blocksmith.tool',text=f'Extend {"+" if sign>0 else "−"}{axis}')
                op.action='EXTEND'; op.axis=axis; op.direction=sign




class BS_PT_tags(bpy.types.Panel):
    bl_label='Теги объектов'; bl_idname='BS_PT_tags'; bl_parent_id='BS_PT_main'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Blocksmith'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        for tag in TAGS:
            row=self.layout.row(align=True)
            row.operator('blocksmith.tag',text=tag.replace('_',' ').title()).tag=tag
            op=row.operator('blocksmith.tag',text='',icon='RESTRICT_SELECT_OFF'); op.tag=tag; op.select=True


class BS_PT_metrics(bpy.types.Panel):
    bl_label='Размеры персонажа и стандарты'; bl_idname='BS_PT_metrics'; bl_parent_id='BS_PT_main'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Blocksmith'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        self.layout.prop(context.scene.bs,'show_metrics',text='Подсказки в сцене')
        for key in ('player_height','player_radius','crouch_height','max_step','jump_height','jump_gap',
                    'max_slope','low_cover','high_cover','max_wade','min_swim','wall_height','wall_thickness',
                    'floor_thickness','door_width','door_height','water_depth'):
            self.layout.prop(context.scene.bs,key)
        self.layout.operator('blocksmith.tool',text='Check Metrics').action='METRICS'


class BS_PT_export(bpy.types.Panel):
    bl_label='Экспорт в Godot'; bl_idname='BS_PT_export'; bl_parent_id='BS_PT_main'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Blocksmith'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        s=context.scene.bs
        for key in ('export_format','export_scope','export_path','filename','prefix','per_object','center','collision'):
            self.layout.prop(s,key)
        self.layout.operator('blocksmith.export',icon='EXPORT')


def draw_dimensions():
    context=bpy.context
    if not context.scene.bs.dimensions or not context.region_data: return
    for obj in context.selected_objects:
        if obj.type!='MESH' or not obj.bs.enabled: continue
        point=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,obj.matrix_world.translation)
        if point is None: continue
        p=obj.bs; dims=(p.width,p.depth,p.height)
        lines=[f'{dims[0]:.2f} × {dims[1]:.2f} × {dims[2]:.2f} м']
        if context.scene.bs.show_metrics: lines.extend(metric_issues(p,context.scene.bs,obj.matrix_world.to_scale()))
        blf.size(0,12); blf.enable(0,blf.SHADOW); blf.shadow(0,5,0,0,0,1)
        for i,line in enumerate(lines):
            blf.position(0,point.x+8,point.y+8+i*18,0); blf.color(0,1,.45,.2,1) if i else blf.color(0,1,.85,.4,1)
            blf.draw(0,line)
        blf.disable(0,blf.SHADOW)
        if context.scene.bs.show_metrics and p.kind in {'BLOCK','LOW_COVER','HIGH_COVER','FLOOR'} and len(context.selected_objects)<=3:
            base,top,height,x,y=reach(context,obj)
            a=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,Vector((x,y,base)))
            b=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,Vector((x,y,top)))
            if a is None or b is None: continue
            s=context.scene.bs
            label,color=('Шаг',(.3,1,.35,1)) if height<=s.max_step else ('Прыжок',(1,.8,.15,1)) if height<=s.jump_height else ('Выше прыжка',(1,.25,.15,1))
            shader=gpu.shader.from_builtin('UNIFORM_COLOR')
            batch=batch_for_shader(shader,'LINES',{'pos':[(a.x,a.y),(b.x,b.y),(a.x-5,a.y),(a.x+5,a.y),(b.x-5,b.y),(b.x+5,b.y)]})
            shader.bind(); shader.uniform_float('color',color); batch.draw(shader)
            blf.position(0,b.x+8,b.y,0); blf.color(0,*color); blf.draw(0,f'{label} {height:.2f} м')


def menu_add(self,context): self.layout.menu('BS_MT_add')

from .ui import UI_CLASSES, register_ui, unregister_ui

CLASSES=(BSShape,BSSettings,BS_OT_add,BS_OT_tool,BS_OT_tag,BS_OT_grid,BS_OT_draw,BS_OT_curve,BS_OT_join,BS_OT_export,
         BS_MT_add,BS_MT_pie,BS_PT_main,BS_PT_tools,BS_PT_tags,BS_PT_metrics,BS_PT_export)+UI_CLASSES


def register():
    global DRAW_HANDLE
    for cls in CLASSES: bpy.utils.register_class(cls)
    bpy.types.Object.bs=PointerProperty(type=BSShape)
    bpy.types.Scene.bs=PointerProperty(type=BSSettings)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_add)
    keyconfig=bpy.context.window_manager.keyconfigs.addon
    if keyconfig:
        km=keyconfig.keymaps.new(name='Object Mode',space_type='EMPTY')
        for operator,key in [('blocksmith.activate','D'),('wm.call_menu_pie','B')]:
            item=km.keymap_items.new(operator,key,'PRESS',shift=True,alt=True)
            if operator=='wm.call_menu_pie': item.properties.name='BS_MT_pie'
            KEYMAPS.append((km,item))
    register_ui()
    guard.register()
    DRAW_HANDLE=bpy.types.SpaceView3D.draw_handler_add(draw_dimensions,(),'WINDOW','POST_PIXEL')


def unregister():
    global DRAW_HANDLE
    guard.unregister()
    unregister_ui()
    from .mesh_cleanup import union
    union.cache_clear()
    if DRAW_HANDLE: bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLE,'WINDOW'); DRAW_HANDLE=None
    for km,item in KEYMAPS: km.keymap_items.remove(item)
    KEYMAPS.clear()
    bpy.types.VIEW3D_MT_mesh_add.remove(menu_add)
    del bpy.types.Object.bs; del bpy.types.Scene.bs
    for cls in reversed(CLASSES): bpy.utils.unregister_class(cls)
