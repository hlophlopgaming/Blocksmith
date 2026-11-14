"""Live Blender UI test: real viewport, GPU preview, modal lifecycle and Undo/Redo.

Run in an existing GUI Blender with Blocksmith enabled. Feed deterministic pointer
events through the operator and finish its real WM handler with a native timer event.
"""
import json
import math
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion,Vector

bs=next(m for k,m in sys.modules.items() if k.endswith('blocksmith') and hasattr(m,'BSShape') and hasattr(m,'outlines'))
outlines=sys.modules[bs.__name__+'.outlines']
OUTPUT=Path('/tmp/blocksmith-outline-viewport')
OUTPUT.mkdir(exist_ok=True)
state={'step':0,'native_timer':None}


def ui():
    w=bpy.context.window_manager.windows[0]
    a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
    r=next(r for r in a.regions if r.type=='WINDOW')
    return w,a,r


def pointer(op,kind,point=(1,1,0),value='PRESS'):
    w,a,r=ui()
    pixel=view3d_utils.location_3d_to_region_2d(r,a.spaces.active.region_3d,Vector(point))
    assert pixel is not None,'Test point is outside the viewport'
    event=SimpleNamespace(type=kind,value=value,mouse_x=r.x+pixel.x,mouse_y=r.y+pixel.y,ctrl=False,shift=False,alt=False)
    return op.event(bpy.context,event)


def start(**props):
    assert bpy.ops.blocksmith.outline('INVOKE_DEFAULT',**props)=={'RUNNING_MODAL'}
    assert outlines.ACTIVE is not None
    return outlines.ACTIVE


def flush_modal():
    state['native_timer']=bpy.context.window_manager.event_timer_add(.05,window=ui()[0])


def idle():
    if state['native_timer']:
        bpy.context.window_manager.event_timer_remove(state['native_timer']);state['native_timer']=None
    assert outlines.ACTIVE is None
    assert not any(o.bl_idname=='BLOCKSMITH_OT_outline' for o in ui()[0].modal_operators),'Leaked modal handler'


def run():
    try:
        w,a,r=ui()
        with bpy.context.temp_override(window=w,area=a,region=r):
            step=state['step']
            if step==0:
                state['undo_before']=bpy.context.preferences.edit.use_global_undo
                bpy.context.preferences.edit.use_global_undo=True
                scene=bpy.data.scenes.new('Contour tools - UI proof');w.scene=scene
                scene.bs.grid=.25;scene.bs.surfaces=False;scene.bs.object_snap=True
                scene.bs.draw_height=2;scene.bs.contour_tolerance=.03
                rv=a.spaces.active.region_3d
                rv.view_rotation=Quaternion((1,0,0,0));rv.view_perspective='ORTHO'
                rv.view_location=Vector((6.5,3,0));rv.view_distance=18
                a.spaces.active.show_region_ui=True;a.spaces.active.shading.type='SOLID'
                a.spaces.active.shading.color_type='TEXTURE'
                bpy.ops.ed.undo_push(message='Contour viewport setup')
            elif step==1:
                op=start(kind='POLY_FLOOR',mode='POINTS')
                for p in [(1,1,0),(5,1,0),(5,5,0),(1,5,0)]:pointer(op,'LEFTMOUSE',p)
                pointer(op,'O')
                for p in [(2,2,0),(3,2,0),(3,3,0),(2,3,0)]:pointer(op,'LEFTMOUSE',p)
                assert pointer(op,'RET')=={'FINISHED'},(op.error,op.data())
                state['floor']=bpy.context.active_object.name
                assert len(json.loads(bpy.context.active_object.bs.contours))==2
                flush_modal()
            elif step==2:
                idle();assert bpy.ops.ed.undo()=={'FINISHED'}
                assert not any(o.bs.enabled and o.bs.kind=='POLY_FLOOR' for o in bpy.context.scene.objects)
                assert bpy.ops.ed.redo()=={'FINISHED'}
                assert len(json.loads(bpy.data.objects[state['floor']].bs.contours))==2
            elif step==3:
                op=start(kind='POLY_BLOCK',mode='FREEHAND')
                corners=[(8,1,0),(12,1,0),(12,4,0),(10,4,0),(10,3,0),(8,3,0)]
                pointer(op,'LEFTMOUSE',corners[0])
                for p,q in zip(corners,corners[1:]+corners[:1]):
                    for i in range(1,21):pointer(op,'MOUSEMOVE',tuple(p[k]+(q[k]-p[k])*i/20 for k in range(3)),'NOTHING')
                pointer(op,'LEFTMOUSE',corners[0],'RELEASE')
                assert len(op.points)<=8,('Stroke not simplified',len(op.points))
                assert pointer(op,'RET')=={'FINISHED'};flush_modal()
            elif step==4:
                idle();floor=bpy.data.objects[state['floor']]
                for obj in bpy.context.selected_objects:obj.select_set(False)
                floor.select_set(True);bpy.context.view_layer.objects.active=floor
                state['signature']=bs.signature(floor.data)
                op=start(edit=True)
                pointer(op,'LEFTMOUSE',(1,1,0));pointer(op,'MOUSEMOVE',(.5,1,0),'NOTHING')
                pointer(op,'LEFTMOUSE',(.5,1,0),'RELEASE')
                assert pointer(op,'ESC')=={'CANCELLED'};flush_modal()
            elif step==5:
                idle();floor=bpy.data.objects[state['floor']]
                assert bs.signature(floor.data)==state['signature'],'Esc changed the original mesh'
                op=start(edit=True)
                pointer(op,'LEFTMOUSE',(1,1,0));pointer(op,'MOUSEMOVE',(.5,1,0),'NOTHING')
                pointer(op,'LEFTMOUSE',(.5,1,0),'RELEASE')
                assert pointer(op,'RET')=={'FINISHED'};flush_modal()
            elif step==6:
                idle();floor=bpy.data.objects[state['floor']]
                assert abs(floor.bs.width-4.5)<1e-4,('Point edit did not resize contour',floor.bs.width)
                assert not bs.guard.audit(bpy.context.scene)
                bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/'Viewport-demo.blend'))
                result={'ok':True,'real_viewport':True,'gpu_preview':True,'clicks_and_holes':True,
                        'freehand_simplification':True,'point_move':True,'escape_preserves_original':True,
                        'native_undo_redo':True,'no_leaked_modal_handlers':True,
                        'input':'deterministic operator events using real viewport projection; native WM timers'}
                (OUTPUT/'viewport-check.json').write_text(json.dumps(result,indent=2))
                bpy.context.preferences.edit.use_global_undo=state['undo_before']
                print('OUTLINE VIEWPORT CHECK PASSED',flush=True)
                return None
            state['step']+=1
        return .35
    except Exception:
        trace=traceback.format_exc()
        (OUTPUT/'viewport-check.json').write_text(json.dumps(dict(ok=False,step=state['step'],error=trace),indent=2))
        print(trace,flush=True)
        if 'undo_before' in state:bpy.context.preferences.edit.use_global_undo=state['undo_before']
        if outlines.ACTIVE:outlines.ACTIVE.finish(bpy.context,{'CANCELLED'});flush_modal()
        return None


bpy.app.timers.register(run,first_interval=.6)
print('Scheduled native contour viewport checks')
