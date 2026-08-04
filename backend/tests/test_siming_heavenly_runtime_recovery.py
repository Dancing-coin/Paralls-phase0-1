import pytest

import app.config as config_module
import app.main as main
from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.siming_event import SimingInput


def _event(event_type: str) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"event:{event_type}",
        event_type=event_type,
        producer_ts=100,
        room_id="room:main",
        scene_id="scene:throne",
        zone_id="zone:archive",
        source=AuthorityEventSource(layer="L1", system="test"),
        routing=AuthorityEventRouting(
            audience_mode="broadcast", routing_mode="event_type"
        ),
        priority="p2",
        durability="replayable",
        causation_id="cause:destroy:1",
        correlation_id="corr:destroy:1",
        payload={
            "target_ref": "obj_letter",
            "current_state": "removed_from_surface",
        },
    )


@pytest.mark.parametrize(
    ("state", "expected_dispatch_record"),
    [
        ("unsent", False),
        ("sent_unconfirmed", True),
        ("authority_confirmed", True),
    ],
)
def test_dispatch_ledger_survives_sqlite_restart(
    tmp_path, state: str, expected_dispatch_record: bool
) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="active",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )
    destruction = _event("world_fact_event")
    first_state = main.build_runtime_state(settings)
    try:
        support = first_state.siming_runtime.heavenly_support
        prepared = support.prepare(
            SimingInput(input_type="world_fact_event", source_event=destruction)
        )
        support.record_selection(prepared, "runtime:bridge:proposal:destroy:1")
        if state != "unsent":
            support.record_dispatch(
                correlation_id=destruction.correlation_id,
                dispatch_event_id="siming:dispatch:destroy:1",
            )
        if state == "authority_confirmed":
            support.record_authority_outcome(_event("esm_result_event"))
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        support = second_state.siming_runtime.heavenly_support
        assert (
            support.has_dispatch(_event("siming_staging_ack"))
            is expected_dispatch_record
        )
    finally:
        second_state.close()
