from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingInput
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import (
    PopulationBatchReport,
    PopulationCadenceInput,
    PopulationCycleResult,
    PopulationOwnerReceipt,
    PopulationProjection,
    PopulationReadSet,
)
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services.siming_runtime import SimingRuntime


def _cadence(**updates: object) -> PopulationCadenceInput:
    values: dict[str, object] = {
        "cadence_id": "cadence:production:1",
        "world_ref": "world:bakery",
        "world_mode_ref": "world-mode:bakery",
        "world_mode_revision": "mode:v1",
        "cadence_source_ref": "world:bakery",
        "cadence_source_revision": 1,
        "window_start": 100,
        "window_end": 101,
        "base_checkpoint_ref": "checkpoint:production:1",
        "base_checkpoint_digest": "sha256:checkpoint",
        "base_revision_vector": {"world:bakery": 1},
        "policy_revision": "policy:population:v1",
        "selector_revision": "selector:population:v1",
        "ruleset_revision": "rules:population:v1",
        "deterministic_seed": "seed:production:1",
        "catch_up_limit": 2,
        "budget": 2,
        "report_scope": "organization:summary",
    }
    values.update(updates)
    return PopulationCadenceInput(**values)


def _event(cadence: PopulationCadenceInput | None = None) -> AuthorityEvent:
    return AuthorityEvent(
        event_id="event:population:production",
        event_type="population_cadence_event",
        producer_ts=100,
        room_id="room:bakery",
        scene_id="scene:bakery",
        zone_id="zone:bakery",
        source=AuthorityEventSource(layer="L2", system="world_runtime.cadence"),
        routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type"),
        priority="p2",
        durability="replayable",
        causation_id="game-start:bakery",
        correlation_id="population:bakery:game-start",
        payload={"population_cadence": (cadence or _cadence()).model_dump(mode="json")},
    )


def _supply_read_set(cadence: PopulationCadenceInput, *, ref: str = "supply") -> PopulationReadSet:
    projection = PopulationProjection(
        ref=ref,
        scope="organization:summary",
        revision_vector=dict(cadence.base_revision_vector),
        payload={
            "actor_ref": "character:char_a",
            "candidate_kind": "schedule_gated_supply",
            "state_deltas": {"task": "restock"},
            "source_event_refs": ("event:supply:projection",),
            "exposure_basis": "affected_directly",
        },
    )
    return PopulationReadSet.from_inputs(cadence, (projection,))


def test_production_population_capability_uses_the_built_character_runtime(tmp_path: Path) -> None:
    import app.main as main

    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / "runtime.sqlite3")))
    try:
        capability = state.siming_runtime._population_capability
        assert capability is not None
        assert capability._continuity_port is not None
        assert capability._continuity_port.runtime is state.character_agent_runtime
    finally:
        state.close()


def test_reset_publishes_one_game_start_population_cadence() -> None:
    import app.main as main

    main.reset_runtime_state()
    events = main.authority_event_bus.list_events(
        event_type="population_cadence_event",
        include_realtime=True,
        current_only=False,
    )
    assert len(events) == 1
    assert events[0].source.system == "world_runtime.cadence"


def test_owner_settlement_required_seed_stays_pending_and_never_reaches_character_core() -> None:
    class RecordingContinuity:
        def __init__(self) -> None:
            self.commands: list[object] = []

        def apply_command(self, command):
            self.commands.append(command)
            raise AssertionError("owner-settlement-required seed must not reach Character Core")

        def current_revision(self, actor_ref: str) -> int:
            return 0

    continuity = RecordingContinuity()
    result = PopulationSimulationCapability(continuity_port=continuity).run_cycle(
        _cadence(), _supply_read_set(_cadence())
    )
    assert result.status == "owner_settlement_required"
    assert result.seed_candidates[0].owner_effect_status == "owner_settlement_required"
    assert result.continuity_receipts == ()
    assert continuity.commands == []


def test_continuity_command_uses_current_actor_revision_for_the_next_window() -> None:
    class RecordingOwner:
        def __init__(self) -> None:
            self.calls = 0

        def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
            self.calls += 1
            return PopulationOwnerReceipt(
                receipt_ref=f"receipt:{self.calls}",
                owner_ref="owner:organization",
                event_family="gameplay.organization.commerce_commitment_accepted",
                committed=True,
                revision_vector={"world:bakery": self.calls + 1},
                zero_write=False,
            )

    class RecordingContinuity:
        def __init__(self) -> None:
            self.revision = 0
            self.expected: list[int] = []

        def current_revision(self, actor_ref: str) -> int:
            return self.revision

        def apply_command(self, command):
            self.expected.append(command.expected_character_revision)
            self.revision += 1
            return type(
                "Receipt",
                (),
                {"status": "committed", "command_id": command.command_id},
            )()

    owner = RecordingOwner()
    continuity = RecordingContinuity()
    capability = PopulationSimulationCapability(owner_executor=owner, continuity_port=continuity)
    first_cadence = _cadence()
    second_cadence = _cadence(
        cadence_id="cadence:production:2",
        window_start=101,
        window_end=102,
        deterministic_seed="seed:production:2",
    )
    first = capability.run_cycle(first_cadence, _supply_read_set(first_cadence))
    second = capability.run_cycle(second_cadence, _supply_read_set(second_cadence, ref="supply:2"))
    assert first.status == "accepted"
    assert second.status == "accepted"
    assert continuity.expected == [0, 1]


def test_missing_continuity_revision_reader_requeues_before_owner_execution() -> None:
    class RecordingOwner:
        def __init__(self) -> None:
            self.calls = 0

        def submit(self, intent, *, read_set):
            self.calls += 1
            raise AssertionError("owner must not execute without a revision reader")

    class ApplyOnlyContinuity:
        def apply_command(self, command):
            raise AssertionError("continuity command must not be built")

    owner = RecordingOwner()
    result = PopulationSimulationCapability(
        owner_executor=owner, continuity_port=ApplyOnlyContinuity()
    ).run_cycle(
        _cadence(), _supply_read_set(_cadence())
    )
    assert result.status == "requeue"
    assert result.reason == "continuity_revision_reader_missing"
    assert owner.calls == 0


@pytest.mark.parametrize("scope", ["branch:preview", "private:memory", "actor:char_b"])
def test_non_mainline_or_cross_actor_scope_is_rejected_before_character_continuity(scope: str) -> None:
    class RecordingContinuity:
        def __init__(self) -> None:
            self.commands = []

        def apply_command(self, command):
            self.commands.append(command)
            raise AssertionError("scope-invalid projection reached Character Core")

    cadence = _cadence()
    projection = PopulationProjection(
        ref="supply:invalid-scope",
        scope=scope,
        revision_vector=dict(cadence.base_revision_vector),
        payload={"actor_ref": "character:char_a", "candidate_kind": "schedule_gated_supply"},
    )
    continuity = RecordingContinuity()
    result = PopulationSimulationCapability(continuity_port=continuity).run_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, (projection,))
    )
    assert result.status == "requeue"
    assert result.reason in {"stale_read_set", "projection_scope_denied"}
    assert continuity.commands == []


def test_branch_payload_is_rejected_even_when_projection_scope_is_public() -> None:
    cadence = _cadence()
    projection = PopulationProjection(
        ref="supply:branch-payload",
        scope="organization:summary",
        revision_vector=dict(cadence.base_revision_vector),
        payload={
            "actor_ref": "character:char_a",
            "candidate_kind": "schedule_gated_supply",
            "story_branch_id": "branch:preview",
        },
    )
    result = PopulationSimulationCapability().run_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, (projection,))
    )
    assert result.status == "requeue"
    assert result.reason == "projection_scope_denied"


@pytest.mark.parametrize("report_scope", ["branch:preview", "private:memory"])
def test_forbidden_cadence_report_scope_is_rejected_before_planning(report_scope: str) -> None:
    cadence = _cadence(report_scope=report_scope)
    result = PopulationSimulationCapability().run_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, ())
    )
    assert result.status == "requeue"
    assert result.reason == "projection_scope_denied"
    assert result.production_append_count == 0


@pytest.mark.parametrize(
    "payload_marker",
    [
        {"privacy_disposition": "private"},
        {"privacy_scope": "private:memory"},
        {"actor_ref": "character:char_b", "actor_scope": "actor:char_a"},
        {"branch_id": "branch:preview"},
    ],
)
def test_forbidden_projection_payload_markers_are_rejected_before_continuity(
    payload_marker: dict[str, object],
) -> None:
    cadence = _cadence()
    projection = PopulationProjection(
        ref="supply:forbidden-marker",
        scope="public",
        revision_vector=dict(cadence.base_revision_vector),
        payload={
            "actor_ref": "character:char_a",
            "candidate_kind": "schedule_gated_supply",
            **payload_marker,
        },
    )
    result = PopulationSimulationCapability().run_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, (projection,))
    )
    assert result.status == "requeue"
    assert result.reason == "projection_scope_denied"
    assert result.production_append_count == 0


def test_production_startup_cadence_contains_real_schedule_seed_and_owner_path() -> None:
    import app.main as main

    main.reset_runtime_state()
    cadence_events = main.authority_event_bus.list_events(
        event_type="population_cadence_event", include_realtime=True, current_only=False
    )
    assert len(cadence_events) == 1
    event = cadence_events[0]
    projections = event.payload["population_projections"]
    assert any(
        item.get("payload", {}).get("candidate_kind") == "schedule_gated_supply"
        for item in projections
    )
    cycle_audit = next(
        audit
        for audit in main.siming_audit_writer.find_by_correlation(
            room_id=event.room_id, correlation_id=event.correlation_id
        )
        if audit.reason.startswith("population_cycle")
    )
    assert "seeds=1" in cycle_audit.reason
    assert "owners=1" in cycle_audit.reason
    assert main.character_agent_runtime.get_seed_projection("char_a")
    assert any(
        stored.event_type == "gameplay.organization.commerce_commitment_accepted"
        for stored in main.gameplay_event_store.read_events()
    )


def test_dialogue_activation_failure_short_circuits_cognition(monkeypatch) -> None:
    import app.main as main
    from app.models.player_input import DialogueSubmit
    from app.population_continuity.models import ActivationReceipt

    main.reset_runtime_state()
    cognition_calls: list[object] = []
    monkeypatch.setattr(
        main.character_agent_runtime,
        "activate_actor",
        lambda *args, **kwargs: ActivationReceipt(
            committed=False,
            status="requeued",
            profile_ref="character:char_a",
            zero_write=True,
            stop_reason="activation_lock_conflict",
        ),
    )
    monkeypatch.setattr(
        main.character_agent_runtime,
        "ingest_character_perceived_event",
        lambda event: cognition_calls.append(event) or [],
    )
    event = DialogueSubmit(
        player_id="player:1",
        room_id="room:bakery",
        scene_id="scene:bakery",
        zone_id="zone:bakery",
        actor_id="char_c",
        producer_ts=101,
        request_id="request:activation-conflict",
        target_actor_id="char_a",
        content="hello",
    )
    messages = main._handle_envelope(
        __import__("app.ws_protocol", fromlist=["Envelope"]).Envelope(
            message_type="player_input", payload=event.model_dump()
        )
    )
    assert cognition_calls == []
    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["route"] == "character_activation"


def test_stream_fallback_cognition_is_executed_inside_activation_lock(monkeypatch) -> None:
    import app.main as main
    from app.models.player_input import DialogueSubmit

    main.reset_runtime_state()
    event = DialogueSubmit(
        player_id="player:1",
        room_id="room:bakery",
        scene_id="scene:bakery",
        zone_id="zone:bakery",
        actor_id="char_c",
        producer_ts=101,
        request_id="request:stream-fallback",
        target_actor_id="char_a",
        content="hello",
    )
    observed: list[bool] = []

    def stream_dialogue(_event, *, cancelled):
        observed.append(
            main.character_agent_runtime._activation_authority.is_lock_active(
                world_ref=main.character_agent_runtime._activation_world_ref,
                profile_ref="character:char_a",
            )
        )
        yield {"event": "completed", "response": object(), "fallback_used": True}

    monkeypatch.setattr(main, "_dialogue_direct_content", lambda _event: "")
    monkeypatch.setattr(main.character_service, "stream_dialogue", stream_dialogue)
    events = main._stream_dialogue_with_activation(event, lambda: False)
    assert events
    assert observed == [True]


def test_interact_without_character_cognition_is_not_reported_as_active() -> None:
    import app.main as main
    from app.models.player_input import InteractIntent

    main.reset_runtime_state()
    decisions: list[object] = []
    original = main.activation_policy.evaluate

    def evaluate(**kwargs):
        decision = original(**kwargs)
        decisions.append(decision)
        return decision

    main.activation_policy.evaluate = evaluate
    main._activate_character_for_player_input(
        InteractIntent(
            player_id="player:1",
            room_id="room:bakery",
            scene_id="scene:bakery",
            zone_id="zone:bakery",
            actor_id="char_c",
            producer_ts=101,
            target_object_id="character:char_a",
            interaction_type="consequential",
        )
    )
    assert decisions[0].state == "activation_candidate"


def test_activation_cognition_callback_runs_while_public_activation_lock_is_held() -> None:
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
    from app.gameplay.event_store import GameplayEventStore
    from app.population_continuity.activation import ProfileActivationAuthority
    from app.population_continuity.models import ActivationDecision

    runtime = CharacterAgentRuntime()
    runtime.set_activation_authority(
        ProfileActivationAuthority(registry=runtime._profile_registry, store=GameplayEventStore())
    )
    seen: list[bool] = []

    receipt = runtime.activate_actor(
        "char_a",
        ActivationDecision(
            actor_id="char_a",
            state="active",
            reason="player_dialogue",
            requires_activation_lock=True,
            load_private_memory=True,
            policy_revision="policy:activation:v1",
        ),
        producer_ts=101,
        cognition_callback=lambda: seen.append(
            runtime._activation_authority.is_lock_active(
                world_ref=runtime._activation_world_ref,
                profile_ref="character:char_a",
            )
        ),
    )
    assert receipt.status == "active"
    assert seen == [True]
    assert runtime._activation_authority.is_lock_active(
        world_ref=runtime._activation_world_ref,
        profile_ref="character:char_a",
    ) is False


def test_activation_cognition_failure_releases_public_activation_lock() -> None:
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
    from app.gameplay.event_store import GameplayEventStore
    from app.population_continuity.activation import ProfileActivationAuthority
    from app.population_continuity.models import ActivationDecision

    runtime = CharacterAgentRuntime()
    authority = ProfileActivationAuthority(
        registry=runtime._profile_registry, store=GameplayEventStore()
    )
    runtime.set_activation_authority(authority)
    with pytest.raises(RuntimeError, match="cognition failed"):
        runtime.activate_actor(
            "char_a",
            ActivationDecision(
                actor_id="char_a",
                state="active",
                reason="player_dialogue",
                requires_activation_lock=True,
                load_private_memory=True,
                policy_revision="policy:activation:v1",
            ),
            producer_ts=101,
            cognition_callback=lambda: (_ for _ in ()).throw(
                RuntimeError("cognition failed")
            ),
        )
    assert authority.is_lock_active(
        world_ref=runtime._activation_world_ref,
        profile_ref="character:char_a",
    ) is False


def test_production_player_dialogue_cognition_runs_inside_activation_lock() -> None:
    import app.main as main
    from app.ws_protocol import Envelope

    main.reset_runtime_state()
    seen: list[bool] = []
    runtime = main.character_agent_runtime
    original = runtime.ingest_character_perceived_event

    def observe(event):
        seen.append(
            runtime._activation_authority.is_lock_active(
                world_ref=runtime._activation_world_ref,
                profile_ref="character:char_a",
            )
        )
        return original(event)

    runtime.ingest_character_perceived_event = observe
    main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "player:1",
                "room_id": "room:bakery",
                "scene_id": "scene:bakery",
                "zone_id": "zone:bakery",
                "actor_id": "char_c",
                "intent_type": "dialogue_submit",
                "producer_ts": 101,
                "request_id": "request:lock:dialogue",
                "target_actor_id": "char_a",
                "content": "hello",
            },
        )
    )
    assert seen == [True]


def test_population_tick_emits_bounded_cycle_summary_in_existing_audit() -> None:
    class RecordingPopulation:
        def run_cycle(self, cadence_input, read_set):
            report = PopulationBatchReport(
                batch_ref="population-batch:summary",
                budget_used=1,
                budget_remaining=1,
                read_set_digest=read_set.read_set_digest,
                result_digest="sha256:summary",
            )
            return PopulationCycleResult(
                status="owner_settlement_required",
                batch_ref=report.batch_ref,
                report=report,
                seed_candidates=(
                    {"seed_id": "seed:char_a:summary", "actor_ref": "character:char_a"},
                ),
                owner_receipts=(
                    PopulationOwnerReceipt(
                        receipt_ref="receipt:summary",
                        owner_ref="owner:organization",
                        event_family="gameplay.organization.commerce_commitment_accepted",
                        committed=False,
                        revision_vector={},
                        zero_write=True,
                    ),
                ),
                reason="owner_settlement_required",
                production_append_count=0,
            )

    runtime = SimingRuntime(population_capability=RecordingPopulation())
    result = runtime.tick([SimingInput(input_type="population_cadence_input", source_event=_event())])
    summary_audits = [audit for audit in result.audit_records if "population_cycle" in audit.reason]
    assert summary_audits
    assert "status=owner_settlement_required" in summary_audits[0].reason
    assert "seeds=1" in summary_audits[0].reason
    assert "owners=1" in summary_audits[0].reason
    assert "receipts=0" in summary_audits[0].reason
