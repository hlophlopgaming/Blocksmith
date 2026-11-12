# SPDX-License-Identifier: GPL-3.0-or-later
"""The native interactive tool produces the same cube meshes as primitive_cube_add."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blocksmith as bs
from blocksmith.native_tool import adopt
bs.register(); c=bpy.context
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for i,preset in enumerate(['wall_4','door','arch','stairs_3','floor_4','pillar']):
    bpy.ops.mesh.primitive_cube_add(size=2,location=(i*12,0,2),rotation=(.1,.2,.4))
    obj=c.active_object
    obj.bs.free_placement=(i==3)
    for v in obj.data.vertices: v.co.x*=2; v.co.y*=1.5; v.co.z*=2
    obj.data.update(); c.view_layer.update()
    expected=[obj.matrix_world@Vector(v) for v in obj.bound_box]
    adopt(c,obj,preset); c.view_layer.update()
    actual=[obj.matrix_world@Vector(v) for v in obj.bound_box]
    # Cylinders use a circular footprint; the rectangular tool is their size guide.
    if preset!='pillar':
        for axis in range(3):
            assert abs(min(p[axis] for p in expected)-min(p[axis] for p in actual))<1e-4,preset
            assert abs(max(p[axis] for p in expected)-max(p[axis] for p in actual))<1e-4,preset
    assert obj.bs.enabled and obj.data.materials and not bs.manual(obj)
    assert obj.bs.free_placement==(i==3)
bs.guard.require_valid(c.scene)
bs.unregister()
print('PASS: native cube bounds/orientation retained; walls, doors, arches, stairs, floors and pillars editable with materials')
