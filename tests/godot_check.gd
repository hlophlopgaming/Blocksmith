# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree

func _initialize():
    var packed = load("res://blockout.glb") as PackedScene
    assert(packed != null, "GLB did not import")
    var scene = packed.instantiate()
    var collisions = scene.find_children("*", "CollisionShape3D", true, false)
    assert(collisions.size() >= 20, "Missing level collisions")
    var water = scene.find_child("*Water*", true, false)
    assert(water != null and water is MeshInstance3D, "Water mesh missing")
    assert(water.find_children("*", "CollisionShape3D", true, false).is_empty(), "Water must have no collision")
    assert(scene.find_child("*Player*", true, false) == null, "Player reference leaked")
    print("PASS: Godot GLB import, ", collisions.size(), " collision shapes, water without collision")
    scene.free()
    quit(0)
