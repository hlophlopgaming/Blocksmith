# SPDX-License-Identifier: GPL-3.0-or-later
"""Real gestures connect stairs/ramp from a floor to an off-grid landing, with Undo and Esc."""
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
with bs.guard.transaction(c):
 floor=bs.create(c,'FLOOR'); floor.bs.width=20; floor.bs.depth=20; floor.location=(-5,-5,0)
 c.scene.cursor.location=(6,-2,2.75); landing=bs.create(c,'FLOOR'); landing.bs.width=4; landing.bs.depth=12
w=c.window; area=next(a for a in w.screen.areas if a.type=='VIEW_3D')
r=next(r for r in area.regions if r.type=='WINDOW'); ui=next(r for r in area.regions if r.type=='UI')
rv=area.spaces.active.region_3d; rv.view_rotation=Quaternion((.88,.3,.18,.3)).normalized(); rv.view_perspective='ORTHO'; rv.view_location=(3,3,1); rv.view_distance=19
area.spaces.active.show_region_ui=True
c.scene.bs.surfaces=False; c.scene.bs.object_snap=True; c.scene.bs.handles=False
state={'step':0}; result=Path('/tmp/blocksmith-access-viewport-result.txt')
def override(): return c.temp_override(window=w,area=area,region=r)
def emit(kind,value='PRESS',point=(0,0,0)):
 p=view3d_utils.location_3d_to_region_2d(r,rv,Vector(point))
 w.event_simulate(type=kind,value=value,x=int(p.x+r.x),y=int(p.y+r.y))
def start(kind,a):
 with override(): bpy.ops.blocksmith.activate(kind=kind)
 with c.temp_override(window=w,area=area,region=ui): assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
 emit('MOUSEMOVE','NOTHING',a); emit('LEFTMOUSE',point=a)
def run():
 try:
  step=state['step']
  if step==0:
   with override(): bpy.ops.ed.undo_push(message='До лестницы')
   start('STAIRS',(0,0,0))
  elif step==1: emit('MOUSEMOVE','NOTHING',(6,0,2.75))
  elif step==2:
   op=drawing.ACTIVE
   assert not op.error,(op.error,tuple(op.frame.translation),tuple(op.end),tuple(op.matrix.translation),op.params.width,op.params.height)
   assert abs(op.params.height-2.75)<1e-4,(op.params.height,tuple(op.end))
   assert abs(op.params.width-6)<.02,op.params.width
   emit('LEFTMOUSE','RELEASE',(6,0,2.75))
  elif step==3:
   assert drawing.ACTIVE is None and c.active_object.bs.kind=='STAIRS'
   assert abs(c.active_object.bs.height-2.75)<1e-4 and not bs.guard.audit(c.scene)
   state['stairs']=c.active_object.name
   with override(): bpy.ops.blocksmith.stop(); bpy.ops.ed.undo()
  elif step==4:
   assert state['stairs'] not in bpy.data.objects
   with override(): bpy.ops.ed.redo()
  elif step==5:
   assert state['stairs'] in bpy.data.objects
   start('RAMP',(0,5,0))
  elif step==6: emit('MOUSEMOVE','NOTHING',(6,5,2.75))
  elif step==7:
   op=drawing.ACTIVE
   assert not op.error and abs(op.params.height-2.75)<1e-4,(op.error,op.params.height,tuple(op.end))
   emit('LEFTMOUSE','RELEASE',(6,5,2.75))
  elif step==8:
   assert drawing.ACTIVE is None and c.active_object.bs.kind=='RAMP'
   assert not bs.guard.audit(c.scene)
   start('STAIRS',(0,9,0))
  elif step==9: emit('MOUSEMOVE','NOTHING',(6,9,2.75)); emit('ESC')
  elif step==10:
   assert drawing.ACTIVE is None and len([o for o in c.scene.objects if o.bs.enabled])==4
   bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-access-final.png')
   result.write_text('PASS: real floor-to-landing stairs and ramp, off-grid rise, automatic steps, Undo/Redo and Esc')
   print(result.read_text(),flush=True); os._exit(0)
  state['step']+=1; return .45
 except Exception:
  message=traceback.format_exc(); result.write_text(message); print(message,flush=True); os._exit(1)
bpy.app.timers.register(run,first_interval=2)
