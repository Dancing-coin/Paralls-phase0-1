import importlib

import pytest
from pydantic import ValidationError

import app.config as config_module
import app.main as main
from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.siming_event import SimingInput


def _reload_settings():
    return importlib.reload(config_module).settings


def _destruction_input(correlation_id: str = "corr:destroy:1") -> SimingInput:
    return SimingInput(
        input_type="world_fact_event",
        source_event=AuthorityEvent(
            event_id="evt:destroy:1",
            event_type="world_fact_event",
            producer_ts=100,
            room_id="room:main",
            scene_id="scene:throne",
            zone_id="zone:archive",
            source=AuthorityEventSource(layer="l1", system="test"),
            routing=AuthorityEventRouting(
                audience_mode="room", routing_mode="broadcast"
            ),
            priority="p2",
            durability="replayable",
            causation_id="cause:destroy:1",
            correlation_id=correlation_id,
            payload={
                "target_ref": "obj_letter",
                "current_state": "removed_from_surface",
            },
        ),
    )


def test_active_mode_composes_shared_sqlite_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SIMING_HEAVENLY_MODE", "active")
    monkeypatch.setenv("PARALLS_HEAVENLY_GRAPH_PATH", str(tmp_path / "runtime.sqlite3"))

    state = main.build_runtime_state(_reload_settings())
    try:
        assert state.siming_runtime.heavenly_support.mode == "active"
        assert state.heavenly_graph is state.character_graph_memory.graph
    finally:
        state.close()


def test_off_mode_keeps_char_b_graph_memory_without_siming_support(tmp_path) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="off",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )

    state = main.build_runtime_state(settings)
    try:
        assert state.siming_runtime.heavenly_support is None
        assert state.character_graph_memory.graph is state.heavenly_graph
    finally:
        state.close()


def test_shadow_mode_marks_owned_family_advisory_and_support_cannot_publish(
    tmp_path,
) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="shadow",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )

    state = main.build_runtime_state(settings)
    try:
        support = state.siming_runtime.heavenly_support
        assert support.mode == "shadow"
        assert "evidence_destruction_consequence" in support.GRAPH_OWNED_EVENT_FAMILIES
        assert support.prepare(_destruction_input()).owns_event_family is False
        assert not hasattr(support, "tick")
        assert not hasattr(support, "publish")
        assert not hasattr(support, "write_actor_memory")
    finally:
        state.close()


def test_active_support_rejects_second_selection_for_one_correlation(tmp_path) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        prepared = state.siming_runtime.heavenly_support.prepare(_destruction_input())
        state.siming_runtime.heavenly_support.record_selection(
            prepared, "runtime:bridge:one"
        )

        with pytest.raises(ValueError, match="already selected"):
            state.siming_runtime.heavenly_support.record_selection(
                prepared, "runtime:bridge:two"
            )
    finally:
        state.close()


@pytest.mark.parametrize("mode", ["invalid", "ACTIVE"])
def test_heavenly_mode_rejects_unknown_values(monkeypatch, mode) -> None:
    monkeypatch.setenv("SIMING_HEAVENLY_MODE", mode)

    with pytest.raises(ValidationError):
        importlib.reload(config_module)
