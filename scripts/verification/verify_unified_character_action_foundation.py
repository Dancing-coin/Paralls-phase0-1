from __future__ import annotations

try:
    from .common import artifact_ref, verification_dir
except ImportError:
    from common import artifact_ref, verification_dir

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "character" / "character-action-foundation-current-state.md"
ACTIVE_SCENES = (
    ROOT / "scenes" / "phase0" / "PlayerShell.tscn",
    ROOT / "scenes" / "phase0" / "CharacterReplica.tscn",
)


def _scene_control_paths() -> list[dict[str, object]]:
    paths: list[dict[str, object]] = []
    for scene_path in ACTIVE_SCENES:
        scene = scene_path.read_text(encoding="utf-8")
        paths.append(
            {
                "scene_reference": artifact_ref(ROOT, scene_path),
                "character_body_count": scene.count('type="CharacterBody3D"'),
                "motor_count": scene.count('name="CharacterMotor" type="Node" parent="."'),
            }
        )
    return paths


def verify_baseline() -> dict[str, object]:
    ledger = LEDGER.read_text(encoding="utf-8")
    control_paths = _scene_control_paths()
    return {
        "stage": "baseline",
        "ledger_present": "## Migration Ledger" in ledger,
        "ledger_rows": [line for line in ledger.splitlines() if line.startswith("| `")],
        "control_paths": control_paths,
        "valid": "## Migration Ledger" in ledger
        and all(path["character_body_count"] == 1 and path["motor_count"] == 1 for path in control_paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("baseline",), required=True)
    parser.parse_args()
    evidence = verify_baseline()
    evidence_path = verification_dir(ROOT) / "unified-character-action-foundation-baseline.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if bool(evidence["valid"]) else 1


if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
