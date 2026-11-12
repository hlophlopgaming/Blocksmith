# SPDX-License-Identifier: GPL-3.0-or-later
"""Use Blender's own Add Cube interaction; adopt its completed result as a module."""
from .translations import tr
import bpy
from bpy.app.handlers import persistent
from mathutils import Vector
from . import guard
from .presets import BY_ID

SEEN={}
HISTORY={}
RESTORING=False


def adopt(context,obj,preset):
    from .ui import apply_preset
    from . import rebuild, build
    import sys
    core=sys.modules[__package__]
    low=Vector([min(v.co[i] for v in obj.data.vertices) for i in range(3)])
    high=Vector([max(v.co[i] for v in obj.data.vertices) for i in range(3)])
    size=high-low
    if min(size)<=.00001: raise guard.ConstraintError('The module has zero size')
    with guard.transaction(context):
        temp=apply_preset(context,preset)
        core.BUSY=True
        try:
            for key,value in guard.props(temp.bs).items():
                if key!='free_placement': setattr(obj.bs,key,value)
            obj.bs.width,obj.bs.depth,obj.bs.height=size
            obj.bs.pivot_offset=(0,0,0)
            shape=build(obj.bs)
            generated=Vector([min(v[i] for v in shape.vertices) for i in range(3)])
            obj.bs.pivot_offset=generated-low
            obj.data.materials.clear()
            for mat in temp.data.materials: obj.data.materials.append(mat)
            obj.color=temp.color
            obj['bs_managed']=True; obj['bs_preset']=preset
        finally: core.BUSY=False
        mesh=temp.data; bpy.data.objects.remove(temp,do_unlink=True)
        if not mesh.users: bpy.data.meshes.remove(mesh)
        rebuild(obj,True)
        obj.select_set(True); context.view_layer.objects.active=obj


def tick():
    global RESTORING
    if bpy.app.is_job_running('RENDER'): return .05
    for window in bpy.context.window_manager.windows:
        scene=window.scene
        tool=window.workspace.tools.from_space_view3d_mode('OBJECT',create=False)
        record=SEEN.get(window.as_pointer())
        active=bool(record and record.get('enabled')) and tool is not None and tool.idname=='builtin.primitive_cube_add'
        key=window.as_pointer()
        ids={o.session_uid for o in scene.objects}
        record=SEEN.get(key)
        running=any(o.bl_idname=='VIEW3D_OT_interactive_add' for o in window.modal_operators)
        if record is None or record['scene']!=scene.session_uid:
            SEEN[key]={'scene':scene.session_uid,'ids':ids,'running':False,'preset':scene.bs.preset,'enabled':False}
            continue
        if active and running:
            record['running']=True; record['preset']=scene.bs.preset
            continue
        if not active and not record['running']: record['enabled']=False
        last=bpy.context.window_manager.operators[-1].bl_idname if bpy.context.window_manager.operators else ''
        native=record['running'] or (active and last=='VIEW3D_OT_interactive_add')
        new=[o for o in scene.objects if o.type=='MESH' and o.session_uid not in record['ids']]
        redo=[o for o in scene.objects if o.type=='MESH' and o.session_uid in HISTORY and not o.bs.enabled] if RESTORING else []
        area=next((a for a in window.screen.areas if a.type=='VIEW_3D'),None)
        if area:
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(window=window,area=area,region=region):
                for obj in (new if native else [])+redo:
                    if obj.bs.enabled: continue
                    preset=HISTORY.get(obj.session_uid,record['preset'])
                    if preset not in BY_ID: preset='wall_4'
                    HISTORY[obj.session_uid]=preset
                    try:
                        adopt(bpy.context,obj,preset)
                    except guard.ConstraintError as exc:
                        mesh=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
                        if mesh.users==0: bpy.data.meshes.remove(mesh)
                        window.workspace.status_text_set('Blocksmith: '+tr(str(exc)))
        record['ids']={o.session_uid for o in scene.objects}; record['running']=False; record['preset']=scene.bs.preset
    RESTORING=False
    return .03


@persistent
def redo(*args):
    global RESTORING
    RESTORING=True


def prime(context):
    SEEN[context.window.as_pointer()]={'scene':context.scene.session_uid,'ids':{o.session_uid for o in context.scene.objects},'running':False,'preset':context.scene.bs.preset,'enabled':True}


def register():
    bpy.app.timers.register(tick,first_interval=.03,persistent=True)
    bpy.app.handlers.redo_post.append(redo)


def unregister():
    if bpy.app.timers.is_registered(tick): bpy.app.timers.unregister(tick)
    if redo in bpy.app.handlers.redo_post: bpy.app.handlers.redo_post.remove(redo)
    SEEN.clear(); HISTORY.clear()
