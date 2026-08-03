from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_tts_voice_profiles.py",
    "backend/tests/test_tts_voice_enrollment.py",
]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    evidence_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = evidence_dir / "tts-voice-profile-adapter-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    results = [
        _result(
            "presentation-profile-boundary",
            "Voice profile, controlled catalog import, advisory ranking, and enrollment-boundary tests pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
            f"exit_code={pytest_result.returncode}",
        )
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_tts_voice_profile_adapter_passed": overall,
        "scope": "presentation-only voice assets and candidate advice; no live synthesis, human audition, or production binding approval",
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log)},
    }
    json_path = evidence_dir / "tts-voice-profile-adapter-report.json"
    markdown_path = evidence_dir / "tts-voice-profile-adapter-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "TTS Voice Profile Adapter Verification Report", report, "overall_tts_voice_profile_adapter_passed")
    print(f"tts_voice_profile_adapter_report_json={json_path}")
    print(f"tts_voice_profile_adapter_report_md={markdown_path}")
    print(f"overall_tts_voice_profile_adapter_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
