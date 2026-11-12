# SPDX-License-Identifier: GPL-3.0-or-later
"""Ordinary modeling stays free while Blocksmith modules retain their guard."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix
import blocksmith as bs
from blocksmith.drawing import parameters
bs.register(); c=bpy.context; g=bs.guard
ordinary=c.scene.objects.get('Cube')
bpy.ops.mesh.primitive_cube_add(size=2,location=(0,0,0)); ordinary2=c.active_object
ordinary.scale.x=-1; c.view_layer.update(); assert g.flush()
c.scene.cursor.location=(0,0,0); left=bs.create(c,'BLOCK')
c.scene.cursor.location=(3,0,0); right=bs.create(c,'BLOCK')
ordinary.location.x=7; c.view_layer.update(); assert g.flush()
g.require_valid(c.scene)
p=parameters(c,'BLOCK'); shape=bs.build(p)
assert not g.placement_error(c,shape.vertices,shape.faces,Matrix.Translation((7,0,0)),'BLOCK')
c.scene.cursor.location=(7,0,0); third=bs.create(c,'BLOCK')
assert ordinary.location.x==7 and ordinary.scale.x<0
# Reject the module edit without undoing an unrelated ordinary-object move/add.
ordinary2.location.y=6; right.location.x=1
bpy.ops.mesh.primitive_cube_add(size=2,location=(0,0,0)); ordinary3=c.active_object
c.view_layer.update(); assert not g.flush()
assert abs(right.location.x-3)<1e-6
assert ordinary2.location.y==6 and ordinary3.name in bpy.data.objects
assert not g.audit(c.scene)
# The plugin export must not reject an ordinary reflected mesh.
for o in c.selected_objects: o.select_set(False)
ordinary.select_set(True); c.view_layer.objects.active=ordinary
c.scene.bs.export_scope='SELECTED'; c.scene.bs.export_path=tempfile.mkdtemp(prefix='blocksmith-scope-')
assert bpy.ops.blocksmith.export()=={'FINISHED'}
assert Path(c.scene.bs.export_path,'blockout.glb').exists()
print('PASS: ordinary/ordinary and ordinary/Blocksmith overlaps, reflected ordinary export, scoped rollback; Blocksmith/Blocksmith still blocked')
bs.unregister()
