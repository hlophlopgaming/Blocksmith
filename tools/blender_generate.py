# SPDX-License-Identifier: GPL-3.0-or-later
"""Internal Blender worker. Use levelgen.py for a stable command-line interface."""
import sys
from pathlib import Path
import json
import math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
import blocksmith as bs
from level_spec import load, resolve

if bpy.app.version<(5,0,0): raise RuntimeError('Blender 5.0 or newer is required')
stage,out=map(Path,sys.argv[sys.argv.index('--')+1:])
def report_error(kind,error,trace):
    (stage/'error.json').write_text(json.dumps({'type':kind.__name__,'error':str(error)},ensure_ascii=False),encoding='utf-8')
    sys.__excepthook__(kind,error,trace)
sys.excepthook=report_error
spec=load(stage/'spec.json')
bs.register()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
context=bpy.context
scene=context.scene; scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
scene.name=spec.get('name','Generated Level')
s=scene.bs
for key,value in spec.get('metrics',{}).items(): setattr(s,key,value)
objects={}
with bs.guard.transaction(context):
    for data in spec['objects']:
        data=resolve(data)
        obj=bs.create(context,data['shape']); obj.name=data['name']
        bs.BUSY=True
        try:
            for key,value in data.get('params',{}).items(): setattr(obj.bs,key,value)
        finally: bs.BUSY=False
        if 'material' in data:
            material=data['material']; obj.bs.palette=material.get('palette','Light')
            obj.bs.texture=material.get('pattern','13'); obj.bs.uv_tile=material.get('tile_size',1)
        bs.rebuild(obj,True)
        obj.location=data.get('position',(0,0,0))
        obj.rotation_euler=[math.radians(v) for v in data.get('rotation',(0,0,0))]
        if 'tag' in data: bs.tag_object(obj,data['tag'])
        context.view_layer.update()
        if 'pivot' in data:
            bb=bs.bounds(obj)
            point=Vector([min(v[i] for v in bb)+(max(v[i] for v in bb)-min(v[i] for v in bb))*data['pivot'][i] for i in range(3)])
            bs.set_pivot(obj,point)
        objects[data['name']]=obj
    for cut in spec.get('cuts',[]):
        for o in context.selected_objects: o.select_set(False)
        target,cutter=objects[cut['target']],objects[cut['cutter']]
        target.select_set(True); cutter.select_set(True); context.view_layer.objects.active=target
        bpy.ops.blocksmith.tool(action='CUT')
bs.guard.require_valid(scene)
s.export_path=str(stage); s.filename='level'; s.collision=True; s.export_format='GLB'
context.view_layer.update()
if bpy.ops.blocksmith.export()!={'FINISHED'}: raise RuntimeError('Export failed')
s.export_path=str(out)
scene.bs.dimensions=False
bpy.ops.wm.save_as_mainfile(filepath=str(stage/'level.blend'))
report={'ok':True,'name':scene.name,'blender':bpy.app.version_string,
        'objects':len(objects),'cuts':len(spec.get('cuts',[])),
        'files':{'blend':str(out/'level.blend'),'glb':str(out/'level.glb'),'log':str(out/'blender.log'),'spec':str(out/'level.spec.json')},
        'coordinates':'meters, Z-up in spec; GLB converted to Godot Y-up',
        'bounds':{name:{'position':list(o.location),'dimensions':list(o.dimensions),
                              'aabb_min':[min(v[i] for v in bs.bounds(o)) for i in range(3)],
                              'aabb_max':[max(v[i] for v in bs.bounds(o)) for i in range(3)]} for name,o in objects.items()}}
(stage/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

bs.unregister()
