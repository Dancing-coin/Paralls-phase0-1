from __future__ import annotations

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.stormnight_realtime_session import (
    PLAYER_REF,
    StormnightPlayerIntent,
    StormnightRealtimeSessionService,
)


def _service() -> StormnightRealtimeSessionService:
    return StormnightRealtimeSessionService(store=GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry()))


def _intent(kind: str, request_id: str, **values: object) -> StormnightPlayerIntent:
    return StormnightPlayerIntent(kind=kind, request_id=request_id, **values)


def test_player_can_start_inspect_advance_question_and_accuse_through_owner_bound_session() -> None:
    service = _service()
    started = service.handle(_intent("start", "start"))
    assert started.accepted and started.projection["opened"] is True
    inspected = service.handle(_intent("inspect", "inspect"))
    assert inspected.accepted and inspected.projection["committed_clue_refs"]
    advanced = service.handle(_intent("advance", "advance"))
    assert advanced.accepted and advanced.projection["phase_ref"] == "phase:stormnight:investigation@1"
    questioned = service.handle(_intent("question", "question", target_ref="character:stormnight-guardian@1"))
    assert questioned.accepted and questioned.projection["statement_refs"]
    accused = service.handle(_intent("accuse", "accuse", target_ref="character:stormnight-guardian@1"))
    assert accused.accepted and accused.projection["terminal_outcome"] == "case_solved"


def test_player_action_is_server_mapped_and_returns_npc_proposal() -> None:
    service = _service()
    assert service.handle(_intent("start", "start")).accepted
    result = service.handle(_intent("pursue", "pursue"))
    assert result.accepted
    assert result.projection["action_window_count"] == 1
    assert result.npc_proposal is not None
    assert "event_specs" not in result.npc_proposal


def test_unauthorized_coordinates_and_invalid_order_are_zero_write() -> None:
    service = _service()
    before = len(service.store.read_events())
    impersonation = service.handle(_intent("start", "bad-actor", actor_ref="character:stormnight-guardian@1"))
    assert not impersonation.accepted and impersonation.error_code == "stormnight_player_actor_forbidden"
    assert len(service.store.read_events()) == before
    invalid_order = service.handle(_intent("advance", "advance-before-start"))
    assert not invalid_order.accepted and invalid_order.error_code == "case_not_open"
    assert len(service.store.read_events()) == before


def test_exact_duplicate_replays_but_changed_duplicate_rejects_zero_write() -> None:
    service = _service()
    first = service.handle(_intent("start", "same"))
    duplicate = service.handle(_intent("start", "same"))
    before = len(service.store.read_events())
    changed = service.handle(_intent("inspect", "same"))
    assert first.accepted and duplicate.accepted and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.accepted and changed.error_code == "stormnight_player_idempotency_reused"
    assert len(service.store.read_events()) == before


def test_response_only_exposes_player_visible_context() -> None:
    service = _service()
    response = service.handle(_intent("start", "start"))
    assert response.accepted
    assert response.player_ref == PLAYER_REF
    assert "private_knowledge_by_actor" not in response.projection
    assert set(response.projection["player_private_fact_refs"]).issubset(set(response.projection["player_visible_fact_refs"]))
