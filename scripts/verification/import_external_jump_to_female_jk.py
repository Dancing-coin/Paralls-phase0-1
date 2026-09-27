import bpy
import json
import struct
from pathlib import Path


JK_SOURCE = Path(r"E:\下载\建模3  金色卷发jk女 T字版  多动作版.blend")
BLACK_HAIR_SOURCE = Path(r"E:\下载\建模2 纹身腿黑卷发女T字版本  基础动作版.blend")
OUTPUT = Path(r"assets/active/female_jk_external/female_jk_external.glb").resolve()


UPPER_EXCLUDED = (
    "root.x",
    "spine_01.x",
    "thigh",
    "leg",
    "foot",
    "toes",
)


def weighted_bones(mesh):
    return {group.name for group in mesh.vertex_groups}


def upper_body_bones(armature, mesh):
    weighted = weighted_bones(mesh)
    return sorted(
        name
        for name in weighted
        if name in armature.data.bones
        and not any(name == excluded or name.startswith(excluded) for excluded in UPPER_EXCLUDED)
    )


def bake_short_punch(armature, mesh, scene):
    source = bpy.data.actions.get("boxing")
    if source is None:
        raise RuntimeError("boxing action missing")
    bones = upper_body_bones(armature, mesh)
    if not bones:
        raise RuntimeError("upper-body deform bones missing")
    armature.animation_data_create()
    armature.animation_data.action = source
    depsgraph = bpy.context.evaluated_depsgraph_get()
    cached = {}
    start, end = int(source.frame_start), int(source.frame_end)
    for frame in range(start, end + 1):
        scene.frame_set(frame)
        depsgraph.update()
        evaluated = armature.evaluated_get(depsgraph)
        cached[frame] = {name: evaluated.pose.bones[name].matrix.copy() for name in bones}

    old = bpy.data.actions.get("short punch")
    if old is not None:
        bpy.data.actions.remove(old)
    derived = bpy.data.actions.new("short punch")
    armature.animation_data.action = derived
    for frame, poses in cached.items():
        scene.frame_set(frame)
        for name, matrix in poses.items():
            pose_bone = armature.pose.bones[name]
            pose_bone.matrix = matrix
            pose_bone.keyframe_insert(data_path="location", frame=frame, group=name)
            if pose_bone.rotation_mode == "QUATERNION":
                pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=name)
            elif pose_bone.rotation_mode == "AXIS_ANGLE":
                pose_bone.keyframe_insert(data_path="rotation_axis_angle", frame=frame, group=name)
            else:
                pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=name)
            pose_bone.keyframe_insert(data_path="scale", frame=frame, group=name)
    scene.frame_set(start)
    derived.frame_start = start
    derived.frame_end = end
    print("SHORT_PUNCH_BONES", len(bones), bones)
    print("SHORT_PUNCH_RANGE", tuple(derived.frame_range))
    return derived


def filter_short_punch_glb(path):
    data = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    offset = 12
    chunks = []
    document = None
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + chunk_length]
        chunks.append((chunk_type, payload))
        if chunk_type == 0x4E4F534A:
            document = json.loads(payload.rstrip(b" ").decode("utf-8"))
        offset += 8 + chunk_length
    if document is None:
        raise RuntimeError("GLB JSON chunk missing")
    nodes = {index: node.get("name", "") for index, node in enumerate(document.get("nodes", []))}

    def is_lower_or_root(name):
        return name in {"root.x", "spine_01.x"} or name.startswith(("thigh", "leg", "foot", "toes"))

    boxing = next(
        (animation for animation in document.get("animations", []) if animation.get("name") == "boxing"),
        None,
    )
    if boxing is None:
        raise RuntimeError("boxing GLB animation missing")
    removed = 0
    targets = set()
    kept_channels = []
    kept_sampler_indices = set()
    for channel in boxing.get("channels", []):
        name = nodes.get(channel.get("target", {}).get("node", -1), "")
        if is_lower_or_root(name):
            removed += 1
        else:
            kept_channels.append(dict(channel))
            kept_sampler_indices.add(channel.get("sampler", -1))
            targets.add(name)
    sampler_remap = {}
    samplers = []
    for old_index, sampler in enumerate(boxing.get("samplers", [])):
        if old_index in kept_sampler_indices:
            sampler_remap[old_index] = len(samplers)
            samplers.append(dict(sampler))
    for channel in kept_channels:
        channel["sampler"] = sampler_remap[channel["sampler"]]
    replacement = {
        "name": "short punch",
        "channels": kept_channels,
        "samplers": samplers,
    }
    document["animations"] = [
        animation
        for animation in document.get("animations", [])
        if animation.get("name") != "short punch"
    ]
    document["animations"].append(replacement)
    if removed == 0:
        raise RuntimeError("short punch GLB filter found no lower/root channels")
    rebuilt = bytearray(struct.pack("<4sII", magic, version, 0))
    for chunk_type, payload in chunks:
        if chunk_type == 0x4E4F534A:
            payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            payload += b" " * ((4 - len(payload) % 4) % 4)
        rebuilt.extend(struct.pack("<II", len(payload), chunk_type))
        rebuilt.extend(payload)
    struct.pack_into("<I", rebuilt, 8, len(rebuilt))
    path.write_bytes(rebuilt)
    print("SHORT_PUNCH_FILTER_REMOVED_CHANNELS", removed)
    print("SHORT_PUNCH_FILTER_TARGETS", sorted(targets))


def main():
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("target armature missing")
    target_armature = armatures[0]
    target_mesh = next(obj for obj in bpy.data.objects if obj.type == "MESH" and len(obj.vertex_groups) > 0)

    scene = bpy.context.scene
    bake_short_punch(target_armature, target_mesh, scene)

    target_signature = [(bone.name, bone.parent.name if bone.parent else "") for bone in target_armature.data.bones]
    with bpy.data.libraries.load(str(BLACK_HAIR_SOURCE), link=False) as (data_from, data_to):
        if "jump" not in data_from.actions:
            raise RuntimeError("black-haired source does not contain jump action")
        data_to.actions = ["jump"]
    jump = bpy.data.actions.get("jump")
    if jump is None:
        raise RuntimeError("jump action append failed")
    target_armature.animation_data_create()
    target_armature.animation_data.action = jump

    weighted = weighted_bones(target_mesh)
    for bone in target_armature.data.bones:
        bone.use_deform = bone.name in weighted

    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    target_armature.select_set(True)
    target_mesh.select_set(True)
    for name in ("weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword"):
        socket = bpy.data.objects.get(name)
        if socket is None:
            socket = bpy.data.objects.new(name, None)
            socket.empty_display_type = "ARROWS"
            socket.empty_display_size = 0.08
            bpy.context.collection.objects.link(socket)
            socket.parent = target_armature
            socket.parent_type = "BONE"
            socket.parent_bone = "hand.r"
            socket.location = (0.0, 0.0, 0.0)
        socket.select_set(True)
    bpy.context.view_layer.objects.active = target_armature

    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_bake_animation=True,
        export_force_sampling=True,
        export_frame_step=1,
        export_def_bones=True,
        export_skins=True,
        export_apply=True,
        export_yup=True,
        export_nla_strips=False,
        export_all_influences=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )
    filter_short_punch_glb(OUTPUT)
    print("TARGET_BONES", len(target_signature))
    print("JUMP_RANGE", tuple(jump.frame_range))
    print("EXPORTED", OUTPUT)


if __name__ == "__main__":
    main()
