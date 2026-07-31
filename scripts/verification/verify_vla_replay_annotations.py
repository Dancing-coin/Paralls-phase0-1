from __future__ import annotations

import argparse

from common import repo_root, verification_dir, write_json, write_markdown
from vla_replay_annotations import coverage_status, load_annotation_manifest, validate_annotation_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the reviewed VLA replay annotation manifest.")
    parser.add_argument("--manifest", default="docs/verification/vla-advisory-replay-annotation-manifest.json")
    args = parser.parse_args()
    root = repo_root()
    manifest_path = root / args.manifest
    manifest = load_annotation_manifest(manifest_path)
    errors = validate_annotation_manifest(manifest)
    coverage = coverage_status(manifest)
    report = {
        "schema_version": "vla-advisory-replay-annotation-verification.v1",
        "manifest_path": str(manifest_path.relative_to(root)),
        "manifest_valid": not errors,
        "validation_errors": errors,
        "coverage": coverage,
        "semantic_accuracy_claim_allowed": False,
        "notes": [
            "A valid bootstrap manifest is not a semantic-accuracy proof.",
            "Only visible scene truth may be scored; PQF and structured-fact context must not receive model credit.",
        ],
    }
    evidence_dir = verification_dir(root)
    json_path = evidence_dir / "vla-advisory-replay-annotation-report.json"
    markdown_path = evidence_dir / "vla-advisory-replay-annotation-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "VLA Advisory Replay Annotation Verification", report, "manifest_valid")
    print(f"vla_advisory_replay_annotation_json={json_path}")
    print(f"vla_advisory_replay_annotation_md={markdown_path}")
    print(f"manifest_valid={not errors}")
    print(f"annotation_coverage_status={coverage['status']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
