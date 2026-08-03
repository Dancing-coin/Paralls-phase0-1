from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_tts_service.py",
    "backend/tests/test_tts_voice_profiles.py",
    "backend/tests/test_tts_voice_enrollment.py",
    "backend/tests/test_config_runtime_modes.py",
]

_TRACKED_TTS_PATHS = [
    ".env.example",
    "assets/tts",
    "assets/characters/voice_sources",
    ".harness/profiles/tts-voice-profile-adapter.json",
    "docs/INDEX.md",
    "docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-design.md",
    "docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-design.md",
    "docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-implementation-plan.md",
    "docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-implementation-plan.md",
    "docs/superpowers/plans/world-character-siming-authority-mainline/2026-08-03-tts-voice-profile-adapter-closure-implementation-plan.md",
]
_NONEMPTY_TTS_KEY = re.compile(r"^[ \t]*TTS_PROVIDER_API_KEY[ \t]*=[ \t]*[^\s#].*$", re.MULTILINE)
_SIGNED_URL_MARKER = re.compile(r"https?://\S+(?:signature|x-oss-signature|x-amz-signature|token)=", re.IGNORECASE)
_LONG_BASE64 = re.compile(r"[A-Za-z0-9+/]{512,}={0,2}")
_RAW_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}


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
    tracked_errors = _tracked_tts_safety_errors(project_root)
    results = [
        _result(
            "presentation-profile-boundary",
            "Voice profile capability, catalog import, advisory ranking, enrollment, fallback, and legacy-mode tests pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
            f"exit_code={pytest_result.returncode}",
        )
    ]
    results.append(
        _result(
            "tracked-tts-evidence-safety",
            "Tracked TTS configuration, assets, plans, and profile metadata contain no non-empty key, signed URL, raw audio, or large base64 payload",
            not tracked_errors,
            _TRACKED_TTS_PATHS,
            "; ".join(tracked_errors) if tracked_errors else "tracked_tts_files_scanned",
        )
    )
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_tts_voice_profile_adapter_passed": overall,
        "scope": "credential-free presentation-only voice profile/capability tests; no live synthesis, human audition, production binding approval, or Godot runtime playback",
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


def _tracked_tts_safety_errors(project_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", *_TRACKED_TTS_PATHS],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return ["git_ls_files_failed"]
    errors: list[str] = []
    for relative_path in (line.strip() for line in result.stdout.splitlines()):
        if not relative_path:
            continue
        path = project_root / relative_path
        if path.suffix.lower() in _RAW_AUDIO_SUFFIXES:
            errors.append(f"raw_audio_tracked:{relative_path}")
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if _NONEMPTY_TTS_KEY.search(content):
            errors.append(f"nonempty_tts_key:{relative_path}")
        if _SIGNED_URL_MARKER.search(content):
            errors.append(f"signed_url:{relative_path}")
        if _LONG_BASE64.search(content):
            errors.append(f"large_base64:{relative_path}")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
