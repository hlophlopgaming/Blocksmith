# SPDX-License-Identifier: GPL-3.0-or-later
"""Creation grid and the file switch keep the installed add-on available."""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import addon_utils
import bpy

bs=addon_utils.enable('blocksmith',default_set=True)
assert bs is not None
from blocksmith.ui import draw_main
from blocksmith.geometry import SHAPES

icons=bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items.keys()
class Layout:
    def __init__(self): self.ops=[]; self.grids=[]; self.props=[]
    def row(self,**kw): return self
    def column(self,**kw): return self
    def box(self): return self
    def panel(self,*args,**kw): return self,self
    def grid_flow(self,**kw): self.grids.append(kw); return self
    def label(self,**kw):
        if 'icon' in kw: assert kw['icon'] in icons,kw
    def prop(self,data,name,**kw): self.props.append((data,name))
    def template_icon(self,**kw): pass
    def popover(self,**kw): pass
    def operator(self,name,**kw):
        if 'icon' in kw: assert kw['icon'] in icons,kw
        op=SimpleNamespace(); self.ops.append((name,op,kw)); return op

obj=bs.create(bpy.context,'WALL')
obj.bs.free_placement=True
bpy.context.scene.bs.grid=.25
layout=Layout(); draw_main(layout,bpy.context)
choices=[op.kind for name,op,_ in layout.ops if name in {'blocksmith.activate','blocksmith.outline'}]
assert len(set(choices))==len(SHAPES)
assert set(choices)==set(SHAPES)
assert {op.kind for name,op,_ in layout.ops if name=='blocksmith.outline'}=={'POLY_FLOOR','POLY_BLOCK'}
assert layout.grids[0]['columns']==2 and layout.grids[0]['row_major']
assert not any(name=='preferences.addon_disable' for name,_,_ in layout.ops)
assert (bpy.context.scene.bs,'file_enabled') in layout.props
for kind in SHAPES:
    bpy.context.scene.bs.shape=kind
    draw_main(Layout(),bpy.context)

before=[(o.name,bs.signature(o.data)) for o in bpy.context.scene.objects if o.type=='MESH']
window=bpy.context.window_manager.windows[0]
area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
region=next(r for r in area.regions if r.type=='WINDOW')
with bpy.context.temp_override(window=window,area=area,region=region):
    assert bpy.ops.blocksmith.activate(kind='WALL')=={'FINISHED'}
    if not bpy.app.background:
        assert bpy.ops.blocksmith.draw('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
        drawing=bs.drawing.ACTIVE
        assert drawing is not None
    bpy.context.scene.bs.file_enabled=False
assert bs.drawing.ACTIVE is None
if not bpy.app.background: assert drawing.closed
assert window.workspace.tools.from_space_view3d_mode('OBJECT',create=False).idname=='builtin.select_box'
assert 'blocksmith' in bpy.context.preferences.addons
assert hasattr(bpy.types.Scene,'bs') and hasattr(bpy.types.Object,'bs')
assert bpy.app.timers.is_registered(bs.guard.tick)
assert bs.DRAW_HANDLE is not None and bs.ui.PREVIEWS is not None and bs.KEYMAPS
assert all(not item.active for _,item in bs.KEYMAPS)
paused=Layout(); draw_main(paused,bpy.context)
assert not paused.ops and paused.props==[(bpy.context.scene.bs,'file_enabled')]
assert [(o.name,bs.signature(o.data)) for o in bpy.context.scene.objects if o.type=='MESH']==before
bpy.context.scene.bs.file_enabled=True
assert obj.bs.enabled and obj.bs.free_placement
assert bpy.context.scene.bs.grid==.25
addon_utils.disable('blocksmith',default_set=True)
print(f'PASS: all {len(SHAPES)} creation choices, valid icons, two columns, file pause, addon stays enabled, objects/settings preserved on resume')
