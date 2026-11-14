"""Apply the staged Blocksmith contour tools to the reconstructed Entryway kit."""
import copy
import json
from pathlib import Path

import rebuild_level as base

ROOT=Path(__file__).resolve().parent


def loops(edges):
    remaining=list(edges);result=[]
    while remaining:
        a,b=remaining.pop();loop=[a];end=b
        while end!=a:
            i=next(i for i,(p,q) in enumerate(remaining) if p==end)
            p,q=remaining.pop(i);loop.append(p);end=q
        result.append(loop)
    result.sort(key=lambda p:-base.area(p))
    return result


def build():
    source=base.build();old={o['name']:o for o in source['objects']}
    keep={o['name'] for o in source['objects'] if not o['name'].startswith('Cut_') and o['shape'] in {'WALL','STAIRS'}}
    cuts=[c for c in source['cuts'] if c['target'] in keep]
    keep.update(c['cutter'] for c in cuts)
    objects=[copy.deepcopy(o) for o in source['objects'] if o['name'] in keep]
    expected=[]
    def add(name,contours,low,high,kind,material,tag):
        coordinates=[[[(x-384)/32,(y-864)/32] for x,y in loop] for loop in contours]
        objects.append(dict(name=name,shape=kind,contours=coordinates,position=[0,0,((high if kind=='POLY_FLOOR' else low)-40)/32],
                            params=dict(height=(high-low)/32),material=material,tag=tag))
        area=sum(base.area(p) for p in contours)/1024
        expected.append(dict(name=name,area=area,top=(high-40)/32,low=(low-40)/32,loops=len(contours)))
    for room in base.rooms:
        parts=[p for p in base.parts if p['group']==room['name']]
        first=parts[0];obj=old[first['name']]
        contours=loops(base.boundary(set(room['sectors'])))
        add(room['name'],contours,first['low'],first['high'],
            'POLY_BLOCK' if obj['shape']=='BLOCK' else 'POLY_FLOOR',obj['material'],obj['tag'])
    edges=[]
    for a,b,flags,special,tag,r,l in base.LINES:
        if (r==65535)==(l==65535):continue
        edges.append((tuple(base.V[b]),tuple(base.V[a])) if r!=65535 else (tuple(base.V[a]),tuple(base.V[b])))
    # Match the deterministic core order used by the room reconstruction.
    remaining=edges[:];index=0
    while remaining:
        a,b=remaining.pop();loop=[a];end=b
        while end!=a:
            k=next(k for k,(p,q) in enumerate(remaining) if p==end)
            p,q=remaining.pop(k);loop.append(p);end=q
        if base.area(loop)<0:
            name=f'Column_{index:02d}'
            first=next(p for p in base.parts if p['name'].startswith(name+'_'))
            obj=old[first['name']]
            add(name,[list(reversed(loop))],first['low'],first['high'],'POLY_BLOCK',obj['material'],obj['tag'])
        index+=1
    spec=dict(version=1,name='Entryway | Native contour tools',metrics=source['metrics'],objects=objects,cuts=cuts)
    return spec,expected


if __name__=='__main__':
    spec,expected=build()
    (ROOT/'level.blocksmith.json').write_text(json.dumps(spec,indent=2))
    (ROOT/'plan.json').write_text(json.dumps(expected,indent=2))
    print(json.dumps(dict(visible=len(spec['objects'])-len(spec['cuts']),cutters=len(spec['cuts']),single_contour_structures=len(expected))))
