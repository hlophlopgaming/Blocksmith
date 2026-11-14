# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict, data-only input contract shared by the CLI and Blender runner."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'blocksmith'))
from geometry import SHAPES
from presets import PRESETS, BY_ID
from outline_geometry import validate as validate_contours

TAGS=('BLOCKOUT','WALKABLE','WALL','COVER','CLIMBABLE','INTERACTIVE','HAZARD','TRIGGER','PROP','OUT_OF_BOUNDS','WATER')
DIMENSIONS={'width','depth','height','thickness','open_width','open_height','sill','offset',
            'max_step','flight_width','inner_radius','spacing','uv_tile'}
METRICS={'wall_height','wall_thickness','floor_thickness','door_width','door_height','water_depth',
         'player_height','player_radius','crouch_height','max_step','jump_height','jump_gap',
         'max_slope','low_cover','high_cover','max_wade','min_swim'}
CHOICES={'opening':('NONE','DOOR','WINDOW','ARCH','ARCH_WINDOW'),
         'room_wall':('FRONT','BACK','LEFT','RIGHT'),
         'arch_style':('ROUND','SEGMENTAL','POINTED'),'roof':('GABLE','SHED')}
BOOLS={'auto_steps','solid','flip','column'}
INTS={'steps':(1,512),'segments':(8,128),'count':(1,100),'rails':(1,12)}


def fail(path,message):
    raise ValueError(path+': '+message)


def number(value,path,low=-10000,high=10000):
    if type(value) not in (int,float) or not low<=value<=high or not math.isfinite(value):
        fail(path,f'expected finite number in [{low}, {high}]')


def keys(value,allowed,path):
    if not isinstance(value,dict): fail(path,'expected object')
    unknown=set(value)-set(allowed)
    if unknown: fail(path,'unknown fields: '+', '.join(sorted(unknown)))


def vector(value,path,low=-10000,high=10000):
    if not isinstance(value,list) or len(value)!=3: fail(path,'expected [x, y, z]')
    for i,n in enumerate(value): number(n,f'{path}[{i}]',low,high)


def validate(spec):
    keys(spec,{'version','name','metrics','objects','cuts'},'$')
    if type(spec.get('version')) is not int or spec['version']!=1: fail('version','must be 1')
    if 'name' in spec and (not isinstance(spec['name'],str) or len(spec['name'])>128): fail('name','expected string up to 128 characters')
    metrics=spec.get('metrics',{}); keys(metrics,METRICS,'metrics')
    for key,value in metrics.items(): number(value,'metrics.'+key,.01,1000)
    objects=spec.get('objects')
    if not isinstance(objects,list) or not 1<=len(objects)<=1000: fail('objects','expected 1 to 1000 objects')
    names=set()
    for i,obj in enumerate(objects):
        path=f'objects[{i}]'
        keys(obj,{'name','shape','preset','material','position','rotation','tag','params','pivot','contours'},path)
        if 'preset' in obj:
            if not isinstance(obj['preset'],str) or obj['preset'] not in BY_ID: fail(path+'.preset','unknown preset')
            if 'shape' in obj and obj['shape']!=BY_ID[obj['preset']][3]: fail(path,'shape conflicts with preset')
        if 'params' in obj and not isinstance(obj['params'],dict): fail(path+'.params','expected object')
        obj=resolve(obj)
        if 'material' in obj:
            mat=obj['material']; keys(mat,{'palette','pattern','tile_size'},path+'.material')
            if mat.get('palette','Light') not in ('Light','Dark','Orange','Green','Purple','Red'): fail(path+'.material.palette','unknown palette')
            if mat.get('pattern','13') not in tuple(f'{i:02d}' for i in range(1,14)): fail(path+'.material.pattern','expected 01 to 13')
            if 'tile_size' in mat: number(mat['tile_size'],path+'.material.tile_size',.01,1000)
        name=obj.get('name')
        if not isinstance(name,str) or not name or len(name)>63 or any(ord(c)<32 for c in name):
            fail(path+'.name','expected nonempty name up to 63 characters without control characters')
        if name in names: fail(path+'.name','duplicate name '+name)
        names.add(name)
        if obj.get('shape') not in SHAPES: fail(path+'.shape','unknown shape; run shapes to list')
        if obj['shape'] in {'POLY_FLOOR','POLY_BLOCK'}:
            if 'contours' not in obj:fail(path+'.contours','required for contour shapes')
            try:validate_contours(obj['contours'])
            except ValueError as exc:fail(path+'.contours',str(exc))
        elif 'contours' in obj:fail(path+'.contours','only supported by contour shapes')
        if 'position' in obj: vector(obj['position'],path+'.position')
        if 'rotation' in obj: vector(obj['rotation'],path+'.rotation',-3600,3600)
        if 'pivot' in obj: vector(obj['pivot'],path+'.pivot',0,1)
        if 'tag' in obj and obj['tag'] not in TAGS: fail(path+'.tag','unknown tag')
        params=obj.get('params',{})
        keys(params,DIMENSIONS|BOOLS|set(INTS)|set(CHOICES)|{'angle','miter_start','miter_end'},path+'.params')
        for key,value in params.items():
            field=path+'.params.'+key
            if key in BOOLS:
                if type(value) is not bool: fail(field,'expected boolean')
            elif key in INTS:
                if type(value) is not int: fail(field,'expected integer')
                number(value,field,*INTS[key])
            elif key in CHOICES:
                if value not in CHOICES[key]: fail(field,'expected '+', '.join(CHOICES[key]))
            else: number(value,field,-1000 if key in {'offset','miter_start','miter_end'} else 0 if key=='sill' else 1 if key=='angle' else .01,1440 if key=='angle' else 1000)
        # Bound procedural work before Blender allocates geometry.
        h=params.get('height',metrics.get('wall_height',3))
        step=params.get('max_step',metrics.get('max_step',.25))
        if 'STAIRS' in obj['shape'] and params.get('auto_steps',True) and h/step>512:
            fail(path,'automatic stair count exceeds 512; increase max_step')
        if obj['shape'] in {'LADDER','RAILING'} and max(h,params.get('width',2))/params.get('spacing',.3)>4096:
            fail(path,'too many rungs/posts; increase spacing')
    cuts=spec.get('cuts',[])
    if not isinstance(cuts,list) or len(cuts)>1000: fail('cuts','expected list of at most 1000 cuts')
    targets=set()
    cutters=set()
    for i,cut in enumerate(cuts):
        keys(cut,{'target','cutter'},f'cuts[{i}]')
        if any(not isinstance(cut.get(k),str) or cut[k] not in names for k in ('target','cutter')):
            fail(f'cuts[{i}]','target and cutter must name existing objects')
        if cut['target']==cut['cutter']: fail(f'cuts[{i}]','cannot cut an object with itself')
        if cut['cutter'] in cutters: fail(f'cuts[{i}]','a cutter may belong to only one target')
        targets.add(cut['target']); cutters.add(cut['cutter'])
    if targets & cutters: fail('cuts','nested cutter dependencies are not supported')
    return spec


def load(path):
    path=Path(path)
    if path.stat().st_size>2_000_000: fail('$','spec exceeds 2 MB')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: fail('$','duplicate JSON key: '+key)
            result[key]=value
        return result
    return validate(json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs))


def schema():
    positive={'type':'number','minimum':.01,'maximum':1000}
    vector3={'type':'array','items':{'type':'number','minimum':-10000,'maximum':10000},'minItems':3,'maxItems':3}
    params={key:dict(positive) for key in DIMENSIONS}
    for key in ('offset','miter_start','miter_end'):
        params[key]={'type':'number','minimum':-1000,'maximum':1000}
    params['sill']={'type':'number','minimum':0,'maximum':1000}
    params['angle']={'type':'number','minimum':1,'maximum':1440}
    params.update({key:{'type':'boolean'} for key in BOOLS})
    params.update({key:{'type':'integer','minimum':a,'maximum':b} for key,(a,b) in INTS.items()})
    params.update({key:{'enum':values} for key,values in CHOICES.items()})
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',
            'title':'Blocksmith level specification v1','type':'object','additionalProperties':False,
            'required':['version','objects'],'properties':{
                'version':{'const':1},'name':{'type':'string','maxLength':128},
                'metrics':{'type':'object','additionalProperties':False,'properties':{key:dict(positive) for key in METRICS}},
                'objects':{'type':'array','minItems':1,'maxItems':1000,'items':{
                    'type':'object','additionalProperties':False,'required':['name'],'anyOf':[{'required':['shape']},{'required':['preset']}],'properties':{
                        'name':{'type':'string','minLength':1,'maxLength':63},'shape':{'enum':SHAPES},'preset':{'enum':list(BY_ID)},
                        'contours':{'type':'array','minItems':1,'maxItems':17,'items':{'type':'array','minItems':3,'maxItems':256,
                            'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':-10000,'maximum':10000}}}},
                        'material':{'type':'object','additionalProperties':False,'properties':{
                            'palette':{'enum':['Light','Dark','Orange','Green','Purple','Red']},
                            'pattern':{'enum':[f'{i:02d}' for i in range(1,14)]},'tile_size':positive}},
                        'position':vector3,'rotation':{**vector3,'items':{'type':'number','minimum':-3600,'maximum':3600}},
                        'pivot':{**vector3,'items':{'type':'number','minimum':0,'maximum':1}},
                        'tag':{'enum':TAGS},'params':{'type':'object','additionalProperties':False,'properties':params}},
                    'allOf':[{'if':{'required':['shape'],'properties':{'shape':{'enum':['POLY_FLOOR','POLY_BLOCK']}}},
                              'then':{'required':['contours']},'else':{'not':{'required':['contours']}}}]}},
                'cuts':{'type':'array','maxItems':1000,'items':{'type':'object','additionalProperties':False,
                    'required':['target','cutter'],'properties':{'target':{'type':'string'},'cutter':{'type':'string'}}}}}}


def resolve(obj):
    if 'preset' not in obj: return obj
    preset=BY_ID[obj['preset']]
    return {**obj,'shape':preset[3],'params':{**preset[4],**obj.get('params',{})}}
