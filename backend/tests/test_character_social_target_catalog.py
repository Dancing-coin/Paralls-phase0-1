"""Social source admission; no live model or Godot claims."""
from app.gameplay.canonical_combat_authority import CanonicalCombatTargetReader
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from test_combat_settlement_threat_consumer import _sources

import pytest
from types import SimpleNamespace


@pytest.fixture
def social_catalog(tmp_path, request):
    from app.character_agent.execution import social_target_catalog
    from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
    from app.models.character_perceived import CharacterPerceivedEvent
    from app.services.embodied_controller_auth_service import (
        EmbodiedControllerAuthService, EmbodiedControllerEnrollment,
    )
    from app.world_runtime.embodied_spatial_source import (
        EmbodiedSpatialScope, EmbodiedSpatialSource, EmbodiedSpatialSample,
    )

    store = DurableGameplayEventStore(tmp_path / "social.db")
    _sources(store)
    clock = [1000]
    auth = EmbodiedControllerAuthService()
    scopes = [EmbodiedSpatialScope(actor_id=actor, room_id="r", scene_id="s", zone_id="z",
        scene_instance_id="s:1", scene_revision=1, source_ref="deployment:s@1",
        spawn_position=(float(index), 0., 0.), bounds_min=(-10., -2., -10.),
        bounds_max=(10., 4., 10.), max_speed_mps=4., physics_ticks_per_second=60,
        max_age_ms=500) for index, actor in enumerate(("char_a", "char_b"))]
    scopes[1] = scopes[1].model_copy(update=getattr(request, "param", {}))
    source = EmbodiedSpatialSource(store=store, auth=auth, scopes=scopes, clock_ms=lambda: clock[0])
    for scope in scopes:
        actor = scope.actor_id
        secret = auth.create_trusted_local_launch_credential(actor_id=actor,
            controller_instance_id=actor, issued_at=0, expires_at=100)
        binding = auth.bind_controller(EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch", credential=secret, actor_id=actor,
            controller_instance_id=actor, protocol_version=1), remote_host="127.0.0.1",
            now=1, connection_ref="network:" + actor).binding
        source.accept(EmbodiedSpatialSample(actor_id=actor, room_id="r", scene_id="s", zone_id="z",
            scene_instance_id=scope.scene_instance_id, scene_revision=scope.scene_revision, connection_epoch=binding.connection_epoch,
            physics_tick=1, position=scope.spawn_position), connection_ref="network:" + actor)
    timeline = SimpleNamespace(status="active", world_scope_ref="world:demo", timeline_id="timeline:main")
    catalog = social_target_catalog.CharacterSocialTargetCatalog(
        store=store, source=source, scopes=scopes, timeline=lambda: timeline)
    snapshot = CharacterAgentL1Service().apply_character_perceived_event(CharacterPerceivedEvent(
        actor_id="char_a", room_id="r", scene_id="s", zone_id="z", producer_ts=10,
        percept_channel="visual", perceived_summary="another character", target_actor_id="char_b",
        source_candidate_event_id="percept:private:a:10"))
    try:
        yield catalog, snapshot, store, source, scopes, clock, auth, timeline
    finally:
        store.close()


def test_social_catalog_combines_private_neutral_and_spatial_sources_without_writes(social_catalog, monkeypatch):
    catalog, snapshot, store, source, scopes, clock, auth, timeline = social_catalog
    original = store.read_stream
    def read(stream, *args, **kwargs):
        assert not stream.startswith("faction:")
        return original(stream, *args, **kwargs)
    monkeypatch.setattr(store, "read_stream", read)
    before = store.get_last_global_sequence()
    descriptors = catalog.project_character_targets(snapshot)
    assert {d["supported_intents"][0] for d in descriptors} == {
        "approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}
    assert len({d["target_admission_digest"] for d in descriptors}) == 5
    assert descriptors == catalog.project_character_targets(snapshot)
    for descriptor in descriptors:
        assert descriptor["owner_route"] == "social_spatial_owner"
        assert descriptor["target_ref"] == "char_b"
        assert descriptor["target_provenance"] == ["percept:private:a:10"]
        assert descriptor["affordance_result"]["status"] == "available"
        assert descriptor["social_source_context"]["target_incarnation_ref"] == "character:char_b@1"
        assert descriptor["target_revision_vector"][source.stream_id("char_a")] == 1
        assert descriptor["target_revision_vector"][source.stream_id("char_b")] == 1
        assert descriptor["social_source_context"]["execution_scope"]["scene_instance_id"] == "s:1"
    assert store.get_last_global_sequence() == before


def test_social_catalog_pins_sources_for_owner_submission(social_catalog):
    from app.gameplay.social_spatial_owner import SocialSpatialOwner
    catalog, snapshot, store, source, scopes, clock, auth, timeline = social_catalog
    descriptor = catalog.project_character_targets(snapshot)[0]
    receipt = SocialSpatialOwner(store=store).submit(
        actor_ref="character:char_a", target_ref="character:char_b",
        action_profile=descriptor["supported_intents"][0], request_ref="social:req:1",
        turn_id="turn:social:1", idempotency_key="social:req:1", causation_id="cause:social:1",
        correlation_id="corr:social:1", producer_ts=10, expected_revision_vector={},
        expected_memory_revision_vector={}, expected_snapshot_revision=0,
        source_read_set=descriptor["target_revision_vector"],
        source_context=descriptor["social_source_context"],
    )
    assert receipt.committed
    event = store.get_event(receipt.committed_event_ids[0])
    assert event.payload["source_read_set"] == descriptor["target_revision_vector"]
    assert event.payload["source_context"] == descriptor["social_source_context"]


@pytest.mark.parametrize("social_catalog", [{"scene_instance_id": "s:other"}, {"scene_revision": 2}], indirect=True)
def test_social_catalog_requires_same_scene_instance_and_revision(social_catalog):
    catalog, snapshot, *_ = social_catalog
    assert catalog.project_character_targets(snapshot) == []


def test_production_social_source_receipt_recovers_without_current_catalog(social_catalog, monkeypatch):
    import app.main as main
    from app.character_agent.execution.object_execution import CharacterObjectExecution
    from app.character_agent.models.character_execution import CharacterExecutionContract
    from app.gameplay.social_spatial_owner import SocialSpatialOwner
    from test_character_execution_contract import _valid_contract

    catalog, snapshot, store, source, scopes, clock, auth, timeline = social_catalog
    main.reset_runtime_state()
    monkeypatch.setattr(main, "social_spatial_owner", SocialSpatialOwner(store=store))
    execution = CharacterObjectExecution(runtime=main.character_agent_runtime, owner=main.esm_service,
        source=source, scopes=scopes, social_targets=catalog)
    monkeypatch.setattr(main, "character_object_execution", execution)
    main.character_agent_runtime._l1._snapshots["char_a"] = snapshot
    descriptor = catalog.project_character_targets(snapshot)[0]
    contract = CharacterExecutionContract.model_validate(_valid_contract(
        actor_ref="character:char_a", target_refs=("character:char_b",), semantic_intent_id="approach",
        semantic_action_id="action:approach", expected_observation={
            "requested_action": "approach", "target_admission_digest": descriptor["target_admission_digest"]},
    ))
    main.character_agent_runtime.record_execution_request(
        actor_id="char_a", producer_ts=10, payload=contract.model_dump(mode="json"))
    envelope = main.Envelope(message_type="character_agent_execution", payload=contract.model_dump(mode="json"))
    first = main._handle_envelope(envelope)
    assert first[0]["payload"]["accepted"], first
    receipt = first[0]["payload"]["owner_receipt"]
    event = store.get_event(receipt["committed_event_ids"][0])
    assert event.payload["source_read_set"] == descriptor["target_revision_vector"]
    assert event.payload["source_context"] == descriptor["social_source_context"]
    snapshot.visible_target_refs = []
    clock[0] += 2000
    before = store.get_last_global_sequence()
    replay = main._handle_envelope(envelope)
    assert replay[0]["payload"]["accepted"], replay
    assert replay[0]["payload"]["owner_receipt"]["transaction_id"] == receipt["transaction_id"]
    assert store.get_last_global_sequence() == before


@pytest.mark.parametrize("case", ["hidden", "no_lineage", "empty_lineage", "self", "scope", "stale", "revoked", "timeline"])
def test_social_catalog_missing_current_admission_never_exposes_actions(social_catalog, case):
    catalog, snapshot, store, source, scopes, clock, auth, timeline = social_catalog
    if case == "hidden":
        snapshot.visible_target_refs = []
    elif case == "no_lineage":
        snapshot.visible_target_sources = {}
    elif case == "empty_lineage":
        snapshot.visible_target_sources = {"char_b": [""]}
    elif case == "self":
        snapshot.visible_target_refs = ["char_a"]
        snapshot.visible_target_sources = {"char_a": ["percept:self"]}
    elif case == "scope":
        snapshot.scene_id = "foreign"
    elif case == "stale":
        clock[0] += 501
    elif case == "revoked":
        auth.revoke_controller_epoch(controller_instance_id="char_b", connection_epoch=1)
    else:
        timeline.status = "ended"
    assert catalog.project_character_targets(snapshot) == []


def test_neutral_participants_resolve_real_presence_life_without_faction_reads(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / "world.db")
    sources = _sources(store)
    original = store.read_stream

    def read(stream, *args, **kwargs):
        assert not stream.startswith("faction:"), "social source must not read faction"
        return original(stream, *args, **kwargs)

    monkeypatch.setattr(store, "read_stream", read)
    before = store.get_last_global_sequence()
    result = CanonicalCombatTargetReader(store=store).resolve_current_participants(
        actor_ref="character:char_a", target_ref="character:char_b",
        world_ref=sources.world_ref, timeline_ref=sources.timeline_ref,
        eligible_life_states=frozenset({"alive"}),
    )
    assert result is not None and result["eligible"]
    assert result["source_event_ids"] == [*sources.presence_source_event_ids, *sources.life_state_source_event_ids]
    assert not any(stream.startswith("faction:") for stream in result["source_revisions"])
    assert store.get_last_global_sequence() == before
    store.close()


def test_neutral_participants_reject_presence_change_during_source_read(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / "presence-race.db")
    sources = _sources(store)
    original = store.read_stream
    raced = False

    def read(stream, *args, **kwargs):
        nonlocal raced
        rows = original(stream, *args, **kwargs)
        if stream == "presence:world:demo" and not raced:
            raced = True
            store.append_batch(build_atomic_event_batch(
                command_id="race:despawn", principal_ref="population.presence_authority",
                stream_id=stream, expected_revision=store.get_stream_head(stream),
                event_specs=(("population.presence.despawned", {
                    "world_ref": "world:demo", "character_ref": "character:char_b",
                    "incarnation": 1, "reason": "race",
                }),), idempotency_key="race:despawn", causation_id="race",
                correlation_id="race",
            ))
        return rows

    monkeypatch.setattr(store, "read_stream", read)
    result = CanonicalCombatTargetReader(store=store).resolve_current_participants(
        actor_ref="character:char_a", target_ref="character:char_b",
        world_ref=sources.world_ref, timeline_ref=sources.timeline_ref,
        eligible_life_states=frozenset({"alive"}),
    )
    assert result is None
    store.close()
