from pathlib import Path
from types import SimpleNamespace
import json
import sys
import xml.etree.ElementTree as ET

import pytest

from scripts.verification.common import verification_dir
from scripts.verification.run_context import run_scope

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_character_population_integrated_loop as verifier

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("fault", [None, "missing", "skip", "exit", "empty"])
def test_integration_report_requires_real_complete_current_junit(monkeypatch, fault):
    def execute(command, cwd, log):
        junit = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--junitxml=")))
        suite = ET.Element("testsuite")
        names = verifier.REQUIRED_CASES[:-1] if fault == "missing" else verifier.REQUIRED_CASES
        for name in (() if fault == "empty" else names):
            case = ET.SubElement(suite, "testcase", name=name)
            if fault == "skip":
                ET.SubElement(case, "skipped")
        junit.write_text(ET.tostring(suite, encoding="unicode"), encoding="utf-8")
        return SimpleNamespace(returncode=1 if fault == "exit" else 0)

    monkeypatch.setattr(verifier, "run_command", execute)
    with run_scope(ROOT):
        assert verifier.main() == (0 if fault is None else 1)
        report = json.loads((verification_dir(ROOT) / "character-population-integrated-loop-report.json").read_text())
        assert report["overall_passed"] == (fault is None)
        assert report["godot_status"] == "paused_by_user"
        assert report["safe_allocation_status"] == "deferred_C3"


def test_integration_profile_does_not_accept_an_existing_junit(monkeypatch):
    with run_scope(ROOT):
        target = verification_dir(ROOT) / "character-population-integrated-loop-junit.xml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("<testsuite/>", encoding="utf-8")
        monkeypatch.setattr(verifier, "run_command", lambda *args: pytest.fail("不应执行"))
        with pytest.raises(RuntimeError, match="artifact_exists"):
            verifier.main()
