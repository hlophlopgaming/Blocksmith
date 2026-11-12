# SPDX-License-Identifier: GPL-3.0-or-later
"""Use the user's evaluated room/cuts to draw a floor and block exactly on the visible sill."""
import bpy,sys,os,traceback,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mathutils import Vector,Quaternion
from bpy_extras import view3d_utils
import blocksmith as bs
from blocksmith import drawing
bs.register();c=bpy.context;c.preferences.view.show_splash=False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
fixture=json.loads((Path(__file__).parent/'fixtures/opening-snap-scene.json').read_text())
room=next(o for o in fixture['objects'] if 'Комната' in o['name'])
mesh=bpy.data.meshes.new('Evaluated cut room');mesh.from_pydata(room['vertices'],[],room['faces']);mesh.update()
obj=bpy.data.objects.new('Room with Boolean/Array openings',mesh);c.collection.objects.link(obj);obj['bs_managed']=True
c.view_layer.update();bs.guard.reload_state();bs.guard.flush()
w=c.window;a=next(a for a in w.screen.areas if a.type=='VIEW_3D');r=next(r for r in a.regions if r.type=='WINDOW');ui=next(r for r in a.regions if r.type=='UI')
rv=a.spaces.active.region_3d;rv.view_rotation=Quaternion(fixture['view_rotation']);rv.view_location=(2.4,.5,.4);rv.view_distance=4;rv.view_perspective='PERSP'
c.scene.bs.object_snap=True;c.scene.bs.surfaces=True;c.scene.bs.handles=False
state={'step':0};result=Path('/tmp/blocksmith-opening-snap-viewport-result.txt');sill=.2345239669084549
start=Vector((2.8,0,sill+.005));end=Vector((2,1.5,sill))
def override():return c.temp_override(window=w,area=a,region=r)
def emit(kind,value='PRESS',point=start):
 p=view3d_utils.location_3d_to_region_2d(r,rv,point)
 assert p is not None
 w.event_simulate(type=kind,value=value,x=int(p.x+r.x),y=int(p.y+r.y))
def begin(kind,point):
 with override():bpy.ops.blocksmith.activate(kind=kind)
 with c.temp_override(window=w,area=a,region=ui):assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
 emit('MOUSEMOVE','NOTHING',point);emit('LEFTMOUSE',point=point)
def run():
 try:
  step=state['step']
  if step==0:begin('FLOOR',start)
  elif step==1:emit('MOUSEMOVE','NOTHING',end)
  elif step==2:
   op=drawing.ACTIVE
   assert not op.front and not op.error,(op.front,op.error,tuple(op.frame.translation))
   assert abs(op.frame.translation.z-sill)<1e-4,tuple(op.frame.translation)
   emit('LEFTMOUSE','RELEASE',end)
  elif step==3:
   assert drawing.ACTIVE is None and c.active_object.bs.kind=='FLOOR'
   assert not bs.guard.audit(c.scene)
   ev=c.active_object.evaluated_get(c.evaluated_depsgraph_get())
   assert abs(max((ev.matrix_world@v.co).z for v in ev.data.vertices)-sill)<1e-4
   rv.view_location=(2.5,3.5,.3);rv.view_distance=3
  elif step==4:begin('BLOCK',Vector((2.8,3,sill+.005)))
  elif step==5:emit('MOUSEMOVE','NOTHING',Vector((2.8,4.5,.2)))
  elif step==6:
   op=drawing.ACTIVE
   assert not op.error,(op.error,tuple(op.frame.translation),tuple(op.end))
   assert abs(op.frame.translation.z-sill)<1e-4,tuple(op.frame.translation)
   emit('LEFTMOUSE','RELEASE',Vector((2.8,4.5,.2)))
  elif step==7:
   assert drawing.ACTIVE is None and c.active_object.bs.kind=='BLOCK' and not bs.guard.audit(c.scene)
   ev=c.active_object.evaluated_get(c.evaluated_depsgraph_get());zs=[(ev.matrix_world@v.co).z for v in ev.data.vertices]
   assert abs(max(zs)-sill)<1e-4 and abs(min(zs)-.2)<1e-4,(min(zs),max(zs))
   bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-opening-snap-final.png')
   result.write_text('PASS: actual evaluated room fixture; floor and block draw onto the off-grid opening sill; no overlaps')
   print(result.read_text(),flush=True);os._exit(0)
  state['step']+=1;return .5
 except Exception:
  message=traceback.format_exc();result.write_text(message);print(message,flush=True);os._exit(1)
bpy.app.timers.register(run,first_interval=2)
