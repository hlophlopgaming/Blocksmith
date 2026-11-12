# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree

func _initialize():
    check.call_deferred()

func fail(message: String):
    push_error(message)
    quit(1)

func pos(p: Array, height: float = 0.95) -> Vector3:
    return Vector3(p[0], height, -p[1])

func check():
    var packed = load("res://level.glb") as PackedScene
    if packed == null:
        fail("Hangar GLB did not import")
        return
    var level = packed.instantiate()
    root.add_child(level)
    await physics_frame
    await physics_frame
    var bodies = level.find_children("*", "CollisionShape3D", true, false)
    if bodies.size() < 150:
        fail("Missing level collision shapes: " + str(bodies.size()))
        return
    var water = level.find_child("*AcidWater*", true, false)
    if water == null or not water.find_children("*", "CollisionShape3D", true, false).is_empty():
        fail("Acid must be visible without solid collision")
        return
    var route = JSON.parse_string(FileAccess.get_file_as_string("res://route.json"))["route"]
    var space = level.get_world_3d().direct_space_state
    var capsule = CapsuleShape3D.new()
    capsule.radius = 0.3
    capsule.height = 1.8
    var shape_query = PhysicsShapeQueryParameters3D.new()
    shape_query.shape = capsule
    shape_query.margin = 0.005
    var samples = 0
    for i in range(route.size()-1):
        var a = pos(route[i])
        var b = pos(route[i+1])
        var steps = ceili(a.distance_to(b) / 0.25)
        for step in range(steps+1):
            var point = a.lerp(b, float(step)/steps)
            shape_query.transform = Transform3D(Basis.IDENTITY, point)
            var overlaps = space.intersect_shape(shape_query, 4)
            if not overlaps.is_empty():
                fail("Player blocked at " + str(point) + " by " + str(overlaps[0]["collider"].get_parent().name))
                return
            var ray = PhysicsRayQueryParameters3D.create(point, point + Vector3(0,-1.1,0))
            var floor_hit = space.intersect_ray(ray)
            if floor_hit.is_empty():
                fail("Gap in route at " + str(point))
                return
            samples += 1
    print("PASS: Hangar imported; ", bodies.size(), " collision shapes; ", samples,
          " player capsule samples from start to exit; acid has no solid collision")
    level.queue_free()
    quit(0)
