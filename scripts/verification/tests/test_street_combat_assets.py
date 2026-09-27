from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(r"D:\Users\User\Documents\paralls-art-assets\exports\citystreets_209\0.3.0")
STAGED = ROOT / "assets" / "active" / "citystreets_209" / "0.3.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_staged_street_pack_matches_environment_only_source() -> None:
    staged = json.loads((STAGED / "manifest.json").read_text(encoding="utf-8"))
    source = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    assert (staged["pack_id"], staged["version"]) == ("citystreets_209", "0.3.0")
    assert staged == source
    for name in ("environment.glb", "collision.glb", "navigation.glb"):
        assert (STAGED / name).is_file()
        assert _sha256(STAGED / name) == _sha256(SOURCE / name)
    assert not any("female" in path.name.lower() for path in STAGED.rglob("*"))


def test_staged_street_metadata_preserves_source_coordinates() -> None:
    for name in ("metadata/anchors.json", "metadata/navigation.json", "scene-binding.md"):
        assert (STAGED / name).read_text(encoding="utf-8") == (SOURCE / name).read_text(encoding="utf-8")
