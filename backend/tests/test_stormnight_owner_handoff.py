from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.scripted_mystery_owner_handoff import StormnightOwnerHandoffService
from app.gameplay.p5.scripted_mystery_case_runtime import CaseOpenIntent, ScriptedMysteryCaseAuthority
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition


def test_statement_and_evidence_handoff_writes_existing_owner_event_families() -> None:
    store = GameplayEventStore()
    service = StormnightOwnerHandoffService(store)
    statement = service.record_social_statement(case_ref="case:stormnight@1", statement_ref="statement:stormnight:01@1", speaker_ref="character:a@1", target_ref="character:b@1", mode="reveal", expected_revision=0, command_id="social-1", idempotency_key="social-1", causation_id="case", correlation_id="case")
    evidence = service.record_quest_evidence(case_ref="case:stormnight@1", clue_ref="clue:stormnight:01@1", discoverer_ref="character:a@1", expected_revision=0, command_id="quest-1", idempotency_key="quest-1", causation_id="case", correlation_id="case")
    assert statement.committed and evidence.committed
    assert [event.event_type for event in store.read_events()] == ["gameplay.social.knowledge_observed", "gameplay.quest.evidence_registered"]
    assert store.read_events()[0].payload["case_ref"] == "case:stormnight@1"


def test_handoff_changed_duplicate_is_zero_write() -> None:
    store = GameplayEventStore()
    service = StormnightOwnerHandoffService(store)
    first = service.record_quest_evidence(case_ref="case:stormnight@1", clue_ref="clue:stormnight:01@1", discoverer_ref="character:a@1", expected_revision=0, command_id="quest-1", idempotency_key="quest-1", causation_id="case", correlation_id="case")
    changed = service.record_quest_evidence(case_ref="case:stormnight@1", clue_ref="clue:stormnight:02@1", discoverer_ref="character:a@1", expected_revision=0, command_id="quest-2", idempotency_key="quest-1", causation_id="case", correlation_id="case")
    assert first.committed
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 1


def test_case_authority_routes_fixed_handoff_to_existing_owners() -> None:
    store = GameplayEventStore()
    case = ScriptedMysteryCaseAuthority.create(store)
    content = case.package.content
    assert case.open_case(CaseOpenIntent(case_ref=content.case_ref, case_revision=content.case_revision, command_id="open", idempotency_key="open", causation_id="case", correlation_id="case", submitted_at="now")).committed
    statement = content.statement_definitions[0]
    social, quest = case.handoff_statement_and_clue(
        handoff=StormnightOwnerHandoffService(store),
        statement_ref=statement.statement_ref,
        speaker_ref=statement.speaker_ref,
        target_ref=statement.target_ref,
        mode="reveal",
        clue_ref=content.clue_definitions[0].clue_ref,
        discoverer_ref=statement.speaker_ref,
        social_expected_revision=0,
        quest_expected_revision=0,
        command_id="handoff",
        idempotency_key="handoff",
        causation_id="case",
        correlation_id="case",
    )
    assert social.committed and quest.committed
    assert {event.event_type for event in store.read_events()} >= {"gameplay.social.knowledge_observed", "gameplay.quest.evidence_registered"}


def test_inventory_clue_custody_uses_existing_inventory_owner() -> None:
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:stormnight:clue@1", "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    actor = "character:stormnight-guardian@1"
    container_id = f"container:stormnight:{actor}:evidence"
    assert inventory.create_container(command_id="container", actor_ref=actor, spec=ContainerSpec(container_id, 10, 10, 10), idempotency_key="container", causation_id="case", correlation_id="case").committed
    result = StormnightOwnerHandoffService(store).record_inventory_clue_custody(inventory_authority=inventory, case_ref="case:stormnight@1", clue_ref="clue:stormnight:01@1", discoverer_ref=actor, container_id=container_id, command_id="custody", idempotency_key="custody", causation_id="case", correlation_id="case")
    assert result.committed
    assert any(event.event_type == "gameplay.inventory.item_instantiated" for event in store.read_events())
