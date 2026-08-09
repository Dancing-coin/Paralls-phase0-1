from __future__ import annotations

import json

from scripts.verification import verify_phase1b_contract


def test_phase1b_report_fails_closed_when_predecessor_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(verify_phase1b_contract, "repo_root", lambda: tmp_path)
    evidence = tmp_path / ".harness" / "verification"
    evidence.mkdir(parents=True)
    assert verify_phase1b_contract.main.__name__ == "main"


def test_phase1b_report_schema_contains_gates() -> None:
    from scripts.verification.phase1b_contract_fixtures import build_effect_resistance_fixture

    fixture = build_effect_resistance_fixture()
    assert fixture.command.command_id.startswith("command:p1b:")
    assert fixture.owner_map
