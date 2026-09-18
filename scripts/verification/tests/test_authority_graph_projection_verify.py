from __future__ import annotations

import pytest

from scripts.verification.common import verification_dir
from scripts.verification.run_context import run_scope

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness
from registry import load_profile_registry


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def evidence_scope():
    with run_scope(ROOT):
        yield


def test_authority_graph_projection_profile_is_registered() -> None:
    registry = load_profile_registry(ROOT)
    assert "authority-graph-projection" in registry.profiles
    assert harness._profiles_for_selection("authority-graph-projection", registry) == [
        "authority-graph-projection"
    ]


def test_authority_graph_projection_verifier_passes_all_domains(evidence_scope) -> None:
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
        (verification_dir(ROOT) / "authority-graph-projection-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["overall_authority_graph_projection_passed"] is True
    assert all(item["status"] == "proved" for item in report["results"])
