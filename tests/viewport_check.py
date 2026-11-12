# SPDX-License-Identifier: GPL-3.0-or-later
"""Run in an isolated UI process with --enable-event-simulate --factory-startup."""
import sys
from pathlib import Path
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Quaternion
import blocksmith as bs

bs.register()
window=bpy.context.window_manager.windows[0]
area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
region=next(r for r in area.regions if r.type=='WINDOW')
ui_region=next(r for r in area.regions if r.type=='UI')
rv=area.spaces.active.region_3d
rv.view_rotation=Quaternion((1,0,0,0)); rv.view_perspective='ORTHO'; rv.view_distance=12; rv.view_location=(0,0,0)
area.spaces.active.show_region_ui=False
s=bpy.context.scene.bs; s.preset='door'; s.shape='DOOR'
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
state={'step':0}

def emit(kind,value='NOTHING',x=240,y=220):
    window.event_simulate(type=kind,value=value,x=region.x+x,y=region.y+y)

def run():
    try:
        step=state['step']
        if step==0:
            with bpy.context.temp_override(window=window,area=area,region=ui_region):
                assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
            emit('MOUSEMOVE'); emit('LEFTMOUSE','PRESS'); emit('MOUSEMOVE',x=400); emit('LEFTMOUSE','RELEASE',x=400)
        elif step==1:
            bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-drawing-preview.png')
            emit('LEFTMOUSE','PRESS',x=400); emit('LEFTMOUSE','RELEASE',x=400); emit('ESC','PRESS')
        elif step==2:
            shapes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.bs.enabled]
            assert len(shapes)==1,[(o.name,o.type) for o in bpy.context.scene.objects]
            o=shapes[0]; assert o.bs.kind=='DOOR' and o.bs.width>.5
            assert not any(op.bl_idname=='BLOCKSMITH_OT_draw' for op in window.modal_operators)
            state['object']=o; state['width']=o.bs.width; state['location']=o.location.copy()
            with bpy.context.temp_override(window=window,area=area,region=region):
                bpy.ops.blocksmith.resize('INVOKE_DEFAULT',key='width',side=-1)
            emit('MOUSEMOVE',x=300)
        elif step==3:
            assert abs(state['object'].bs.width-state['width'])>.01,'Drag did not resize'
            emit('ESC','PRESS')
        elif step==4:
            o=state['object']
            assert abs(o.bs.width-state['width'])<1e-4 and (o.location-state['location']).length<1e-4,'Cancel did not restore shape'
            with bs.guard.transaction(bpy.context):
                o.location.x=-20
                bpy.context.scene.cursor.location=(0,0,0); bs.create(bpy.context,'BLOCK')
                bpy.context.scene.cursor.location=(3,0,0); state['neighbor']=bs.create(bpy.context,'BLOCK')
            with bpy.context.temp_override(window=window,area=area,region=region):
                bpy.ops.transform.translate(value=(-2,0,0))
        elif step==5:
            assert abs(state['neighbor'].location.x-3)<1e-5,'Timer did not reject native translate'
            state['neighbor'].scale.x=-1
            bpy.context.view_layer.update()
        elif step==6:
            assert state['neighbor'].scale.x>0,'Timer did not reject negative scale'
            with bpy.context.temp_override(window=window,area=area,region=region):
                bpy.ops.ed.undo_push(message='Safe guard test layout')
                bpy.ops.object.duplicate_move('INVOKE_DEFAULT')
            emit('RET','PRESS')
        elif step==7:
            count=sum(o.type=='MESH' for o in bpy.context.scene.objects)
            assert count==3,('Native overlapping duplicate was not rejected',count)
            with bpy.context.temp_override(window=window,area=area,region=region): bpy.ops.ed.undo()
        elif step==8:
            with bpy.context.temp_override(window=window,area=area,region=region): bpy.ops.ed.redo()
        elif step==9:
            assert sum(o.type=='MESH' for o in bpy.context.scene.objects)==3,'History discarded a valid object'
            assert not bs.guard.audit(bpy.context.scene),'Redo bypassed collision guard'
            print('PASS: draw/resize, native translate/negative scale/duplicate and invalid redo rejected',flush=True)
            Path('/tmp/blocksmith-viewport-result.txt').write_text('PASS')
            bs.unregister(); bpy.ops.wm.quit_blender(); return None
        state['step']+=1
        return .7
    except Exception:
        traceback.print_exc()
        Path('/tmp/blocksmith-viewport-result.txt').write_text(traceback.format_exc())
        bpy.ops.wm.quit_blender(); return None

bpy.app.timers.register(run,first_interval=2)
