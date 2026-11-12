# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw an arch on a room with real mouse events; no facade, intact back wall, Undo/Redo and Esc."""
import sys, os, traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector, Quaternion
from bpy_extras import view3d_utils
import blocksmith as bs
from blocksmith import drawing

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
room=bs.create(c,'ROOM'); room.bs.width=6; room.bs.depth=6; room.bs.height=4
name=room.name; stamp=bs.signature(room.data)
w=c.window; area=next(a for a in w.screen.areas if a.type=='VIEW_3D')
region=next(r for r in area.regions if r.type=='WINDOW'); ui=next(r for r in area.regions if r.type=='UI')
rv=area.spaces.active.region_3d; rv.view_rotation=Quaternion((.70710678,.70710678,0,0)); rv.view_perspective='ORTHO'; rv.view_location=(3,0,2); rv.view_distance=11
area.spaces.active.show_region_ui=True
c.scene.bs.handles=False; c.scene.bs.surfaces=False; c.scene.bs.object_snap=True
state={'step':0}; result=Path('/tmp/blocksmith-drawn-opening-viewport-result.txt')
def override(): return c.temp_override(window=w,area=area,region=region)
def emit(kind,value='PRESS',point=(1,0,1)):
 p=view3d_utils.location_3d_to_region_2d(region,rv,Vector(point))
 w.event_simulate(type=kind,value=value,x=int(p.x+region.x),y=int(p.y+region.y))
def start(kind,a):
 with override(): bpy.ops.blocksmith.activate(kind=kind)
 with c.temp_override(window=w,area=area,region=ui): assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
 emit('MOUSEMOVE','NOTHING',a); emit('LEFTMOUSE',point=a)
def run():
 try:
  step=state['step']; room=bpy.data.objects[name]
  if step==0:
   with override(): bpy.ops.ed.undo_push(message='До рисования проёма')
   start('ARCH',(1,0,1))
  elif step==1: emit('MOUSEMOVE','NOTHING',(3,0,3))
  elif step==2:
   op=drawing.ACTIVE
   assert op.cut_target==room and not op.error,op.error
   assert abs(op.cut_depth-.2)<1e-4
   emit('LEFTMOUSE','RELEASE',(3,0,3))
  elif step==3:
   assert drawing.ACTIVE is None and len(room.modifiers)==1
   assert len([o for o in c.visible_objects if o.type=='MESH'])==1
   assert bs.signature(room.data)==stamp and not bs.guard.audit(c.scene)
   evaluated=room.evaluated_get(c.evaluated_depsgraph_get())
   assert evaluated.ray_cast(Vector((2,-1,2)),Vector((0,1,0)))[1].y>5
   with override(): bpy.ops.blocksmith.stop(); bpy.ops.ed.undo()
  elif step==4:
   assert not room.modifiers
   with override(): bpy.ops.ed.redo()
  elif step==5:
   assert len(room.modifiers)==1 and not bs.guard.audit(c.scene)
   start('WINDOW',(4,0,1))
  elif step==6: emit('MOUSEMOVE','NOTHING',(5,0,2))
  elif step==7: emit('LEFTMOUSE','RELEASE',(5,0,2))
  elif step==8:
   assert drawing.ACTIVE is None and len(room.modifiers)==2
   start('WINDOW',(4,0,2.5))
  elif step==9: emit('MOUSEMOVE','NOTHING',(5,0,3.5)); emit('ESC')
  elif step==10:
   assert drawing.ACTIVE is None and len(room.modifiers)==2 and bs.signature(room.data)==stamp
   assert not bs.guard.audit(c.scene)
   bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-drawn-opening-final.png')
   result.write_text('PASS: real arch/window drags cut the clicked room, intact back wall, no facade, independent cuts, Undo/Redo and Esc')
   print(result.read_text(),flush=True); os._exit(0)
  state['step']+=1; return .45
 except Exception:
  message=traceback.format_exc(); result.write_text(message); print(message,flush=True); os._exit(1)
bpy.app.timers.register(run,first_interval=2)
