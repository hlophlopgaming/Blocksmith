# SPDX-License-Identifier: GPL-3.0-or-later
"""Workspace activation and modal gestures in a separate Blender UI with --enable-event-simulate."""
import sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Quaternion, Vector
import blocksmith as bs
from blocksmith import drawing
from bpy_extras import view3d_utils

state={'step':-1}
RESULT=Path('/tmp/blocksmith-drafting-viewport-result.txt')

def context(): return bpy.context.temp_override(window=w,area=a,region=r)
def emit(kind,value='PRESS',point=None):
    if point is not None:
        p=view3d_utils.location_3d_to_region_2d(r,rv,Vector(point)); x,y=int(p.x+r.x),int(p.y+r.y)
    else: x,y=r.x+200,r.y+200
    w.event_simulate(type=kind,value=value,x=x,y=y)
def shapes(): return [o for o in bpy.context.scene.objects if o.type=='MESH' and o.bs.enabled]
def idle():
    assert drawing.ACTIVE is None,'Modal survived placement/cancellation'
    assert not any(o.bl_idname=='BLOCKSMITH_OT_draw' for o in w.modal_operators),'Leaked modal handler'
def tool(): return w.workspace.tools.from_space_view3d_mode('OBJECT',create=False).idname
def preset(identifier):
    with context(): bpy.ops.blocksmith.preset(identifier=identifier)
def activate():
    with context(): bpy.ops.blocksmith.activate()
def drag(start,end):
    # event_simulate does not switch Blender's active region for tool-keymap dispatch.
    # Start the same operator in the UI context, then exercise its real modal events.
    ui=next(x for x in a.regions if x.type=='UI')
    with bpy.context.temp_override(window=w,area=a,region=ui):
        assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
    emit('MOUSEMOVE','NOTHING',start); emit('LEFTMOUSE',point=start)
    state['drag_end']=end

def run():
    try:
        step=state['step']
        if step==-1:
            preset('floor_8'); activate()
        elif step==0:
            drag((-6,-5,0),(4,5,0))
        elif step==1:
            assert drawing.ACTIVE is not None,'Toolbar did not invoke drawing'
            emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==2:
            assert drawing.ACTIVE.params.kind=='FLOOR' and drawing.ACTIVE.batch is not None
            bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-drafting-preview.png')
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==3:
            idle(); assert len(shapes())==1,[(o.name,o.bs.kind) for o in shapes()]
            assert tool()==drawing.TOOL_ID
            floor=shapes()[0]; assert abs(floor.bs.width-10)<.01 and abs(floor.bs.depth-10)<.01,(floor.bs.width,floor.bs.depth)
            # A second piece must undo independently, even while the toolbar tool remains selected.
            preset('wall_4'); drag((-4,-4,0),(2,-4,0))
        elif step==4:
            drawing.ACTIVE.params.opening='DOOR'
            emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==5:
            op=drawing.ACTIVE; assert op.params.kind=='WALL' and op.params.opening=='DOOR' and len(bs.build(op.params).vertices)>8
            bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-drafting-door-preview.png')
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==6:
            idle(); assert len(shapes())==2
            with context(): bpy.ops.blocksmith.stop()
        elif step==7:
            idle(); assert tool()=='builtin.select_box'
            with context(): bpy.ops.ed.undo()
        elif step==8:
            idle(); assert len(shapes())==1,('One Undo did not remove exactly one construction',[(o.name,o.bs.kind) for o in shapes()])
            with context(): bpy.ops.ed.redo()
        elif step==9:
            assert len(shapes())==2 and not bs.guard.audit(bpy.context.scene)
            preset('stairs_1'); activate(); drag((-4,0,0),(0,0,0))
        elif step==10: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==11:
            assert drawing.ACTIVE.params.kind=='STAIRS'
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==12:
            idle(); assert len(shapes())==3
            with context(): bpy.ops.blocksmith.stop()
        elif step==13:
            # Cancellation discards a pending preview and returns selection in one Esc.
            preset('room_6'); activate(); drag((5,-4,0),(7,2,0))
        elif step==14: emit('MOUSEMOVE','NOTHING',state['drag_end']); emit('ESC')
        elif step==15:
            idle(); assert len(shapes())==3 and tool()=='builtin.select_box'
            preset('room_6'); activate(); drag((5,-4,0),(7,2,0))
        elif step==16: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==17: emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==18:
            idle(); assert len(shapes())==4
            room=next(o for o in shapes() if o.bs.kind=='ROOM'); assert room.bs.width==2 and room.bs.depth==6
            # Idle tools must not intercept UI clicks or run a permanent modal.
            ui=next(x for x in a.regions if x.type=='UI')
            before=len(shapes()); state['count']=before
            w.event_simulate(type='LEFTMOUSE',value='PRESS',x=ui.x+ui.width-20,y=ui.y+90)
            w.event_simulate(type='LEFTMOUSE',value='RELEASE',x=ui.x+ui.width-20,y=ui.y+90)
        elif step==19:
            idle(); assert len(shapes())==state['count']
            with context(): bpy.ops.blocksmith.stop()
        elif step==20:
            s=bpy.context.scene.bs; s.handles=True
            obj=next(o for o in shapes() if o.bs.kind=='WALL' and o.bs.opening=='DOOR')
            for o in bpy.context.selected_objects: o.select_set(False)
            obj.select_set(True); bpy.context.view_layer.objects.active=obj
            state['obj']=obj.name; state['width']=obj.bs.width; state['location']=obj.location.copy()
            with context(): bpy.ops.blocksmith.resize('INVOKE_DEFAULT',key='width',side=-1)
            emit('MOUSEMOVE','NOTHING',point=(-2,-3,0))
        elif step==21:
            assert abs(bpy.data.objects[state['obj']].bs.width-state['width'])>.01,'Resize did not move'
            emit('ESC')
        elif step==22:
            obj=bpy.data.objects[state['obj']]
            assert abs(obj.bs.width-state['width'])<1e-5 and (obj.location-state['location']).length<1e-5
            assert not bs.guard.audit(bpy.context.scene)
        elif step==23:
            s=bpy.context.scene.bs; s.handles=False
            with bs.guard.transaction(bpy.context):
                wall=bs.create(bpy.context,'WALL'); wall.location=(0,12,0)
                wall.bs.width=4; wall.bs.depth=.2; wall.bs.height=3
            bpy.context.scene.cursor.location=(500,500,500)
            rv.view_rotation=Quaternion((.70710678,.70710678,0,0)); rv.view_location=(2,12,1.5); rv.view_distance=10
            s.surfaces=True
            preset('ladder'); activate()
        elif step==24: drag((1,12,0),(2,12,2.5))
        elif step==25: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==26:
            op=drawing.ACTIVE
            assert op.front and abs(op.params.depth-.12)<1e-5 and not op.error,(op.front,op.error)
            bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-drafting-surface.png')
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==27:
            idle(); assert len(shapes())==6
            ladder=next(o for o in shapes() if o.bs.kind=='LADDER')
            assert abs(ladder.bs.height-2.5)<1e-4 and abs(ladder.bs.width-1)<1e-4
            assert max(v.y for v in bs.bounds(ladder))<=12.0001
            rv.view_rotation=Quaternion((1,0,0,0)); rv.view_location=(-2,9,0); rv.view_distance=16
            s=bpy.context.scene.bs; s.surfaces=False
            preset('wall_4'); s.draw_chain=True
        elif step==28: drag((-6,8,0),(-2,8,0))
        elif step==29: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==30: emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==31:
            idle(); assert len(shapes())==7
            drag((-2,8,0),(-2,11,0))
        elif step==32: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==33:
            op=drawing.ACTIVE; assert op.previous is not None and not op.error,op.error
            assert abs(op.params.miter_start-.2)<1e-4
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==34:
            idle(); assert len(shapes())==8 and not bs.guard.audit(bpy.context.scene)
            state['middle']=bpy.context.active_object.name
            drag((-2,11,0),(1,11,0))
        elif step==35: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==36:
            assert not drawing.ACTIVE.error,drawing.ACTIVE.error
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==37:
            idle(); assert len(shapes())==9 and not bs.guard.audit(bpy.context.scene)
            with context(): bpy.ops.blocksmith.stop(); bpy.ops.ed.undo()
        elif step==38:
            assert len(shapes())==8 and abs(bpy.data.objects[state['middle']].bs.miter_end)<1e-5
            assert not bs.guard.audit(bpy.context.scene)
            # Releasing over the sidebar must cancel the pending gesture immediately.
            preset('platform'); activate(); drag((-6,15,0),(-4,15,0))
        elif step==39:
            ui=next(x for x in a.regions if x.type=='UI')
            w.event_simulate(type='LEFTMOUSE',value='RELEASE',x=ui.x+ui.width-20,y=ui.y+90)
        elif step==40:
            idle(); assert len(shapes())==8
            with context(): bpy.ops.blocksmith.stop()
            rv.view_rotation=Quaternion((.88,.3,.18,.3)).normalized(); rv.view_location=(0,4,1); rv.view_distance=25
            s=bpy.context.scene.bs; s.handles=True
        elif step==41:
            preset('platform'); activate(); drag((-6,15,0),(-4,15,0))
        elif step==42:
            assert drawing.ACTIVE is not None
            emit('WINDOW_DEACTIVATE','NOTHING')
        elif step==43:
            idle(); assert len(shapes())==8,'Losing focus placed a construction'
            with context(): bpy.ops.blocksmith.stop()
            room=next(o for o in shapes() if o.bs.kind=='ROOM')
            state['room']=room.name
            for obj in bpy.context.selected_objects: obj.select_set(False)
            room.select_set(True); bpy.context.view_layer.objects.active=room
            # Python calls must request the Undo push that a panel button gets automatically.
            with context(): bpy.ops.blocksmith.opening('EXEC_DEFAULT',True,variant='DOOR')
        elif step==44:
            room=bpy.data.objects[state['room']]
            assert room.bs.kind=='ROOM' and room.bs.opening=='DOOR' and not bs.guard.audit(bpy.context.scene)
            with context(): bpy.ops.ed.undo()
        elif step==45:
            room=bpy.data.objects[state['room']]
            assert room.bs.kind=='ROOM' and room.bs.opening=='NONE',('Undo did not restore the room wall',room.bs.kind,room.bs.opening,bs.guard.message(bpy.context.scene),len(shapes()))
            with context(): bpy.ops.ed.redo()
        elif step==46:
            room=bpy.data.objects[state['room']]
            assert room.bs.kind=='ROOM' and room.bs.opening=='DOOR' and not bs.guard.audit(bpy.context.scene)
            with bs.guard.transaction(bpy.context):
                bpy.context.scene.cursor.location=(30,0,0); floor=bs.create(bpy.context,'FLOOR')
                floor.bs.width=4.37; floor.bs.depth=4
                bpy.context.scene.cursor.location=(29.5,0,0); wall=bs.create(bpy.context,'WALL')
                wall.bs.width=4; wall.bs.depth=.5; wall.rotation_euler.z=__import__('math').pi/2
            state['contact_floor']=floor.name; state['contact_wall']=wall.name
            rv.view_rotation=Quaternion((1,0,0,0)); rv.view_location=(34,2,0); rv.view_distance=12
            settings=bpy.context.scene.bs; settings.handles=False; settings.object_snap=True; settings.surfaces=False
            preset('floor_4'); activate()
        elif step==47: drag((37,1,0),(34.37,3,0))
        elif step==48: emit('MOUSEMOVE','NOTHING',state['drag_end'])
        elif step==49:
            op=drawing.ACTIVE
            assert not op.error,op.error
            assert abs(op.matrix.translation.x-34.37)<1e-4,op.matrix.translation
            emit('LEFTMOUSE','RELEASE',state['drag_end'])
        elif step==50:
            idle()
            assert abs(min(v.x for v in bs.bounds(bpy.context.active_object))-34.37)<1e-4
            with context(): bpy.ops.blocksmith.stop()
            for obj in bpy.context.selected_objects: obj.select_set(False)
            floor=bpy.data.objects[state['contact_floor']]; wall=bpy.data.objects[state['contact_wall']]
            floor.select_set(True); wall.select_set(True); bpy.context.view_layer.objects.active=floor
            with context(): bpy.ops.ed.undo_push(message='До примыкания к полу')
        elif step==51:
            with context(): assert bpy.ops.blocksmith.attach('EXEC_DEFAULT',True,axis='X',direction=-1)=={'FINISHED'}
        elif step==52:
            wall=bpy.data.objects[state['contact_wall']]
            assert abs(max(v.x for v in bs.bounds(wall))-30)<1e-4
            with context(): bpy.ops.ed.undo()
        elif step==53:
            wall=bpy.data.objects[state['contact_wall']]
            assert abs(max(v.x for v in bs.bounds(wall))-29.5)<1e-4
            with context(): bpy.ops.ed.redo()
        elif step==54:
            wall=bpy.data.objects[state['contact_wall']]
            assert abs(max(v.x for v in bs.bounds(wall))-30)<1e-4
            assert not bs.guard.audit(bpy.context.scene)
            bpy.ops.screen.screenshot(filepath='/tmp/blocksmith-drafting-final.png')
            RESULT.write_text('PASS: drawing gestures, lifecycle, surfaces, chain joints, room openings, off-grid edge contact and face attachment Undo/Redo')
            print(RESULT.read_text(),flush=True)
            bs.unregister(); bpy.ops.wm.quit_blender(); return None
        state['step']+=1; return .55
    except Exception:
        message=traceback.format_exc(); print(message,flush=True); RESULT.write_text(message)
        bpy.ops.wm.quit_blender(); return None
def setup():
    global w,a,r,rv,s
    bs.register()
    w=bpy.context.window_manager.windows[0]; a=next(a for a in w.screen.areas if a.type=='VIEW_3D')
    r=next(r for r in a.regions if r.type=='WINDOW')
    a.spaces.active.show_region_ui=True
    rv=a.spaces.active.region_3d; rv.view_rotation=Quaternion((1,0,0,0)); rv.view_perspective='ORTHO'; rv.view_distance=16; rv.view_location=(0,0,0)
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    s=bpy.context.scene.bs; s.handles=False; s.surfaces=False
    bpy.app.timers.register(run,first_interval=1)
    return None
bpy.app.timers.register(setup,first_interval=2)
