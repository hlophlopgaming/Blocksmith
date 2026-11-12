# SPDX-License-Identifier: GPL-3.0-or-later
"""Generic opening creation/closing Undo/Redo and the compact panel in a real UI."""
import sys, os, traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Vector, Quaternion
import blocksmith as bs
from blocksmith.openings import modifier

bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1)
obj=c.active_object; obj.name='Обычный меш'
obj.data.transform(Matrix.Translation((0,0,2))@Matrix.Diagonal((6,.4,4,1)))
name=obj.name; stamp=bs.signature(obj.data)
w=c.window; area=next(a for a in w.screen.areas if a.type=='VIEW_3D')
region=next(r for r in area.regions if r.type=='WINDOW'); rv=area.spaces.active.region_3d
rv.view_rotation=Quaternion((.88,.44,.05,.12)).normalized(); rv.view_location=(0,0,2); rv.view_distance=11
area.spaces.active.show_region_ui=True
state={'step':0,'tab':0}; result=Path('/tmp/blocksmith-mesh-opening-viewport-result.txt')
def override(): return c.temp_override(window=w,area=area,region=region)
def hole():
 obj=bpy.data.objects[name]; evaluated=obj.evaluated_get(c.evaluated_depsgraph_get())
 return not evaluated.ray_cast(Vector((0,-2,1.5)),Vector((0,1,0)))[0]
def run():
 try:
  ui=next(r for r in area.regions if r.type=='UI')
  if ui.active_panel_category!='Blocksmith':
   assert state['tab']<30,'Could not select Blocksmith sidebar'
   y=ui.y+ui.height-20-state['tab']*15; x=ui.x+ui.width-12
   w.event_simulate(type='LEFTMOUSE',value='PRESS',x=x,y=y)
   w.event_simulate(type='LEFTMOUSE',value='RELEASE',x=x,y=y)
   state['tab']+=1; return .15
  step=state['step']; obj=bpy.data.objects[name]
  if step==0:
   with override(): bpy.ops.ed.undo_push(message='До проёма')
  elif step==1:
   with override(): assert bpy.ops.blocksmith.opening('EXEC_DEFAULT',True,variant='ARCH_WINDOW')=={'FINISHED'}
  elif step==2:
   assert hole() and bs.signature(obj.data)==stamp
   with override(): bpy.ops.ed.undo()
  elif step==3:
   assert not modifier(obj) and not hole() and bs.signature(obj.data)==stamp
   with override(): bpy.ops.ed.redo()
  elif step==4:
   assert hole() and modifier(obj) and bs.signature(obj.data)==stamp
   bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-mesh-opening-panel.png')
   with override(): assert bpy.ops.blocksmith.opening('EXEC_DEFAULT',True,variant='NONE')=={'FINISHED'}
  elif step==5:
   assert not hole() and obj.bs.opening=='NONE'
   with override(): bpy.ops.ed.undo()
  elif step==6:
   assert hole() and obj.bs.opening=='ARCH_WINDOW'
   with override(): bpy.ops.ed.redo()
  elif step==7:
   assert not hole() and obj.bs.opening=='NONE' and bs.signature(obj.data)==stamp
   result.write_text('PASS: generic opening creation and closing Undo/Redo, untouched mesh and compact panel')
   print(result.read_text(),flush=True); os._exit(0)
  state['step']+=1; return .5
 except Exception:
  message=traceback.format_exc(); result.write_text(message); print(message,flush=True); os._exit(1)
bpy.app.timers.register(run,first_interval=2)
