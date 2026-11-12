# SPDX-License-Identifier: GPL-3.0-or-later
"""Small geometry edits shared by panel buttons and viewport handles."""
from .translations import tr
from mathutils import Vector
from . import guard


@guard.checked
def attach(context,obj,target,axis='X',direction=1):
    """Translate actual mesh support planes into contact, in the target's axes."""
    if axis not in {'X','Y','Z'} or direction not in (-1,1):
        raise ValueError('Specify an X/Y/Z axis and a −1/+1 direction')
    if obj==target or target in obj.children_recursive:
        raise ValueError('Moving also affects the target: remove the parent link')
    if abs(target.matrix_world.determinant())<1e-12:
        raise ValueError('The target has zero scale')
    normal=Vector(tuple(direction if a==axis else 0 for a in 'XYZ'))
    normal=target.matrix_world.to_3x3().inverted().transposed()@normal
    normal.normalize()
    dg=context.evaluated_depsgraph_get()
    def points(o):
        evaluated=o.evaluated_get(dg)
        return [evaluated.matrix_world@v.co for v in evaluated.data.vertices]
    source=points(obj); destination=points(target)
    if not source or not destination: raise ValueError('Attachment requires nonempty meshes')
    offset=max(normal.dot(v) for v in destination)-min(normal.dot(v) for v in source)
    world=obj.matrix_world.copy(); world.translation+=normal*offset
    inv=target.matrix_world.inverted()
    source=[inv@(v+normal*offset) for v in source]; destination=[inv@v for v in destination]
    shift=Vector()
    for i in range(3):
        if i=='XYZ'.index(axis): continue
        low=min(v[i] for v in destination); high=max(v[i] for v in destination)
        a=min(v[i] for v in source); b=max(v[i] for v in source)
        if b-a<=high-low+1e-5:
            shift[i]=max(low-a,min(0,high-b))
    world.translation+=target.matrix_world.to_3x3()@shift
    obj.matrix_world=world


@guard.checked
def resize(obj, key, value, side=1):
    """Resize while keeping the opposite local bounding face fixed."""
    p=obj.bs
    old=getattr(p,key)
    prop=p.bl_rna.properties[key]
    value=max(prop.hard_min,min(prop.hard_max,value))
    before=[Vector(v) for v in obj.bound_box]
    index={'width':0,'depth':1,'height':2}[key]
    boundary=min(v[index] for v in before) if side>0 else max(v[index] for v in before)
    setattr(p,key,value)
    value=getattr(p,key)
    # The caller updates the depsgraph after edits; data bounds can lag a rebuild.
    coords=[v.co[index] for v in obj.data.vertices]
    after=min(coords) if side>0 else max(coords)
    shift=Vector((0,0,0)); shift[index]=boundary-after
    world=obj.matrix_world.copy();world.translation+=world.to_3x3()@shift
    obj.matrix_world=world
    return value-old


def metric_issues(p,s,scale=(1,1,1)):
    """Report playable dimensions with the same values in panels and overlays."""
    import math
    issues=[]; x,y,z=(abs(v) for v in scale)
    if 'STAIRS' in p.kind:
        count=max(1,math.ceil(p.height/p.max_step) if p.auto_steps else p.steps)
        step=p.height*z/count
        if step>s.max_step+1e-5: issues.append(tr('Step {0:.2f} m > step {1:.2f} m').format(step,s.max_step))
        width=(p.depth if p.kind=='STAIRS' else p.flight_width)*y
        if width<2*s.player_radius: issues.append(tr('Stairs {0:.2f} m < player width {1:.2f} m').format(width,2 * s.player_radius))
    if p.kind=='RAMP':
        slope=math.degrees(math.atan2(p.height*z,p.width*x))
        if slope>s.max_slope: issues.append(tr('Slope {0:.0f}° > {1:.0f}°').format(slope,s.max_slope))
    if p.kind in {'DOOR','ARCH'} or (p.kind in {'WALL','ROOM'} and p.opening in {'DOOR','ARCH'}):
        length=p.width; axis=x
        if p.kind=='ROOM' and p.room_wall in {'LEFT','RIGHT'}:
            length=p.depth-2*min(p.thickness,p.width/3,p.depth/3); axis=y
        height=min(p.open_height,p.height*.98)*z; width=min(p.open_width,length*.95)*axis
        if height<s.player_height: issues.append(tr('Opening {0:.2f} m < player height {1:.2f} m').format(height,s.player_height))
        if width<2*s.player_radius: issues.append(tr('Opening {0:.2f} m < width {1:.2f} m').format(width,2 * s.player_radius))
    if p.kind=='WATER' and s.max_wade<p.height*z<s.min_swim: issues.append('Depth between wading and swimming')
    if p.kind in {'LOW_COVER','HIGH_COVER'}:
        target=s.low_cover if p.kind=='LOW_COVER' else s.high_cover
        if abs(p.height*z-target)>.25: issues.append(tr('Cover {0:.2f} m · target {1:.2f} m').format(p.height * z,target))
    return issues


def sync_references(s,context):
    from . import rebuild
    import sys
    core=sys.modules[__package__]
    if core.BUSY or not hasattr(s.id_data,'objects'): return
    from .geometry import REFERENCES
    with guard.transaction(context):
        for obj in s.id_data.objects:
            if obj.type!='MESH' or not obj.bs.enabled or obj.bs.kind not in REFERENCES or core.manual(obj): continue
            p=obj.bs; core.BUSY=True
            try:
                for key in ('player_height','player_radius','crouch_height','max_step','jump_height','jump_gap','low_cover','high_cover'):
                    setattr(p,key,getattr(s,key))
                if p.kind in {'PLAYER','CROUCH'}:
                    p.width=p.depth=s.player_radius*2
                    p.height=s.player_height if p.kind=='PLAYER' else s.crouch_height
                if p.kind=='HEIGHT_RULER': p.height=s.player_height
            finally: core.BUSY=False
            rebuild(obj,True)


def reach(context,obj):
    """Measure a ledge from a supporting surface, excluding its own geometry."""
    from .geometry import REFERENCES
    from . import bounds
    box=bounds(obj); low=min(v.z for v in box); high=max(v.z for v in box)
    center=sum(box,Vector())/8; origin=Vector((center.x,center.y,low+.0001))
    support=None; dg=context.evaluated_depsgraph_get()
    for other in context.visible_objects:
        if other==obj or other.type!='MESH' or other.get('bs_cutter') or (other.bs.enabled and other.bs.kind in REFERENCES|{'WATER'}): continue
        bb=bounds(other)
        if not all(min(v[i] for v in bb)-.0001<=origin[i]<=max(v[i] for v in bb)+.0001 for i in (0,1)): continue
        if min(v.z for v in bb)>origin.z: continue
        world=other.matrix_world
        if abs(world.determinant())<1e-12: continue
        inv=world.inverted(); evaluated=other.evaluated_get(dg)
        hit,point,normal,_=evaluated.ray_cast(inv@origin,inv.to_3x3()@Vector((0,0,-1)))
        if not hit: continue
        point=world@point; normal=inv.to_3x3().transposed()@normal
        if normal.z>0 and point.z<=origin.z and (support is None or point.z>support): support=point.z
    support=context.scene.bs.draw_plane_z if support is None else support
    return support,high,max(0,high-support),max(v.x for v in box)+.15,center.y
