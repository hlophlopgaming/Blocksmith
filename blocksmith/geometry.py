# SPDX-License-Identifier: GPL-3.0-or-later
"""Closed mesh pieces in meters; no Blender dependency."""
from math import sin, cos, pi, ceil, sqrt
from types import SimpleNamespace

SHAPES = ('BLOCK', 'WALL', 'DOOR', 'WINDOW', 'ARCH', 'FLOOR', 'STAIRS',
          'RAMP', 'CYLINDER', 'CORNER', 'L_STAIRS', 'U_STAIRS', 'CURVED_WALL',
          'SPIRAL_STAIRS', 'ROOF', 'LOW_COVER', 'HIGH_COVER', 'LADDER',
          'RAILING', 'WATER', 'ROOM', 'PLAYER', 'CROUCH', 'HEIGHT_RULER',
          'JUMP_RULER', 'CLEARANCE', 'POLY_FLOOR', 'POLY_BLOCK')
REFERENCES = {'PLAYER','CROUCH','HEIGHT_RULER','JUMP_RULER','CLEARANCE'}


def wall_min_width(p):
    if p.kind not in {'WALL','DOOR','WINDOW','ARCH'}: return .01
    opening=p.opening if p.kind=='WALL' else p.kind
    if opening=='NONE': return max(.01,p.miter_start-p.miter_end+.01)
    cut=max(p.miter_start,-p.miter_end)
    return p.count*p.open_width+(p.count+1)*(cut+.01) if cut>0 else .01

def arch_top(f,width,height,sill,style):
    rise=min(width/2,height*.5); u=2*f-1
    if style=='POINTED': return sill+height-rise+rise*(1-abs(u))
    if style=='SEGMENTAL': return sill+height-rise*.5+rise*.5*sqrt(max(0,1-u*u))
    return sill+height-rise+rise*sqrt(max(0,1-u*u))


class Mesh:
    def __init__(self):
        self.vertices, self.faces = [], []

    def prism(self, profile, depth, y=0):
        """Extrude a counterclockwise X/Z polygon along Y."""
        n, start = len(profile), len(self.vertices)
        self.vertices += [(x, y, z) for x, z in profile]
        self.vertices += [(x, y + depth, z) for x, z in profile]
        self.faces += [tuple(start + i for i in range(n)),
                       tuple(start + n + i for i in reversed(range(n)))]
        self.faces += [(start+i, start+n+i, start+n+(i+1)%n, start+(i+1)%n)
                       for i in range(n)]

    def box(self, x, y, z, w, d, h):
        if min(w, d, h) > 1e-7:
            self.prism([(x,z),(x+w,z),(x+w,z+h),(x,z+h)], d, y)

    def sector(self, inner, outer, a, b, z, height, steps):
        full=abs(abs(b-a)-2*pi)<1e-7
        count=steps if full else steps+1
        base=len(self.vertices)
        for i in range(count):
            angle=a+(b-a)*i/steps
            self.vertices += [(r*cos(angle),r*sin(angle),zz) for r,zz in ((inner,z),(outer,z),(inner,z+height),(outer,z+height))]
        for i in range(steps):
            j=(i+1)%count; p=base+4*i; q=base+4*j
            self.faces += [(p,q,q+1,p+1),(p+2,p+3,q+3,q+2),(p+1,q+1,q+3,p+3)]
            if inner>1e-7: self.faces.append((p,p+2,q+2,q))
        if not full:
            p=base; q=base+4*(count-1)
            self.faces += [(p,p+1,p+3,p+2),(q,q+2,q+3,q+1)]
        if inner<=1e-7:
            # A shared axial edge keeps cylinder fans connected without radial internal faces.
            remap={base+4*i+j:base+j for i in range(count) for j in (0,2)}
            self.faces=[tuple(dict.fromkeys(remap.get(v,v) for v in face)) for face in self.faces]
            self.faces=[face for face in self.faces if len(face)>=3]

    def spiral(self,inner,outer,angle,height,n,segments,column,solid,thickness):
        total=n*max(1,segments//n)
        extent=angle*pi/180
        tau=2*pi
        angles=sorted({0,round(tau,12),*(round((extent*i/total)%tau,12) for i in range(total+1))})
        def face(points):
            start=len(self.vertices); self.vertices.extend(points); self.faces.append(tuple(range(start,start+len(points))))
        def at(r,a,z): return (r*cos(a),r*sin(a),z)
        def band(a,lo,hi,reverse=False):
            if hi-lo<1e-8:return
            points=[at(inner,a,lo),at(outer,a,lo),at(outer,a,hi),at(inner,a,hi)]
            face(list(reversed(points)) if reverse else points)
        def difference(lo,hi,blocked):
            for a,b in blocked:
                if a>lo+1e-8:yield lo,min(hi,a)
                lo=max(lo,b)
                if lo>=hi-1e-8:return
            if lo<hi-1e-8:yield lo,hi
        cells=[]
        for a,b in zip(angles,angles[1:]):
            intervals=[]
            for turn in range(ceil(extent/tau)):
                middle=(a+b)/2+turn*tau
                if middle>=extent:continue
                i=min(n-1,int(middle/extent*n)); top=height*(i+1)/n
                intervals.append((0 if solid else max(0,top-thickness),top))
            merged=[]
            for lo,hi in sorted(intervals):
                if merged and lo<=merged[-1][1]+1e-8:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
                else:merged.append((lo,hi))
            cells.append(merged)
        for i,(a,b) in enumerate(zip(angles,angles[1:])):
            cell=cells[i]
            if column:
                face([at(0,a,0),at(inner,b,0),at(inner,a,0)])
                face([at(0,a,height),at(inner,a,height),at(inner,b,height)])
                for lo,hi in difference(0,height,cell):
                    face([at(inner,a,lo),at(inner,b,lo),at(inner,b,hi),at(inner,a,hi)])
            for bottom,top in cell:
                face([at(inner,a,bottom),at(inner,b,bottom),at(outer,b,bottom),at(outer,a,bottom)])
                face([at(inner,a,top),at(outer,a,top),at(outer,b,top),at(inner,b,top)])
                face([at(outer,a,bottom),at(outer,b,bottom),at(outer,b,top),at(outer,a,top)])
                if not column:face([at(inner,a,bottom),at(inner,a,top),at(inner,b,top),at(inner,b,bottom)])
                for boundary,neighbour,reverse in ((a,cells[i-1],False),(b,cells[(i+1)%len(cells)],True)):
                    for lo,hi in difference(bottom,top,neighbour):band(boundary,lo,hi,reverse)
        # Split vertical seams at adjacent tread heights, then share their vertices.
        levels={}
        for x,y,z in self.vertices:levels.setdefault((round(x,10),round(y,10)),set()).add(z)
        vertices=[];indices={};faces=[]
        for polygon in self.faces:
            points=[self.vertices[i] for i in polygon]; expanded=[]
            for a,b in zip(points,points[1:]+points[:1]):
                expanded.append(a)
                key=(round(a[0],10),round(a[1],10))
                if key==(round(b[0],10),round(b[1],10)):
                    zs=sorted(z for z in levels[key] if min(a[2],b[2])+1e-8<z<max(a[2],b[2])-1e-8)
                    if a[2]>b[2]:zs.reverse()
                    expanded.extend((a[0],a[1],z) for z in zs)
            face_indices=[]
            for point in expanded:
                key=tuple(round(v,10) for v in point)
                if key not in indices:indices[key]=len(vertices);vertices.append(point)
                if not face_indices or face_indices[-1]!=indices[key]:face_indices.append(indices[key])
            if len(face_indices)>2 and face_indices[0]==face_indices[-1]:face_indices.pop()
            if len(face_indices)>2:faces.append(tuple(face_indices))
        self.vertices=vertices; self.faces=faces


def build(p):
    m = Mesh()
    k = p.kind
    w,d,h = max(.001,p.width), max(.001,p.depth), max(.001,p.height)
    t = min(p.thickness,w/3,d/3)
    if k in {'POLY_FLOOR','POLY_BLOCK'}:
        import json
        if __package__:
            from .outline_geometry import extrude
        else:
            from outline_geometry import extrude
        m.vertices,m.faces=extrude(json.loads(p.contours),h,k=='POLY_FLOOR',w,d)
    elif k in {'BLOCK','LOW_COVER','HIGH_COVER','FLOOR','WATER'}:
        m.box(0,0,-h if k in {'FLOOR','WATER'} else 0,w,d,h)
    elif k in {'WALL','DOOR','WINDOW','ARCH'}:
        opening = p.opening if k == 'WALL' else {'DOOR':'DOOR','WINDOW':'WINDOW','ARCH':'ARCH'}[k]
        if opening == 'NONE':
            start,end=getattr(p,'miter_start',0),getattr(p,'miter_end',0)
            if w+end-start<=1e-5:
                raise ValueError('The wall is too short for this angle')
            if start or end:
                m.vertices=[(x,y,z) for z in (0,h) for x,y in ((0,0),(w,0),(w+end,d),(start,d))]
                m.faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
            else: m.box(0,0,0,w,d,h)
        else:
            ow, oh = min(p.open_width,w*.95), min(p.open_height,h*.98)
            sill = min(p.sill,max(0,h-oh-.01)) if opening in {'WINDOW','ARCH_WINDOW'} else 0
            count = max(1,min(p.count,int(w/(ow+.02))))
            gap = (w-count*ow)/(count+1)
            offset = max(-gap*.95,min(gap*.95,p.offset))
            start,end=getattr(p,'miter_start',0),getattr(p,'miter_end',0)
            if gap-max(0,start,-end)<=1e-5:
                raise ValueError('The wall is too short for the opening and miter')
            offset=max(max(-gap*.95,start-gap+.0001),min(min(gap*.95,gap+end-.0001),offset))
            last = 0
            for i in range(count):
                x = gap*(i+1)+ow*i+offset
                m.box(last,0,0,x-last,d,h)
                m.box(x,0,0,ow,d,sill)
                if opening in {'ARCH','ARCH_WINDOW'}:
                    for j in range(p.segments):
                        a,b = j/p.segments,(j+1)/p.segments
                        def top(f): return arch_top(f,ow,oh,sill,p.arch_style)
                        m.prism([(x+ow*a,top(a)),(x+ow*b,top(b)),(x+ow*b,h),(x+ow*a,h)],d)
                else:
                    m.box(x,0,sill+oh,ow,d,h-sill-oh)
                last=x+ow
            m.box(last,0,0,w-last,d,h)
    elif k == 'RAMP':
        m.prism([(0,0),(w,0),(w,h)],d)
    elif k in {'STAIRS','L_STAIRS','U_STAIRS'}:
        n = max(1,p.steps if not p.auto_steps else ceil(h/p.max_step))
        if k == 'STAIRS' or min(w,d)<3*t:
            if p.solid:
                profile=[(0,0),(w,0),(w,h)]
                for i in range(n-1,-1,-1):
                    profile.append((w*i/n,h*(i+1)/n))
                    if i: profile.append((w*i/n,h*i/n))
                m.prism(profile,d)
            else:
                for i in range(n):
                    z=max(0,h*(i+1)/n-p.thickness)
                    m.box(w*i/n,0,z,w/n,d,h*(i+1)/n-z)
        else:
            flight = min(p.flight_width,d/2,w/2)
            n1,n2 = max(1,n//2),max(1,n-n//2)
            run = max(.01,w-flight)
            for i in range(n1):
                m.box(run*i/n1,0,0,run/n1,flight,h*(i+1)/(2*n1))
            m.box(run,0,0,flight,d if k=='U_STAIRS' else flight,h/2)
            for i in range(n2):
                if k == 'U_STAIRS':
                    m.box(run-(i+1)*run/n2,d-flight,0,run/n2,flight,h/2+h*(i+1)/(2*n2))
                else:
                    m.box(run,flight+(d-flight)*i/n2,0,flight,(d-flight)/n2,h/2+h*(i+1)/(2*n2))
    elif k in {'CYLINDER','CURVED_WALL','SPIRAL_STAIRS'}:
        radius = w/2
        if k == 'CYLINDER':
            m.sector(0,radius,0,2*pi,0,h,p.segments)
        elif k == 'CURVED_WALL':
            m.sector(max(.001,radius-p.thickness),radius,0,min(360,p.angle)*pi/180,0,h,p.segments)
        else:
            n = max(1,p.steps if not p.auto_steps else ceil(h/p.max_step))
            inner = min(radius*.9,p.inner_radius)
            m.spiral(inner,radius,p.angle,h,n,p.segments,p.column,p.solid,p.thickness)
    elif k == 'CORNER':
        m.box(0,0,0,w,t,h)
        m.box(0,t,0,t,d-t,h)
    elif k == 'ROOF':
        profile = [(0,0),(w,0),(w/2,h)] if p.roof=='GABLE' else [(0,0),(w,0),(w,h)]
        m.prism(profile,d)
    elif k == 'ROOM':
        m.box(0,0,-p.thickness,w,d,p.thickness)
        for side,x,y,length,turned in [('FRONT',0,0,w,False),('BACK',0,d-t,w,False),
                                        ('LEFT',t,t,d-2*t,True),('RIGHT',w,t,d-2*t,True)]:
            wall=SimpleNamespace(**{key:getattr(p,key) for key in
                ('thickness','open_width','open_height','sill','offset','count','segments','arch_style')},
                kind='WALL',width=length,depth=t,height=h,flip=False,miter_start=0,miter_end=0,
                opening=p.opening if side==p.room_wall else 'NONE')
            part=build(wall); base=len(m.vertices)
            m.vertices += [(x-b,y+a,z) if turned else (x+a,y+b,z) for a,b,z in part.vertices]
            m.faces += [tuple(base+i for i in face) for face in part.faces]
    elif k == 'LADDER':
        bar = min(p.thickness,w/4)
        m.box(0,0,0,bar,d,h); m.box(w-bar,0,0,bar,d,h)
        for i in range(1,max(2,ceil(h/p.spacing))):
            m.box(bar,0,min(h-bar,i*p.spacing),w-2*bar,d,bar)
    elif k == 'RAILING':
        n=max(1,ceil(w/p.spacing))
        for i in range(n+1):
            m.box(min(w-t,i*w/n),0,0,t,d,h)
        for i in range(p.rails):
            m.box(0,0,h*(i+1)/p.rails-t,w,d,t)
    elif k in {'PLAYER','CROUCH'}:
        # Capsule surface, with an explicit equatorial seam for the straight body.
        r=min(w/2,h/2); rings=[]; n=p.segments
        for zc,lower in [(r,True),(h-r,False)]:
            for j in range(9):
                a=(-pi/2+j*pi/16) if lower else j*pi/16
                rr=max(1e-6,r*cos(a)); z=zc+r*sin(a)
                rings.append([(w/2+rr*cos(i*2*pi/n),d/2+rr*sin(i*2*pi/n),z) for i in range(n)])
        m.vertices=[v for ring in rings for v in ring]
        m.faces=[tuple(reversed(range(n))),tuple((len(rings)-1)*n+i for i in range(n))]
        for j in range(len(rings)-1):
            m.faces.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
    elif k == 'HEIGHT_RULER':
        m.box(0,0,0,.05,.05,h)
        for z in (p.max_step,p.low_cover,p.crouch_height,p.jump_height,p.high_cover,p.player_height):
            m.box(0,0,z,.3,.05,.02)
    elif k == 'JUMP_RULER':
        m.box(0,0,0,p.jump_gap,.08,.02)
        for i in range(ceil(p.jump_gap)+1):
            m.box(min(i,p.jump_gap),0,0,.02,.08,.2)
    elif k == 'CLEARANCE':
        m.box(0,0,0,.05,.1,p.player_height+.05)
        m.box(p.player_radius*2+.05,0,0,.05,.1,p.player_height+.05)
        m.box(0,0,p.player_height,p.player_radius*2+.1,.1,.05)
    if k in {'WALL','DOOR','WINDOW','ARCH'} and not (k=='WALL' and p.opening=='NONE'):
        start,end=getattr(p,'miter_start',0),getattr(p,'miter_end',0)
        m.vertices=[(x+(start if abs(x)<1e-7 else end if abs(x-w)<1e-7 else 0)*y/d,y,z) for x,y,z in m.vertices]
    if p.flip:
        m.vertices=[(w-x,y,z) for x,y,z in m.vertices]
        m.faces=[tuple(reversed(f)) for f in m.faces]
    used=sorted({i for face in m.faces for i in face})
    if len(used)!=len(m.vertices):
        remap={old:new for new,old in enumerate(used)}
        m.vertices=[m.vertices[i] for i in used]
        m.faces=[tuple(remap[i] for i in face) for face in m.faces]
    return m
