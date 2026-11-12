# SPDX-License-Identifier: GPL-3.0-or-later
"""One toolbar tool, semantic previews, and a short modal per drawing gesture."""
from .translations import tr
from types import SimpleNamespace
import math
import bpy
import blf
import gpu
from bpy.props import BoolProperty
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon, intersect_line_line
from gpu_extras.batch import batch_for_shader
from .geometry import SHAPES
from . import build
from . import guard
from .presets import BY_ID

LINE_SHAPES={'WALL','DOOR','WINDOW','ARCH','RAILING','LADDER','STAIRS','RAMP'}
CENTERED={'CYLINDER','CURVED_WALL','SPIRAL_STAIRS'}
ACTIVE=None
CHAIN={}
CHOOSING=False
TOOL_ID='blocksmith.draw_tool'


def select_preset(s,identifier):
    global CHOOSING
    if identifier not in BY_ID: return
    CHOOSING=True
    try:
        preset=BY_ID[identifier]
        s.preset=identifier; s.shape=preset[3]
        values=parameters(bpy.context,s.shape,identifier)
        s.draw_width=values.width; s.draw_depth=values.depth; s.draw_height=values.height
        CHAIN.clear()
    finally: CHOOSING=False


def shape_changed(s,context):
    if CHOOSING: return
    preset=next((p for p in BY_ID.values() if p[3]==s.shape),None)
    if preset: select_preset(s,preset[0])
    else:
        s.preset=''
        p=parameters(context,s.shape)
        s.draw_width=p.width; s.draw_depth=p.depth; s.draw_height=p.height
        CHAIN.clear()


def parameters(context,kind,preset=''):
    from . import BSShape
    values={p.identifier:p.default for p in BSShape.bl_rna.properties if hasattr(p,'default') and not getattr(p,'is_array',False)}
    s=context.scene.bs
    values.update(kind=kind,height=s.wall_height,thickness=s.wall_thickness,max_step=s.max_step,
                  open_width=s.door_width,open_height=s.door_height)
    if kind in {'WALL','DOOR','WINDOW','ARCH','RAILING','LADDER'}: values['depth']=s.wall_thickness
    for shape,key in [('FLOOR','floor_thickness'),('WATER','water_depth'),('LOW_COVER','low_cover'),('HIGH_COVER','high_cover')]:
        if kind==shape: values['height']=getattr(s,key)
    if kind=='WINDOW': values['open_height']=1
    for key in ('player_height','player_radius','crouch_height','jump_height','jump_gap','low_cover','high_cover'):
        values[key]=getattr(s,key)
    if kind in {'PLAYER','CROUCH'}:
        values.update(width=s.player_radius*2,depth=s.player_radius*2,height=s.player_height if kind=='PLAYER' else s.crouch_height)
    if preset in BY_ID and BY_ID[preset][3]==kind: values.update(BY_ID[preset][4])
    return SimpleNamespace(**values)


def ray(context,event):
    region=next(r for r in context.area.regions if r.type=='WINDOW')
    pos=Vector((event.mouse_x-region.x,event.mouse_y-region.y))
    rv=context.space_data.region_3d
    return (view3d_utils.region_2d_to_origin_3d(region,rv,pos),
            view3d_utils.region_2d_to_vector_3d(region,rv,pos))


def point_on_plane(context,event,origin,normal):
    eye,direction=ray(context,event); denominator=normal.dot(direction)
    if abs(denominator)<1e-6: return None
    t=normal.dot(origin-eye)/denominator
    return eye+direction*t if t>=0 else None


def surface_frame(normal):
    """Keep walls upright; let floors follow their supporting surface."""
    normal=normal.normalized()
    front=abs(normal.z)<.707
    if front:
        x=normal.cross(Vector((0,0,1))).normalized(); y=normal; z=x.cross(y)
    else:
        z=normal; x=Vector((1,0,0))-z*z.x; x.normalize(); y=z.cross(x)
    return Matrix((x,y,z)).transposed().to_4x4(),front


def surface_hit(context,event,force_surfaces=False,access=False):
    from .geometry import REFERENCES
    s=context.scene.bs; eye,direction=ray(context,event); missing_plane=False
    hit,point,normal,_,obj,_=context.scene.ray_cast(context.evaluated_depsgraph_get(),eye,direction)
    if not (hit and (s.surfaces or force_surfaces) and not obj.get('bs_cutter') and not (obj.bs.enabled and obj.bs.kind in REFERENCES)):
        normal=Vector((0,0,1)); point=point_on_plane(context,event,Vector((0,0,s.draw_plane_z)),normal)
        if point is None:
            if not (s.surfaces or force_surfaces):return None
            point=eye+direction;missing_plane=True
        obj=None
    if access and obj is not None and normal.z<.7:
        world=obj.matrix_world; inv=world.inverted()
        above=point-normal*.001
        above.z=max((world@Vector(v)).z for v in obj.bound_box)+.01
        evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
        found,top,up,_=evaluated.ray_cast(inv@above,(inv.to_3x3()@Vector((0,0,-1))).normalized())
        if found and (inv.to_3x3().transposed()@up).normalized().z>.7: point.z=(world@top).z
    frame,front=surface_frame(normal)
    if s.object_snap and not event.ctrl:
        mode='WALKABLE' if access else 'SPACE' if (s.surfaces or force_surfaces) else 'PLANE'
        point,snapped=snap_point(context,event,point,frame,front,mode=mode)
        if snapped is not None and mode!='PLANE':
            obj=snapped;missing_plane=False
            if not access:
                normal=face_normal(context,obj,point,direction,normal)
                frame,front=surface_frame(normal)
    if missing_plane:return None
    frame.translation=point
    return frame,front,obj.original if obj is not None else None


def face_normal(context,obj,point,direction,fallback):
    """At an edge choose its camera-facing surface, including evaluated cut faces."""
    evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
    world=evaluated.matrix_world; normals=world.to_3x3().inverted().transposed()
    candidates=[]
    for face in evaluated.data.polygons:
        normal=(normals@face.normal).normalized()
        origin=world@evaluated.data.vertices[face.vertices[0]].co
        if abs(normal.dot(point-origin))<1e-4:candidates.append(normal)
    return min(candidates,key=lambda n:n.dot(direction)) if candidates else fallback


def snap_point(context,event,point,frame,front=False,objects=None,mode='PLANE'):
    """Return a nearby geometric point and its owner; ordinary drafts stay in their plane."""
    from .geometry import REFERENCES
    in_plane=mode=='PLANE'
    region=next(r for r in context.area.regions if r.type=='WINDOW')
    rv=context.space_data.region_3d; pos=Vector((event.mouse_x-region.x,event.mouse_y-region.y))
    normal=frame.col[1 if front else 2].xyz.normalized()
    closest=None; closest_obj=None; distance=12
    eye,direction=ray(context,event)
    dg=context.evaluated_depsgraph_get()
    def visible(v):
        delta=v-eye; length=delta.length
        if length<1e-6: return True
        hit,where,*_=context.scene.ray_cast(dg,eye,delta/length,distance=length+.002)
        return not hit or (where-eye).length>=length-max(.002,length*1e-6)
    def consider(v,owner):
        nonlocal closest,closest_obj,distance
        screen=view3d_utils.location_3d_to_region_2d(region,rv,v)
        if screen is not None:
            d=(screen-pos).length
            if d<distance and visible(v): closest=v; closest_obj=owner; distance=d
    edges=[]
    for obj in context.visible_objects if objects is None else objects:
        if obj.type!='MESH' or obj.get('bs_cutter') or (obj.bs.enabled and obj.bs.kind in REFERENCES): continue
        evaluated=obj.evaluated_get(dg)
        box=[evaluated.matrix_world@Vector(v) for v in evaluated.bound_box]
        bounds=[normal.dot(v-point) for v in box]
        if in_plane and (min(bounds)>1e-4 or max(bounds)<-1e-4): continue
        screen=[view3d_utils.location_3d_to_region_2d(region,rv,v) for v in box]
        if all(v is not None for v in screen) and any(
            pos[i]<min(v[i] for v in screen)-12 or pos[i]>max(v[i] for v in screen)+12 for i in (0,1)): continue
        mesh=evaluated.data
        vertices=[evaluated.matrix_world@v.co for v in mesh.vertices]
        top_edges=None
        if mode=='WALKABLE':
            normals=evaluated.matrix_world.to_3x3().inverted().transposed()
            top_edges={tuple(sorted(edge)) for face in mesh.polygons if (normals@face.normal).normalized().z>.7 for edge in face.edge_keys}
        offsets=[normal.dot(v-point) if in_plane else 0 for v in vertices]
        top_vertices={i for edge in top_edges for i in edge} if top_edges is not None else None
        for i,(v,d) in enumerate(zip(vertices,offsets)):
            if abs(d)<1e-4 and (top_vertices is None or i in top_vertices): consider(v-normal*d,obj)
        for edge in mesh.edges:
            a,b=edge.vertices
            if top_edges is not None and tuple(sorted((a,b))) not in top_edges: continue
            da,db=offsets[a],offsets[b]
            if abs(da)<1e-4 and abs(db)<1e-4:
                edges.append((vertices[a]-normal*da,vertices[b]-normal*db,obj))
            elif da*db<0:
                consider(vertices[a]+(vertices[b]-vertices[a])*(da/(da-db)),obj)
    # Prefer vertices/intersections over sliding along an adjacent edge.
    if closest is None or not in_plane:
        for a,b,owner in edges:
            sa=view3d_utils.location_3d_to_region_2d(region,rv,a)
            sb=view3d_utils.location_3d_to_region_2d(region,rv,b)
            if sa is None or sb is None: continue
            segment=sb-sa
            if segment.length_squared<1e-8: continue
            f=max(0,min(1,(pos-sa).dot(segment)/segment.length_squared))
            d=(sa+segment*f-pos).length
            if d<distance:
                ab=b-a
                nearest=intersect_line_line(a,b,eye,eye+direction) if not in_plane else None
                projected=nearest[0] if nearest else point
                f=max(0,min(1,(projected-a).dot(ab)/max(ab.length_squared,1e-8)))
                candidate=a+ab*f
                if visible(candidate): closest=candidate; closest_obj=owner; distance=d
    if closest is not None: return closest,closest_obj
    local=frame.inverted()@point
    for i in ((0,2) if front else (0,1)): local[i]=round(local[i]/context.scene.bs.grid)*context.scene.bs.grid
    return frame@local,None


def layout(p,start,end,frame,front=False):
    """Map a drawing gesture to the actual shape parameters and transform."""
    delta=end-start
    if front:
        p.width=max(.01,abs(delta.x)); p.height=max(.01,abs(delta.z))
        origin=Vector((min(start.x,end.x),0,max(start.z,end.z) if p.kind=='FLOOR' else min(start.z,end.z)))
        if p.kind in CENTERED:origin.x=(start.x+end.x)/2
        angle=0
    elif p.kind in {'STAIRS','RAMP'}:
        low,high=(end,start) if delta.z<0 else (start,end)
        run=high-low; p.width=max(.01,math.hypot(run.x,run.y))
        if abs(run.z)>.001: p.height=abs(run.z)
        angle=math.atan2(run.y,run.x)
        origin=low-Vector((-math.sin(angle),math.cos(angle),0))*p.depth/2
    elif p.kind in LINE_SHAPES:
        p.width=max(.01,math.hypot(delta.x,delta.y)); origin=start.copy(); angle=math.atan2(delta.y,delta.x)
    else:
        p.width=max(.01,abs(delta.x)); p.depth=max(.01,abs(delta.y)); angle=0
        origin=(start+end)/2 if p.kind in CENTERED else Vector((min(start.x,end.x),min(start.y,end.y),start.z))
    # Rooms include a slab below local Z=0; place its bottom on the supporting plane.
    if p.kind=='ROOM': origin.z+=p.thickness
    return frame@Matrix.Translation(origin)@Matrix.Rotation(angle,4,'Z')


def landing_points(context,obj,lower,upper,width):
    """Fit the full opening of the stair on its landing, rather than only its centre."""
    if obj is None: return lower,upper,width
    direction=Vector((upper.x-lower.x,upper.y-lower.y,0))
    length=direction.length
    if length<.01: return lower,upper,width
    origin=Vector((lower.x,lower.y,upper.z-.001))
    inv=obj.matrix_world.inverted()
    evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
    found,point,normal,index=evaluated.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())
    if not found: return lower,upper,width
    point=obj.matrix_world@point
    if (point-origin).length>length+.002: return lower,upper,width
    upper=Vector((point.x,point.y,upper.z))
    normal=(inv.to_3x3().transposed()@normal).normalized()
    tangent=Vector((0,0,1)).cross(normal)
    if tangent.length<.01: return lower,upper,width
    tangent.normalize()
    intervals=[]
    normals=inv.to_3x3().transposed()
    for face in evaluated.data.polygons:
        if (normals@face.normal).normalized().dot(normal)<.9999: continue
        vertices=[obj.matrix_world@evaluated.data.vertices[i].co for i in face.vertices]
        if any(abs((v-point).dot(normal))>.0001 for v in vertices): continue
        section=[]
        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
            da=a.z-origin.z; db=b.z-origin.z
            if abs(da)<1e-5: section.append(a.dot(tangent))
            if da*db<0: section.append((a+(b-a)*(da/(da-db))).dot(tangent))
        if len(section)>=2: intervals.append((min(section),max(section)))
    merged=[]
    for left,right in sorted(intervals):
        if merged and left<=merged[-1][1]+1e-5: merged[-1]=(merged[-1][0],max(right,merged[-1][1]))
        else: merged.append((left,right))
    centre=upper.dot(tangent)
    limits=next(((a,b) for a,b in merged if a-1e-5<=centre<=b+1e-5),None)
    if limits is None: return lower,upper,width
    side=Vector((-direction.y,direction.x,0)).normalized()
    projection=abs(side.dot(tangent))
    if projection<.01: return lower,upper,width
    left,right=limits
    width=min(width,(right-left)/projection)
    half=width*projection/2
    centre=upper.dot(tangent)
    shift=max(left+half,min(right-half,centre))-centre
    delta=tangent*shift
    return lower+delta,upper+delta,width


def landing_modifier(obj,target):
    mod=obj.modifiers.new('BS_Landing','BOOLEAN')
    mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.use_self=True; mod.object=target
    return mod


def fit_landing(context,shape,world,target):
    """Preview the same landing trim that the placed parametric module will keep."""
    from .geometry import Mesh
    mesh=bpy.data.meshes.new('__BS_landing_preview')
    obj=None
    try:
        mesh.from_pydata(shape.vertices,[],shape.faces); mesh.update()
        obj=bpy.data.objects.new('__BS_landing_preview',mesh); obj['bs_guard_temp']=True
        context.scene.collection.objects.link(obj); obj.matrix_world=world
        obj.hide_render=True; obj.hide_set(True)
        landing_modifier(obj,target)
        evaluated=obj.evaluated_get(context.evaluated_depsgraph_get()); result=evaluated.to_mesh()
        try:
            trimmed=Mesh()
            trimmed.vertices=[tuple(v.co) for v in result.vertices]
            trimmed.faces=[tuple(p.vertices) for p in result.polygons]
            return trimmed
        finally: evaluated.to_mesh_clear()
    finally:
        if obj is not None: bpy.data.objects.remove(obj,do_unlink=True)
        if not mesh.users: bpy.data.meshes.remove(mesh)


def chain_previous(context):
    s=context.scene.bs
    if not (s.draw_chain and s.keep_drawing and s.shape=='WALL'): return None
    record=CHAIN.get(context.window.as_pointer())
    if record is None or record[0]!=context.scene.session_uid: return None
    obj=bpy.data.objects.get(record[1])
    if obj is None or obj.session_uid!=record[2] or obj.name not in context.scene.objects: return None
    from . import manual
    if manual(obj) or obj.bs.kind!='WALL' or obj.bs.opening!='NONE' or obj.modifiers: return None
    if any(abs(v-1)>1e-6 for v in obj.matrix_world.to_scale()): return None
    return obj


def leave_tool(context):
    CHAIN.clear()
    if context.area and context.area.type=='VIEW_3D':
        bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
        context.area.tag_redraw()


class BS_OT_draw(bpy.types.Operator):
    bl_idname='blocksmith.draw'; bl_label='Draw Structure'
    bl_options={'REGISTER','UNDO','BLOCKING'}
    use_preset: BoolProperty(name='Use Preset',default=True)
    place_only: BoolProperty(name='Place Only',default=False,options={'HIDDEN'})
    repeat: BoolProperty(name='Repeat',default=False,options={'HIDDEN'})
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and context.area and context.area.type=='VIEW_3D'
    def invoke(self,context,event):
        global ACTIVE
        from .curves import ACTIVE as CURVE
        if event.alt: return {'PASS_THROUGH'}
        if ACTIVE is not None or CURVE is not None: return {'CANCELLED'}
        self.closed=False; self.stop_requested=False; self.batch=None; self.error=''
        self.window=context.window; self.workspace=context.workspace; self.area=context.area; self.scene=context.scene
        tool=self.workspace.tools.from_space_view3d_mode('OBJECT',create=False)
        self.tool_started=tool is not None and tool.idname==TOOL_ID
        self.region=next(r for r in self.area.regions if r.type=='WINDOW')
        self.preset=context.scene.bs.preset if self.use_preset else ''
        self.params=parameters(context,context.scene.bs.shape,self.preset)
        if not self.place_only:
            self.params.width=context.scene.bs.draw_width; self.params.depth=context.scene.bs.draw_depth; self.params.height=context.scene.bs.draw_height
        self.default=SimpleNamespace(**vars(self.params))
        self.start=Vector((0,0,0)); self.end=self.start.copy(); self.phase='WAIT'; self.front=False
        self.frame=Matrix.Identity(4); self.matrix=self.frame.copy(); self.previous=None; self.previous_mesh=None
        self.turn=0; self.navigating=False; self.mouse=(event.mouse_x,event.mouse_y); self.press_mouse=self.mouse
        self.cut_target=None; self.cut_depth=0; self.access_target=None; self.access_start_target=None; self.clip_target=None; self.support_target=None; self.support_normal=Vector((0,0,1))
        self.created=False; self.exit_after=False
        self.handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_preview,(),'WINDOW','POST_VIEW')
        self.hud=bpy.types.SpaceView3D.draw_handler_add(self.draw_hud,(),'WINDOW','POST_PIXEL')
        self.timer=context.window_manager.event_timer_add(.1,window=context.window)
        ACTIVE=self
        self.workspace.status_text_set(tr('Blocksmith · Drag on a surface · Ctrl: no snapping · Esc / RMB: exit'))
        self.window.cursor_modal_set('CROSSHAIR'); context.window_manager.modal_handler_add(self)
        if event.type=='LEFTMOUSE' and context.region.type=='WINDOW': self.begin(context,event)
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}
    def begin(self,context,event):
        self.cut_target=None
        if self.params.kind in {'DOOR','WINDOW','ARCH'} and not self.place_only:
            from .openings import surface
            try: self.cut_target,self.frame,self.cut_depth=surface(context,event)
            except ValueError as exc:
                self.error=tr(str(exc)); return
            self.front=True; self.previous=None
        else:
            access=self.params.kind in {'STAIRS','RAMP'} and not self.place_only
            target=surface_hit(context,event,force_surfaces=access,access=access)
            if target is None: return
            self.frame,self.front=target[:2]; self.support_target=target[2]
            self.support_normal=self.frame.col[1 if self.front else 2].xyz.normalized()
            if self.front and self.params.kind in {'FLOOR','WATER','ROOM'}:
                x=self.frame.col[0].xyz; z=Vector((0,0,1)); y=z.cross(x)
                horizontal=Matrix((x,y,z)).transposed().to_4x4(); horizontal.translation=self.frame.translation
                self.frame=horizontal; self.front=False
            if access:
                self.access_start_target=target[2]
                self.frame=Matrix.Translation(self.frame.translation); self.front=False
            self.previous=chain_previous(context) if not self.place_only else None
        if self.previous is not None:
            obj=self.previous
            self.frame=obj.matrix_world.copy()
            self.frame.translation=obj.matrix_world@Vector((obj.bs.width,0,0))
            self.front=False
        self.start=Vector((0,0,0)); self.end=self.start.copy()
        self.press_mouse=(event.mouse_x,event.mouse_y); self.phase='BASE'
        self.move(context,event)
    def move(self,context,event):
        normal=self.frame.col[1].xyz if self.front else self.frame.col[2].xyz
        access=self.params.kind in {'STAIRS','RAMP'} and not self.place_only
        target=surface_hit(context,event,force_surfaces=True,access=True) if access else None
        point=target[0].translation if target else point_on_plane(context,event,self.frame.translation,normal)
        if point is None: return
        s=context.scene.bs
        if access:
            self.params.height=self.default.height; self.params.depth=self.default.depth
            self.access_target=target[2] if target else None
            if point.z<self.frame.translation.z-.001: self.access_target=self.access_start_target
        if s.object_snap and not event.ctrl and target is None:
            point,_=snap_point(context,event,point,self.frame,self.front)
        if access:
            self.start=Vector()
            origin=self.frame.translation
            if point.z>origin.z+.001:
                lower,point,self.params.depth=landing_points(context,self.access_target,origin,point,self.params.depth)
                self.start=self.frame.inverted()@lower
            elif point.z<origin.z-.001:
                point,upper,self.params.depth=landing_points(context,self.access_start_target,point,origin,self.params.depth)
                self.start=self.frame.inverted()@upper
        self.end=self.frame.inverted()@point
        if event.shift and not self.front:
            d=self.end-self.start
            if self.params.kind in LINE_SHAPES:
                a=round(math.atan2(d.y,d.x)/(math.pi/4))*(math.pi/4); length=math.hypot(d.x,d.y)
                self.end=self.start+Vector((math.cos(a)*length,math.sin(a)*length,d.z))
            else:
                size=max(abs(d.x),abs(d.y)); self.end.x=math.copysign(size,d.x); self.end.y=math.copysign(size,d.y)
        self.update_preview(context)
    def pose(self):
        matrix=layout(self.params,self.start,self.end,self.frame,self.front)
        if self.place_only and self.params.kind in {'STAIRS','RAMP'}:
            matrix.translation+=self.frame.col[1].xyz*self.params.depth/2
        if self.turn: matrix=self.frame@Matrix.Rotation(self.turn,4,'Z')@self.frame.inverted()@matrix
        return matrix
    def update_preview(self,context=None):
        context=context or bpy.context
        self.matrix=self.pose(); self.previous_mesh=None; self.params.miter_start=0; self.clip_target=None
        if self.previous is not None:
            from .joints import plan
            try:
                axis=self.previous.matrix_world.col[0].xyz.normalized().dot(self.matrix.col[0].xyz.normalized())
                if axis>.9999:
                    self.previous_params=SimpleNamespace(**guard.props(self.previous.bs))
                    self.previous_matrix=self.previous.matrix_world.copy()
                else:
                    if axis<-.866: raise ValueError('The angle is too sharp — start a separate wall')
                    (self.previous_params,self.previous_matrix),(self.params,self.matrix)=plan(
                        self.previous.bs,self.previous.matrix_world,self.params,self.matrix,context.scene.bs.joint_mode)
                self.previous_mesh=build(self.previous_params)
            except ValueError as exc:
                self.error=tr(str(exc)); self.batch=None; return
        try:
            if self.cut_target is not None:
                from .openings import drawn_mesh
                result=drawn_mesh(self.params.kind,self.start,self.end,self.cut_depth)
                self.matrix=self.frame.copy(); self.error=''
            else:
                result=build(self.params)
                if self.support_target is not None and self.params.kind in CENTERED:
                    normal=self.support_normal
                    low=min(normal.dot(self.matrix@Vector(v)-self.frame.translation) for v in result.vertices)
                    if low<0:self.matrix.translation-=normal*low
            replacements={self.previous:(self.previous_mesh,self.previous_matrix)} if self.previous_mesh else None
            if self.cut_target is None:
                self.error=guard.placement_error(context,result.vertices,result.faces,self.matrix,self.params.kind,replacements)
                contact=self.access_target if self.params.kind in {'STAIRS','RAMP'} else self.support_target
                if self.error and contact is not None:
                    original=result
                    trimmed=fit_landing(context,result,self.matrix,contact)
                    if self.params.kind=='FLOOR':
                        up=self.matrix.col[2].xyz.normalized(); top=up.dot(self.frame.translation)
                        if not trimmed.vertices or max(up.dot(self.matrix@Vector(v)) for v in trimmed.vertices)<top-1e-4:
                            self.matrix.translation+=self.matrix.col[2].xyz*self.params.height
                            result=original
                        else: result=trimmed
                    else: result=trimmed
                    self.error=guard.placement_error(context,result.vertices,result.faces,self.matrix,self.params.kind,replacements)
                    if not self.error and result is trimmed:self.clip_target=contact
            if not self.error and self.previous_mesh:
                self.error=guard.placement_error(context,self.previous_mesh.vertices,self.previous_mesh.faces,self.previous_matrix,'WALL',{self.previous:None})
            vertices=[self.matrix@Vector(v) for v in result.vertices]; tris=[]; edges=[]
            for face in result.faces:
                coords=[vertices[i] for i in face]
                tris.extend(v for tri in tessellate_polygon([coords]) for v in tri)
                for i,a in enumerate(coords): edges.extend((a,coords[(i+1)%len(coords)]))
            self.shader=gpu.shader.from_builtin('UNIFORM_COLOR')
            self.batch=batch_for_shader(self.shader,'TRIS',{'pos':tris}); self.lines=batch_for_shader(self.shader,'LINES',{'pos':edges})
        except (ValueError,ArithmeticError) as exc:
            self.error=tr(str(exc)); self.batch=None
    def draw_preview(self):
        if self.batch is None or bpy.context.area!=self.area: return
        gpu.state.blend_set('ALPHA'); gpu.state.depth_test_set('LESS_EQUAL')
        try:
            self.shader.bind(); self.shader.uniform_float('color',(1,.15,.1,.3) if self.error else (.15,.65,1,.25)); self.batch.draw(self.shader)
            self.shader.uniform_float('color',(1,.2,.1,1) if self.error else (.3,.8,1,1)); self.lines.draw(self.shader)
        finally: gpu.state.blend_set('NONE'); gpu.state.depth_test_set('NONE')
    def draw_hud(self):
        if bpy.context.area!=self.area: return
        p=self.params
        label=tr(BY_ID[self.preset][1] if self.preset in BY_ID else p.kind.replace('_',' ').title())
        cutting=p.kind in {'DOOR','WINDOW','ARCH'} and not self.place_only
        lines=[label+(tr(' · opening {0:.2f} × {1:.2f} m').format(p.width,p.height) if cutting else tr('  {0:.2f} × {1:.2f} × {2:.2f} m').format(p.width,p.depth,p.height))]
        if self.error: lines.append(self.error[:90])
        elif self.phase=='HEIGHT': lines.append('Height: move mouse up / down · LMB: create · Esc: exit')
        elif self.phase=='WAIT': lines.append('Drag an opening on a wall · Esc / RMB: exit' if cutting else 'Drag LMB in the scene · Esc / RMB: exit')
        else: lines.append('Release LMB: cut · Esc: cancel' if cutting else 'Release LMB: create · Esc: exit' if p.kind in {'STAIRS','RAMP'} else 'Release LMB: create · H: height · Esc: exit')
        if 'STAIRS' in p.kind:
            n=max(1,math.ceil(p.height/p.max_step) if p.auto_steps else p.steps)
            lines.append(tr('{0} steps · rise {1:.2f} m').format(n,p.height / n))
        if self.scene.bs.show_metrics and not cutting:
            from .editing import metric_issues
            lines.extend(metric_issues(p,self.scene.bs)[:2])
        x=max(12,min(self.mouse[0]-self.region.x+18,self.region.width-460)); y=max(60,min(self.mouse[1]-self.region.y-28,self.region.height-35))
        blf.size(0,13); blf.enable(0,blf.SHADOW); blf.shadow(0,5,0,0,0,1)
        blf.color(0,1,.35,.2,1) if self.error else blf.color(0,.9,.95,1,1)
        for i,line in enumerate(lines): blf.position(0,x,y-i*20,0); blf.draw(0,tr(line))
        blf.disable(0,blf.SHADOW)
    def finish(self,context,exit_tool=False):
        global ACTIVE
        if not getattr(self,'closed',True):
            self.closed=True
            bpy.types.SpaceView3D.draw_handler_remove(self.handle,'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self.hud,'WINDOW')
            context.window_manager.event_timer_remove(self.timer)
            self.area.header_text_set(None); self.workspace.status_text_set(None)
            self.window.cursor_modal_restore(); self.area.tag_redraw()
        if ACTIVE is self: ACTIVE=None
        if exit_tool:
            with context.temp_override(window=self.window,area=self.area,region=self.region): leave_tool(context)
        # Cancelled gestures must not insert an extra Undo entry after a placed piece.
        return {'FINISHED'} if self.created else {'CANCELLED'}
    def cancel(self,context): self.finish(context,True)
    def place(self,context):
        from . import create,rebuild
        from .ui import texture_view
        import sys
        core=sys.modules[__package__]
        self.update_preview(context)
        if self.error:
            self.report({'WARNING'},tr(self.error)); return {'RUNNING_MODAL'}
        try:
            with guard.transaction(context):
                if self.previous_mesh:
                    from .joints import apply
                    apply(self.previous,self.previous_params,self.previous_matrix)
                if self.cut_target is not None:
                    from .openings import apply_drawn, drawn_mesh
                    obj=self.cut_target
                    apply_drawn(context,obj,drawn_mesh(self.params.kind,self.start,self.end,self.cut_depth),self.frame)
                else:
                    obj=create(context,self.params.kind)
                    core.BUSY=True
                    try:
                        for key,value in vars(self.params).items():
                            if key in obj.bs.bl_rna.properties and key not in {'enabled','tag','name','use_kenney','palette','texture'}:
                                setattr(obj.bs,key,value)
                    finally: core.BUSY=False
                    rebuild(obj,True); obj.matrix_world=self.matrix
                    if self.clip_target is not None: landing_modifier(obj,self.clip_target)
                    if self.preset in BY_ID: obj.name=BY_ID[self.preset][1]; obj['bs_preset']=self.preset
                context.view_layer.update()
        except guard.ConstraintError as exc:
            self.error=tr(str(exc)); self.report({'WARNING'},tr(self.error)); return {'RUNNING_MODAL'}
        self.created=True; texture_view(context)
        if context.scene.bs.draw_chain and self.params.kind=='WALL' and self.params.opening=='NONE' and not self.front:
            CHAIN[context.window.as_pointer()]=(context.scene.session_uid,obj.name,obj.session_uid)
        if self.place_only and self.repeat:
            bpy.ops.ed.undo_push(message='Place Module'); self.phase='WAIT'; self.batch=None
            self.params=SimpleNamespace(**vars(self.default)); return {'RUNNING_MODAL'}
        return self.finish(context,not context.scene.bs.keep_drawing or self.place_only)
    def modal(self,context,event):
        if self.closed or self.stop_requested: return self.finish(context,True)
        try: return self.handle_event(context,event)
        except Exception as exc:
            self.report({'WARNING'},tr('Drawing stopped: ')+tr(str(exc)))
            return self.finish(context,True)
    def handle_event(self,context,event):
        self.area.tag_redraw()
        tool=self.workspace.tools.from_space_view3d_mode('OBJECT',create=False)
        if context.scene!=self.scene or context.mode!='OBJECT' or (self.tool_started and tool and tool.idname!=TOOL_ID):
            return self.finish(context)
        if event.type=='WINDOW_DEACTIVATE': return self.finish(context)
        if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS': return self.finish(context,True)
        if event.type=='TIMER': return {'RUNNING_MODAL'}
        inside=self.region.x<=event.mouse_x<self.region.x+self.region.width and self.region.y<=event.mouse_y<self.region.y+self.region.height
        panel=next((r for r in self.area.regions if r.type in {'UI','TOOLS','HEADER','TOOL_HEADER'} and r.width>1 and r.x<=event.mouse_x<r.x+r.width and r.y<=event.mouse_y<r.y+r.height),None)
        if panel is not None or not inside:
            if event.type=='LEFTMOUSE' and event.value in {'PRESS','RELEASE'}:
                self.finish(context); return {'CANCELLED','PASS_THROUGH'}
            return {'PASS_THROUGH'}
        self.mouse=(event.mouse_x,event.mouse_y)
        if event.type=='MIDDLEMOUSE':
            self.navigating=event.value=='PRESS'; return {'PASS_THROUGH'}
        if self.navigating or event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE','NDOF_MOTION'}: return {'PASS_THROUGH'}
        if event.type=='LEFTMOUSE' and event.value=='PRESS' and self.phase=='WAIT': self.begin(context,event)
        if event.type=='R' and event.value=='PRESS' and self.place_only: self.turn+=math.pi/2; self.update_preview(context)
        if event.type=='F' and event.value=='PRESS': self.params.flip=not self.params.flip; self.update_preview(context)
        if event.type=='H' and event.value=='PRESS' and self.phase=='BASE' and not self.front:
            self.phase='HEIGHT'; self.height_origin=event.mouse_y; self.base_height=self.params.height
        if event.type=='MOUSEMOVE':
            if self.place_only:
                target=surface_hit(context,event)
                if target:
                    self.frame,self.front=target[:2]; self.support_target=target[2]
                    self.support_normal=self.frame.col[1 if self.front else 2].xyz.normalized(); self.front=False
                    p=self.params; self.start=Vector((-p.width/2,-p.depth/2,0))
                    self.end=self.start+Vector((p.width,0 if p.kind in LINE_SHAPES else p.depth,0)); self.update_preview(context)
            elif self.phase=='BASE': self.move(context,event)
            elif self.phase=='HEIGHT':
                # Use viewport scale instead of a fixed pixels-to-metres constant.
                a=view3d_utils.location_3d_to_region_2d(self.region,context.space_data.region_3d,self.matrix.translation)
                b=view3d_utils.location_3d_to_region_2d(self.region,context.space_data.region_3d,self.matrix.translation+self.frame.col[2].xyz)
                scale=max(10,(b-a).length if a is not None and b is not None else 50)
                value=self.base_height+(event.mouse_y-self.height_origin)/scale
                self.params.height=max(.01,value if event.ctrl or not context.scene.bs.object_snap else round(value/context.scene.bs.grid)*context.scene.bs.grid)
                self.update_preview(context)
        if self.place_only and event.type=='LEFTMOUSE' and event.value=='PRESS':
            if self.batch is not None: return self.place(context)
        if not self.place_only and event.type=='LEFTMOUSE':
            if event.value=='RELEASE' and self.phase=='BASE':
                if self.cut_target is not None and math.hypot(event.mouse_x-self.press_mouse[0],event.mouse_y-self.press_mouse[1])<4:
                    return self.finish(context)
                if self.previous is None and math.hypot(event.mouse_x-self.press_mouse[0],event.mouse_y-self.press_mouse[1])<4:
                    p=self.default; self.end=Vector((p.width,0,p.height)) if self.front else Vector((p.width,0 if p.kind in LINE_SHAPES else p.depth,0))
                elif not self.front or self.cut_target is not None: self.move(context,event)
                return self.place(context)
            if event.value=='PRESS' and self.phase=='HEIGHT': return self.place(context)
        if event.type in {'RET','NUMPAD_ENTER'} and event.value=='PRESS' and self.phase!='WAIT': return self.place(context)
        if event.ctrl and event.type in {'Z','S'}:
            self.finish(context); return {'CANCELLED','PASS_THROUGH'}
        return {'RUNNING_MODAL'}


class BS_WST_draw(bpy.types.WorkSpaceTool):
    bl_space_type='VIEW_3D'; bl_context_mode='OBJECT'; bl_idname=TOOL_ID
    bl_label='Blocksmith'; bl_description='Choose a structure and drag LMB. Esc / RMB returns to selection'
    bl_icon='ops.mesh.primitive_cube_add_gizmo'; bl_cursor='CROSSHAIR'
    bl_operator='blocksmith.draw'
    bl_keymap=(('blocksmith.draw',{'type':'LEFTMOUSE','value':'PRESS','any':True},{'properties':[('use_preset',True)]}),
               ('blocksmith.stop',{'type':'ESC','value':'PRESS'},None),
               ('blocksmith.stop',{'type':'RIGHTMOUSE','value':'PRESS'},None))
    @staticmethod
    def draw_settings(context,layout,tool):
        s=context.scene.bs
        layout.prop(s,'shape',text='')
        if s.shape not in {'DOOR','WINDOW','ARCH','STAIRS','RAMP'}:
            layout.prop(s,'draw_height',text='Height')
            layout.prop(s,'draw_depth',text='Depth')
        layout.prop(s,'object_snap',text='Snapping',toggle=True)
        if s.shape not in {'DOOR','WINDOW','ARCH','STAIRS','RAMP'}: layout.prop(s,'surfaces',text='Surfaces',toggle=True)
        layout.prop(s,'keep_drawing',text='Repeat',toggle=True)
