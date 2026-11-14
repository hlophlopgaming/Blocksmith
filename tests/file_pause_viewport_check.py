# SPDX-License-Identifier: GPL-3.0-or-later
"""Pause a live tool, enter Sculpt Mode and preserve edits across resume and Undo."""
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import blocksmith as bs

result=Path('/tmp/blocksmith-file-pause-viewport-result.txt')
state={'step':0}

def context(): return bpy.context.temp_override(window=w,area=a,region=r)
def run():
    try:
        step=state['step']
        if step==0:
            with context():
                bpy.ops.blocksmith.activate(kind='WALL')
                assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
            bpy.context.scene.bs.file_enabled=False
        elif step==1:
            assert bs.drawing.ACTIVE is None
            assert not any(op.bl_idname=='BLOCKSMITH_OT_draw' for op in w.modal_operators)
            assert w.workspace.tools.from_space_view3d_mode('OBJECT',create=False).idname=='builtin.select_box'
            assert not any(item.active for _,item in bs.KEYMAPS)
            assert not bpy.ops.blocksmith.draw.poll() and not bpy.ops.blocksmith.activate.poll()
            with context(): bpy.ops.object.mode_set(mode='SCULPT')
        elif step==2:
            assert bpy.context.mode=='SCULPT'
            obj=bpy.context.active_object
            obj.data.vertices[0].co.z+=.375; obj.data.update()
            state['stamp']=bs.signature(obj.data)
        elif step==3:
            assert bs.signature(bpy.context.active_object.data)==state['stamp']
            bpy.context.scene.bs.file_enabled=True
        elif step==4:
            assert bpy.context.mode=='SCULPT' and bs.signature(bpy.context.active_object.data)==state['stamp']
            with context(): bpy.ops.object.mode_set(mode='OBJECT')
        elif step==5:
            assert bs.manual(bpy.context.active_object)
            with context(): bpy.ops.ed.undo_push(message='Sculpted mesh')
            with context(): bpy.ops.wm.context_toggle('EXEC_DEFAULT',True,data_path='scene.bs.file_enabled')
        elif step==6:
            assert not bs.guard.enabled()
            with context(): bpy.ops.ed.undo()
        elif step==7:
            assert bs.guard.enabled() and bs.signature(bpy.context.active_object.data)==state['stamp']
            with context(): bpy.ops.ed.redo()
        elif step==8:
            assert not bs.guard.enabled() and bs.signature(bpy.context.active_object.data)==state['stamp']
            assert not any(item.active for _,item in bs.KEYMAPS)
            result.write_text('PASS: live drawing cancelled, shortcuts/gizmos paused, Sculpt Mode edits preserved, resume and Undo/Redo preserve geometry')
            print(result.read_text(),flush=True)
            bs.unregister(); bpy.ops.wm.quit_blender(); return None
        state['step']+=1
        return .65
    except Exception:
        result.write_text(traceback.format_exc()); print(result.read_text(),flush=True)
        bpy.ops.wm.quit_blender(); return None

def setup():
    global w,a,r
    bs.register()
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bs.create(bpy.context,'BLOCK')
    w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
    r=next(r for r in a.regions if r.type=='WINDOW')
    a.spaces.active.show_region_ui=True
    bpy.app.timers.register(run,first_interval=1)
bpy.app.timers.register(setup,first_interval=2)
