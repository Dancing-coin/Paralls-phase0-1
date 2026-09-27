"""Copy the qualified JK short-punch realization into the T-model GLB.

This is a build-time asset operation. It does not alter either source blend
file and it keeps female_t's mesh/skeleton as the target runtime package.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets/active/female_jk_external/female_jk_external.glb"
TARGET = ROOT / "assets/active/female_t_external/female_t_external.glb"
SOCKET_NAMES = ("weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword")
ACTION_NAMES = ("boxing", "sword attack", "short punch")


def read_glb(path: Path) -> tuple[dict, bytes, list[tuple[int, bytes]]]:
    data = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise RuntimeError(f"not a GLB: {path}")
    offset = 12
    document = None
    chunks: list[tuple[int, bytes]] = []
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + chunk_length]
        chunks.append((chunk_type, payload))
        if chunk_type == 0x4E4F534A:
            document = json.loads(payload.rstrip(b" ").decode("utf-8"))
        offset += 8 + chunk_length
    if document is None:
        raise RuntimeError(f"missing JSON chunk: {path}")
    binary = next((payload for chunk_type, payload in chunks if chunk_type == 0x004E4942), b"")
    return document, binary, chunks


def align4(value: int) -> int:
    return (value + 3) & ~3


def append_bytes(binary: bytearray, payload: bytes) -> int:
    start = align4(len(binary))
    binary.extend(b"\0" * (start - len(binary)))
    binary.extend(payload)
    return start


def copy_animation(
    source: dict,
    source_binary: bytes,
    target: dict,
    target_binary: bytearray,
    animation_name: str,
) -> None:
    source_animation = next(
        animation for animation in source.get("animations", []) if animation.get("name") == animation_name
    )
    source_nodes = {node.get("name", ""): index for index, node in enumerate(source.get("nodes", []))}
    target_nodes = {node.get("name", ""): index for index, node in enumerate(target.get("nodes", []))}
    source_node_names = {
        source.get("nodes", [])[channel["target"]["node"]].get("name", "")
        for channel in source_animation["channels"]
    }
    missing_names = sorted(name for name in source_node_names if name not in target_nodes)
    if missing_names:
        raise RuntimeError(f"target skeleton is missing animation bones: {missing_names}")

    source_accessors = source.get("accessors", [])
    source_views = source.get("bufferViews", [])
    accessor_map: dict[int, int] = {}
    view_map: dict[int, int] = {}

    def clone_accessor(accessor_index: int) -> int:
        if accessor_index in accessor_map:
            return accessor_map[accessor_index]
        accessor = dict(source_accessors[accessor_index])
        source_view_index = accessor.get("bufferView")
        if source_view_index is not None:
            if source_view_index not in view_map:
                view = dict(source_views[source_view_index])
                view_start = int(view.get("byteOffset", 0))
                view_end = view_start + int(view["byteLength"])
                if view_end > len(source_binary):
                    raise RuntimeError("source animation buffer view is out of bounds")
                view["buffer"] = 0
                view["byteOffset"] = append_bytes(target_binary, source_binary[view_start:view_end])
                view_map[source_view_index] = len(target.setdefault("bufferViews", []))
                target["bufferViews"].append(view)
            accessor["bufferView"] = view_map[source_view_index]
        accessor_map[accessor_index] = len(target.setdefault("accessors", []))
        target["accessors"].append(accessor)
        return accessor_map[accessor_index]

    samplers = []
    sampler_map: dict[int, int] = {}
    for source_sampler_index in sorted({channel["sampler"] for channel in source_animation["channels"]}):
        source_sampler = source_animation["samplers"][source_sampler_index]
        sampler = dict(source_sampler)
        sampler["input"] = clone_accessor(int(source_sampler["input"]))
        sampler["output"] = clone_accessor(int(source_sampler["output"]))
        sampler_map[source_sampler_index] = len(samplers)
        samplers.append(sampler)

    channels = []
    for channel in source_animation["channels"]:
        copied = dict(channel)
        copied["sampler"] = sampler_map[channel["sampler"]]
        target_name = source["nodes"][channel["target"]["node"]].get("name", "")
        copied["target"] = dict(channel["target"])
        copied["target"]["node"] = target_nodes[target_name]
        channels.append(copied)

    target["animations"] = [
        animation for animation in target.get("animations", []) if animation.get("name") != animation_name
    ]
    target["animations"].append({"name": animation_name, "channels": channels, "samplers": samplers})


def add_socket_nodes(source: dict, target: dict) -> None:
    source_nodes_by_name = {node.get("name", ""): node for node in source.get("nodes", [])}
    target_nodes_by_name = {node.get("name", ""): index for index, node in enumerate(target.get("nodes", []))}
    hand_index = target_nodes_by_name.get("hand.r")
    if hand_index is None:
        raise RuntimeError("target hand.r node missing")
    hand = target["nodes"][hand_index]
    children = list(hand.get("children", []))
    for name in SOCKET_NAMES:
        if name in target_nodes_by_name:
            continue
        node = dict(source_nodes_by_name[name])
        node_index = len(target["nodes"])
        target["nodes"].append(node)
        target_nodes_by_name[name] = node_index
        children.append(node_index)
    hand["children"] = children


def write_glb(path: Path, document: dict, binary: bytes, chunks: list[tuple[int, bytes]]) -> None:
    document["buffers"][0]["byteLength"] = len(binary)
    json_payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_payload += b" " * ((4 - len(json_payload) % 4) % 4)
    binary_payload = binary + b"\0" * ((4 - len(binary) % 4) % 4)
    output = bytearray(struct.pack("<4sII", b"glTF", 2, 0))
    output.extend(struct.pack("<II", len(json_payload), 0x4E4F534A))
    output.extend(json_payload)
    output.extend(struct.pack("<II", len(binary_payload), 0x004E4942))
    output.extend(binary_payload)
    struct.pack_into("<I", output, 8, len(output))
    path.write_bytes(output)


def main() -> None:
    source, source_binary, _ = read_glb(SOURCE)
    target, target_binary, chunks = read_glb(TARGET)
    binary = bytearray(target_binary)
    for animation_name in ACTION_NAMES:
        copy_animation(source, source_binary, target, binary, animation_name)
    add_socket_nodes(source, target)
    write_glb(TARGET, target, bytes(binary), chunks)
    print("COPIED_ACTIONS", ",".join(ACTION_NAMES))
    print("COPIED_SOCKETS", ",".join(SOCKET_NAMES))
    print("TARGET", TARGET)


if __name__ == "__main__":
    main()
