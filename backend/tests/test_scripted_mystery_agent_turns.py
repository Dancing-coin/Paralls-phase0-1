from __future__ import annotations

from app.gameplay.p5.scripted_mystery_content import stormnight_case_content
from app.gameplay.p5.scripted_mystery_evidence import CaseProjection, ScriptedMysteryEvidenceAdapter
from app.services.scripted_mystery_agent_turns import ScriptedMysteryAgentTurnService
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


def test_investigator_and_guardian_emit_typed_proposals_from_filtered_context() -> None:
    content = stormnight_case_content()
    adapter = ScriptedMysteryEvidenceAdapter(content=content)
    context = adapter.build_turn_context(CaseProjection(committed_clue_refs=(content.clue_definitions[0].clue_ref,)), content.actor_refs[0])
    service = ScriptedMysteryAgentTurnService()
    investigator = service.propose_turn(context, case_ref=content.case_ref, turn_id="turn:1", policy="investigator")
    guardian = service.propose_turn(context, case_ref=content.case_ref, turn_id="turn:2", policy="guardian")
    assert investigator.accepted and investigator.proposal is not None
    assert investigator.proposal.proposal_kind == "investigate"
    assert guardian.accepted and guardian.proposal is not None
    assert guardian.proposal.proposal_kind == "pursue"


def test_agent_proposal_cannot_carry_canonical_truth_or_event_vector() -> None:
    content = stormnight_case_content()
    context = ScriptedMysteryEvidenceAdapter(content=content).build_turn_context(CaseProjection(), content.actor_refs[0])
    result = ScriptedMysteryAgentTurnService().propose_turn(context, case_ref=content.case_ref, turn_id="turn:truth", policy="investigator")
    assert result.accepted
    dumped = result.proposal.model_dump() if result.proposal else {}
    assert "event_specs" not in dumped
    assert "truth" not in dumped


def test_existing_character_runtime_can_feed_a_noncanonical_case_turn() -> None:
    content = stormnight_case_content()
    actor = content.actor_refs[0]
    adapter = ScriptedMysteryEvidenceAdapter(content=content)
    context = adapter.build_turn_context(CaseProjection(), actor)
    event = CharacterPerceivedEvent(actor_id=actor, percept_channel="visual", producer_ts=1, room_id="stormnight", scene_id="stormnight", zone_id="arrival", perceived_summary="A copper latch catches the light.", source_candidate_event_id="source:stormnight:perception@1")
    decision = ScriptedMysteryAgentTurnService().propose_turn_from_character_runtime(CharacterAgentRuntime(), event, context=context, case_ref=content.case_ref, turn_id="turn:runtime", policy="investigator")
    assert decision.accepted and decision.proposal is not None
    assert decision.proposal.owner_route in {"quest", "social"}
