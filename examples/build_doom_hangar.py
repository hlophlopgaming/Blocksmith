# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate a modular E1M1-inspired test layout, not an exact WAD conversion."""
import json
import math
from pathlib import Path
from collections import defaultdict, deque

ROOT=Path(__file__).resolve().parents[1]
objects=[]
cuts=[]
occupied={}
# x0, y0, x1, y1, zone. Shared edges become open passages.
rooms=[(-32,-7,-18,7,'Start'),(-38,-2,-32,2,'ArmorPassage'),(-52,-8,-38,8,'ArmorRoom'),
       (-26,7,-22,16,'NorthPassage'),(-26,12,-8,16,'NorthPassage'),
       (-12,16,12,30,'ControlRoom'),(12,19,24,23,'EastPassage'),(20,12,24,23,'EastPassage'),
       (18,-10,36,12,'Zigzag'),(24,-16,28,-10,'ExitPassage'),(22,-24,32,-16,'ExitHall'),
       (24,-29,30,-24,'ExitBooth'),(2,-14,24,-10,'SecretPassage'),(0,-12,4,-8,'SecretPassage'),
       (-18,-8,16,12,'Courtyard')]
for x0,y0,x1,y1,zone in rooms:
    for x in range(x0,x1):
        for y in range(y0,y1): occupied[x,y]=zone


def module(name,shape,x,y,z=0,rotation=0,palette='Light',pattern='13',tag=None,**params):
    obj={'name':name,'position':[x,y,z],'params':params,
         'material':{'palette':palette,'pattern':pattern,'tile_size':2}}
    if shape in {'FLOOR','WALL','DOOR','WINDOW','BLOCK','CYLINDER','STAIRS','WATER','PLAYER'}: obj['shape']=shape
    else: obj['preset']=shape
    if rotation: obj['rotation']=[0,0,rotation]
    if tag: obj['tag']=tag
    objects.append(obj)
    return obj


# Merge each zone's cells into disjoint rectangles: no coplanar overlapping room floors.
remaining=dict(occupied)
floor_index=0
while remaining:
    x,y=min(remaining,key=lambda p:(p[1],p[0])); zone=remaining[x,y]
    width=1
    while remaining.get((x+width,y))==zone: width+=1
    depth=1
    while all(remaining.get((u,y+depth))==zone for u in range(x,x+width)): depth+=1
    for u in range(x,x+width):
        for v in range(y,y+depth): del remaining[u,v]
    floor_index+=1
    z=-.8 if zone=='Zigzag' else 0
    palette='Green' if zone=='Courtyard' else 'Dark'
    module(f'{zone}_Floor_{floor_index:02d}','FLOOR',x,y,z,width=width,depth=depth,height=.25,palette=palette,tag='WALKABLE')

# Merge exterior unit edges into long modular walls.
edges=defaultdict(list)
for x,y in occupied:
    for dx,dy,axis,line,start in [(0,-1,'H',y,x),(0,1,'H',y+1,x),(-1,0,'V',x,y),(1,0,'V',x+1,y)]:
        if (x+dx,y+dy) not in occupied: edges[axis,line,dx,dy].append(start)
wall_index=0
def quadrant_count(x,y):
    return sum((u,v) in occupied for u in (x-1,x) for v in (y-1,y))

for (axis,line,dx,dy),starts in sorted(edges.items()):
    starts=sorted(starts); runs=[]; a=b=starts[0]
    for v in starts[1:]:
        if v==b+1: b=v
        else: runs.append((a,b+1)); a=b=v
    runs.append((a,b+1))
    for a,b in runs:
        wall_index+=1
        # Place shells outside the floor footprint; split the dark belt from the wall.
        if axis=='H':
            if quadrant_count(a,line)==3: a+=.25
            if quadrant_count(b,line)==3: b-=.25
            x,y,rotation=a,line if dy>0 else line-.25,0
        else: x,y,rotation=line+.25 if dx>0 else line,a,90
        module(f'OuterWall_{wall_index:03d}','WALL',x,y,.4,rotation=rotation,width=b-a,depth=.25,height=3.4,palette='Light')
        module(f'WallBelt_{wall_index:03d}','WALL',x,y,-.9,rotation=rotation,width=b-a,depth=.25,height=1.3,palette='Dark',pattern='03')

# Fill convex outside corners with butted posts, avoiding overlapped wall ends.
vertices={(x+dx,y+dy) for x,y in occupied for dx in (0,1) for dy in (0,1)}
for x,y in sorted(vertices):
    if quadrant_count(x,y)!=1: continue
    q=next((u,v) for u in (x-1,x) for v in (y-1,y) if (u,v) in occupied)
    px=x if q[0]==x-1 else x-.25; py=y if q[1]==y-1 else y-.25
    module(f'CornerUpper_{x}_{y}','BLOCK',px,py,.4,width=.25,depth=.25,height=3.4,palette='Light')
    module(f'CornerBelt_{x}_{y}','BLOCK',px,py,-.9,width=.25,depth=.25,height=1.3,palette='Dark',pattern='03')

# The courtyard touches the starting hall, but remains separated by two large windows.
module('Start_CourtyardWindows','WINDOW',-18,-7,rotation=90,width=14,depth=.35,height=3.8,
       count=2,open_width=4,open_height=1.9,sill=.9,palette='Light')
module('Start_WestDoor','DOOR',-32,-2,rotation=90,width=4,depth=.4,height=3.8,open_width=3.2,open_height=2.8,palette='Orange',pattern='03')
module('North_EntryFrame','DOOR',-12,16,width=4,depth=.4,height=3.8,open_width=3.2,open_height=2.8,palette='Orange',pattern='03')
module('North_EastFrame','DOOR',12,19,rotation=90,width=4,depth=.4,height=3.8,open_width=3.2,open_height=2.8,palette='Orange',pattern='03')
module('Zigzag_EntryFrame','DOOR',20,12,width=4,depth=.4,height=3.8,open_width=3.3,open_height=2.8,palette='Orange',pattern='03')
module('Exit_HallFrame','DOOR',24,-16,width=4,depth=.4,height=3.8,open_width=3.2,open_height=2.8,palette='Orange',pattern='03')
module('Exit_FinalFrame','DOOR',24,-24,width=6,depth=.4,height=3.8,open_width=3,open_height=2.8,palette='Red',pattern='03')
module('Secret_OpenFrame','DOOR',17,-14,rotation=90,width=4,depth=.35,height=3.8,open_width=3.2,open_height=2.8,palette='Dark',pattern='03')

# West armor dais and staircase: the first memorable detour.
module('Armor_RaisedDais','BLOCK',-51,-5,width=9,depth=10,height=1,palette='Dark',tag='WALKABLE')
module('Armor_Stairs','STAIRS',-38,1.5,rotation=180,width=4,depth=3,height=1,palette='Orange',max_step=.2)
module('Armor_PickupPedestal','CYLINDER',-47,0,1,width=1.2,depth=1.2,height=.4,segments=8,palette='Green',tag='INTERACTIVE')
for y in (-5,4):
    module(f'Start_Pedestal_{y}','BLOCK',-29,y,width=1.5,depth=1,height=.9,palette='Dark')

# Northern computer room: two consoles, a stair and raised control station.
module('Control_RaisedStation','BLOCK',3,19,width=6,depth=8,height=1,palette='Dark',tag='WALKABLE')
module('Control_StationStairs','STAIRS',-1,21,width=4,depth=4,height=1,palette='Orange',max_step=.2)
for y in (20,25):
    module(f'Control_Console_{y}','BLOCK',-8,y,width=4,depth=1.3,height=1.1,palette='Dark')
    module(f'Control_Screen_{y}','BLOCK',-7.8,y+.12,1.1,width=3.6,depth=1,height=.12,palette='Purple',pattern='09',tag='INTERACTIVE')
for x in (-11,10):
    for y in (17,28): module(f'Control_Pillar_{x}_{y}','BLOCK',x,y,width=.65,depth=.65,height=3.8,palette='Dark')
module('Courtyard_Island','CYLINDER',-2,2,width=8,depth=8,height=.35,segments=8,palette='Dark',tag='WALKABLE')
module('Courtyard_ArmorMarker','CYLINDER',-2,2,.35,width=.8,depth=.8,height=.6,segments=8,palette='Purple',tag='INTERACTIVE')

# Non-colliding acid volume above the lowered basin floor; route remains on solid beams.
module('Zigzag_AcidWater','WATER',18,-10,-.25,width=18,depth=22,height=.5,palette='Green',pattern='08',tag='WATER')
zigzag=[(22,12),(22,8),(31,4),(22,-1),(31,-6),(26,-10)]
for i,(a,b) in enumerate(zip(zigzag,zigzag[1:])):
    dx,dy=b[0]-a[0],b[1]-a[1]; length=math.hypot(dx,dy); angle=math.atan2(dy,dx); half=1.5
    # Small height offsets at overlapping joints prevent coplanar texture flickering.
    z=-.5+i*.002
    module(f'Zigzag_Bridge_{i:02d}','BLOCK',a[0]+math.sin(angle)*half,a[1]-math.cos(angle)*half,z,
           rotation=math.degrees(angle),width=length,depth=3,height=.5,palette='Dark',tag='WALKABLE')
# Trim each new bridge against the preceding beam with an explicit live cutter.
import copy
for i in range(1,len(zigzag)-1):
    source=next(o for o in objects if o['name']==f'Zigzag_Bridge_{i-1:02d}')
    cutter=copy.deepcopy(source); cutter['name']=f'BridgeJoint_Cutter_{i:02d}'; objects.append(cutter)
    cuts.append({'target':f'Zigzag_Bridge_{i:02d}','cutter':cutter['name']})
module('BridgeExit_Flush','BLOCK',17,-14,-1,width=20,depth=4,height=2)
cuts.append({'target':'Zigzag_Bridge_04','cutter':'BridgeExit_Flush'})
module('Zigzag_ImpLedge','BLOCK',33,-1,width=2.6,depth=9,height=1.5,palette='Dark')
module('Zigzag_LedgeStair','STAIRS',35.7,-5,rotation=90,width=4,depth=2.5,height=1.5,palette='Dark',max_step=.2)
for i,y in enumerate((0,5)):
    module(f'Zigzag_Barrel_{i}','CYLINDER',34.3,y,1.5,width=.7,depth=.7,height=1,segments=12,palette='Orange',pattern='11',tag='PROP')
for x,y in [(23,-22),(29,-19),(6,-12)]:
    module(f'TechCrate_{x}_{y}','BLOCK',x,y,width=1.2,depth=1.2,height=1,palette='Dark',pattern='11',tag='PROP')
module('Exit_ButtonPanel','BLOCK',26.4,-28.65,.7,width=1.2,depth=.25,height=1.2,palette='Dark',tag='INTERACTIVE')
module('Exit_Button','BLOCK',26.7,-28.4,1,width=.6,depth=.12,height=.5,palette='Red',pattern='01',tag='INTERACTIVE')
module('Start_PlayerScale','PLAYER',-25,-4)

# Assert the layout is connected before asking Blender to create hundreds of meshes.
visited={next(iter(occupied))}; queue=deque(visited)
while queue:
    x,y=queue.popleft()
    for p in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
        if p in occupied and p not in visited: visited.add(p); queue.append(p)
assert len(visited)==len(occupied),'Disconnected floorplan'
assert len(objects)==len({o['name'] for o in objects})
route=[[-25,-4],[-24,4],[-24,14],[-10,14],[-10,18],[-2,18],[-2,28],[9.4,28],[10,27],[10,21],[22,21]]
route+=list(map(list,zigzag))+[[26,-14],[26,-19],[27,-25],[27,-27]]
for x,y in route: assert (math.floor(x),math.floor(y)) in occupied,(x,y)
spec={'version':1,'name':'Hangar — E1M1 inspired blockout','metrics':{'player_height':1.8,'player_radius':.3,'max_step':.25},'objects':objects,'cuts':cuts}
out=ROOT/'examples'/'doom-hangar.json'; out.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
(ROOT/'examples'/'doom-hangar-route.json').write_text(json.dumps({'start':[-25,-4,0],'route':route,'expected_objects':len(objects),'water':'Zigzag_AcidWater'},indent=2)+'\n')
print(f'{len(objects)} modules, {len(occupied)} connected floor cells, {len(route)} route waypoints → {out}')
