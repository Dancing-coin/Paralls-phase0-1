from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_tracked_model_secrets as guard


def test_secret_guard_flags_only_tracked_exact_secret(tmp_path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("contains test-secret", encoding="utf-8")
    ignored = tmp_path / ".env"
    ignored.write_text("CHARACTER_MODEL_API_KEY=test-secret", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt", ".gitignore"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)

    offenders = guard.scan(tmp_path, {"CHARACTER_MODEL_API_KEY": "test-secret"})

    assert offenders == ["tracked.txt"]


def test_secret_guard_reads_route_level_keys(tmp_path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("contains route-secret", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)

    offenders = guard.scan(
        tmp_path,
        {"SIMING_LLM_ROUTES_JSON": '[{"provider":"deepseek_chat","api_key":"route-secret"}]'},
    )

    assert offenders == ["tracked.txt"]
