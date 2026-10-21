from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import xml.etree.ElementTree as ET

import pytest

from scripts.verification.common import verification_dir
from scripts.verification.run_context import run_scope

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_social_model_compiler_contract as verifier
from registry import load_profile_registry


ROOT = Path(__file__).resolve().parents[3]


def test_am1_contract_profile_is_opt_in_and_does_not_claim_bm1():
    profile = load_profile_registry(ROOT).profiles["social-model-compiler-contract"]
    assert not profile["requires_godot"] and not profile["include_in_all"]
    assert profile["result_artifact"] == ".harness/verification/social-model-compiler-contract-report.json"


@pytest.mark.parametrize("failure", [None, "exit", "missing", "skip", "malformed", "empty"])
def test_contract_profile_rejects_incomplete_test_evidence(monkeypatch, failure):
    def run(command, cwd, log):
        junit = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--junitxml=")))
        tests = ET.Element("testsuite")
        names = verifier.REQUIRED_CASES[:-1] if failure == "missing" else verifier.REQUIRED_CASES
        for name in (() if failure == "empty" else names):
            case = ET.SubElement(tests, "testcase", name=name)
            if failure == "skip":
                ET.SubElement(case, "skipped")
        junit.write_text("invalid XML" if failure == "malformed" else ET.tostring(tests, encoding="unicode"), encoding="utf-8")
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)

    monkeypatch.setattr(verifier, "run_command", run)
    with run_scope(ROOT):
        assert verifier.main() == (0 if failure is None else 1)
        report = json.loads((verification_dir(ROOT) / "social-model-compiler-contract-report.json").read_text())
        assert report["overall_passed"] == (failure is None)
        assert report["hm0_status"] == ("pure_calculator_verified" if failure is None else "verification_failed")
        assert report["shadow_status"] == report["advisory_status"] == "blocked_live_source_contract"


def test_contract_profile_cannot_reuse_an_old_junit(monkeypatch):
    with run_scope(ROOT):
        directory = verification_dir(ROOT)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "social-model-compiler-contract-junit.xml").write_text("<testsuite/>")
        monkeypatch.setattr(verifier, "run_command", lambda *args: pytest.fail("复用旧文件前不得执行"))
        with pytest.raises(RuntimeError, match="artifact_exists"):
            verifier.main()
