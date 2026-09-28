from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "docs" / "character" / "action-foundation-series-baseline-2026-09-28.md"
PROBE = ROOT / "scripts" / "verification" / "CharacterActionFoundationBaselineProbe.gd"


def read_active_callers() -> list[str]:
    callers: list[str] = []
    roots = [ROOT / "scenes", ROOT / "scripts", ROOT / "backend"]
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".gd", ".tscn", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "CharacterReplica" in text:
                callers.append(path.relative_to(ROOT).as_posix())
    return sorted(set(callers))


def test_baseline_doc_and_probe_define_required_evidence_fields() -> None:
    assert BASELINE.exists(), BASELINE
    assert PROBE.exists(), PROBE
    baseline = BASELINE.read_text(encoding="utf-8")
    probe = PROBE.read_text(encoding="utf-8")
    for field in ("actor_id", "source_kind", "state", "clip", "velocity_world", "position", "action_locked", "root_policy", "caller_path"):
        assert field in baseline
        assert field in probe
    for source_kind in ("player", "agent", "program", "perception", "interaction", "authority", "probe"):
        assert source_kind in baseline


def test_active_replica_callers_are_registered_in_baseline_matrix() -> None:
    baseline = BASELINE.read_text(encoding="utf-8")
    registered = set(re.findall(r"`([^`]+)`", baseline))
    missing = [caller for caller in read_active_callers() if caller not in registered]
    assert not missing, f"unregistered CharacterReplica callers: {missing}"


def test_only_character_motor_owns_move_and_slide() -> None:
    owners: list[str] = []
    excluded_legacy = {"scripts/street_combat/streetdemo.gd"}
    for path in (ROOT / "scripts").rglob("*.gd"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT).as_posix()
        if relative in excluded_legacy:
            continue
        if "move_and_slide(" in text:
            owners.append(relative)
    assert owners == ["scripts/character/CharacterMotor.gd"], owners


def test_street_skin_does_not_call_animation_playback_directly() -> None:
    skin = (ROOT / "scripts" / "street_combat" / "StreetCharacterSkin.gd").read_text(encoding="utf-8")
    assert re.search(r"\.(play|travel|seek)\s*\(", skin) is None

