from __future__ import annotations

import json
from pathlib import Path
import sys


def test_phase5d_profile_and_verifier_exist() -> None:
    verification_root = Path(__file__).parents[1]
    profile = verification_root.parents[1] / ".harness" / "profiles" / "phase5d-investigation-vertical-slice.json"
    verifier = verification_root / "verify_phase5d_investigation_vertical_slice.py"
    assert profile.exists() and verifier.exists()
    payload = json.loads(profile.read_text(encoding="utf-8"))
    assert payload["name"] == "phase5d-investigation-vertical-slice"
    assert payload["script"] == "scripts/verification/verify_phase5d_investigation_vertical_slice.py"


def test_phase5d_verifier_reports_required_sections() -> None:
    sys.path.insert(0, str(Path(__file__).parents[1]))
    import verify_phase5d_investigation_vertical_slice as verifier

    evidence = verifier.collect_evidence()
    assert set(("provenance", "permission_redaction", "decision_receipt", "replay_hash", "failure_zero_write")) <= set(evidence.__dict__)
