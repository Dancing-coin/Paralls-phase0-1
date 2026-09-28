extends RefCounted
class_name CharacterReplicaRetirementProbe

static func inspect() -> Dictionary:
    var scene_source := FileAccess.get_file_as_string("res://scenes/phase0/StreetCombatDemo.tscn")
    var controller_source := FileAccess.get_file_as_string("res://scripts/street_combat/StreetCombatDemo.gd")
    var scene_replica_instances := scene_source.count("CharacterReplica.tscn") + scene_source.count('instance=ExtResource("replica")')
    var script_references := controller_source.count("CharacterReplica.gd")
    var node_path_references := controller_source.count("/CharacterReplica\"")
    var concrete_behavior_callers := controller_source.count("CharacterReplicaRef") + controller_source.count("CharacterReplicaSceneRef")
    return {
        "scene_replica_instances": scene_replica_instances,
        "script_references": script_references,
        "node_path_references": node_path_references,
        "concrete_behavior_callers": concrete_behavior_callers,
        "passed": scene_replica_instances == 0 and script_references == 0 and node_path_references == 0 and concrete_behavior_callers == 0,
    }
