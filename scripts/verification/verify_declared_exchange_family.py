from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.gameplay.patch_runtime import GameplayPatchManifest


def main() -> int:
    test_path = "backend/tests/test_declared_exchange_family.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", test_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "declared-exchange-family",
        "family_ref": "declared_exchange@1",
        "focused_tests": [test_path],
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Economy remains the sole ledger owner",
            "immutable package rows remain exact-one; settle_declared_exchange now derives either the v7 inventory row or committed completed-service rows from the source event",
            "provider/item derive from Inventory custody for the v7 item row, and provider/receiver derive from fulfilled Contract service rows for completed-service instances",
            "caller cannot choose party, account, amount, currency, stream, event, privacy, receipt, or idempotency",
            "existing package_declared_negotiated_exchange append, receipt, and replay spine is reused",
            "duplicate and changed duplicate remain zero-write",
            "historical package_declared_negotiated_exchange rows are not renamed or rewritten",
        ],
        "family_binding_evidence": [],
    }
    manifest_paths = (
        ROOT
        / "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/declared-exchange/package-declared-exchange-item-v7.manifest.json",
        ROOT
        / "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/declared-exchange/package-declared-exchange-service-v5.manifest.json",
    )
    try:
        manifests = tuple(
            GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
            for path in manifest_paths
        )
        report["family_binding_evidence"] = [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "patch_revision_id": manifest.patch_revision_id,
                "content_digest": manifest.content_digest,
                "binding_capability_ref": manifest.platform_extension.capability_binding_requests[0].capability_ref,
            }
            for path, manifest in zip(manifest_paths, manifests)
        ]
        report["family_binding_evidence_valid"] = (
            len(manifests) == 2
            and all(manifest.content_digest == manifest.expected_content_digest() for manifest in manifests)
            and all(
                len(manifest.platform_extension.capability_binding_requests) == 1
                and manifest.platform_extension.capability_binding_requests[0].capability_ref
                == "capability:declared-exchange@1"
                for manifest in manifests
            )
        )
    except Exception:
        report["family_binding_evidence_valid"] = False
    report["overall_passed"] = report["overall_passed"] and report["family_binding_evidence_valid"]
    artifact = ROOT / ".harness" / "verification" / "declared-exchange-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"declared_exchange_family_report_json={artifact}")
    print(f"overall_declared_exchange_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
