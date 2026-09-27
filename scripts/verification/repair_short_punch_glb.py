import json
import struct
from pathlib import Path


GLB = Path("assets/active/female_jk_external/female_jk_external.glb")
LOWER_PREFIXES = ("thigh", "leg", "foot", "toes")


def main() -> None:
    data = GLB.read_bytes()
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
    boxing = next(animation for animation in document["animations"] if animation.get("name") == "boxing")

    def is_lower_or_root(name: str) -> bool:
        return name in {"root.x", "spine_01.x"} or name.startswith(LOWER_PREFIXES)

    kept_channels = []
    kept_sampler_indices = set()
    removed = 0
    for channel in boxing["channels"]:
        name = nodes.get(channel.get("target", {}).get("node", -1), "")
        if is_lower_or_root(name):
            removed += 1
            continue
        kept_channels.append(dict(channel))
        kept_sampler_indices.add(channel["sampler"])

    sampler_remap = {}
    samplers = []
    for old_index, sampler in enumerate(boxing["samplers"]):
        if old_index in kept_sampler_indices:
            sampler_remap[old_index] = len(samplers)
            samplers.append(dict(sampler))
    for channel in kept_channels:
        channel["sampler"] = sampler_remap[channel["sampler"]]

    replacement = {"name": "short punch", "channels": kept_channels, "samplers": samplers}
    document["animations"] = [
        animation for animation in document["animations"] if animation.get("name") != "short punch"
    ]
    document["animations"].append(replacement)

    rebuilt = bytearray(struct.pack("<4sII", magic, version, 0))
    for chunk_type, payload in chunks:
        if chunk_type == 0x4E4F534A:
            payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            payload += b" " * ((4 - len(payload) % 4) % 4)
        rebuilt.extend(struct.pack("<II", len(payload), chunk_type))
        rebuilt.extend(payload)
    struct.pack_into("<I", rebuilt, 8, len(rebuilt))
    GLB.write_bytes(rebuilt)
    print(f"REPAIRED_SHORT_PUNCH removed={removed} channels={len(kept_channels)} samplers={len(samplers)}")


if __name__ == "__main__":
    main()
