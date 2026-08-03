from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from common import repo_root, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture distinct VLA replay candidates pending human annotation review.")
    parser.add_argument("--godot-exe", required=True)
    parser.add_argument("--variants-per-scene", type=int, default=10)
    args = parser.parse_args()
    if args.variants_per_scene < 1:
        parser.error("--variants-per-scene must be positive")

    root = repo_root()
    evidence_dir = verification_dir(root)
    candidate_dir = evidence_dir / "vla-replay-candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    hashes: set[str] = set()
    for scene_key in ("main_demo", "throne_hall"):
        for variant_index in range(args.variants_per_scene):
            candidate_id = f"{scene_key}-{variant_index + 1:02d}"
            capture_relative = f".harness/verification/vla-replay-candidates/{candidate_id}.png"
            report_relative = f".harness/verification/vla-replay-candidates/{candidate_id}.json"
            log_path = candidate_dir / f"{candidate_id}.log"
            result = run_command(
                [
                    args.godot_exe,
                    "--path",
                    str(root),
                    "--scene",
                    "res://scenes/phase0/VLAReplayCoverageCaptureProbe.tscn",
                    "--quit-after",
                    "300",
                    "--render-thread",
                    "safe",
                ],
                root,
                log_path,
                env={
                    "VLA_COVERAGE_SCENE": scene_key,
                    "VLA_COVERAGE_CANDIDATE_ID": candidate_id,
                    "VLA_COVERAGE_CAPTURE_PATH": capture_relative,
                    "VLA_COVERAGE_REPORT_PATH": report_relative,
                    "VLA_COVERAGE_VARIANT_INDEX": str(variant_index),
                },
                timeout_seconds=45,
            )
            capture_path = root / capture_relative
            payload = _load_json(root / report_relative)
            image_hash = _sha256(capture_path) if capture_path.is_file() else ""
            distinct = bool(image_hash) and image_hash not in hashes
            if image_hash:
                hashes.add(image_hash)
            records.append(
                {
                    "candidate_id": candidate_id,
                    "scene_key": scene_key,
                    "variant_index": variant_index,
                    "capture_path": capture_relative,
                    "report_path": report_relative,
                    "log_path": str(log_path.relative_to(root)),
                    "capture_sha256": image_hash,
                    "distinct_image": distinct,
                    "capture_status": payload.get("status", "missing_report"),
                    "human_review_status": "pending_human_review",
                    "exit_code": result.returncode,
                }
            )
    ready = [record for record in records if record["capture_status"] == "candidate_capture_ready" and record["distinct_image"]]
    report = {
        "schema_version": "vla-advisory-replay-candidate-captures.v1",
        "candidate_count": len(records),
        "distinct_capture_count": len(ready),
        "human_review_status": "pending_human_review",
        "promotion_rule": "A candidate may enter the official annotation manifest only after human review of visible scene truth and scoring policy.",
        "candidates": records,
    }
    json_path = evidence_dir / "vla-replay-candidate-captures.json"
    markdown_path = evidence_dir / "vla-replay-candidate-captures.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "VLA Replay Candidate Captures", report, "human_review_status")
    print(f"vla_replay_candidate_captures_json={json_path}")
    print(f"vla_replay_candidate_captures_md={markdown_path}")
    print(f"distinct_capture_count={len(ready)}")
    return 0 if len(ready) == len(records) else 1


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
