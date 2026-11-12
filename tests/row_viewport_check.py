# SPDX-License-Identifier: GPL-3.0-or-later
"""Mouse-driven object/cut arrays: wheel, preview, cancellation, collision rollback and Undo."""
import bpy,sys,os,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mathutils import Vector,Matrix,Quaternion
from bpy_extras import view3d_utils
import blocksmith as bs
from blocksmith import array_tool as row,openings
bs.register();c=bpy.context
c.preferences.view.show_splash=False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
source=bs.create(c,'CYLINDER');source.bs.width=1;source.bs.height=3;name=source.name
w=c.window;a=next(a for a in w.screen.areas if a.type=='VIEW_3D');r=next(r for r in a.regions if r.type=='WINDOW');ui=next(r for r in a.regions if r.type=='UI')
rv=a.spaces.active.region_3d;rv.view_rotation=Quaternion((1,0,0,0));rv.view_perspective='ORTHO';rv.view_location=(3,0,1.5);rv.view_distance=14
c.scene.bs.object_snap=False;state={'step':0};result=Path('/tmp/blocksmith-row-result.txt')
def override():return c.temp_override(window=w,area=a,region=r)
def emit(kind,value='PRESS',point=(6,0,1.5)):
 p=view3d_utils.location_3d_to_region_2d(r,rv,Vector(point));w.event_simulate(type=kind,value=value,x=int(p.x+r.x),y=int(p.y+r.y))
def start(opening=False,count=3):
 with c.temp_override(window=w,area=a,region=ui):assert bpy.ops.blocksmith.row('INVOKE_DEFAULT',opening=opening,count=count)=={'RUNNING_MODAL'}
def clean():assert not any(o.get('bs_guard_temp') for o in c.scene.objects)
def run():
 try:
  step=state['step'];source=bpy.data.objects[name]
  if step==0:
   with override():
    bpy.ops.blocksmith.activate(kind='CYLINDER')
    bpy.ops.ed.undo_push(message='Before row')
   start()
  elif step==1:emit('MOUSEMOVE','NOTHING')
  elif step==2:emit('WHEELUPMOUSE')
  elif step==3:
   assert row.ACTIVE.count==4 and not row.ACTIVE.error,row.ACTIVE.error
   assert not source.modifiers
   bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-row-columns-preview.png')
   emit('LEFTMOUSE')
  elif step==4:
   clean();assert row.ACTIVE is None and source.modifiers['BS_Row'].count==4 and not bs.guard.audit(c.scene)
   with override():bpy.ops.ed.undo()
  elif step==5:
   assert not source.modifiers
   with override():bpy.ops.ed.redo()
  elif step==6:
   assert source.modifiers['BS_Row'].count==4
   # Editing a row to overlap a different protected object must restore its modifier state.
   with bs.guard.transaction(c):
    c.scene.cursor.location=(8,-.5,0);obstacle=bs.create(c,'BLOCK');obstacle.bs.width=1;obstacle.bs.depth=1;obstacle.bs.height=3
   source.modifiers['BS_Row'].count=6;c.view_layer.update();bs.guard.flush()
   assert source.modifiers['BS_Row'].count==4
   c.view_layer.objects.active=source;start(count=2)
  elif step==7:emit('MOUSEMOVE','NOTHING',(8,0,1.5));emit('ESC')
  elif step==8:
   clean();assert row.ACTIVE is None and source.modifiers['BS_Row'].count==4
   with bs.guard.transaction(c):
    c.scene.cursor.location=(0,8,0);wall=bs.create(c,'WALL');wall.bs.width=12;wall.bs.depth=.2;wall.bs.height=4
    frame=Matrix.Diagonal((-1,-1,1,1));frame.translation=(0,8,0)
    openings.apply_drawn(c,wall,openings.drawn_mesh('WINDOW',Vector((-2,0,1)),Vector((-1,0,2.5)),.2),frame)
   state['wall']=wall.name
   rv.view_rotation=Quaternion((.70710678,.70710678,0,0));rv.view_location=(6,8,2);rv.view_distance=16
   with override():bpy.ops.ed.undo_push(message='Before window row')
  elif step==9:start(opening=True)
  elif step==10:emit('MOUSEMOVE','NOTHING',(9.5,8,1.75))
  elif step==11:
   assert row.ACTIVE.opening and not row.ACTIVE.error,row.ACTIVE.error
   original=row.ACTIVE.delta.copy();row.ACTIVE.delta=Vector((16,0,0));row.ACTIVE.update_preview(c)
   assert 'пределы' in row.ACTIVE.error
   row.ACTIVE.delta=original;row.ACTIVE.update_preview(c);assert not row.ACTIVE.error
   assert bpy.data.objects[state['wall']].hide_get()
   bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-row-windows-preview.png')
   emit('LEFTMOUSE',point=(9.5,8,1.75))
  elif step==12:
   clean();wall=bpy.data.objects[state['wall']];assert not wall.hide_get()
   cutter=row.opening_source(wall);assert cutter.modifiers['BS_Row'].count==3
   ev=wall.evaluated_get(c.evaluated_depsgraph_get())
   for x in (1.5,5.5,9.5):assert not ev.ray_cast(Vector((x,-1,1.75)),Vector((0,1,0)))[0],(x,tuple(cutter.modifiers['BS_Row'].constant_offset_displace),[tuple(r) for r in cutter.matrix_world],[(m.name,m.object.name if m.type=='BOOLEAN' and m.object else None) for m in wall.modifiers],tuple(wall.location))
   assert ev.ray_cast(Vector((3.5,-1,1.75)),Vector((0,1,0)))[0]
   assert not bs.guard.audit(c.scene)
   with override():bpy.ops.ed.undo()
  elif step==13:
   wall=bpy.data.objects[state['wall']];assert not row.opening_source(wall).modifiers
   with override():bpy.ops.ed.redo()
  elif step==14:
   wall=bpy.data.objects[state['wall']];assert row.opening_source(wall).modifiers['BS_Row'].count==3
   start(opening=True,count=2)
  elif step==15:emit('ESC',point=(9.5,8,1.75))
  elif step==16:
   wall=bpy.data.objects[state['wall']];assert not wall.hide_get();clean()
   assert not bs.guard.audit(c.scene)
   result.write_text('PASS: object/window rows, wheel count, real preview, native Array, Esc cleanup, modifier rollback and Undo/Redo')
   print(result.read_text(),flush=True);os._exit(0)
  state['step']+=1;return .5
 except Exception:
  message=traceback.format_exc();result.write_text(message);print(message,flush=True);os._exit(1)
bpy.app.timers.register(run,first_interval=2)
