# SPDX-License-Identifier: GPL-3.0-or-later
"""Real modal events and Undo/Redo in an isolated Blender window."""
import sys, traceback, math, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Quaternion, Vector, Matrix
from bpy_extras import view3d_utils
import blocksmith as bs
from blocksmith import curves, guard

bs.register(); c=bpy.context
c.preferences.view.show_splash=False
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
guard.reload_state(); guard.flush()
w=c.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
r=next(r for r in a.regions if r.type=='WINDOW'); ui=next(r for r in a.regions if r.type=='UI')
rv=a.spaces.active.region_3d; rv.view_rotation=Quaternion((1,0,0,0)); rv.view_perspective='ORTHO'; rv.view_distance=22
a.spaces.active.show_region_ui=False
c.scene.bs.draw_depth=.2; c.scene.bs.draw_height=3; c.scene.bs.surfaces=False
state={'step':0}
RESULT=Path('/tmp/blocksmith-070-viewport-result.txt')
def override(): return c.temp_override(window=w,area=a,region=r)
def emit(kind,value='PRESS',point=(0,0,0)):
    p=view3d_utils.location_3d_to_region_2d(r,rv,Vector(point))
    w.event_simulate(type=kind,value=value,x=int(p.x+r.x),y=int(p.y+r.y))
def click(point): emit('MOUSEMOVE','NOTHING',point); emit('LEFTMOUSE','PRESS',point); emit('LEFTMOUSE','RELEASE',point)
def objects(): return [o for o in c.scene.objects if o.get('bs_curve_wall')]
def start(mode):
    with c.temp_override(window=w,area=a,region=ui): assert bpy.ops.blocksmith.curve('INVOKE_DEFAULT',True,mode=mode)=={'RUNNING_MODAL'}
def idle():
    assert curves.ACTIVE is None and not any(o.bl_idname=='BLOCKSMITH_OT_curve' for o in w.modal_operators)

def run():
    try:
        step=state['step']
        if step==0: start('POINTS'); click((-6,-4,0))
        elif step==1: click((-4,-2,0))
        elif step==2: click((-2,-4,0)); emit('RET')
        elif step==3:
            idle(); assert len(objects())==1 and objects()[0].data.splines[0].type=='BEZIER'
            with override(): bpy.ops.ed.undo()
        elif step==4:
            assert len(objects())==0
            with override(): bpy.ops.ed.redo()
        elif step==5:
            assert len(objects())==1 and not guard.audit(c.scene)
            start('FREEHAND'); emit('LEFTMOUSE',point=(2,-4,0))
        elif step==6: emit('MOUSEMOVE','NOTHING',(3,-2,0))
        elif step==7: emit('MOUSEMOVE','NOTHING',(5,-3,0))
        elif step==8: emit('LEFTMOUSE','RELEASE',(6,-4,0))
        elif step==9:
            idle(); assert len(objects())==2
            start('ARC'); click((-6,2,0))
        elif step==10: click((-4,4,0))
        elif step==11: click((-2,2,0))
        elif step==12:
            idle(); assert len(objects())==3 and c.active_object.data.splines[0].type=='POLY'
            start('POINTS'); click((2,2,0)); emit('ESC')
        elif step==13:
            idle(); assert len(objects())==3
            start('ARC'); click((2,2,0)); emit('WINDOW_DEACTIVATE','NOTHING')
        elif step==14:
            idle(); assert len(objects())==3
            with override(): bpy.ops.object.mode_set(mode='EDIT')
        elif step==15:
            assert c.mode=='EDIT_CURVE'
            with override(): bpy.ops.object.mode_set(mode='OBJECT')
        elif step==16:
            assert not guard.audit(c.scene)
            with guard.transaction(c):
                c.scene.cursor.location=(2,5,0); left=bs.create(c,'WALL'); left.bs.width=3; left.bs.depth=.2
                c.scene.cursor.location=(5,5,0); right=bs.create(c,'WALL'); right.bs.width=3; right.bs.depth=.2; right.rotation_euler.z=-math.pi/2
            for o in c.selected_objects: o.select_set(False)
            left.select_set(True); right.select_set(True); c.view_layer.objects.active=left
            with override(): bpy.ops.ed.undo_push(message='Стены перед стыковкой')
        elif step==17:
            with override(): assert bpy.ops.blocksmith.join('EXEC_DEFAULT',True,mode='MITER')=={'FINISHED'}
        elif step==18:
            assert abs(c.active_object.bs.miter_end)>.1
            with override(): bpy.ops.ed.undo()
        elif step==19:
            assert abs(c.active_object.bs.miter_end)<1e-5
            with override(): bpy.ops.ed.redo()
        elif step==20:
            assert abs(c.active_object.bs.miter_end)>.1 and not guard.audit(c.scene)
            rv.view_rotation=Quaternion((.88,.39,.12,.23)).normalized(); a.spaces.active.show_region_ui=True
        elif step==21:
            bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-070-curves.png')
            RESULT.write_text('PASS: three curve gestures, native edit mode, Esc/focus cleanup, curve Undo/Redo, atomic joint Undo/Redo')
            print(RESULT.read_text(),flush=True); sys.stdout.flush(); os._exit(0)
        state['step']+=1
        return .35
    except Exception:
        message=traceback.format_exc(); RESULT.write_text(message); print(message,flush=True); sys.stdout.flush(); os._exit(1)
bpy.app.timers.register(run,first_interval=1)
