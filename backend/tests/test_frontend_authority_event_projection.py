import pytest

from app.models.authority_event import AuthorityEvent
from app.services.frontend_authority_event_projection import (
    FRONTEND_AUTHORITY_EVENT_TYPES,
    FrontendAuthorityEventProjector,
    project_authority_event_for_frontend,
)
from tests.test_authority_event import valid_event_dict


def make_event(event_type: str, payload: dict[str, object] | None = None) -> AuthorityEvent:
    data = valid_event_dict()
    data["event_id"] = f"evt_{event_type.replace('.', '_')}"
    data["event_type"] = event_type
    data["payload"] = payload or {
        "established_fact_id": "visual_fact:300:char_c:light_level_drop",
        "presentation_hint": "increase observability for established light change",
    }
    return AuthorityEvent.model_validate(data)


def test_projector_whitelists_visual_observability_request() -> None:
    envelope = project_authority_event_for_frontend(make_event("siming.visual_observability_request"))

    assert envelope is not None
    assert envelope["message_type"] == "authority_event"
    payload = envelope["payload"]
    assert payload["event_type"] == "siming.visual_observability_request"
    assert payload["event_id"] == "evt_siming_visual_observability_request"
    assert payload["causation_id"] == "visual_fact:100"
    assert payload["correlation_id"] == "visual_fact:100"
    assert payload["durability"] == "replayable"
    assert payload["payload"]["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"


@pytest.mark.parametrize("event_type", ["siming.audit_recorded", "siming.fairness_snapshot", "visual_fact_event"])
def test_projector_rejects_non_frontend_event_families(event_type: str) -> None:
    assert project_authority_event_for_frontend(make_event(event_type)) is None


def test_projector_buffers_and_drains_projected_events() -> None:
    projector = FrontendAuthorityEventProjector()

    projector.handle_event(make_event("siming.visual_observability_request"))
    projector.handle_event(make_event("siming.audit_recorded"))

    drained = projector.drain()
    assert [message["payload"]["event_type"] for message in drained] == ["siming.visual_observability_request"]
    assert projector.drain() == []


def test_projector_can_clear_stale_pending_events() -> None:
    projector = FrontendAuthorityEventProjector()
    projector.handle_event(make_event("siming.visual_observability_request"))

    projector.clear()

    assert projector.drain() == []
    assert "siming.visual_observability_request" in FRONTEND_AUTHORITY_EVENT_TYPES
