"""Copy the canonical JK ``walking2`` clip into the other street characters.

The three runtime packages use the same canonical deform-bone names.  This
build-time operation copies the animation samplers and retargets their channel
node indices by bone/node name while preserving each target model's mesh,
skin, and other animations.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets/active/female_jk_external/female_jk_external.glb"
TARGETS = (
    ROOT / "assets/active/female_bandage_external/female_bandage_external.glb",
    ROOT / "assets/active/female_t_external/female_t_external.glb",
)
ACTION_NAME = "walking2"


def read_glb(path: Path) -> tuple[dict, bytes, list[tuple[int, bytes]]]:
    data = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise RuntimeError(f"not a glTF 2.0 GLB: {path}")
    offset = 12
    document = None
    chunks: list[tuple[int, bytes]] = []
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + chunk_length]
        chunks.append((chunk_type, payload))
        if chunk_type == 0x4E4F534A:
            document = json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
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
) -> tuple[int, int, float]:
    source_animation = next(
        animation for animation in source.get("animations", []) if animation.get("name") == ACTION_NAME
    )
    source_nodes = source.get("nodes", [])
    target_nodes = {node.get("name", ""): index for index, node in enumerate(target.get("nodes", []))}
    source_node_names = {
        source_nodes[channel["target"]["node"]].get("name", "")
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
        target_name = source_nodes[channel["target"]["node"]].get("name", "")
        copied["target"] = dict(channel["target"])
        copied["target"]["node"] = target_nodes[target_name]
        channels.append(copied)

    target["animations"] = [
        animation for animation in target.get("animations", []) if animation.get("name") != ACTION_NAME
    ]
    target["animations"].append({"name": ACTION_NAME, "channels": channels, "samplers": samplers})

    duration = 0.0
    for sampler in source_animation["samplers"]:
        input_accessor = source_accessors[sampler["input"]]
        max_values = input_accessor.get("max", [])
        if max_values:
            duration = max(duration, float(max_values[0]))
    return len(channels), len(samplers), duration


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
    if not any(animation.get("name") == ACTION_NAME for animation in source.get("animations", [])):
        raise RuntimeError(f"source action missing: {ACTION_NAME}")
    for target_path in TARGETS:
        target, target_binary, chunks = read_glb(target_path)
        binary = bytearray(target_binary)
        channels, samplers, duration = copy_animation(source, source_binary, target, binary)
        write_glb(target_path, target, bytes(binary), chunks)
        print(
            f"COPIED target={target_path.name} action={ACTION_NAME} "
            f"channels={channels} samplers={samplers} duration={duration:.9f}"
        )


if __name__ == "__main__":
    main()
