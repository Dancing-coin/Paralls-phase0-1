from __future__ import annotations

from app.gameplay.p5.stormnight_scenario import StormnightScenarioRunner


def test_cross_owner_event_ledger_contains_case_social_quest_and_inventory_facts() -> None:
    runner = StormnightScenarioRunner()
    result = runner.run()
    assert result.case_opened and result.statement_committed and result.clue_committed and result.custody_committed
    types = {event.event_type for event in runner.store.read_events()}
    assert "gameplay.p5.mystery.case_opened@1" in types
    assert "gameplay.social.knowledge_observed" in types
    assert "gameplay.quest.evidence_registered" in types
    assert "gameplay.inventory.item_instantiated" in types

    first_hash = result.owner_replay_hash
    second = runner._owner_replay_hash()
    assert first_hash == second
