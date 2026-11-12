# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared constraints for operators, native transforms, scripts and export."""
from contextlib import contextmanager
from functools import wraps
import sys
import bpy
from bpy.app.handlers import persistent
from .collision import Solid, overlaps, GeometryError, EPS
from .geometry import REFERENCES

class ConstraintError(ValueError): pass

_states={}
_messages={}
_backups=[]
_surfaces={}
_dirty=set()
_depth=0
_checking=False
_history=None
_history_reverting=False
_bootstrap=False


def core(): return sys.modules[__package__]


def managed(obj):
    return ((obj.type=='MESH' and (obj.bs.enabled or obj.get('bs_managed',False))) or
            (obj.type=='CURVE' and obj.get('bs_curve_wall'))) and not obj.get('bs_guard_temp')


def excluded(obj,scene,*,include_water=False):
    if obj.get('bs_guard_temp') or obj.get('bs_opening') or obj.get('bs_drawn_opening'): return True
    if obj.get('bs_source_backup') and obj.hide_get() and obj.hide_render:
        if any(o.get('bs_source')==obj for o in scene.objects): return True
    role=obj.bs.kind if obj.bs.enabled else obj.get('bs_role')
    if role in REFERENCES or (role=='WATER' and not include_water): return True
    if obj.get('bs_cutter'):
        return any(m.type=='BOOLEAN' and m.object==obj for o in scene.objects for m in o.modifiers)
    return False


def props(p):
    return {prop.identifier:(tuple(getattr(p,prop.identifier)) if getattr(prop,'is_array',False) else getattr(p,prop.identifier))
            for prop in p.bl_rna.properties if prop.identifier not in {'rna_type','name'} and not prop.is_readonly}


def matrix_key(matrix): return tuple(round(v,7) for row in matrix for v in row)


def capture(scene,previous=None):
    result={}; previous=previous or {}
    dg=bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.get('bs_guard_temp'): continue
        key=obj.as_pointer(); old=previous.get(key)
        geometry=obj.type=='MESH' or (obj.type=='CURVE' and obj.get('bs_curve_wall'))
        raw=core().signature(obj.data) if geometry else None
        stamp=raw
        if geometry and (obj.modifiers or obj.type=='CURVE'):
            evaluated=obj.evaluated_get(dg); mesh=evaluated.to_mesh()
            try: stamp=core().signature(mesh)
            finally: evaluated.to_mesh_clear()
        backup=old['backup'] if old and old['raw']==raw and (obj.type!='CURVE' or old['stamp']==stamp) else None
        if geometry and backup is None:
            backup=obj.data.copy(); backup.name='__BS_guard_backup'; _backups.append(backup)
        result[key]={'obj':obj,'name':obj.name,'uid':obj.session_uid,'raw':raw,'stamp':stamp,'backup':backup,
                     'free':obj.bs.free_placement,
                     'basis':obj.matrix_basis.copy(),'world':obj.matrix_world.copy(),
                     'parent':obj.parent,'inverse':obj.matrix_parent_inverse.copy(),
                     'params':props(obj.bs) if managed(obj) else None,
                     'signature':obj.get('bs_signature'),'selected':obj.select_get(),
                     'active':bpy.context.view_layer.objects.active==obj,
                     'arrays':[(m.name,m.count,m.use_relative_offset,m.use_constant_offset,tuple(m.constant_offset_displace),tuple(m.relative_offset_displace)) for m in obj.modifiers if m.type=='ARRAY'],
                     'booleans':[(m.name,m.operation,m.solver,m.object,m.use_self,m.show_viewport)
                                 for m in obj.modifiers if m.type=='BOOLEAN']}
    return result


def cleanup():
    live={obj.session_uid for obj in bpy.data.objects}
    for uid in list(_surfaces):
        if uid not in live: del _surfaces[uid]
    used=set()
    for states in _states.values():
        for s in states.values():
            try:
                if s['backup'] is not None: used.add(s['backup'].as_pointer())
            except ReferenceError: pass
    for mesh in list(_backups):
        try:
            if mesh.as_pointer() not in used and mesh.users==0:
                _backups.remove(mesh)
                (bpy.data.curves if isinstance(mesh,bpy.types.Curve) else bpy.data.meshes).remove(mesh)
        except ReferenceError: _backups.remove(mesh)
    profiles={data.bevel_object for data in bpy.data.curves if data.bevel_object is not None}
    for obj in list(bpy.data.objects):
        if obj.get('bs_guard_temp') and 'bs_curve_owner' in obj and obj not in profiles:
            data=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
            if data.users==0: bpy.data.curves.remove(data)


def unchanged(a,b):
    return a['uid']==b['uid'] and a['free']==b['free'] and a['stamp']==b['stamp'] and matrix_key(a['world'])==matrix_key(b['world'])


def relative_unchanged(a,b,old):
    x,y=old.get(a.as_pointer()),old.get(b.as_pointer())
    if not x or not y: return False
    if x['free']!=a.bs.free_placement or y['free']!=b.bs.free_placement: return False
    if core().signature(a.data)!=x['raw'] or core().signature(b.data)!=y['raw']: return False
    if a.modifiers or b.modifiers or a.type=='CURVE' or b.type=='CURVE': return False
    try:
        return matrix_key(x['world'].inverted()@y['world'])==matrix_key(a.matrix_world.inverted()@b.matrix_world)
    except ValueError: return False



def surface(obj,depsgraph):
    key=obj.session_uid
    evaluated=obj.evaluated_get(depsgraph) if obj.modifiers or obj.type=='CURVE' else None
    mesh=evaluated.to_mesh() if evaluated is not None else obj.data
    try:
        stamp=(core().signature(mesh),matrix_key(obj.matrix_world))
        cached=_surfaces.get(key)
        if cached and cached[0]==stamp: return cached[1]
        solid=Solid([obj.matrix_world@v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
        _surfaces[key]=(stamp,solid)
        return solid
    finally:
        if evaluated is not None: evaluated.to_mesh_clear()

def audit(scene,objects=None,changed=None,previous=None,limit=20):
    """Return actionable errors, testing real mesh components rather than object boxes."""
    dg=bpy.context.evaluated_depsgraph_get()
    objects=list(objects) if objects is not None else list(scene.objects)
    objects=[o for o in objects if managed(o) and not o.bs.free_placement and not excluded(o,scene)]
    errors=[]; solids={}
    for obj in objects:
        if changed is not None and obj.as_pointer() not in changed: continue
        node=obj
        while node:
            if any(v<=EPS for v in node.scale) or node.matrix_world.to_3x3().determinant()<=EPS**3:
                errors.append((obj,None,'Отрицательный или нулевой масштаб: '+obj.name)); break
            node=node.parent
    for obj in objects:
        try: solids[obj.as_pointer()]=surface(obj,dg)
        except GeometryError as exc:
            if managed(obj) and (changed is None or obj.as_pointer() in changed): errors.append((obj,None,obj.name+': '+str(exc)))
    ids={o.as_pointer():i for i,o in enumerate(objects)}
    candidates=[o for o in objects if changed is None or o.as_pointer() in changed]
    for a in candidates:
        aid=a.as_pointer(); left=solids.get(aid)
        if left is None: continue
        for b in objects:
            bid=b.as_pointer()
            if aid==bid or ((changed is None or bid in changed) and ids[bid]<ids[aid]): continue
            if previous and relative_unchanged(a,b,previous): continue
            right=solids.get(bid)
            if right is not None and overlaps(left,right,scene): errors.append((a,b,'Пересечение: '+a.name+' ↔ '+b.name))
            if len(errors)>=limit: return errors
    return errors


def require_valid(scene,objects=None):
    global _checking
    saved=_checking; _checking=True
    try:
        errors=audit(scene,objects)
        if errors: raise ConstraintError('; '.join(e[2] for e in errors[:5]))
    finally: _checking=saved


def restore(scene,previous,current,changed):
    engine=core(); saved=engine.BUSY; engine.BUSY=True
    affected={key for key in changed if not current[key]['free'] and
              (managed(current[key]['obj']) or (key in previous and previous[key]['params'] is not None))}
    for key in list(affected):
        parent=current[key]['obj'].parent
        while parent:
            if parent.as_pointer() in changed: affected.add(parent.as_pointer())
            parent=parent.parent
    try:
        for key in affected:
            state=previous.get(key); obj=current[key]['obj']
            if state is None:
                if obj.type in {'MESH','CURVE'}:
                    mesh=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
                    if mesh.users==0: (bpy.data.curves if isinstance(mesh,bpy.types.Curve) else bpy.data.meshes).remove(mesh)
                continue
            obj.parent=state['parent']; obj.matrix_parent_inverse=state['inverse']; obj.matrix_basis=state['basis']
            if state['params']:
                for name,value in state['params'].items(): setattr(obj.bs,name,value)
            if state['backup'] is not None and (current[key]['raw']!=state['raw'] or
                    (obj.type=='CURVE' and current[key]['stamp']!=state['stamp'])):
                mesh=obj.data; obj.data=state['backup'].copy()
                if mesh.users==0: (bpy.data.curves if isinstance(mesh,bpy.types.Curve) else bpy.data.meshes).remove(mesh)
            if obj.type=='CURVE' and obj.get('bs_curve_wall'):
                from .curves import update_profile
                update_profile(obj)
            if state['signature'] is not None: obj['bs_signature']=state['signature']
            names={m[0] for m in state['arrays']}
            for mod in list(obj.modifiers):
                if mod.type=='ARRAY' and mod.name not in names:obj.modifiers.remove(mod)
            for name,count,relative,constant,offset,relative_offset in state['arrays']:
                mod=obj.modifiers.get(name) or obj.modifiers.new(name,'ARRAY')
                mod.count=count;mod.use_relative_offset=relative;mod.use_constant_offset=constant
                mod.constant_offset_displace=offset;mod.relative_offset_displace=relative_offset
            names={m[0] for m in state['booleans']}
            for mod in list(obj.modifiers):
                if mod.type=='BOOLEAN' and mod.name not in names: obj.modifiers.remove(mod)
            for name,operation,solver,target,use_self,visible in state['booleans']:
                mod=obj.modifiers.get(name) or obj.modifiers.new(name,'BOOLEAN')
                mod.operation=operation; mod.solver=solver; mod.object=target; mod.use_self=use_self; mod.show_viewport=visible
        for key,state in previous.items():
            if key in current and state['obj'].name in bpy.context.view_layer.objects:
                state['obj'].select_set(state['selected'])
                if state['active']: bpy.context.view_layer.objects.active=state['obj']
    finally: engine.BUSY=saved


def flush(scene=None,throw=False):
    global _checking
    if _checking or _depth: return True
    scene=scene or bpy.context.scene
    _checking=True
    try:
        if scene==bpy.context.scene: bpy.context.view_layer.update()
        key=scene.as_pointer(); old=_states.get(key)
        current=capture(scene,old)
        if old is None:
            _states[key]=current; return True
        changed={k for k,v in current.items() if k not in old or not unchanged(v,old[k])}
        # Let Blender's native duplicate-and-move operation reach its final location.
        transforming=any(op.bl_idname.startswith('TRANSFORM_OT_') for w in bpy.context.window_manager.windows for op in w.modal_operators)
        if transforming and any(k not in old for k in changed): return True
        errors=audit(scene,changed=changed,previous=old) if changed else []
        if errors:
            restore(scene,old,current,changed)
            if scene==bpy.context.scene: bpy.context.view_layer.update()
            _states[key]=capture(scene,old)
            _messages[key]=errors[0][2]
            if throw: raise ConstraintError('; '.join(e[2] for e in errors[:3]))
            return False
        _states[key]=current
        if changed: _messages.pop(key,None)
        return True
    finally:
        _checking=False; cleanup()


@contextmanager
def transaction(context):
    global _depth
    if not _depth and not _checking and context.scene.as_pointer() not in _states:
        _states[context.scene.as_pointer()]=capture(context.scene)
    _depth+=1
    try: yield
    finally:
        _depth-=1
        if not _depth and not _checking: flush(context.scene,throw=True)


def checked(function):
    def run(args,kwargs):
        context=next((a for a in args if hasattr(a,'scene') and hasattr(a,'view_layer')),bpy.context)
        try:
            with transaction(context): return function(*args,**kwargs)
        except ConstraintError as exc:
            if args and isinstance(args[0],bpy.types.Operator):
                args[0].report({'WARNING'},str(exc))
                return {'RUNNING_MODAL'} if args[0].bl_idname in {'blocksmith.resize','blocksmith.draw'} else {'CANCELLED'}
            raise
    # Blender validates the concrete callback argument count, not inspect.signature.
    if function.__name__=='execute':
        def wrapper(self,context): return run((self,context),{})
    elif function.__name__=='modal':
        def wrapper(self,context,event): return run((self,context,event),{})
    else:
        def wrapper(*args,**kwargs): return run(args,kwargs)
    return wraps(function)(wrapper)


def message(scene): return _messages.get(scene.as_pointer(),'')


@persistent
def dirty(scene,depsgraph):
    if not _checking and not _depth: _dirty.add(scene.as_pointer())


@persistent
def reload_state(*args):
    global _history
    _history=None; _states.clear(); _surfaces.clear(); _dirty.update(s.as_pointer() for s in bpy.data.scenes)


def history_event(action):
    global _history
    baseline={s['name']:{'raw':s['raw'],'stamp':s['stamp'],'world':s['world'].copy(),'free':s['free']}
              for states in _states.values() for s in states.values()}
    _states.clear()
    if not _history_reverting: _history=(action,baseline)
    _dirty.update(s.as_pointer() for s in bpy.data.scenes)


@persistent
def after_undo(*args): history_event('UNDO')


@persistent
def after_redo(*args): history_event('REDO')


def check_history(scene):
    global _history,_history_reverting,_checking
    action,baseline=_history; _history=None; _checking=True
    try:
        current=capture(scene)
        previous={k:baseline[s['name']] for k,s in current.items() if s['name'] in baseline}
        changed={k for k,s in current.items() if k not in previous or s['free']!=previous[k]['free'] or s['stamp']!=previous[k]['stamp']
                 or matrix_key(s['world'])!=matrix_key(previous[k]['world'])}
        errors=audit(scene,changed=changed,previous=previous)
        if errors:
            _history_reverting=True
            try:
                if action=='REDO': bpy.ops.ed.undo()
                else: bpy.ops.ed.redo()
            finally: _history_reverting=False
            _messages[bpy.context.scene.as_pointer()]=errors[0][2]
            _states[bpy.context.scene.as_pointer()]=capture(bpy.context.scene)
        else: _states[scene.as_pointer()]=current
    finally: _checking=False; cleanup()


def tick():
    global _bootstrap
    if _bootstrap:
        _bootstrap=False
        for scene in bpy.data.scenes: _states[scene.as_pointer()]=capture(scene)
    if not bpy.app.is_job_running('RENDER') and not _checking and not _depth:
        for scene in list(bpy.data.scenes):
            if scene!=bpy.context.scene: continue
            if scene.as_pointer() in _dirty:
                _dirty.discard(scene.as_pointer())
                if all(o.mode=='OBJECT' for o in scene.objects if managed(o)):
                    if _history: check_history(scene)
                    else: flush(scene)
    return .08


def register():
    global _bootstrap
    # Blender restricts scene access while enabling an installed extension.
    _bootstrap=not hasattr(bpy.data,'scenes')
    if not _bootstrap:
        for scene in bpy.data.scenes: _states[scene.as_pointer()]=capture(scene)
    bpy.app.handlers.depsgraph_update_post.append(dirty)
    bpy.app.handlers.load_post.append(reload_state)
    bpy.app.handlers.undo_post.append(after_undo); bpy.app.handlers.redo_post.append(after_redo)
    bpy.app.timers.register(tick,first_interval=.08,persistent=True)


def unregister():
    if bpy.app.timers.is_registered(tick): bpy.app.timers.unregister(tick)
    if dirty in bpy.app.handlers.depsgraph_update_post: bpy.app.handlers.depsgraph_update_post.remove(dirty)
    for handlers,function in [(bpy.app.handlers.load_post,reload_state),(bpy.app.handlers.undo_post,after_undo),(bpy.app.handlers.redo_post,after_redo)]:
        if function in handlers: handlers.remove(function)
    _states.clear(); _dirty.clear(); _messages.clear(); _surfaces.clear(); cleanup()


def placement_error(context,vertices,faces,matrix,kind,replacements=None):
    global _checking
    if kind in REFERENCES|{'WATER'}: return ''
    saved=_checking; _checking=True
    try:
        from mathutils import Vector
        candidate=Solid([matrix@Vector(v) for v in vertices],faces)
        dg=context.evaluated_depsgraph_get()
        for obj in context.scene.objects:
            if not managed(obj) or obj.bs.free_placement or excluded(obj,context.scene): continue
            if replacements and obj in replacements:
                replacement=replacements[obj]
                if replacement is None: continue
                mesh,world=replacement
                obstacle=Solid([world@Vector(v) for v in mesh.vertices],mesh.faces)
                if overlaps(candidate,obstacle,context.scene): return 'Пересечение с '+obj.name
                continue
            from .collision import bounds, bounds_overlap
            if not bounds_overlap(candidate.bounds,bounds([obj.matrix_world@Vector(v) for v in obj.bound_box])): continue
            try: obstacle=surface(obj,dg)
            except GeometryError: continue
            if overlaps(candidate,obstacle,context.scene): return 'Пересечение с '+obj.name
        return ''
    except GeometryError as exc: return str(exc)
    finally: _checking=saved
