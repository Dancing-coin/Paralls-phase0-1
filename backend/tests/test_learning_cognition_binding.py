"""Committed owner facts affect new turns and invalidate old provider work."""
from copy import deepcopy
import json

import pytest

from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot
from test_registered_learning_authority import setup as owner_setup
from test_cognition_completion_revision import ModelGateway, perceived
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service


def runtime(path, owner, *, world="world:test"):
    result = CharacterAgentRuntime(storage_root=path, learning_authority=owner, learning_world_ref=world)
    gateway = ModelGateway()
    result._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=result._profile_registry)
    result._l3 = CharacterAgentL3Service(gateway=gateway)
    return result


def freeze(rt, actor="char_a"):
    snapshot = CharacterPrivateWorldSnapshot(actor_id=actor, room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", producer_ts=10, updated_at=10)
    turn = CharacterTurnContext.begin(actor_id=actor, source_event_ref="source:10", producer_ts=10,
        causation_id="cause", correlation_id="corr", input_revision_vector={}, memory_revision_vector={},
        policy_revision="policy:1", snapshot_revision=1, branch_id="branch:main")
    return rt._freeze_turn_cognition_contract(actor, snapshot, turn)


def test_owner_snapshot_preserves_one_read_revision_and_scope():
    _, owner, _, request = owner_setup(rank="master", proficiency=.99)
    empty = owner.read_snapshot(world_ref="world:test", actor_id="char_a")
    receipt = owner.settle(request, caller_principal="service:learning")
    learned = owner.read_snapshot(world_ref="world:test", actor_id="char_a")
    assert empty.revision == 0 and empty.states == ()
    assert learned.revision == 1 and learned.source_event_refs == tuple(receipt.committed_event_ids)
    assert owner.read_snapshot(world_ref="other", actor_id="char_a").revision == 0
    assert owner.read_snapshot(world_ref="world:test", actor_id="char_b").states == ()


def test_new_turn_compiles_owner_facts_without_mutating_old_turn_or_profile(tmp_path):
    _, owner, _, request = owner_setup(rank="master", proficiency=.99)
    rt = runtime(tmp_path, owner)
    try:
        profile = deepcopy(rt._profile_payload("char_a"))
        old = freeze(rt)
        saved = deepcopy(old)
        other = freeze(rt, "char_b")
        owner.settle(request, caller_principal="service:learning")
        new = freeze(rt)
        learned = next(skill for skill in new["stable_ability_snapshot"]["skills"] if skill["skill_id"] == "observation")
        assert learned["source"] == "learned" and learned["rank"] == "master"
        assert new["capability_envelope"]["capability_revision"] != old["capability_envelope"]["capability_revision"]
        assert new["capability_envelope"]["revision_pins"]["learning_revision"] == dict(rt._capture_cognition_pin("char_a"))["learning"]
        assert old == saved and rt._profile_payload("char_a") == profile
        assert freeze(rt, "char_b") == other
    finally:
        rt.close()


def test_pending_sync_result_rejects_learning_commit_with_no_completion_write(tmp_path):
    _, owner, _, request = owner_setup()
    rt = runtime(tmp_path, owner)
    try:
        pending = rt.prepare_cognition_job(source_kind="ingest_character_perceived_event", payload=perceived())
        owner.settle(request, caller_principal="service:learning")
        before = rt.get_session_timeline("char_a")
        result = rt.commit_cognition_result(pending.next_job, output={})
        assert result.status == "requeued" and result.reason == "stale_context"
        assert rt.get_session_timeline("char_a") == before
    finally:
        rt.close()


def test_commit_between_freeze_and_handoff_is_rejected(tmp_path, monkeypatch):
    _, owner, _, request = owner_setup()
    rt = runtime(tmp_path, owner)
    original = rt._l2._gateway.prepare_run_request

    def concurrent_commit(**kwargs):
        prepared = original(**kwargs)
        owner.settle(request, caller_principal="service:learning")
        return prepared

    monkeypatch.setattr(rt._l2._gateway, "prepare_run_request", concurrent_commit)
    try:
        with pytest.raises(ValueError, match="learning_contract_stale"):
            rt.prepare_cognition_job(source_kind="ingest_character_perceived_event", payload=perceived())
    finally:
        rt.close()


@pytest.mark.parametrize("reopen", [False, True])
def test_durable_coordinator_rejects_old_pending_result(tmp_path, monkeypatch, reopen):
    import test_character_cognition_coordinator as helpers

    _, owner, _, request = owner_setup()
    constructor = CharacterAgentRuntime
    monkeypatch.setattr(helpers, "CharacterAgentRuntime", lambda **kw:
        constructor(**kw, learning_authority=owner, learning_world_ref="world:test"))
    rt, admissions, coordinator, child, handle = helpers.setup(tmp_path)
    try:
        coordinator.begin_entry(child.child_key, activation=handle, now=110.)
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
        pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
        if reopen:
            rt.close()
            rt, admissions, coordinator, child, handle = helpers.setup(tmp_path)
            assert coordinator.prepare_l2(child.child_key, activation=handle, now=112.5) == pending
        owner.settle(request, caller_principal="service:learning")
        before = admissions.read_progress(child.child_key)
        with pytest.raises(ValueError, match="stale_pin"):
            coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})
        assert admissions.read_progress(child.child_key) == before == pending
    finally:
        rt.close()


def test_durable_handoff_race_does_not_persist_pending_provider(tmp_path, monkeypatch):
    import test_character_cognition_coordinator as helpers

    _, owner, _, request = owner_setup()
    constructor = CharacterAgentRuntime
    monkeypatch.setattr(helpers, "CharacterAgentRuntime", lambda **kw:
        constructor(**kw, learning_authority=owner, learning_world_ref="world:test"))
    rt, admissions, coordinator, child, handle = helpers.setup(tmp_path)
    try:
        coordinator.begin_entry(child.child_key, activation=handle, now=110.)
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
        original = rt._freeze_siming_l2_request

        def concurrent_commit(*args):
            frozen = original(*args)
            owner.settle(request, caller_principal="service:learning")
            return frozen

        monkeypatch.setattr(rt, "_freeze_siming_l2_request", concurrent_commit)
        before = admissions.read_progress(child.child_key)
        with pytest.raises(ValueError, match="learning_contract_stale"):
            coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
        assert admissions.read_progress(child.child_key) == before
    finally:
        rt.close()


def test_production_lifespan_binds_reader_to_shared_store_and_world(tmp_path):
    import subprocess
    import sys
    from scripts.verification.population_godot_runner import child_environment

    (tmp_path / "roster.json").write_text(json.dumps(dict(actor_ids=["char_a", "char_b", "char_c",
        *[f"resident_{i:05d}" for i in range(97)]])), encoding="utf-8")
    code = '''
import asyncio, sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from scripts.verification.population_mixed_backend import configure
async def run():
    with ExitStack() as stack:
        main, _, _ = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode='local_probe')
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        async with main.component_app.router.lifespan_context(main.component_app):
            def inspect():
                rt = main.character_agent_runtime
                assert rt._learning_authority is not None
                assert rt._learning_authority._store is main.gameplay_event_store
                assert rt._learning_world_ref == main._bakery_population_mode().world_ref
                read = rt._learning_snapshot('char_a')
                assert read.actor_id == 'char_a' and read.revision == 0
                assert 'learning' in dict(rt._capture_cognition_pin('char_a'))
            await asyncio.wrap_future(main.runtime_execution.submit(inspect))
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=child_environment(),
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout[-2500:] + result.stderr[-2500:]
