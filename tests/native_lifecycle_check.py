# SPDX-License-Identifier: GPL-3.0-or-later
"""Native cancellation and the completed-cube adoption/undo/redo boundary."""
import sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import blocksmith as bs
bs.register(); w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D'); r=next(r for r in a.regions if r.type=='WINDOW')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.context.scene.bs.preset='door'; step=0

def run():
    global step
    try:
        with bpy.context.temp_override(window=w,area=a,region=r):
            if step==0:
                bpy.ops.blocksmith.native_tool()
                bpy.ops.ed.undo_push(message='Empty native test')
            elif step==1:
                # Match the completed primitive emitted by interactive_add.
                bs.native_tool.SEEN[w.as_pointer()]['running']=True
                bpy.ops.mesh.primitive_cube_add(size=4,location=(0,0,2))
                bpy.ops.ed.undo_push(message='Native Add Cube completion')
            elif step==2:
                obj=bpy.context.active_object
                assert obj and obj.bs.enabled and obj.bs.kind=='DOOR'
                assert not [o for o in w.modal_operators if o.bl_idname=='BLOCKSMITH_OT_draw']
                bpy.ops.ed.undo()
            elif step==3:
                assert not bpy.context.scene.objects,'Undo left the created cube'
                bpy.ops.ed.redo()
            elif step==4:
                objects=list(bpy.context.scene.objects)
                print('REDO_STATE',[(o.name,o.session_uid,o.bs.enabled) for o in objects],flush=True)
                assert len(objects)==1 and objects[0].bs.enabled,'Redo lost editable module'
                print('PASS: completed native cube becomes preset; one-step undo and redo retain module parameters',flush=True)
                Path('/tmp/blocksmith-native-lifecycle-result.txt').write_text('PASS')
                bs.unregister(); bpy.ops.wm.quit_blender(); return None
        step+=1; return .9
        with bpy.context.temp_override(window=w,area=a,region=r):
            if step==1:
                bpy.ops.ed.undo_push(message='Empty native test')
                assert bpy.ops.view3d.interactive_add('INVOKE_DEFAULT',wait_for_input=True)=={'RUNNING_MODAL'}
                w.event_simulate(type='ESC',value='PRESS')
            elif step==2:
                assert not w.modal_operators and not bpy.context.scene.objects
                # interactive_add ultimately calls primitive_cube_add; drive its completion seam.
                bs.native_tool.SEEN[w.as_pointer()]['running']=True
                bpy.ops.mesh.primitive_cube_add(size=4,location=(0,0,2))
                bpy.ops.ed.undo_push(message='Native Add Cube completion')
            elif step==3:
                obj=bpy.context.active_object
                assert obj and obj.bs.enabled and obj.bs.kind=='DOOR'
                assert not [o for o in w.modal_operators if o.bl_idname=='BLOCKSMITH_OT_draw']
                bpy.ops.ed.undo()
            elif step==4:
                assert not bpy.context.scene.objects,'Undo left the created cube'
                bpy.ops.ed.redo()
            elif step==5:
                objects=list(bpy.context.scene.objects)
                print('REDO_STATE',[(o.name,o.session_uid,o.bs.enabled) for o in objects],flush=True)
                assert len(objects)==1 and objects[0].bs.enabled,'Redo lost editable module'
                print('PASS: native operator cancellation, completed cube becomes preset, undo removes whole creation and redo restores module',flush=True)
                Path('/tmp/blocksmith-native-lifecycle-result.txt').write_text('PASS')
                bs.unregister(); bpy.ops.wm.quit_blender(); return None
        step+=1; return .9
    except Exception:
        traceback.print_exc(); Path('/tmp/blocksmith-native-lifecycle-result.txt').write_text(traceback.format_exc()); bpy.ops.wm.quit_blender(); return None
bpy.app.timers.register(run,first_interval=2)
