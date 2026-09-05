from __future__ import annotations

from app.gameplay.p5.scripted_mystery_case_runtime import CaseProjection
from app.gameplay.p5.scripted_mystery_content import stormnight_case_content
from app.gameplay.p5.scripted_mystery_evidence import AccusationIntent, EvidenceDiscoveryIntent, ScriptedMysteryEvidenceAdapter, StatementIntent


def _context():
    content = stormnight_case_content()
    adapter = ScriptedMysteryEvidenceAdapter(content=content)
    actor = content.actor_refs[0]
    projection = CaseProjection(phase_ref="phase:stormnight:investigation@1", committed_clue_refs=(content.clue_definitions[0].clue_ref,), source_revision_vector={"gameplay:p5:mystery:stormnight": 1})
    return content, adapter, adapter.build_turn_context(projection, actor)


def test_turn_context_filters_private_knowledge_by_actor() -> None:
    content, adapter, first = _context()
    second = adapter.build_turn_context(CaseProjection(), content.actor_refs[1])
    assert first.private_fact_refs != second.private_fact_refs
    assert first.recipient_ref != second.recipient_ref


def test_statement_and_discovery_reject_private_or_wrong_subject() -> None:
    content, adapter, context = _context()
    statement = content.statement_definitions[0]
    assert adapter.validate_statement(StatementIntent(statement_ref=statement.statement_ref, speaker_ref=context.recipient_ref, target_ref=statement.target_ref, mode="reveal", expected_case_revision=1, command_id="statement"), context) is None
    assert adapter.validate_statement(StatementIntent(statement_ref=statement.statement_ref, speaker_ref=content.actor_refs[1], target_ref=statement.target_ref, mode="reveal", expected_case_revision=1, command_id="statement"), context) == "stormnight_statement_unadmitted"
    assert adapter.validate_discovery(EvidenceDiscoveryIntent(clue_ref=content.clue_definitions[0].clue_ref, discoverer_ref=context.recipient_ref, expected_case_revision=1, collect_to_custody=True, command_id="discover"), context) is None


def test_accusation_requires_canonical_visible_evidence() -> None:
    content, adapter, context = _context()
    two = tuple(sorted((context.public_fact_refs[1], context.visible_clue_refs[0])))
    valid = AccusationIntent(accuser_ref=context.recipient_ref, target_ref=content.actor_refs[1], evidence_refs=two, expected_case_revision=1, command_id="accuse")
    assert adapter.validate_accusation(valid, context) is None
    missing = valid.model_copy(update={"evidence_refs": ("clue:secret@1",)})
    assert adapter.validate_accusation(missing, context) == "stormnight_accusation_evidence_private_or_missing"
