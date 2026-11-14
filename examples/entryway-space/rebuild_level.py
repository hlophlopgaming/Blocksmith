"""Reconstruct Entryway from room boundaries and heights, using native Blocksmith tools.

Only map01-sectors.json is input. No old meshes, triangulation or assembly plans are read.
"""
import copy
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = json.loads((ROOT/'map01-sectors.json').read_text())
V, SIDES, SECTORS, LINES = (SOURCE[k] for k in ('vertices','sides','sectors','lines'))
EPS = 1e-7
ZONES = [
    ('StairHall', {0,2,3,4,5,6}, 8),
    ('WestLanding', {7}, 56),
    ('Lift', {8,21,22}, 152),
    ('WestPassage', {9,10}, 56),
    ('WestYard', {11}, 8),
    ('WestTerrace', {12,13}, 64),
    ('OuterBasin', {14}, -40),
    ('EastYard', {15,16}, 24),
    ('EastIsland', {17}, -32),
    ('EntryHall', {18,19,20,23,25,27,28,29,32,33,34,35,36,37,38,39,40}, 40),
    ('EntryBasin', {24}, -8),
    ('EntryInset', {26,30,31}, 16),
    ('NorthGallery', set(range(41,52)), 48),
    ('NorthRoute', {1,52,53,54,55}, 56),
    ('NorthSecret', {56,57,58}, 56),
]
objects, cuts, parts, rooms, stairs = [], [], [], [], []


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def area(poly):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2


def world(p,z):
    return [(p[0]-384)/32,(p[1]-864)/32,(z-40)/32]


def side(index):
    return SIDES[index]['sector'] if index != 65535 else None


def boundary(members):
    edges=[]
    for a,b,flags,special,tag,r,l in LINES:
        R,L=side(r),side(l)
        if (R in members)==(L in members):continue
        edges.append((tuple(V[b]),tuple(V[a])) if R in members else (tuple(V[a]),tuple(V[b])))
    return edges


def cells(edges):
    """Sweep room outlines into maximal horizontal trapezoids, retaining holes."""
    ys=sorted({p[1] for edge in edges for p in edge})
    result=[]
    for y0,y1 in zip(ys,ys[1:]):
        mid=(y0+y1)/2
        active=[]
        for a,b in edges:
            if not min(a[1],b[1]) < mid < max(a[1],b[1]):continue
            def x(y):return a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1])
            active.append((x(mid),x(y0),x(y1)))
        active.sort()
        assert len(active)%2==0,('unclosed outline',y0,y1)
        for left,right in zip(active[::2],active[1::2]):
            cell=[(left[1],y0),(right[1],y0),(right[2],y1),(left[2],y1)]
            for previous in result:
                if (abs(previous[2][1]-y0)<EPS and
                    math.dist(previous[3],cell[0])<EPS and math.dist(previous[2],cell[1])<EPS and
                    abs(cross(previous[0],previous[3],cell[3]))<EPS and
                    abs(cross(previous[1],previous[2],cell[2]))<EPS):
                    previous[2:]=cell[2:]
                    break
            else:result.append(cell)
    return result


def add(name,shape,position,params,rotation=0,palette='Light',tag='WALKABLE'):
    obj=dict(name=name,shape=shape,position=list(position),rotation=[0,0,rotation],
             params=params,material=dict(palette=palette,pattern='07',tile_size=2),tag=tag)
    objects.append(obj)
    return obj


def add_cut(target,cutter):
    cutter=copy.deepcopy(cutter);cutter['name']=f'Cut_{len(cuts):03d}'
    objects.append(cutter);cuts.append(dict(target=target,cutter=cutter['name']))


def halfplane(target,a,b,low,high,reach):
    """Remove the right side of a directed contour edge with a native BLOCK."""
    length=math.dist(a,b);ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    origin=(b[0]+ux*reach,b[1]+uy*reach)
    add_cut(target,dict(shape='BLOCK',position=world(origin,low-1),
                        rotation=[0,0,math.degrees(math.atan2(-uy,-ux))],
                        params=dict(width=(length+2*reach)/32,depth=reach/32,height=(high-low+2)/32)))


def solid(name,poly,low,high,palette='Light',tag='WALKABLE',group=None):
    """One rectangular floor module, with native cuts only along slanted sides."""
    poly=[p for i,p in enumerate(poly) if math.dist(p,poly[i-1])>EPS]
    if area(poly)<0:poly.reverse()
    assert len(poly)>=3 and high>low and area(poly)>EPS,(name,poly)
    x0,x1=min(p[0] for p in poly),max(p[0] for p in poly)
    y0,y1=min(p[1] for p in poly),max(p[1] for p in poly)
    # A small stock margin prevents diagonal cuts from grazing the box corners.
    if any(abs(a[0]-b[0])>EPS and abs(a[1]-b[1])>EPS for a,b in zip(poly,poly[1:]+poly[:1])):
        x0-=1;x1+=1
        if len(poly)==3:y0-=1;y1+=1
    standing=group=='Columns' or name.startswith('Platform_')
    obj=add(name,'BLOCK' if standing else 'FLOOR',world((x0,y0),low if standing else high),
            dict(width=(x1-x0)/32,depth=(y1-y0)/32,height=(high-low)/32),palette=palette,tag=tag)
    corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    reach=math.hypot(x1-x0,y1-y0)+32
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if min(cross(a,b,p) for p in corners)<-EPS:
            halfplane(name,a,b,low,high,reach)
    parts.append(dict(name=name,polygon=poly,low=low,high=high,group=group))
    return obj


def room(name,members,top,low,palette='Light',tag='WALKABLE'):
    edges=boundary(members);polys=cells(edges)
    expected=sum((a[0]*b[1]-b[0]*a[1])/2 for a,b in edges)
    assert abs(sum(area(p) for p in polys)-expected)<.001,(name,'outline coverage')
    rooms.append(dict(name=name,sectors=sorted(members),height=top,area=expected/1024))
    for i,p in enumerate(polys):
        solid(f'{name}_{i:02d}',p,low,top,palette,tag,name)


def wall(name,a,b,low,high,thickness=3.2,miters=(0,0)):
    if high-low<.01:return
    dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    nx,ny=-dy/length,dx/length
    poly=[a,b,(b[0]+nx*thickness+dx/length*miters[1],b[1]+ny*thickness+dy/length*miters[1]),
          (a[0]+nx*thickness+dx/length*miters[0],a[1]+ny*thickness+dy/length*miters[0])]
    add(name,'WALL',world(a,low),dict(width=length/32,depth=thickness/32,height=(high-low)/32,
        miter_start=miters[0]/32,miter_end=miters[1]/32),
        math.degrees(math.atan2(dy,dx)),palette='Dark',tag='WALL')
    parts.append(dict(name=name,polygon=poly,low=low,high=high,group='Walls'))


def clip(poly,a,b):
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        P,Q=cross(a,b,p),cross(a,b,q)
        if P>=-EPS:out.append(p)
        if P*Q < -EPS:
            t=P/(P-Q);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return out


def intersects(a,b):
    if min(a['high'],b['high'])-max(a['low'],b['low'])<.001:return False
    p=a['polygon'][:]
    for A,B in zip(b['polygon'],b['polygon'][1:]+b['polygon'][:1]):
        p=clip(p,A,B)
        if len(p)<3:return False
    return abs(area(p))>.001


def trim_wall_overlaps():
    by_name={o['name']:o for o in objects}
    for i,part in enumerate(parts):
        if part['group']!='Walls':continue
        for previous in parts[:i]:
            if not intersects(part,previous):continue
            src=by_name[previous['name']]
            if src['shape']=='WALL':
                cutter=copy.deepcopy(src)
                # Match the stock tool's established 0.1 mm Boolean clearance.
                angle=math.radians(src['rotation'][2]);c,s=math.cos(angle),math.sin(angle)
                cutter['position'][0]+=-.0001*c+.0001*s
                cutter['position'][1]+=-.0001*s-.0001*c
                cutter['position'][2]-=.0001
                for k in ('width','depth','height'):cutter['params'][k]+=.0002
                add_cut(part['name'],cutter)
            else:
                # Solid floor cells have horizontal bases; a mitred WALL is an exact cutter.
                p=previous['polygon'];ys=sorted({v[1] for v in p})
                front=sorted(v[0] for v in p if abs(v[1]-ys[0])<EPS)
                back=sorted(v[0] for v in p if abs(v[1]-ys[-1])<EPS)
                if len(front)!=2 or len(back)!=2:
                    for j in range(1,len(p)-1):
                        tri=[p[0],p[j],p[j+1]]
                        k=max(range(3),key=lambda t:math.dist(tri[t],tri[(t+1)%3]))
                        a,b,c=tri[k],tri[(k+1)%3],tri[(k+2)%3]
                        dx,dy=b[0]-a[0],b[1]-a[1]
                        t=((c[0]-a[0])*dx+(c[1]-a[1])*dy)/(dx*dx+dy*dy)
                        foot=(a[0]+t*dx,a[1]+t*dy)
                        for end in (a,b):
                            w,h=math.dist(end,foot),math.dist(c,foot)
                            if w*h<EPS:continue
                            ux,uy=(foot[0]-end[0])/w,(foot[1]-end[1])/w
                            sign=1 if uy*(c[0]-foot[0])-ux*(c[1]-foot[1])>0 else -1
                            add_cut(part['name'],dict(shape='RAMP',
                                position=world(end,previous['low'] if sign>0 else previous['high']),
                                rotation=[90*sign,0,math.degrees(math.atan2(uy,ux))],
                                params=dict(width=w/32,depth=(previous['high']-previous['low'])/32,height=h/32)))
                    continue
                add_cut(part['name'],dict(shape='WALL',position=world((front[0],ys[0]),previous['low']),
                    rotation=[0,0,0],params=dict(width=(front[1]-front[0])/32,
                    depth=(ys[-1]-ys[0])/32,height=(previous['high']-previous['low'])/32,
                    miter_start=(back[0]-front[0])/32,miter_end=(back[1]-front[1])/32)))


def merge_walls():
    """Source linedef subdivisions are not separate architectural modules."""
    by_name={o['name']:o for o in objects}
    while True:
        walls=[p for p in parts if p['group']=='Walls']
        for a in walls:
            for b in walls:
                if a is b or (a['low'],a['high'])!=(b['low'],b['high']):continue
                A,B=a['polygon'],b['polygon']
                if math.dist(A[1],B[0])>EPS or abs(cross(A[0],A[1],B[1]))>EPS:continue
                if sum((A[1][i]-A[0][i])*(B[1][i]-B[0][i]) for i in (0,1))<=0:continue
                first,second=by_name[a['name']],by_name[b['name']]
                first['params']['width']+=second['params']['width']
                first['params']['miter_end']=second['params']['miter_end']
                a['polygon']=[A[0],B[1],B[2],A[3]]
                objects.remove(second);parts.remove(b)
                break
            else:continue
            break
        else:break


def build():
    for target in (objects,cuts,parts,rooms,stairs):target.clear()
    membership={i:(name,members,height) for name,members,height in ZONES for i in members}
    assert set(membership)==set(range(59)) and sum(len(z[1]) for z in ZONES)==59
    neighbors={name:set() for name,_,_ in ZONES}
    for a,b,flags,special,tag,r,l in LINES:
        R,L=side(r),side(l)
        if R is not None and L is not None:
            nr,nl=membership[R][0],membership[L][0]
            if nr!=nl:neighbors[nr].add(membership[L][2]);neighbors[nl].add(membership[R][2])
    for name,members,top in ZONES:
        low=min([top]+list(neighbors[name]))-5.12
        palette='Green' if name.endswith(('Yard','Island')) else 'Purple' if name=='OuterBasin' else 'Light'
        room(name,members,top,low,palette)
    # Platforms are separate structures standing on the common room foundations.
    for i in [20,23,25,27,31,39,40,46,47,50,51]:
        base=membership[i][2];top=SECTORS[i]['floor']
        room(f'Platform_S{i:02d}',{i},top,base,'Orange')
    for label,members in [('Right',{45,46,47}),('Left',{49,50,51})]:
        room('Canopy_'+label,members,240,176,'Dark','WALL')

    # The six one-sided holes are real solid structures, not wall shells.
    edges=[];sector_by_edge={}
    for a,b,flags,special,tag,r,l in LINES:
        if (r==65535)==(l==65535):continue
        R,L=side(r),side(l)
        A,B=(tuple(V[b]),tuple(V[a])) if R is not None else (tuple(V[a]),tuple(V[b]))
        edges.append((A,B));sector_by_edge[A,B]=R if R is not None else L
    loops=[];remaining=edges[:]
    while remaining:
        A,B=remaining.pop();loop=[A];used=[(A,B)];end=B
        while end!=A:
            k=next(k for k,(p,q) in enumerate(remaining) if p==end)
            p,q=remaining.pop(k);loop.append(p);used.append((p,q));end=q
        loops.append((loop,used))
    for i,(poly,used) in enumerate(loops):
        if area(poly)>=0:continue
        adjacent={sector_by_edge[e] for e in used}
        low=min(membership[j][2] for j in adjacent);high=max(SECTORS[j]['ceiling'] for j in adjacent)
        contour=list(reversed(poly))
        for j,p in enumerate(cells(list(zip(contour,contour[1:]+contour[:1])))):
            solid(f'Column_{i:02d}_{j:02d}',p,low,high,'Dark','WALL','Columns')

    # Two native STAIRS flights make a single chevron, cropped at its seam and landing.
    tangent=math.hypot(192,320);nx,ny=320/tangent,192/tangent
    run=320*ny
    for label,origin,dx,dy in [('Left',(-64,960),nx,ny),('Right',(128,1280),-nx,ny)]:
        name='Stairs_'+label
        add(name,'STAIRS',world(origin,8),dict(width=run/32,depth=tangent/32,height=1.5,
            auto_steps=False,steps=6,solid=True),math.degrees(math.atan2(dy,dx)),palette='Light')
        # CUT reparents rotated flights; allow 0.05 mm per side for matrix round-off.
        seam_x=-64+(-.0016 if label=='Left' else .0016)
        seam=((seam_x,0),(seam_x,2000)) if label=='Left' else ((seam_x,2000),(seam_x,0))
        halfplane(name,*seam,8,56,3000)
        halfplane(name,(1000,1280),(-1000,1280),8,56,3000)
        stairs.append(dict(name=name,origin=list(origin),direction=[dx,dy],run=run,depth=tangent))

    ceilings=[s['ceiling'] for s in SECTORS]
    for i,s in enumerate(SECTORS):
        if s['floor']!=s['ceiling'] or s['ceiling_texture']=='F_SKY1':continue
        heights=[]
        for a,b,flags,special,tag,r,l in LINES:
            R,L=side(r),side(l)
            if R==i and L is not None and ceilings[L]>s['floor']:heights.append(ceilings[L])
            if L==i and R is not None and ceilings[R]>s['floor']:heights.append(ceilings[R])
        if heights:ceilings[i]=min(heights)-4
    solid_edges={e for poly,used in loops if area(poly)<0 for e in used}
    # Plan offset intersections once, so both walls own the same corner seam.
    offsets={}
    def offset(a,b):
        d=math.dist(a,b);return ((b[1]-a[1])*3.2/d,-(b[0]-a[0])*3.2/d)
    for poly,used in loops:
        if area(poly)<0:continue
        for i,p in enumerate(poly):
            prev,nxt=poly[i-1],poly[(i+1)%len(poly)]
            a,b=offset(prev,p),offset(p,nxt)
            u=(p[0]-prev[0],p[1]-prev[1]);v=(nxt[0]-p[0],nxt[1]-p[1])
            den=u[0]*v[1]-u[1]*v[0]
            if abs(den)<EPS:offsets[p]=(p[0]+a[0],p[1]+a[1]);continue
            t=((b[0]-a[0])*v[1]-(b[1]-a[1])*v[0])/den
            offsets[p]=(p[0]+a[0]+t*u[0],p[1]+a[1]+t*u[1])
    for index,(a,b,flags,special,tag,r,l) in enumerate(LINES):
        R,L=side(r),side(l)
        if R==L:continue
        A,B=tuple(V[a]),tuple(V[b])
        if R is None or L is None:
            edge=(B,A) if R is not None else (A,B)
            if edge in solid_edges:continue
            i=R if R is not None else L
            start,end=(A,B) if R is not None else (B,A)
            u=((end[0]-start[0])/math.dist(start,end),(end[1]-start[1])/math.dist(start,end))
            miters=tuple(sum((offsets[p][k]-p[k])*u[k] for k in (0,1)) for p in (start,end))
            wall(f'Wall_{index:03d}',start,end,SECTORS[i]['floor'],ceilings[i],miters=miters)
        elif ceilings[R]!=ceilings[L]:
            if {R,L}&{45,46,47,49,50,51}:continue
            if all(SECTORS[i]['ceiling_texture']=='F_SKY1' for i in (R,L)):continue
            if all(SECTORS[i]['ceiling_texture']!='F_SKY1' for i in (R,L)) and min(ceilings[R],ceilings[L])>=192:continue
            start,end=(A,B) if ceilings[L]<ceilings[R] else (B,A)
            wall(f'Lintel_{index:03d}',start,end,min(ceilings[R],ceilings[L]),max(ceilings[R],ceilings[L]))
    merge_walls()
    trim_wall_overlaps()
    assert len(objects)<=1000 and len({o['name'] for o in objects})==len(objects)
    return dict(version=1,name='Entryway | Room reconstruction',
                metrics=dict(player_height=1.75,max_step=.25),objects=objects,cuts=cuts)


if __name__=='__main__':
    spec=build()
    (ROOT/'rebuild.blocksmith.json').write_text(json.dumps(spec,indent=2))
    (ROOT/'rebuild-plan.json').write_text(json.dumps(dict(rooms=rooms,parts=parts,stairs=stairs),indent=2))
    print(json.dumps(dict(visible=len(objects)-len(cuts),cutters=len(cuts),
                         shapes=dict(Counter(o['shape'] for o in objects if not o['name'].startswith('Cut_'))))))
