from __future__ import annotations

from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority
from app.gameplay.p5.scripted_mystery_content import stormnight_case_content
from app.gameplay.p5.scripted_mystery_evidence import AccusationIntent, EvidenceDiscoveryIntent, ScriptedMysteryEvidenceAdapter
from app.services.scripted_mystery_agent_turns import ScriptedMysteryAgentTurnService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from test_action_conflict_window import _command as action_command, _graph as action_graph, _intent as action_intent, _snapshot as action_snapshot, _registry as action_registry, _seed_source
from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent
from app.gameplay.p5.scripted_mystery_content import stormnight_case_content


def test_stormnight_turn_to_action_and_evidence_is_owner_bound() -> None:
    store = GameplayEventStore()
    case = ScriptedMysteryCaseAuthority.create(store)
    opened = case.open_case(CaseOpenIntent(case_ref=case.package.content.case_ref, case_revision=case.package.content.case_revision, command_id="open", idempotency_key="open", causation_id="cause", correlation_id="corr", submitted_at="now"))
    assert opened.committed
    content = stormnight_case_content()
    evidence = ScriptedMysteryEvidenceAdapter(content=content)
    context = evidence.build_turn_context(case.project(), content.actor_refs[0])
    proposal = ScriptedMysteryAgentTurnService().propose_turn(context, case_ref=content.case_ref, turn_id="turn:1", policy="investigator")
    assert proposal.accepted and proposal.proposal is not None
    assert proposal.proposal.owner_route in {"quest", "social"}
    discovery = EvidenceDiscoveryIntent(clue_ref=content.clue_definitions[0].clue_ref, discoverer_ref=context.recipient_ref, expected_case_revision=1, collect_to_custody=True, command_id="discover")
    assert evidence.validate_discovery(discovery, context) is None
    accusation = AccusationIntent(accuser_ref=context.recipient_ref, target_ref=content.actor_refs[1], evidence_refs=tuple(sorted((context.public_fact_refs[1], context.private_fact_refs[0]))), expected_case_revision=1, command_id="accuse")
    assert evidence.validate_accusation(accusation, context) is None
    assert all(not event.event_type.startswith("gameplay.inventory") for event in store.read_events())


def test_invalid_action_loop_inputs_are_zero_write_at_boundary() -> None:
    content = stormnight_case_content()
    evidence = ScriptedMysteryEvidenceAdapter(content=content)
    context = evidence.build_turn_context(case_projection=__import__("app.gameplay.p5.scripted_mystery_case_runtime", fromlist=["CaseProjection"]).CaseProjection(), recipient_ref=content.actor_refs[0])
    invalid = EvidenceDiscoveryIntent(clue_ref="clue:unknown@1", discoverer_ref=context.recipient_ref, expected_case_revision=0, collect_to_custody=True, command_id="invalid")
    assert evidence.validate_discovery(invalid, context) == "stormnight_clue_unadmitted"


def test_case_open_then_existing_p5_action_window_commits_on_same_store() -> None:
    store = GameplayEventStore()
    case = ScriptedMysteryCaseAuthority.create(store)
    content = stormnight_case_content()
    assert case.open_case(CaseOpenIntent(case_ref=content.case_ref, case_revision=content.case_revision, command_id="case-open", idempotency_key="case-open", causation_id="case", correlation_id="case", submitted_at="now")).committed
    _seed_source(store)
    result = InvestigationConflictAuthority(registry=action_registry(), store=store).resolve_action_window(command=action_command(), intent=action_intent(), graph=action_graph(), spatial_snapshot=action_snapshot(), role_ref="role:survivor@1", now="now")
    assert result.committed
    assert len([event for event in store.read_events() if event.event_type == "gameplay.conflict.action_window_resolved"]) == 1
