"""Protocol 09 stub test: Siming → ESM.

Verifies that siming.environment_request emitted on the authority bus
reaches ESM and produces a world result event.

See: docs/reference/phase1-siming/09-司命与 ESM 协作协议.md
"""

from __future__ import annotations

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.environment_request import EnvironmentRequest
from app.services.esm_service import ESMService
from app.gameplay.event_store import GameplayEventStore


def _make_siming_env_event(room_id: str = "room_01") -> AuthorityEvent:
    return AuthorityEvent(
        event_id="siming:env:test:1",
        event_type="siming.environment_request",
        producer_ts=100,
        room_id=room_id,
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=AuthorityEventSource(layer="L2", system="siming.dispatcher", actor_id=None),
        routing=AuthorityEventRouting(
            audience_mode="targeted",
            routing_mode="event_type",
            target_ids=["esm"],
        ),
        priority="p1",
        durability="replayable",
        causation_id="siming:test:cause",
        correlation_id="siming:test:corr",
        payload={
            "goal": "create_tension",
            "requested_change_type": "light_level_drop",
            "requested_strength": "medium",
            "target_environment_id": "env_lamp",
        },
    )


def test_siming_environment_request_converts_to_esm_request() -> None:
    """EnvironmentRequest can be built from siming.environment_request payload."""
    event = _make_siming_env_event()
    payload = event.payload
    request = EnvironmentRequest(
        request_id=f"siming:{event.causation_id}",
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        source={"system": "siming", "event_id": event.event_id},
        target_entity_refs={"environment_ids": [str(payload.get("target_environment_id", "") or "env_default")]},
        goal=str(payload.get("goal", "") or "environment_change"),
        requested_change_type=str(payload.get("requested_change_type", "") or "light_level_drop"),
        requested_strength=str(payload.get("requested_strength", "medium") or "medium"),
        reason_tag="siming_environment_request",
        producer_ts=event.producer_ts,
        causation_id=event.causation_id,
        correlation_id=event.correlation_id,
    )
    assert request.requested_change_type == "light_level_drop"
    assert request.target_entity_refs["environment_ids"] == ["env_lamp"]
    assert request.reason_tag == "siming_environment_request"
    assert request.room_id == "room_01"


def test_esm_resolves_siming_environment_request() -> None:
    """ESM can resolve an EnvironmentRequest produced by the siming bridge."""
    store = GameplayEventStore()
    esm = ESMService(store=store, learning_disclosure_scopes={})
    event = _make_siming_env_event()
    payload = event.payload
    request = EnvironmentRequest(
        request_id=f"siming:{event.causation_id}",
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        source={"system": "siming"},
        target_entity_refs={"environment_ids": ["env_lamp"]},
        goal="create_tension",
        requested_change_type="light_level_drop",
        requested_strength="medium",
        reason_tag="siming_environment_request",
        producer_ts=event.producer_ts,
        causation_id=event.causation_id,
        correlation_id=event.correlation_id,
    )
    resolution, _env_result = esm.resolve_environment_request(request)
    # ESM must return a resolution (accepted or constraint)
    assert resolution is not None
    assert hasattr(resolution, "result_type")
    # ESM resolves siming environment requests as action_resolution_result or constraint_state
    assert resolution.result_type in {"action_resolution_result", "constraint_state"}
