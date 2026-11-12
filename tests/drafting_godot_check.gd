# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree

func _initialize():
    var packed = load("res://joins.glb") as PackedScene
    assert(packed != null, "Drafting GLB did not import")
    var scene = packed.instantiate()
    var meshes = scene.find_children("*", "MeshInstance3D", true, false)
    var collisions = scene.find_children("*", "CollisionShape3D", true, false)
    assert(meshes.size() == 7, "Expected seven visible constructions, without Player")
    assert(collisions.size() == 7, "Each construction needs a collision shape")
    for label in ["Floor", "Door wall", "East wall", "North wall", "Stairs", "Cover", "Room"]:
        assert(scene.find_child(label, true, false) != null, "Missing construction: " + label)
    assert(scene.find_child("*Player*", true, false) == null, "Player reference leaked")
    for collision in collisions:
        assert(collision.shape != null, "Empty collision shape")
    print("PASS: Godot drafting import, seven meshes and collisions, no player reference")
    scene.free()
    quit(0)
