"""Build the third primary external character package from the exact source blend.

The source blend is never saved or modified.  Blender performs the only
authoring-side operation here: it normalizes the source's 30 fps actions to the
runtime 60 fps convention, appends the already-qualified jump/run actions from
the same canonical rig family, derives an upper-body short-punch action, adds
explicit weapon sockets, and exports a fresh GLB.
"""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path

import bpy


SOURCE = Path(r"E:/下载/建模1 绷带血迹黑长直 T字版本 多动作版本.blend")
LOCOMOTION_SOURCE = Path(r"E:/下载/建模2 纹身腿黑卷发女T字版本  基础动作版.blend")
OUTPUT = Path(__file__).resolve().parents[2] / "assets/active/female_bandage_external/female_bandage_external.glb"
SOCKET_NAMES = ("weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword")
LOWER_BODY_PREFIXES = ("thigh", "leg", "foot", "toes")
ROOT_AND_PELVIS = {"root.x", "spine_01.x"}
NATIVE_ACTIONS = ("boxing", "idle", "walking", "left turn", "right turn", "SWORD ATTACK", "drinking", "waving")
CONTROLLER_ONLY_BONES = {"c_hand_fk.l", "c_hand_fk.r"}


def _action_fcurves(action: bpy.types.Action):
    if hasattr(action, "fcurves"):
        yield from action.fcurves
        return
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                yield from channelbag.fcurves


def _scale_action_frames(action: bpy.types.Action, factor: float) -> None:
    for fcurve in _action_fcurves(action):
        for key in fcurve.keyframe_points:
            key.co.x *= factor
            key.handle_left.x *= factor
            key.handle_right.x *= factor
        fcurve.update()


def _find_runtime_objects() -> tuple[bpy.types.Object, bpy.types.Object]:
    armature = bpy.data.objects.get("rig")
    if armature is None or armature.type != "ARMATURE":
        armature = next((obj for obj in bpy.data.objects if obj.type == "ARMATURE"), None)
    if armature is None:
        raise RuntimeError("bandage source armature is missing")
    meshes = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH"
        and len(obj.vertex_groups) >= 60
        and any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers)
    ]
    if len(meshes) != 1:
        raise RuntimeError(f"expected one skinned runtime mesh, found {[obj.name for obj in meshes]}")
    return armature, meshes[0]


def _append_missing_locomotion_actions() -> None:
    with bpy.data.libraries.load(str(LOCOMOTION_SOURCE), link=False) as (data_from, data_to):
        missing = [name for name in ("jump", "running") if name in data_from.actions and bpy.data.actions.get(name) is None]
        data_to.actions = missing
    if bpy.data.actions.get("jump") is None or bpy.data.actions.get("running") is None:
        raise RuntimeError("same-family locomotion source did not provide jump and running")


def _normalize_actions() -> None:
    # The source is authored at 30 fps; preserve its seconds while normalizing
    # the exported package to the 60 fps convention used by the other roles.
    for name in NATIVE_ACTIONS:
        action = bpy.data.actions.get(name)
        if action is None:
            raise RuntimeError(f"required native action missing: {name}")
        _scale_action_frames(action, 2.0)
    if bpy.data.actions.get("SWORD ATTACK") is None:
        raise RuntimeError("SWORD ATTACK action missing")
    duplicate = bpy.data.actions.get("mixamo.com_remap")
    if duplicate is not None:
        bpy.data.actions.remove(duplicate)
    # The source rig keeps two hand FK controllers animated even though they
    # are not deform/weighted bones.  Removing only their action channels on
    # this in-memory export copy prevents Blender's glTF exporter from
    # promoting them into runtime skin joints; the source blend is untouched.
    for action in bpy.data.actions:
        for fcurve in list(_action_fcurves(action)):
            if any(f'pose.bones["{bone}"]' in fcurve.data_path for bone in CONTROLLER_ONLY_BONES):
                if hasattr(action, "fcurves"):
                    action.fcurves.remove(fcurve)
                else:
                    for layer in action.layers:
                        for strip in layer.strips:
                            for channelbag in strip.channelbags:
                                if fcurve in list(channelbag.fcurves):
                                    channelbag.fcurves.remove(fcurve)
    bpy.context.scene.render.fps = 60
    bpy.context.scene.render.fps_base = 1.0


def _weighted_deform_bones(armature: bpy.types.Object, mesh: bpy.types.Object) -> list[str]:
    weighted = {group.name for group in mesh.vertex_groups}
    deform = {bone.name for bone in armature.data.bones if bone.use_deform}
    if weighted != deform:
        raise RuntimeError(
            "source deform/weight boundary mismatch: "
            f"weighted_only={sorted(weighted - deform)}, deform_only={sorted(deform - weighted)}"
        )
    if len(weighted) != 68:
        raise RuntimeError(f"expected 68 weighted deform bones, found {len(weighted)}")
    return sorted(weighted)


def _upper_body_bones(armature: bpy.types.Object, mesh: bpy.types.Object) -> list[str]:
    weighted = set(_weighted_deform_bones(armature, mesh))
    return sorted(
        name
        for name in weighted
        if name not in ROOT_AND_PELVIS and not name.startswith(LOWER_BODY_PREFIXES)
    )


def _set_active_action(armature: bpy.types.Object, action: bpy.types.Action) -> None:
    armature.animation_data_create()
    armature.animation_data.action = action
    if action.slots:
        armature.animation_data.action_slot_handle = action.slots[0].handle


def _derive_short_punch(armature: bpy.types.Object, mesh: bpy.types.Object) -> None:
    source = bpy.data.actions.get("boxing")
    if source is None:
        raise RuntimeError("boxing action missing")
    bones = _upper_body_bones(armature, mesh)
    if not bones:
        raise RuntimeError("upper-body deform bones are missing")
    old = bpy.data.actions.get("short punch")
    if old is not None:
        bpy.data.actions.remove(old)
    # Copy the authored multi-key boxing curves first, then retain only the
    # canonical upper-body deform tracks.  Sampling evaluated matrices and
    # inserting them into a fresh layered action collapses to a single key in
    # Blender 5.1, which would create a static, non-concurrent clip.
    derived = source.copy()
    derived.name = "short punch"
    upper_body = set(bones)
    for fcurve in list(_action_fcurves(derived)):
        match = re.search(r'pose\.bones\["([^"]+)"\]', fcurve.data_path)
        if match is None or match.group(1) not in upper_body:
            if hasattr(derived, "fcurves"):
                derived.fcurves.remove(fcurve)
            else:
                for layer in derived.layers:
                    for strip in layer.strips:
                        for channelbag in strip.channelbags:
                            if fcurve in list(channelbag.fcurves):
                                channelbag.fcurves.remove(fcurve)
    _set_active_action(armature, derived)
    derived["derived_from_clip_ref"] = "boxing"
    derived["derived_bone_mask"] = "canonical:upper_body"
    print(f"SHORT_PUNCH_BONES={len(bones)}")


def _add_weapon_sockets(armature: bpy.types.Object) -> list[bpy.types.Object]:
    if armature.data.bones.get("hand.r") is None:
        raise RuntimeError("canonical right hand bone hand.r is missing")
    sockets: list[bpy.types.Object] = []
    for name in SOCKET_NAMES:
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        socket = bpy.data.objects.new(name, None)
        socket.empty_display_type = "CUBE"
        socket.empty_display_size = 0.08
        socket.parent = armature
        socket.parent_type = "BONE"
        socket.parent_bone = "hand.r"
        socket.location = (0.0, 0.0, 0.0)
        socket["canonical_bone"] = "right_hand"
        socket["slot_id"] = name
        bpy.context.collection.objects.link(socket)
        sockets.append(socket)
    return sockets


def _select_runtime_objects(armature: bpy.types.Object, mesh: bpy.types.Object, sockets: list[bpy.types.Object]) -> None:
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    armature.select_set(True)
    mesh.select_set(True)
    for socket in sockets:
        socket.select_set(True)
    bpy.context.view_layer.objects.active = armature


def _read_glb(path: Path) -> tuple[dict, bytes, list[tuple[int, bytes]]]:
    data = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise RuntimeError(f"not a GLB: {path}")
    offset = 12
    document = None
    chunks: list[tuple[int, bytes]] = []
    while offset < total_length:
        length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + length]
        chunks.append((chunk_type, payload))
        if chunk_type == 0x4E4F534A:
            document = json.loads(payload.rstrip(b" ").decode("utf-8"))
        offset += 8 + length
    if document is None:
        raise RuntimeError("GLB JSON chunk missing")
    binary = next((payload for chunk_type, payload in chunks if chunk_type == 0x004E4942), b"")
    return document, binary, chunks


def _write_glb(path: Path, document: dict, chunks: list[tuple[int, bytes]], binary: bytes | None = None) -> None:
    rebuilt = bytearray(struct.pack("<4sII", b"glTF", 2, 0))
    for chunk_type, payload in chunks:
        if chunk_type == 0x4E4F534A:
            payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            payload += b" " * ((4 - len(payload) % 4) % 4)
        elif chunk_type == 0x004E4942 and binary is not None:
            payload = binary
        rebuilt.extend(struct.pack("<II", len(payload), chunk_type))
        rebuilt.extend(payload)
    struct.pack_into("<I", rebuilt, 8, len(rebuilt))
    path.write_bytes(rebuilt)


def _prune_non_deform_controller_nodes(path: Path) -> None:
    document, binary, chunks = _read_glb(path)
    nodes = document.get("nodes", [])
    removed_indices = {
        index for index, node in enumerate(nodes) if node.get("name") in CONTROLLER_ONLY_BONES
    }
    if removed_indices != {index for index, node in enumerate(nodes) if node.get("name") in CONTROLLER_ONLY_BONES}:
        raise RuntimeError("controller node discovery was not deterministic")
    if not removed_indices:
        raise RuntimeError("expected non-deform controller nodes in Blender export")

    skin = document.get("skins", [])[0]
    joints = list(skin.get("joints", []))
    if not removed_indices.intersection(joints):
        raise RuntimeError("controller nodes were not exported as skin joints")
    retained_joint_positions = [position for position, node_index in enumerate(joints) if node_index not in removed_indices]
    old_joint_to_new = {
        old_position: new_position for new_position, old_position in enumerate(retained_joint_positions)
    }
    removed_joint_positions = set(range(len(joints))) - set(retained_joint_positions)
    inverse_bind_accessor_index = skin.get("inverseBindMatrices")
    if inverse_bind_accessor_index is None:
        raise RuntimeError("skin inverse bind matrices are missing")
    accessor = document["accessors"][inverse_bind_accessor_index]
    buffer_view = document["bufferViews"][accessor["bufferView"]]
    if accessor.get("type") != "MAT4" or accessor.get("componentType") != 5126:
        raise RuntimeError("unexpected inverse bind matrix accessor format")
    if int(accessor.get("count", 0)) != len(joints):
        raise RuntimeError("inverse bind matrix count does not match skin joints")
    matrix_stride = 16 * 4
    base_offset = int(buffer_view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    matrices = [binary[base_offset + position * matrix_stride : base_offset + (position + 1) * matrix_stride] for position in range(len(joints))]
    if any(len(matrix) != matrix_stride for matrix in matrices):
        raise RuntimeError("inverse bind matrix buffer is truncated")
    packed_matrices = b"".join(matrices[position] for position in retained_joint_positions)
    mutable_binary = bytearray(binary)
    mutable_binary[base_offset : base_offset + len(packed_matrices)] = packed_matrices
    accessor["count"] = len(retained_joint_positions)
    buffer_view["byteLength"] = int(accessor.get("byteOffset", 0)) + len(packed_matrices)
    skin["joints"] = [joints[position] for position in retained_joint_positions]

    # The mesh JOINTS_* attributes index the original 70-element skin.  Once
    # the two controller joints are removed, compact every vertex index to the
    # new 68-element skin while preserving the existing binary layout.
    component_sizes = {5121: 1, 5123: 2, 5125: 4}
    component_formats = {5121: "<B", 5123: "<H", 5125: "<I"}
    remapped_accessors: set[int] = set()
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            for attribute_name, accessor_index in primitive.get("attributes", {}).items():
                if not str(attribute_name).startswith("JOINTS_") or accessor_index in remapped_accessors:
                    continue
                accessor = document["accessors"][accessor_index]
                component_type = int(accessor.get("componentType", 0))
                if component_type not in component_sizes or accessor.get("type") != "VEC4":
                    raise RuntimeError("unsupported JOINTS accessor format")
                view = document["bufferViews"][accessor["bufferView"]]
                component_size = component_sizes[component_type]
                element_size = component_size * 4
                stride = int(view.get("byteStride", element_size))
                start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
                unpack_format = component_formats[component_type]
                for vertex_index in range(int(accessor.get("count", 0))):
                    element_start = start + vertex_index * stride
                    for component_index in range(4):
                        value_offset = element_start + component_index * component_size
                        old_value = struct.unpack_from(unpack_format, mutable_binary, value_offset)[0]
                        if old_value in removed_joint_positions:
                            # Controller joints are not weighted by the source
                            # mesh; zero-weight filler slots are remapped to
                            # the root joint so every index remains in range.
                            new_value = 0
                        else:
                            new_value = old_joint_to_new[old_value]
                        struct.pack_into(unpack_format, mutable_binary, value_offset, new_value)
                remapped_accessors.add(accessor_index)

    for node in nodes:
        if "children" in node:
            node["children"] = [child for child in node["children"] if child not in removed_indices]
    for index in removed_indices:
        nodes[index] = {"extras": {"pruned_controller_bone": True}}

    for animation in document.get("animations", []):
        kept_channels = []
        kept_sampler_indices = set()
        for channel in animation.get("channels", []):
            target_node = channel.get("target", {}).get("node", -1)
            if target_node in removed_indices:
                continue
            kept_channels.append(dict(channel))
            kept_sampler_indices.add(channel.get("sampler", -1))
        sampler_remap = {}
        samplers = []
        for old_index, sampler in enumerate(animation.get("samplers", [])):
            if old_index in kept_sampler_indices:
                sampler_remap[old_index] = len(samplers)
                samplers.append(dict(sampler))
        for channel in kept_channels:
            channel["sampler"] = sampler_remap[channel["sampler"]]
        animation["channels"] = kept_channels
        animation["samplers"] = samplers

    _write_glb(path, document, chunks, bytes(mutable_binary))
    print(f"PRUNED_CONTROLLER_NODES={len(removed_indices)} SKIN_JOINTS={len(skin['joints'])}")


def _filter_short_punch(path: Path) -> None:
    document, _, chunks = _read_glb(path)
    nodes = {index: node.get("name", "") for index, node in enumerate(document.get("nodes", []))}
    animation = next(item for item in document.get("animations", []) if item.get("name") == "short punch")
    kept_channels = []
    kept_sampler_indices = set()
    removed = 0
    for channel in animation.get("channels", []):
        name = nodes.get(channel.get("target", {}).get("node", -1), "")
        if name in ROOT_AND_PELVIS or name.startswith(LOWER_BODY_PREFIXES):
            removed += 1
            continue
        kept_channels.append(dict(channel))
        kept_sampler_indices.add(channel.get("sampler", -1))
    sampler_remap = {}
    samplers = []
    for old_index, sampler in enumerate(animation.get("samplers", [])):
        if old_index in kept_sampler_indices:
            sampler_remap[old_index] = len(samplers)
            samplers.append(dict(sampler))
    for channel in kept_channels:
        channel["sampler"] = sampler_remap[channel["sampler"]]
    animation["channels"] = kept_channels
    animation["samplers"] = samplers
    if removed == 0:
        raise RuntimeError("short punch filter found no lower/root channels")

    _write_glb(path, document, chunks)
    print(f"SHORT_PUNCH_FILTER_REMOVED={removed}")


def _repair_short_punch_channels(path: Path) -> None:
    document, _, chunks = _read_glb(path)
    nodes = {index: node.get("name", "") for index, node in enumerate(document.get("nodes", []))}
    source = next(item for item in document.get("animations", []) if item.get("name") == "boxing")
    derived = next(item for item in document.get("animations", []) if item.get("name") == "short punch")
    repaired_channels = []
    repaired_samplers = []
    for channel in source.get("channels", []):
        target = channel.get("target", {})
        node_name = nodes.get(target.get("node", -1), "")
        if node_name in ROOT_AND_PELVIS or node_name.startswith(LOWER_BODY_PREFIXES):
            continue
        sampler_index = channel.get("sampler", -1)
        new_sampler_index = len(repaired_samplers)
        repaired_samplers.append(dict(source["samplers"][sampler_index]))
        copied = dict(channel)
        copied["sampler"] = new_sampler_index
        repaired_channels.append(copied)
    if not repaired_channels:
        raise RuntimeError("short punch lost all upper-body animation channels")
    derived["channels"] = repaired_channels
    derived["samplers"] = repaired_samplers
    _write_glb(path, document, chunks)
    print(f"SHORT_PUNCH_UPPER_CHANNELS_RESTORED={len(repaired_channels)}")


def main() -> None:
    if bpy.app.version[:2] != (5, 1):
        raise RuntimeError(f"Blender 5.1.x is required, got {bpy.app.version_string}")
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    armature, mesh = _find_runtime_objects()
    _weighted_deform_bones(armature, mesh)
    _append_missing_locomotion_actions()
    _normalize_actions()
    _derive_short_punch(armature, mesh)
    # Keep a full-body locomotion action active during export, matching the
    # established JK/T package build boundary and preventing controller-only
    # hand FK bones from becoming runtime skin joints.
    _set_active_action(armature, bpy.data.actions["jump"])
    sockets = _add_weapon_sockets(armature)
    _select_runtime_objects(armature, mesh, sockets)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
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
    _prune_non_deform_controller_nodes(OUTPUT)
    _filter_short_punch(OUTPUT)
    _repair_short_punch_channels(OUTPUT)
    print(f"EXPORTED={OUTPUT}")
    print(f"SOURCE_DIGEST_REQUIRED={SOURCE}")


if __name__ == "__main__":
    main()
