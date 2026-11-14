# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated planar outlines, closed-stroke simplification and watertight extrusion."""
import math

MAX_POINTS=256
EPS=1e-8


def area(loop):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(loop,loop[1:]+loop[:1]))/2


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def on_segment(p,a,b):
    return abs(cross(a,b,p))<=EPS and all(min(a[i],b[i])-EPS<=p[i]<=max(a[i],b[i])+EPS for i in (0,1))


def touches(a,b,c,d):
    sides=(cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b))
    return (sides[0]*sides[1]<0 and sides[2]*sides[3]<0) or any(
        abs(value)<=EPS and on_segment(p,u,v) for value,p,u,v in
        ((sides[0],c,a,b),(sides[1],d,a,b),(sides[2],a,c,d),(sides[3],b,c,d)))


def inside(p,loop):
    hit=False
    for a,b in zip(loop,loop[1:]+loop[:1]):
        if on_segment(p,a,b):return False
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit


def validate(contours):
    if not isinstance(contours,(list,tuple)) or not 1<=len(contours)<=17:
        raise ValueError('An outer contour and at most 16 holes are required')
    if any(not isinstance(loop,(list,tuple)) for loop in contours) or sum(len(loop) for loop in contours)>MAX_POINTS:
        raise ValueError('Use at most 256 contour points; increase stroke simplification')
    result=[]
    for number,loop in enumerate(contours):
        points=[]
        for p in loop:
            if (not isinstance(p,(list,tuple)) or len(p)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10000 for v in p)):
                raise ValueError('Contour points must be finite [x, y] coordinates within 10000 m')
            # Viewport ray projection is float32; discard sub-micron coordinate noise.
            p=tuple(round(v,6) for v in p)
            if not points or math.dist(points[-1],p)>EPS:points.append(p)
        if len(points)>1 and math.dist(points[0],points[-1])<=EPS:points.pop()
        if len(points)<3:raise ValueError('Each contour needs at least three distinct points')
        # Collinear points do not add a corner; removing them avoids zero-area cap triangles.
        changed=True
        while changed and len(points)>3:
            changed=False
            for i,p in enumerate(points):
                a,b=points[i-1],points[(i+1)%len(points)]
                if on_segment(p,a,b):points.pop(i);changed=True;break
        for i,(a,b) in enumerate(zip(points,points[1:]+points[:1])):
            prev=points[i-1]
            if abs(cross(prev,a,b))<=EPS and sum((a[k]-prev[k])*(b[k]-a[k]) for k in (0,1))<0:
                raise ValueError('A contour cannot retrace an edge')
            for j in range(i+1,len(points)):
                if j==i+1 or (i==0 and j==len(points)-1):continue
                if touches(a,b,points[j],points[(j+1)%len(points)]):
                    raise ValueError('A contour cannot cross or touch itself')
        signed=area(points)
        if abs(signed)<1e-6:raise ValueError('The contour has no usable area')
        if (signed>0)!=(number==0):points.reverse()
        result.append(points)
    if any(not .01<=max(p[k] for p in result[0])-min(p[k] for p in result[0])<=10000 for k in (0,1)):
        raise ValueError('The outer contour must be between 1 cm and 10000 m wide and deep')
    for i,hole in enumerate(result[1:],1):
        if not inside(hole[0],result[0]):raise ValueError('Holes must be strictly inside the outer contour')
        for j,other in enumerate(result[:i]):
            if any(touches(a,b,c,d) for a,b in zip(hole,hole[1:]+hole[:1])
                   for c,d in zip(other,other[1:]+other[:1])):
                raise ValueError('Contour boundaries cannot cross or touch')
            if j and (inside(hole[0],other) or inside(other[0],hole)):
                raise ValueError('Holes cannot overlap or contain other holes')
    return result


def simplify_stroke(points,tolerance):
    """Simplify two open arcs of a closed stroke, preserving sharp corners."""
    if not math.isfinite(tolerance) or tolerance<0:raise ValueError('Invalid simplification distance')
    points=[tuple(p) for p in points]
    if len(points)>2048:raise ValueError('The stroke is too long; finish it before 2048 samples')
    if len(points)>1 and math.dist(points[0],points[-1])<=max(EPS,tolerance):points.pop()
    if len(points)<3:raise ValueError('Draw a closed outline with at least three points')
    def reduce(arc):
        keep={0,len(arc)-1};stack=[(0,len(arc)-1)]
        while stack:
            first,last=stack.pop()
            if last-first<2:continue
            a,b=arc[first],arc[last];dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
            def distance(p):
                t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
                return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
            index=max(range(first+1,last),key=lambda i:distance(arc[i]))
            if distance(arc[index])>tolerance:
                keep.add(index);stack.extend(((first,index),(index,last)))
        return [arc[i] for i in sorted(keep)]
    split=max(range(1,len(points)),key=lambda i:math.dist(points[0],points[i]))
    reduced=reduce(points[:split+1])[:-1]+reduce(points[split:]+points[:1])[:-1]
    return validate([reduced])[0]


def extrude(contours,height,floor=False,width=None,depth=None):
    """Sweep horizontal bands into conforming caps; holes need no Boolean cutters."""
    loops=validate(contours)
    if type(height) not in (int,float) or not math.isfinite(height) or not .005<=height<=10000:
        raise ValueError('Extrusion height must be between 0.005 and 10000 m')
    xs=[p[0] for loop in loops for p in loop];ys0=[p[1] for loop in loops for p in loop]
    sx=(width/(max(xs)-min(xs))) if width is not None else 1
    sy=(depth/(max(ys0)-min(ys0))) if depth is not None else 1
    if not all(math.isfinite(v) and v>0 for v in (sx,sy)):raise ValueError('Outline dimensions must be positive')
    loops=[[(x*sx,y*sy) for x,y in loop] for loop in loops]
    ys=sorted({p[1] for loop in loops for p in loop})
    edges=[(a,b) for loop in loops for a,b in zip(loop,loop[1:]+loop[:1])]
    def at(a,b,y):return a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1])
    rows={y:sorted({round(p[0],10) for loop in loops for p in loop if abs(p[1]-y)<EPS}|
                   {round(at(a,b,y),10) for a,b in edges if min(a[1],b[1])<y<max(a[1],b[1])}) for y in ys}
    vertices=[];faces=[];indices={}
    bottom,top=(-height,0) if floor else (0,height)
    def vertex(x,y,z):
        key=(round(x,10),round(y,10),z)
        if key not in indices:indices[key]=len(vertices);vertices.append(key)
        return indices[key]
    def face(points):
        ids=[vertex(*p) for p in points]
        if len(set(ids))==len(ids):faces.append(tuple(ids))
    for y0,y1 in zip(ys,ys[1:]):
        mid=(y0+y1)/2
        active=sorted((at(a,b,mid),a,b) for a,b in edges if min(a[1],b[1])<mid<max(a[1],b[1]))
        for left,right in zip(active[::2],active[1::2]):
            x0,x1=at(*left[1:],y0),at(*right[1:],y0)
            x2,x3=at(*left[1:],y1),at(*right[1:],y1)
            low=[(x,y0) for x in rows[y0] if x0-EPS<=x<=x1+EPS]
            high=[(x,y1) for x in reversed(rows[y1]) if x2-EPS<=x<=x3+EPS]
            poly=low+high
            center=((x0+x1+x2+x3)/4,(y0+y1)/2)
            for a,b in zip(poly,poly[1:]+poly[:1]):
                if abs(cross(center,a,b))<1e-12:continue
                face([(*center,top),(*a,top),(*b,top)])
                face([(*center,bottom),(*b,bottom),(*a,bottom)])
    for a,b in edges:
        if abs(a[1]-b[1])<EPS:
            points=[(x,a[1]) for x in rows[a[1]] if min(a[0],b[0])-EPS<=x<=max(a[0],b[0])+EPS]
            if a[0]>b[0]:points.reverse()
        else:
            points=[(at(a,b,y),y) for y in ys if min(a[1],b[1])-EPS<=y<=max(a[1],b[1])+EPS]
            if a[1]>b[1]:points.reverse()
        for p,q in zip(points,points[1:]):face([(*p,bottom),(*q,bottom),(*q,top),(*p,top)])
    return vertices,faces
