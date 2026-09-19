from __future__ import annotations

from pathlib import Path
import sys


VERIFICATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFICATION_ROOT))

import common


def test_verification_paths_has_a_stable_godot_uid_sidecar() -> None:
    uid_path = VERIFICATION_ROOT / "VerificationPaths.gd.uid"

    assert uid_path.exists()
    assert uid_path.read_text(encoding="utf-8").strip().startswith("uid://")


def test_godot_prepare_starts_the_project_without_forced_repository_wide_import(monkeypatch, tmp_path: Path) -> None:
    captured: list[object] = []

    monkeypatch.setattr(common, "verification_dir", lambda _root: tmp_path)
    monkeypatch.setattr(common, "run_command", lambda *args, **kwargs: captured.append(args) or object())

    common.ensure_godot_import(tmp_path, Path("D:/Godot/Godot.exe"))

    command = captured[0][0]
    assert "--headless" in command
    assert "--quit-after" in command
    assert "--import" not in command
