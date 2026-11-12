# SPDX-License-Identifier: GPL-3.0-or-later
"""Array transforms, live window rows, guarded edits, export and saved state."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix,Vector
import blocksmith as bs
from blocksmith.array_tool import array_modifier,opening_source,spacing_error
from blocksmith.openings import apply_drawn,drawn_mesh
bs.register();c=bpy.context
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
with bs.guard.transaction(c):
 wall=bs.create(c,'WALL');wall.bs.width=12;wall.bs.depth=.2;wall.bs.height=4
 frame=Matrix.Diagonal((-1,-1,1,1))
 apply_drawn(c,wall,drawn_mesh('WINDOW',Vector((-2,0,1)),Vector((-1,0,2.5)),.2),frame)
 cutter=opening_source(wall);array_modifier(cutter,3,Vector((8,0,0)))
c.view_layer.update()
def hole(x):return not wall.evaluated_get(c.evaluated_depsgraph_get()).ray_cast(Vector((x,-1,1.75)),Vector((0,1,0)))[0]
assert all(hole(x) for x in (1.5,5.5,9.5)) and not hole(3.5)
with bs.guard.transaction(c):
 c.scene.cursor.location=(5.25,.05,1.1);blocker=bs.create(c,'BLOCK');blocker.bs.width=.3;blocker.bs.depth=.1;blocker.bs.height=.4
cutter.modifiers['BS_Row'].count=1;c.view_layer.update();bs.guard.flush()
assert cutter.modifiers['BS_Row'].count==3 and not bs.guard.audit(c.scene)
assert all(hole(x) for x in (1.5,5.5,9.5))
with bs.guard.transaction(c):
 c.scene.cursor.location=(20,0,0);column=bs.create(c,'CYLINDER');column.bs.width=1
 column.matrix_world=Matrix.Translation((20,0,0))@Matrix.Rotation(.4,4,'Z')@Matrix.Diagonal((1.2,.8,1.1,1))
 delta=Vector((6,3,0));mod=array_modifier(column,4,delta)
c.view_layer.update()
assert (column.matrix_world.to_3x3()@Vector(mod.constant_offset_displace)*3-delta).length<1e-5
assert spacing_error(column,100,Vector((.1,0,0)))
for o in c.selected_objects:o.select_set(False)
column.select_set(True);wall.select_set(True);c.view_layer.objects.active=wall
folder=Path(tempfile.mkdtemp(prefix='blocksmith-row-'))
c.scene.bs.export_scope='SELECTED';c.scene.bs.export_path=str(folder)
assert bpy.ops.blocksmith.export()=={'FINISHED'}
bpy.ops.wm.save_as_mainfile(filepath=str(folder/'rows.blend'))
bs.unregister();bs.register()
assert opening_source(wall).modifiers['BS_Row'].count==3 and column.modifiers['BS_Row'].count==4
assert not bs.guard.audit(c.scene)
bs.unregister();print('PASS: object/window arrays, transform-correct offsets, guarded hole closure, export, save/reload')
