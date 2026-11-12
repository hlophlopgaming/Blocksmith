# SPDX-License-Identifier: GPL-3.0-or-later
"""UI regression: each exit frees modal handlers, timers and drawing previews."""
import sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Quaternion
import blocksmith as bs
bs.register()
w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D'); r=next(r for r in a.regions if r.type=='WINDOW')
a.spaces.active.show_region_ui=False
rv=a.spaces.active.region_3d; rv.view_rotation=Quaternion((1,0,0,0)); rv.view_perspective='ORTHO'; rv.view_distance=12
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.context.scene.bs.preset='wall_4'
step=0

def invoke(repeat=False):
    with bpy.context.temp_override(window=w,area=a,region=r):
        return bpy.ops.blocksmith.draw('INVOKE_DEFAULT',place_only=True,repeat=repeat)

def emit(kind,value='PRESS',x=220,y=220): w.event_simulate(type=kind,value=value,x=r.x+x,y=r.y+y)

def idle():
    assert bs.drawing.ACTIVE is None
    assert not any(o.bl_idname=='BLOCKSMITH_OT_draw' for o in w.modal_operators)

def run():
    global step
    try:
        if step==0:
            invoke(); emit('MOUSEMOVE','NOTHING'); emit('R'); emit('LEFTMOUSE'); emit('LEFTMOUSE','RELEASE')
        elif step==1:
            idle(); objects=[o for o in bpy.context.scene.objects if o.type=='MESH']; assert len(objects)==1
            assert abs(objects[0].rotation_euler.z-1.570796)<.0001
            invoke(); emit('ESC')
        elif step==2:
            idle(); invoke(repeat=True); emit('MOUSEMOVE','NOTHING',x=400); emit('RIGHTMOUSE')
        elif step==3:
            idle(); invoke(repeat=True)
        elif step==4:
            assert bs.drawing.ACTIVE is not None
            with bpy.context.temp_override(window=w,area=a,region=r):
                assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT',place_only=True)=={'CANCELLED'}
                bpy.ops.blocksmith.stop()
        elif step==5:
            idle()
            with bpy.context.temp_override(window=w,area=a,region=r): bpy.ops.wm.tool_set_by_id(name='builtin.select_box')
            invoke(repeat=True); emit('ESC')
        elif step==6:
            idle(); assert w.workspace.tools.from_space_view3d_mode('OBJECT',create=False).idname=='builtin.select_box'
            assert len([o for o in bpy.context.scene.objects if o.type=='MESH'])==1,'Cancellation added an object'
            print('PASS: single click returns control; R rotates; Esc, RMB, Stop exit; duplicate mode blocked',flush=True)
            Path('/tmp/blocksmith-placement-exits.txt').write_text('PASS')
            bs.unregister(); bpy.ops.wm.quit_blender(); return None
        step+=1; return .65
    except Exception:
        traceback.print_exc(); Path('/tmp/blocksmith-placement-exits.txt').write_text(traceback.format_exc()); bpy.ops.wm.quit_blender(); return None
bpy.app.timers.register(run,first_interval=2)
