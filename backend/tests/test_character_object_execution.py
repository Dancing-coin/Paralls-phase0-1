"""Real source/owner/session vertical; no model or Godot claims."""
from contextlib import contextmanager

import pytest

from app.character_agent.models.character_execution import CharacterExecutionContract
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.gameplay.event_store import DurableGameplayEventStore
from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.embodied_controller_auth_service import (
    EmbodiedControllerAuthService, EmbodiedControllerEnrollment,
)
from app.services.esm_service import ESMService
from app.world_runtime.embodied_spatial_source import (
    EmbodiedSpatialScope, EmbodiedSpatialSample, EmbodiedSpatialSource,
)


@contextmanager
def vertical(tmp_path, *, target="obj_plaque", intent="inspect_object", action="action:inspect", admit_sample=True):
    from app.character_agent.execution.object_execution import CharacterObjectExecution

    world = DurableGameplayEventStore(tmp_path / "world.sqlite3")
    sessions = CharacterAgentSessionStore(database_path=tmp_path / "sessions.sqlite3")
    runtime = CharacterAgentRuntime(session_store=sessions)
    owner = ESMService(store=world)
    clock = [1000]
    auth = EmbodiedControllerAuthService()
    scope = EmbodiedSpatialScope(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
        scene_instance_id="s:1", scene_revision=1, source_ref="authored:plaque@1",
        spawn_position=(-2.2, 1.2, -2), bounds_min=(-10, -2, -10), bounds_max=(10, 4, 10),
        max_speed_mps=4, physics_ticks_per_second=60, max_age_ms=500)
    source = EmbodiedSpatialSource(store=world, auth=auth, scopes=[scope], clock_ms=lambda: clock[0])
    secret = auth.create_trusted_local_launch_credential(actor_id="char_a", controller_instance_id="c",
        issued_at=0, expires_at=100)
    binding = auth.bind_controller(EmbodiedControllerEnrollment(credential_kind="trusted_local_launch",
        credential=secret, actor_id="char_a", controller_instance_id="c", protocol_version=1),
        remote_host="127.0.0.1", now=1, connection_ref="network:c").binding
    if admit_sample:
        source.accept(EmbodiedSpatialSample(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
            scene_instance_id="s:1", scene_revision=1, connection_epoch=binding.connection_epoch,
            physics_tick=1, position=scope.spawn_position), connection_ref="network:c")
    snapshot = CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
        producer_ts=10, updated_at=10, visible_target_refs=[target])
    runtime._l1._snapshots["char_a"] = snapshot
    descriptor = owner.project_character_targets(snapshot)[0]
    contract = CharacterExecutionContract(turn_id="turn:a:1", actor_ref="character:char_a",
        source_ref="percept:1", producer_ts=10, target_refs=[f"object:{target}"],
        semantic_intent_id=intent, semantic_action_id=action,
        expected_revision_vector={"session:char_a": 1}, idempotency_key="execution:a:1",
        causation_id="cause:a:1", correlation_id="corr:a:1", privacy_scope="actor_private:char_a",
        authority_scope="world:default", expected_observation={
            "candidate_id": "candidate:1", "candidate_digest": "sha256:candidate1",
            "owner_route": "esm.interaction", "target_admission_digest": descriptor["target_admission_digest"],
            "execution_scope": {"room_id": "r", "scene_id": "s", "zone_id": "z"}})
    sessions.append_event("char_a", "character_agent_execution_request", 10, contract.model_dump(mode="json"))
    execution = CharacterObjectExecution(runtime=runtime, owner=owner, source=source,
        scopes=[scope], clock_ms=lambda: clock[0])
    try:
        yield execution, runtime, owner, source, world, sessions, clock, contract
    finally:
        runtime.close()
        world.close()


@pytest.mark.parametrize("case, expected", [
    ("fresh", "satisfied"), ("far", "blocked"), ("stale", "unknown"),
    ("foreign_scope", "unknown"), ("missing", "unknown"), ("revoked", "unknown"),
])
def test_production_target_projection_requires_current_spatial_evidence(tmp_path, case, expected):
    from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
    from app.models.character_perceived import CharacterPerceivedEvent

    with vertical(tmp_path, admit_sample=case != "missing") as (execution, runtime, owner, source, world, sessions, clock, contract):
        target = "obj_plaque"
        scene = "foreign" if case == "foreign_scope" else "s"
        if case == "stale":
            clock[0] += 501
        elif case == "far":
            clock[0] += 800
            source.accept(EmbodiedSpatialSample(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
                scene_instance_id="s:1", scene_revision=1, connection_epoch=1,
                physics_tick=49, position=(-5.3, 1.2, -2)), connection_ref="network:c")
        elif case == "revoked":
            source._auth.revoke_controller_epoch(controller_instance_id="c", connection_epoch=1)
        before = world.get_last_global_sequence()
        l1 = CharacterAgentL1Service(target_catalog_resolver=execution.project_character_targets)
        snapshot = l1.apply_character_perceived_event(CharacterPerceivedEvent(
            actor_id="char_a", percept_channel="visual", producer_ts=10,
            room_id="r", scene_id=scene, zone_id="z", perceived_summary="visible object",
            target_object_id=target, source_candidate_event_id="perceived:spatial:10"))
        restored = CharacterPrivateWorldSnapshot.model_validate_json(snapshot.model_dump_json())
        descriptor, = restored.target_catalog
        assert descriptor["required_conditions"]["range"] == expected
        assert descriptor["target_provenance"] == ["perceived:spatial:10"]
        spatial_refs = [ref for ref in descriptor["source_refs"] if ref.startswith("spatial:")]
        assert bool(spatial_refs) == (case in {"fresh", "far"})
        if case == "fresh":
            assert descriptor["target_admission_digest"] == owner.project_character_targets(restored)[0]["target_admission_digest"]
            assert descriptor["affordance_result"]["status"] == "available"
        import json
        from app.character_agent.planning.l3_planner import CharacterAgentL3Service
        from app.models.character_agent_runtime import CharacterInterpretation

        prepared = CharacterAgentL3Service().prepare_intent_plan(
            interpretation=CharacterInterpretation(actor_id="char_a", interpreted_summary="visible plaque",
                interpretation_type="object", salience_score=0.5, ambiguity_level="low", risk_level="low",
                opportunity_level="medium", attention_target=target),
            control_mode="agent_full_auto", snapshot=restored.model_dump(mode="json"))
        context = json.loads(prepared.request_json)["context"]
        assert ("inspect_object:obj_plaque" in context["candidate_intents"]) == (case == "fresh")
        assert world.get_last_global_sequence() == before


def test_frozen_contract_commits_owner_and_writes_original_receipt_once(tmp_path):
    with vertical(tmp_path) as (execution, runtime, owner, source, world, sessions, clock, contract):
        execution.offer(contract)
        event, request, result, receipt = execution.execute(contract)
        assert result.settlement_status == "committed" and receipt.committed
        assert request.turn_id == contract.turn_id and request.idempotency_key == contract.idempotency_key
        tx = world.get_transaction(receipt.transaction_id)
        assert tx.read_stream_revisions == {source.stream_id("char_a"): 1}
        assert request.causation_id == contract.causation_id
        outcomes = [e for e in runtime.get_session_timeline("char_a")
                    if e["event_type"] == "character_agent_settlement_result"]
        assert len(outcomes) == 1 and outcomes[0]["payload"]["settlement_id"] == receipt.transaction_id
        before = sessions.event_count("char_a")
        clock[0] += 2000
        assert execution.execute(contract) == (event, request, result, receipt)
        assert sessions.event_count("char_a") == before and world.get_last_global_sequence() == 2


@pytest.mark.parametrize("case", ["no_offer", "expired", "reversed", "hidden", "scope", "digest", "superseded"])
def test_failed_admission_has_no_owner_or_outcome_write(tmp_path, case):
    with vertical(tmp_path) as (execution, runtime, owner, source, world, sessions, clock, contract):
        if case != "no_offer":
            execution.offer(contract)
        if case == "expired":
            clock[0] += 1001
            execution.offer(contract)  # Re-emission must not renew the original deadline.
        elif case == "reversed":
            clock[0] -= 1
        elif case == "hidden":
            runtime._l1._snapshots["char_a"].visible_target_refs = []
        elif case == "scope":
            runtime._l1._snapshots["char_a"].scene_id = "other"
        elif case == "digest":
            owner._registered_interaction_owners[("r", "s", "z", "obj_plaque")] = "char_b"
        elif case == "superseded":
            newer = contract.model_copy(update={"turn_id": "turn:a:2", "idempotency_key": "execution:a:2"})
            sessions.append_event("char_a", "character_agent_execution_request", 11, newer.model_dump(mode="json"))
        with pytest.raises(ValueError):
            execution.execute(contract)
        assert world.get_last_global_sequence() == 1
        assert not any(e["event_type"] == "character_agent_settlement_result"
                       for e in runtime.get_session_timeline("char_a"))


def test_receipt_repairs_writeback_gap_after_new_execution_service(tmp_path, monkeypatch):
    from app.character_agent.execution.object_execution import CharacterObjectExecution

    with vertical(tmp_path) as (execution, runtime, owner, source, world, sessions, clock, contract):
        execution.offer(contract)
        original = runtime.record_settlement_result
        def lost(**kwargs):
            raise OSError("session write unavailable")
        monkeypatch.setattr(runtime, "record_settlement_result", lost)
        with pytest.raises(OSError, match="session write"):
            execution.execute(contract)
        assert world.get_last_global_sequence() == 2
        monkeypatch.setattr(runtime, "record_settlement_result", original)
        runtime._l1._snapshots.clear()
        clock[0] += 2000
        restarted = CharacterObjectExecution(runtime=runtime, owner=ESMService(store=world), source=source,
            scopes=[], clock_ms=lambda: clock[0])
        assert restarted.execute(contract)[3].committed
        assert world.get_last_global_sequence() == 2
        assert sum(e["event_type"] == "character_agent_settlement_result"
                   for e in runtime.get_session_timeline("char_a")) == 1


def test_new_service_cannot_reissue_old_dispatch_to_commit(tmp_path):
    from app.character_agent.execution.object_execution import CharacterObjectExecution

    with vertical(tmp_path) as (execution, runtime, owner, source, world, sessions, clock, contract):
        execution.offer(contract)
        restarted = CharacterObjectExecution(runtime=runtime, owner=owner, source=source,
            scopes=[], clock_ms=lambda: clock[0])
        restarted.offer(contract)
        with pytest.raises(ValueError, match="dispatch"):
            restarted.execute(contract)
        assert world.get_last_global_sequence() == 1


@pytest.mark.parametrize("target,intent,action", [
    ("obj_plaque", "inspect_object", "action:inspect"),
    ("obj_worktable", "use_object", "action:use"),
])
def test_production_egress_and_ingress_use_owner_receipt(tmp_path, monkeypatch, target, intent, action):
    import app.main as main
    from app.models.character_agent_runtime import CharacterGoalCommand

    main.reset_runtime_state()
    with vertical(tmp_path, target=target, intent=intent, action=action) as (execution, runtime, owner, source, world, sessions, clock, contract):
        monkeypatch.setattr(main, "character_agent_runtime", runtime)
        monkeypatch.setattr(main, "character_object_execution", execution)
        command = CharacterGoalCommand(actor_id="char_a", command_type="interact", ttl_ms=1000,
            causation_id=contract.causation_id, correlation_id=contract.correlation_id,
            execution_payload={"execution_contract": contract.model_dump(mode="json")})
        outbound = main._as_character_agent_execution_envelopes([command])
        messages = main._handle_envelope(main.Envelope.model_validate(outbound[0]))
        results = [m["payload"] for m in messages if m["message_type"] == "world_result"
                   and m["payload"].get("result_type") == "action_resolution_result"]
        assert len(results) == 1 and results[0]["settlement_status"] == "committed"
        assert world.get_transaction(results[0]["settlement_id"]) is not None
        requests = [m["payload"] for m in messages if m["message_type"] == "action_request"]
        assert requests[0]["idempotency_key"] == contract.idempotency_key
        assert requests[0]["payload"]["execution_contract_ref"] == contract.idempotency_key
        assert messages[0]["payload"]["owner_receipt"]["transaction_id"] == results[0]["settlement_id"]


def test_production_composes_esm_on_shared_world_store():
    import app.main as main

    main.reset_runtime_state()
    assert main.esm_service._object_store is main.gameplay_event_store


def test_sqlite_reopen_repairs_original_receipt_without_fresh_dispatch_or_pose(tmp_path, monkeypatch):
    from app.character_agent.execution.object_execution import CharacterObjectExecution

    with vertical(tmp_path) as (execution, runtime, owner, source, world, sessions, clock, contract):
        execution.offer(contract)
        def unavailable(**kwargs):
            raise OSError("session unavailable")
        monkeypatch.setattr(runtime, "record_settlement_result", unavailable)
        with pytest.raises(OSError):
            execution.execute(contract)
        runtime.close()
        world.close()
        reopened_world = DurableGameplayEventStore(tmp_path / "world.sqlite3")
        reopened_runtime = CharacterAgentRuntime(session_store=CharacterAgentSessionStore(
            database_path=tmp_path / "sessions.sqlite3"))
        try:
            recovered = CharacterObjectExecution(runtime=reopened_runtime,
                owner=ESMService(store=reopened_world), source=None, scopes=[])
            result, receipt = recovered.execute(contract)[2:]
            assert receipt.committed and result.settlement_id == receipt.transaction_id
            assert recovered.execute(contract)[2:] == (result, receipt)
            assert reopened_world.get_last_global_sequence() == 2
            assert sum(e["event_type"] == "character_agent_settlement_result"
                       for e in reopened_runtime.get_session_timeline("char_a")) == 1
        finally:
            reopened_runtime.close()
            reopened_world.close()
