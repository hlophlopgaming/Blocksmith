# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree

func _initialize():
    check.call_deferred()

func check():
    var scene = load("res://room.glb").instantiate()
    root.add_child(scene)
    assert(scene.find_children("*", "CollisionShape3D", true, false).size() == 1)
    await physics_frame
    await physics_frame
    var space = root.world_3d.direct_space_state
    var through_door = PhysicsRayQueryParameters3D.create(Vector3(4.4, 1, 1), Vector3(4.4, 1, -0.4))
    assert(space.intersect_ray(through_door).is_empty(), "Room doorway is blocked by collision")
    var through_wall = PhysicsRayQueryParameters3D.create(Vector3(0.5, 1, 1), Vector3(0.5, 1, -0.4))
    assert(not space.intersect_ray(through_wall).is_empty(), "Room wall lost its collision")
    var through_floor = PhysicsRayQueryParameters3D.create(Vector3(4, 1, -3), Vector3(4, -1, -3))
    assert(not space.intersect_ray(through_floor).is_empty(), "Room floor lost its collision")
    print("PASS: Godot room doorway is clear, wall and floor retain collision")
    quit(0)
