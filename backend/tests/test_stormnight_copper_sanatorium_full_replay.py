from __future__ import annotations

from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.p5.scripted_mystery_evidence import ScriptedMysteryEvidenceAdapter
from app.gameplay.models import ProjectionCheckpoint
from app.gameplay.p5.scripted_mystery_case_package import load_stormnight_case_package
from app.gameplay.event_store import GameplayEventStore
import pytest


def test_all_four_terminal_outcomes_are_package_admitted() -> None:
    package = load_stormnight_case_package()
    assert {item.outcome_kind for item in package.content.outcome_definitions} == {"case_solved", "false_accusation", "culprit_escaped", "investigator_captured"}


def test_case_full_replay_rejects_tampered_package_pin() -> None:
    authority = ScriptedMysteryCaseAuthority.create(GameplayEventStore())
    result = authority.open_case(CaseOpenIntent(case_ref=authority.package.content.case_ref, case_revision=authority.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now"))
    assert result.committed
    checkpoint = authority.create_checkpoint(authority.store.read_events())
    checkpoint = checkpoint.model_copy(update={"projection_hash": "sha256:" + "f" * 64}, deep=True)
    result = authority.replay_checkpoint_tail(checkpoint)
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "case_checkpoint_mismatch"


def test_four_outcome_fixtures_are_replayable_with_statement_and_accusation() -> None:
    package = load_stormnight_case_package()
    for index, outcome_kind in enumerate(("case_solved", "false_accusation", "culprit_escaped", "investigator_captured")):
        store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
        authority = ScriptedMysteryCaseAuthority.create(store, package)
        actor = package.content.actor_refs[0]
        opened = authority.open_case(CaseOpenIntent(case_ref=package.content.case_ref, case_revision=package.content.case_revision, command_id=f"open-{index}", idempotency_key=f"open-{index}", causation_id=f"cause-{index}", correlation_id=f"corr-{index}", submitted_at="now"))
        assert opened.committed
        statement = package.content.statement_definitions[0]
        assert authority.record_statement(statement_ref=statement.statement_ref, speaker_ref=statement.speaker_ref, target_ref=statement.target_ref, mode=statement.allowed_modes[0], command_id=f"statement-{index}", idempotency_key=f"statement-{index}", expected_revision=1, causation_id=f"cause-{index}", correlation_id=f"corr-{index}").committed
        context = ScriptedMysteryEvidenceAdapter(content=package.content).build_turn_context(authority.project(), actor)
        evidence = tuple(sorted((context.public_fact_refs[1], context.private_fact_refs[0])))
        assert authority.submit_accusation(accuser_ref=actor, target_ref=package.content.actor_refs[1], evidence_refs=evidence, command_id=f"accuse-{index}", idempotency_key=f"accuse-{index}", expected_revision=2, causation_id=f"cause-{index}", correlation_id=f"corr-{index}").committed
        resolved = authority.resolve_outcome(command_id=f"outcome-{index}", idempotency_key=f"outcome-{index}", outcome_kind=outcome_kind, expected_revision=3, causation_id=f"cause-{index}", correlation_id=f"corr-{index}")
        assert resolved.committed
        full = authority.replay_full()
        assert full.succeeded and full.state["terminal_outcome"] == outcome_kind
