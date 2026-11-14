"""Exercise the modal input logic headlessly; projection and GPU drawing are stubbed."""
import json
import sys
from pathlib import Path
from types import MethodType,SimpleNamespace
from unittest.mock import patch

import bpy
from mathutils import Matrix,Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import blocksmith as bs
from blocksmith import outlines,drawing

bs.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.bs.object_snap=False
region=SimpleNamespace(type='WINDOW',x=0,y=0,width=2400,height=1200)
area=SimpleNamespace(type='VIEW_3D',regions=[region],spaces=SimpleNamespace(active=SimpleNamespace(region_3d=None)),
                     header_text_set=lambda text:None,tag_redraw=lambda:None)
window=SimpleNamespace(cursor_modal_set=lambda kind:None,cursor_modal_restore=lambda:None)
class Context:
    def __getattr__(self,key):return getattr(bpy.context,key)
context=Context();context.area=area;context.window=window
context.window_manager=SimpleNamespace(modal_handler_add=lambda obj:None)
fake_bpy=SimpleNamespace(types=SimpleNamespace(SpaceView3D=SimpleNamespace(
    draw_handler_add=lambda *args:object(),draw_handler_remove=lambda *args:None)))
fake_gpu=SimpleNamespace(shader=SimpleNamespace(from_builtin=lambda name:object()))
def hit(context,event):
    frame=Matrix.Translation((event.mouse_x/100,event.mouse_y/100,0));return frame,False,None
def plane(context,event,origin,normal):return Vector((event.mouse_x/100,event.mouse_y/100,origin.z))
def project(region,rv,p):return Vector((p.x*100,p.y*100))


def event(op,kind,point=(1,1),value='PRESS',**kw):
    e=SimpleNamespace(type=kind,value=value,mouse_x=point[0]*100,mouse_y=point[1]*100,
                      ctrl=False,shift=False,alt=False,**kw)
    return op.event(context,e)


def start(mode='POINTS',kind='POLY_FLOOR',edit=False):
    op=SimpleNamespace(mode=mode,kind=kind,edit=edit,report=lambda *args:None)
    for name in ('invoke','event','finish','preview','data','nearest','commit','end_stroke','draw_preview'):
        setattr(op,name,MethodType(getattr(outlines.BS_OT_outline,name),op))
    assert op.invoke(context,SimpleNamespace())=={'RUNNING_MODAL'}
    assert outlines.ACTIVE is op
    return op


with (patch.object(outlines,'bpy',fake_bpy),patch.object(outlines,'gpu',fake_gpu),
      patch.object(outlines,'batch_for_shader',lambda *args,**kwargs:object()),
      patch.object(outlines.view3d_utils,'location_3d_to_region_2d',project),
      patch.object(drawing,'surface_hit',hit),patch.object(drawing,'point_on_plane',plane),
      patch.object(drawing,'leave_tool',lambda context:None)):
    op=start()
    for p in [(1,1),(5,1),(5,5),(1,5)]:event(op,'LEFTMOUSE',p)
    event(op,'O')
    for p in [(2,2),(3,2),(3,3),(2,3)]:event(op,'LEFTMOUSE',p)
    assert event(op,'RET')=={'FINISHED'} and outlines.ACTIVE is None
    floor=bpy.context.active_object
    assert len(json.loads(floor.bs.contours))==2
    signature=bs.signature(floor.data)

    op=start(edit=True)
    event(op,'LEFTMOUSE',(1,1));event(op,'MOUSEMOVE',(.5,1),'NOTHING');event(op,'LEFTMOUSE',(.5,1),'RELEASE')
    event(op,'I',(3,1));assert len(op.loops[0])==5
    event(op,'LEFTMOUSE',(3,1))
    event(op,'BACK_SPACE');assert len(op.loops[0])==4
    event(op,'MOUSEMOVE',(3,1.25),'NOTHING');assert not op.moving
    assert event(op,'ESC')=={'CANCELLED'} and bs.signature(floor.data)==signature
    op=start(edit=True)
    event(op,'LEFTMOUSE',(1,1));event(op,'MOUSEMOVE',(.5,1),'NOTHING');event(op,'LEFTMOUSE',(.5,1),'RELEASE')
    assert event(op,'RET')=={'FINISHED'}
    assert abs(floor.bs.width-4.5)<1e-5 and not bs.manual(floor)

    op=start(mode='FREEHAND',kind='POLY_BLOCK')
    corners=[(8,1),(12,1),(12,4),(10,4),(10,3),(8,3)]
    event(op,'LEFTMOUSE',corners[0])
    for a,b in zip(corners,corners[1:]+corners[:1]):
        for i in range(1,31):event(op,'MOUSEMOVE',(a[0]+(b[0]-a[0])*i/30,a[1]+(b[1]-a[1])*i/30),'NOTHING')
    event(op,'LEFTMOUSE',(26,14),'RELEASE')
    assert len(op.points)==6
    event(op,'H',(8,1));event(op,'MOUSEMOVE',(8,1.5),'NOTHING');event(op,'LEFTMOUSE',(8,1.5))
    assert abs(op.height-3.5)<1e-6
    assert event(op,'RET')=={'FINISHED'}
    block=bpy.context.active_object
    assert block.bs.kind=='POLY_BLOCK' and not bs.manual(block)

    count=len(bpy.context.scene.objects)
    op=start()
    for p in [(14,1),(18,4),(14,4),(18,1)]:event(op,'LEFTMOUSE',p)
    assert event(op,'RET')=={'RUNNING_MODAL'}
    assert len(bpy.context.scene.objects)==count
    event(op,'ESC')
    op=start();bpy.context.scene.bs.file_enabled=False
    assert outlines.ACTIVE is None and op.closed
    bpy.context.scene.bs.file_enabled=True
assert not bs.guard.audit(bpy.context.scene)
print('OUTLINE INPUT CHECK PASSED: clicks, holes, freehand, simplification, H, move/insert/delete, Enter, Esc, invalid draft and file pause',flush=True)
