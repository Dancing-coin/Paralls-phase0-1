from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ("female_bandage_external", "female_jk_external", "female_t_external")


def read_gltf(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2
    offset = 12
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:
            return json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
        offset += 8 + chunk_length
    raise AssertionError(f"GLB JSON chunk missing: {path}")


def animation_duration(document: dict, name: str) -> float:
    animation = next(item for item in document["animations"] if item.get("name") == name)
    return max(
        float(document["accessors"][sampler["input"]].get("max", [0.0])[0])
        for sampler in animation["samplers"]
    )


def test_all_street_character_packages_ship_shared_walking2_clip() -> None:
    durations = []
    for package_id in PACKAGES:
        package_dir = ROOT / "assets" / "active" / package_id
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["clip_aliases"]["walk_forward"] == "walking2"
        assert manifest["locomotion_map"]["walk_forward"] == "walking2"
        document = read_gltf(package_dir / f"{package_id}.glb")
        assert any(item.get("name") == "walking2" for item in document["animations"])
        durations.append(animation_duration(document, "walking2"))
    assert all(abs(duration - durations[0]) < 1e-9 for duration in durations)
    assert abs(durations[0] - 0.5666666666666667) < 1e-9


def test_copied_walking2_preserves_canonical_bone_channels() -> None:
    source = read_gltf(ROOT / "assets/active/female_jk_external/female_jk_external.glb")
    source_animation = next(item for item in source["animations"] if item.get("name") == "walking2")
    source_nodes = source["nodes"]
    source_names = {
        source_nodes[channel["target"]["node"]].get("name", "")
        for channel in source_animation["channels"]
    }
    assert len(source_names) == 68
    for package_id in PACKAGES:
        document = read_gltf(ROOT / "assets/active" / package_id / f"{package_id}.glb")
        target_names = {node.get("name", "") for node in document["nodes"]}
        assert source_names <= target_names


def test_manifest_digests_match_updated_runtime_glbs() -> None:
    for package_id in PACKAGES:
        package_dir = ROOT / "assets" / "active" / package_id
        glb = package_dir / f"{package_id}.glb"
        digest = hashlib.sha256(glb.read_bytes()).hexdigest().upper()
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["source"]["digest_sha256"] == digest
