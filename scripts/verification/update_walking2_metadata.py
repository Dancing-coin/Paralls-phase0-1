"""Update manifests and qualification metadata after installing shared walking2."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("female_bandage_external", "female_jk_external", "female_t_external")
WALK_DURATION = 0.566666667
WALK_SOURCE_STEP = 0.016666667


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    for package_id in PACKAGES:
        package_dir = ROOT / "assets/active" / package_id
        glb = package_dir / f"{package_id}.glb"
        manifest_path = package_dir / "manifest.json"
        manifest = load_json(manifest_path)
        manifest.setdefault("clip_aliases", {})["walk_forward"] = "walking2"
        manifest.setdefault("locomotion_map", {})["walk_forward"] = "walking2"
        if package_id != "female_jk_external":
            package_digest = digest(glb)
            manifest.setdefault("source", {})["digest_sha256"] = package_digest
            manifest.setdefault("provenance", {})["package_digest"] = package_digest
        save_json(manifest_path, manifest)

        report_path = ROOT / "assets/characters/qualification_reports" / f"{package_id}.json"
        report = load_json(report_path)
        walking_audit = copy.deepcopy(report.setdefault("clip_audits", {}).get("walking", {}))
        walking_audit["duration_seconds"] = WALK_DURATION
        walking_audit["source_step_seconds"] = WALK_SOURCE_STEP
        report.setdefault("clip_audits", {})["walking2"] = walking_audit
        report.setdefault("locomotion", {}).setdefault("walk_forward", {})["clip_ref"] = "walking2"
        if package_id != "female_jk_external":
            package_digest = digest(glb)
            report.setdefault("provenance", {})["package_digest"] = package_digest
            report.setdefault("source", {})["digest_sha256"] = package_digest
        save_json(report_path, report)

        timing_path = package_dir / "docs/action-timing.json"
        timing = load_json(timing_path)
        for action in timing.get("actions", []):
            if action.get("action_id") == "Walk":
                action["clip"] = "walking2"
                action.setdefault("timing", {})["duration_seconds"] = WALK_DURATION
                action["timing"]["source_frames"] = [1, 34]
        save_json(timing_path, timing)


if __name__ == "__main__":
    main()
