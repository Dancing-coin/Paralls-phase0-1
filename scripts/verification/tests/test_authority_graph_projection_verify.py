from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness
from registry import load_profile_registry


ROOT = Path(__file__).resolve().parents[3]


def test_authority_graph_projection_profile_is_registered() -> None:
    registry = load_profile_registry(ROOT)
    assert "authority-graph-projection" in registry.profiles
    assert harness._profiles_for_selection("authority-graph-projection", registry) == [
        "authority-graph-projection"
    ]


def test_authority_graph_projection_verifier_passes_all_domains() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_authority_graph_projection.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout
    report = json.loads(
        (ROOT / ".harness/verification/authority-graph-projection-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["overall_authority_graph_projection_passed"] is True
    assert all(item["status"] == "proved" for item in report["results"])
