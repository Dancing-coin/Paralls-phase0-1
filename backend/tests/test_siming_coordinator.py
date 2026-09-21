import pytest
from test_siming_continuation import adaptive_state

from app.services.siming_coordinator import SimingCoordinator
from app.services.siming_admission import SimingAdmissionService
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app import main
from app.config import Settings
from test_siming_heavenly_runtime_composition import _authority_destruction_event


def coordinator(state):
    state.siming_runtime._source_pin_reader = lambda event: {"event": event.event_id}
    state.siming_runtime._actor_pin_reader = lambda actor: {"actor": actor}
    return SimingCoordinator(runtime=state.siming_runtime,
        admissions=SimingAdmissionService(SimingHeavenlyMemoryService(state.heavenly_graph)),
        graph=state.heavenly_graph, invalidation_reader=lambda _: None)


def test_coordinator_admits_then_freezes_whole_initial_plan_without_business_writes(tmp_path):
    state = main.build_runtime_state(Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        owner = coordinator(state)
        event = _authority_destruction_event()
        first = owner.admit_event(event, now=100, expires_at=200, policy_version="policy:v1")
        assert owner.admit_event(event, now=101, expires_at=201, policy_version="policy:v1").replayed
        assert state.siming_runtime._narrative_core._revision_by_room == {}
        frozen = owner.begin(first.entry.key, now=101)
        assert frozen.entry.state == "commit_started"
        assert frozen.entry.transition.stage == "initial"
        assert len(frozen.entry.transition.effects) >= 14
        assert all(not state.heavenly_graph.has_idempotency_key(scope=batch.scope, idempotency_key=batch.idempotency_key)
            for batch in owner.read_plan(frozen.entry.key).effects.batches)
        assert owner.begin(first.entry.key, now=102).entry == frozen.entry
        assert state.siming_runtime.pending_count == 0
    finally:
        state.close()


@pytest.mark.parametrize("cut", [0, 1, 7, 13])
def test_coordinator_reopens_initial_effect_prefix_and_keeps_room_blocked(tmp_path, cut):
    settings = Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db"))
    state = main.build_runtime_state(settings)
    owner = coordinator(state)
    event = _authority_destruction_event()
    first = owner.admit_event(event, now=100, expires_at=200, policy_version="policy:v1")
    second_event = event.model_copy(update={"event_id": "event:later", "scene_id": "other"})
    second = owner.admit_event(second_event, now=100, expires_at=200, policy_version="policy:v1")
    owner.begin(first.entry.key, now=101)
    plan = owner.read_plan(first.entry.key)
    for batch in plan.effects.batches[:cut]:
        state.heavenly_graph.write_batch(batch)
    state.close()
    restored = main.build_runtime_state(settings)
    try:
        recovered = coordinator(restored)
        with pytest.raises(ValueError, match="room_busy"):
            recovered.begin(second.entry.key, now=102)
        done = recovered.resume_committed(first.entry.key, now=102)
        assert done.entry.state == "commit_started"
        assert len(done.entry.transition.receipts) == len(done.entry.transition.effects)
        assert all(restored.heavenly_graph.write_batch(batch).replayed for batch in plan.effects.batches)
        snapshot = dict(restored.siming_runtime._narrative_core._revision_by_room)
        again = recovered.resume_committed(first.entry.key, now=103)
        assert again.entry == done.entry
        assert restored.siming_runtime._narrative_core._revision_by_room == snapshot
        assert recovered.admissions.read_room_head(first.entry.key.scope).completed_sequence == 0
    finally:
        restored.close()

@pytest.mark.parametrize("reason", ["source_revoked", "branch_reset", "authorization_revoked", None])
def test_coordinator_rejected_plan_only_reconciles_existing_receipts(tmp_path, reason):
    settings = Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db"))
    state = main.build_runtime_state(settings)
    try:
        owner = coordinator(state)
        event = _authority_destruction_event()
        receipt = owner.admit_event(event, now=100, expires_at=200, policy_version="policy:v1")
        owner.begin(receipt.entry.key, now=101)
        plan = owner.read_plan(receipt.entry.key)
        state.heavenly_graph.write_batch(plan.effects.batches[0])
        if reason is not None:
            owner._invalidation_reader = lambda _: reason
        result = owner.resume_committed(receipt.entry.key, now=200 if reason is None else 102)
        assert result.entry.state == "stale"
        assert owner.read_plan(receipt.entry.key) == plan
        assert len(result.entry.transition.receipts) == 1
        assert not state.heavenly_graph.has_idempotency_key(scope=plan.effects.batches[1].scope,
            idempotency_key=plan.effects.batches[1].idempotency_key)
        assert state.siming_runtime._narrative_core._revision_by_room == {}
        assert owner.admissions.read_room_head(receipt.entry.key.scope).completed_sequence == 1
    finally:
        state.close()


def test_initial_plan_ledger_failure_does_not_apply_domain_state(tmp_path, monkeypatch):
    state = main.build_runtime_state(Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        owner = coordinator(state)
        event = _authority_destruction_event()
        receipt = owner.admit_event(event, now=100, expires_at=200, policy_version="policy:v1")
        def fail(*args, **kwargs):
            raise OSError("ledger unavailable")
        monkeypatch.setattr(owner.admissions, "advance", fail)
        with pytest.raises(OSError, match="ledger unavailable"):
            owner.begin(receipt.entry.key, now=101)
        assert owner.admissions.read(receipt.entry.key).entry.state == "admitted"
        assert state.siming_runtime._narrative_core._revision_by_room == {}
        for batch in state.siming_runtime.heavenly_support.plan_authority_outcome(event).batches:
            assert not state.heavenly_graph.has_idempotency_key(scope=batch.scope, idempotency_key=batch.idempotency_key)
    finally:
        state.close()

def test_coordinator_bounded_ready_cursor_does_not_skip_remainder_or_cross_owner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    state = main.build_runtime_state(Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        owner = coordinator(state)
        event = _authority_destruction_event()
        expected = set()
        for index in range(9):
            admitted = owner.admit_event(event.model_copy(update={"event_id": f"event:{index}", "room_id": f"room:{index}"}),
                now=100, expires_at=200, policy_version="policy:v1")
            expected.add(admitted.entry.key.entry_id)
        first = owner.take_ready(now=101)
        second = owner.take_ready(now=101)
        third = owner.take_ready(now=101)
        assert list(map(len, (first, second, third))) == [4, 4, 1]
        assert {key.entry_id for key in (*first, *second, *third)} == expected
        with ThreadPoolExecutor(max_workers=1) as worker:
            with pytest.raises(RuntimeError, match="owner_thread"):
                worker.submit(owner.take_ready, now=101).result()
    finally:
        state.close()


def test_receipt_failure_after_real_batch_reconciles_without_replanning(tmp_path, monkeypatch):
    settings = Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db"))
    state = main.build_runtime_state(settings)
    owner = coordinator(state)
    receipt = owner.admit_event(_authority_destruction_event(), now=100, expires_at=200, policy_version="policy:v1")
    owner.begin(receipt.entry.key, now=101)
    plan = owner.read_plan(receipt.entry.key)
    def cut(*args, **kwargs):
        raise OSError("receipt write interrupted")
    monkeypatch.setattr(owner.admissions, "advance", cut)
    with pytest.raises(OSError, match="receipt write interrupted"):
        owner.resume_committed(receipt.entry.key, now=102)
    assert state.heavenly_graph.has_idempotency_key(scope=plan.effects.batches[0].scope,
        idempotency_key=plan.effects.batches[0].idempotency_key)
    assert owner.admissions.read(receipt.entry.key).entry.transition.receipts == []
    state.close()
    restored = main.build_runtime_state(settings)
    try:
        recovered = coordinator(restored)
        monkeypatch.setattr(restored.siming_runtime, "plan_initial", lambda *args: pytest.fail("replanned accepted prefix"))
        completed = recovered.resume_committed(receipt.entry.key, now=103)
        assert len(completed.entry.transition.receipts) == len(completed.entry.transition.effects)
    finally:
        restored.close()


def test_accepted_plan_survives_normal_source_and_actor_progress(tmp_path):
    state = main.build_runtime_state(Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        owner = coordinator(state)
        receipt = owner.admit_event(_authority_destruction_event(), now=100, expires_at=200, policy_version="policy:v1")
        owner.begin(receipt.entry.key, now=101)
        state.siming_runtime._source_pin_reader = lambda _: {"revision": "normal progress"}
        state.siming_runtime._actor_pin_reader = lambda _: {"revision": 999}
        finished = owner.resume_committed(receipt.entry.key, now=102)
        assert finished.entry.state == "commit_started"
        assert len(finished.entry.transition.receipts) == len(finished.entry.transition.effects)
    finally:
        state.close()

def test_accepted_plan_keeps_original_graph_cas_after_external_revision_change(tmp_path):
    state = main.build_runtime_state(Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        owner = coordinator(state)
        receipt = owner.admit_event(_authority_destruction_event(), now=100, expires_at=200, policy_version="policy:v1")
        owner.begin(receipt.entry.key, now=101)
        batch = owner.read_plan(receipt.entry.key).effects.batches[0]
        altered = batch.nodes[0].model_copy(update={"attributes": {**batch.nodes[0].attributes, "state_value": "different"}})
        competing = batch.model_copy(update={"transaction_id": "tx:competing", "idempotency_key": "key:competing", "nodes": [altered]})
        state.heavenly_graph.write_batch(competing)
        from app.services.siming_heavenly_graph_port import HeavenlyGraphRevisionConflict
        with pytest.raises(HeavenlyGraphRevisionConflict):
            owner.resume_committed(receipt.entry.key, now=102)
        assert owner.admissions.read(receipt.entry.key).entry.state == "commit_started"
        assert not state.heavenly_graph.has_idempotency_key(scope=batch.scope, idempotency_key=batch.idempotency_key)
        assert state.heavenly_graph.get_node(scope=batch.scope, node_id=altered.node_id, valid_at=101).attributes == altered.attributes
    finally:
        state.close()


def test_provider_registration_is_durable_before_handoff_and_rolls_back_local_frame(tmp_path, monkeypatch):
    import time
    from app.services.siming_continuation import SimingTurnFrame
    from app.services.siming_runtime import SimingRuntime
    from test_siming_continuation import make_visual_fact_event
    state = main.build_runtime_state(Settings(siming_heavenly_mode="active", heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        state.siming_runtime = SimingRuntime()
        owner = coordinator(state)
        now = time.time()
        receipt = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now + 60, policy_version="v1")
        owner.begin(receipt.entry.key, now=now)
        owner.resume_committed(receipt.entry.key, now=now)
        original = owner.admissions.advance
        def fail(*args, **kwargs):
            raise OSError('provider ledger unavailable')
        monkeypatch.setattr(owner.admissions, 'advance', fail)
        with pytest.raises(OSError, match='provider ledger unavailable'):
            owner.prepare_provider(receipt.entry.key, now=now)
        assert state.siming_runtime.pending_count == 0
        assert owner.admissions.read(receipt.entry.key).entry.state == 'commit_started'
        monkeypatch.setattr(owner.admissions, 'advance', original)
        advance = owner.prepare_provider(receipt.entry.key, now=now)
        saved = owner.admissions.read(receipt.entry.key).entry
        assert saved.state == 'provider_pending'
        frame = SimingTurnFrame.model_validate_json(saved.transition.provider.frame_json)
        assert frame.job == advance.job
        assert saved.transition.provider.request_json.encode() == advance.job.request_json
        again = owner.prepare_provider(receipt.entry.key, now=now)
        assert again.replayed and again.job == advance.job
        assert owner.admissions.read(receipt.entry.key).entry == saved
    finally:
        state.close()


@pytest.mark.parametrize("restart", [False, True])
def test_provider_result_is_saved_before_pure_plan_and_duplicate_is_not_applied(tmp_path, monkeypatch, restart):
    import time
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_continuation import run_siming_provider
    from test_siming_continuation import make_visual_fact_event
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        state.siming_runtime = SimingRuntime()
        owner = coordinator(state)
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now + 60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        owner.resume_committed(key, now=now)
        job = owner.prepare_provider(key, now=now).job
        completion = run_siming_provider(state.siming_runtime._llm_provider, job.request_json)
        original = state.siming_runtime.plan_accepted
        monkeypatch.setattr(state.siming_runtime, 'plan_accepted', lambda *_: pytest.fail('planned before result durable'))
        result = owner.accept_provider(key, job, completion, now=now)
        assert result.entry.state == 'result_ready'
        assert owner.accept_provider(key, job, completion, now=now).replayed
        monkeypatch.setattr(state.siming_runtime, 'plan_accepted', original)
        if restart:
            state.close()
            state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'g.db')))
            state.siming_runtime = SimingRuntime()
            owner = coordinator(state)
        plan_receipt = owner.freeze_result(key, now=now)
        assert plan_receipt.entry.state == 'commit_started'
        assert plan_receipt.entry.transition.stage == 'candidate'
        assert plan_receipt.entry.transition.ordinal == 1
        assert plan_receipt.entry.transition.receipts == []
        assert owner.accept_provider(key, job, completion, now=now).replayed
        assert owner.read_plan(key).after.stage == 'completed'
        assert state.siming_runtime.pending_count == 0
    finally:
        state.close()


def test_provider_pending_restart_reissues_only_request_with_new_token(tmp_path):
    import time
    from app.services.siming_runtime import SimingRuntime
    from test_siming_continuation import make_visual_fact_event
    settings = Settings(heavenly_graph_path=str(tmp_path / 'g.db'))
    state = main.build_runtime_state(settings)
    state.siming_runtime = SimingRuntime()
    owner = coordinator(state)
    now = time.time()
    key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now + 60, policy_version='v1').entry.key
    owner.begin(key, now=now)
    owner.resume_committed(key, now=now)
    previous = owner.prepare_provider(key, now=now)
    pending = owner.admissions.read(key).entry
    state.close()
    state = main.build_runtime_state(settings)
    try:
        state.siming_runtime = SimingRuntime()
        owner = coordinator(state)
        current = owner.prepare_provider(key, now=time.time())
        assert current.job.token != previous.job.token
        assert current.job.generation != previous.job.generation
        assert current.job.request_json == previous.job.request_json
        assert current.job.attempt == previous.job.attempt + 1
        assert not current.replayed
        saved = owner.admissions.read(key).entry
        assert saved.revision == pending.revision + 1
        assert saved.transition.ordinal == pending.transition.ordinal
        assert saved.expires_at == pending.expires_at
    finally:
        state.close()


@pytest.mark.parametrize('change', ['source', 'actor', 'revoked', 'ttl'])
def test_provider_rejection_has_no_candidate_fallback_or_new_effects(tmp_path, change):
    import time
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_continuation import run_siming_provider
    from test_siming_continuation import make_visual_fact_event
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'g.db')))
    try:
        state.siming_runtime = SimingRuntime()
        owner = coordinator(state)
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now + 60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        owner.resume_committed(key, now=now)
        job = owner.prepare_provider(key, now=now).job
        completion = run_siming_provider(state.siming_runtime._llm_provider, job.request_json)
        before = state.siming_runtime._narrative_core._revision_by_room.copy()
        if change == 'source':
            state.siming_runtime._source_pin_reader = lambda _: False
        elif change == 'actor':
            state.siming_runtime._actor_pin_reader = lambda _: 999
        elif change == 'revoked':
            owner._invalidation_reader = lambda _: 'source_revoked'
        result = owner.accept_provider(key, job, completion, now=now + 60 if change == 'ttl' else now)
        assert result.entry.state == 'stale'
        assert result.entry.result_revision is None
        assert state.siming_runtime.pending_count == 0
        assert state.siming_runtime._narrative_core._revision_by_room == before
        assert result.entry.transition.effects == []
    finally:
        state.close()


def test_timeout_completion_is_durable_before_stale_pin_terminal(tmp_path):
    import time
    from app.services.siming_continuation import SimingProviderCompletion, run_siming_provider
    from app.services.siming_llm_provider import SimingLlmProviderTimeout
    from app.services.siming_runtime import SimingRuntime
    from test_siming_continuation import make_visual_fact_event

    class TimeoutProvider:
        def generate_candidates(self, **_kwargs):
            raise SimingLlmProviderTimeout("controlled timeout")

    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / "g.db")))
    try:
        versions = [1]
        state.siming_runtime = SimingRuntime(llm_provider=TimeoutProvider())
        owner = coordinator(state)
        owner.runtime._actor_pin_reader = lambda actor: {"actor": actor, "revision": versions[0]}
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now,
            expires_at=now + 60, policy_version="v1").entry.key
        job, provider, provider_revision = owner.prepare_ready(key, now=now)
        completion = run_siming_provider(provider, job.request_json)
        assert SimingProviderCompletion.model_validate_json(completion).error == "SimingLlmProviderTimeout"
        versions[0] = 2

        terminal = owner.finish_ready(key, job, completion,
            provider_revision=provider_revision, now=now)

        assert terminal.entry.state == "stale"
        assert terminal.entry.transition.reason.startswith("stale_pin;")
        assert terminal.entry.result_revision is not None
        durable = owner.admissions.read(key, revision=terminal.entry.result_revision).entry
        assert durable.state == "result_ready"
        assert SimingProviderCompletion.model_validate_json(
            durable.transition.completion_json).error == "SimingLlmProviderTimeout"
        assert terminal.entry.transition.effects == []
        assert state.siming_runtime.pending_count == 0
    finally:
        state.close()


def test_adaptive_provider_plan_uses_same_durable_stage_boundary(adaptive_state):
    import time
    from app.services.siming_continuation import run_siming_provider
    from test_siming_continuation import _adaptive_input
    runtime = adaptive_state.siming_runtime
    owner = SimingCoordinator(runtime=runtime, graph=adaptive_state.graph,
        admissions=SimingAdmissionService(SimingHeavenlyMemoryService(adaptive_state.graph)),
        invalidation_reader=lambda _: None)
    now = time.time()
    key = owner.admit_event(_adaptive_input().source_event, now=now, expires_at=now + 60, policy_version='v1').entry.key
    owner.begin(key, now=now)
    owner.resume_committed(key, now=now)
    job = owner.prepare_provider(key, now=now).job
    assert job.stage == 'adaptive'
    completion = run_siming_provider(runtime.heavenly_support._llm_provider, job.request_json)
    owner.accept_provider(key, job, completion, now=now)
    frozen = owner.freeze_result(key, now=now)
    assert frozen.entry.state == 'commit_started'
    plan = owner.read_plan(key)
    assert any(output.output_type == 'staging_request' for output in plan.after.result.outputs)
    assert len(plan.effects.batches) >= 7
    assert all(not adaptive_state.graph.has_idempotency_key(scope=batch.scope, idempotency_key=batch.idempotency_key)
               for batch in plan.effects.batches)
    applied = owner.resume_committed(key, now=now)
    assert len(applied.entry.transition.receipts) == len(applied.entry.transition.effects)
    assert owner.admissions.read_room_head(key.scope).completed_sequence == 0


@pytest.mark.parametrize('change', ['actor', 'source', 'policy'])
def test_unsubmitted_provider_request_does_not_adopt_new_external_pin(tmp_path, change):
    import time
    from app.services.siming_runtime import SimingRuntime
    from test_siming_continuation import make_visual_fact_event
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'g.db')))
    try:
        state.siming_runtime = SimingRuntime()
        owner = coordinator(state)
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now + 60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        if change == 'actor':
            state.siming_runtime._actor_pin_reader = lambda _: 999
        elif change == 'source':
            state.siming_runtime._source_pin_reader = lambda _: {'changed': True}
        else:
            state.siming_runtime._policy.UNSAFE_REASON_TAGS = set(state.siming_runtime._policy.UNSAFE_REASON_TAGS) | {'new_policy'}
        applied = owner.resume_committed(key, now=now)
        assert len(applied.entry.transition.receipts) == len(applied.entry.transition.effects)
        refused = owner.prepare_provider(key, now=now)
        assert refused.status == 'zero_write'
        assert refused.reason == 'stale_pin'
        assert state.siming_runtime.pending_count == 0
        assert owner.admissions.read(key).entry.state == 'stale'
    finally:
        state.close()


@pytest.mark.parametrize('change', ['resource', 'fatigue'])
def test_unsubmitted_adaptive_request_rejects_changed_resource_inputs(adaptive_state, change):
    import time
    from test_siming_continuation import _adaptive_input
    runtime = adaptive_state.siming_runtime
    owner = SimingCoordinator(runtime=runtime, graph=adaptive_state.graph,
        admissions=SimingAdmissionService(SimingHeavenlyMemoryService(adaptive_state.graph)),
        invalidation_reader=lambda _: None)
    now = time.time()
    key = owner.admit_event(_adaptive_input().source_event, now=now, expires_at=now + 60, policy_version='v1').entry.key
    owner.begin(key, now=now)
    owner.resume_committed(key, now=now)
    if change == 'resource':
        runtime.heavenly_support._resources.set_cooldown('unified_3d_validation', until=1000)
    else:
        runtime.heavenly_support._resources._recent_signatures.append('external')
    rejected = owner.prepare_provider(key, now=now)
    assert rejected.status == 'zero_write' and rejected.reason == 'stale_pin'
    assert runtime.pending_count == 0


def test_provider_self_write_exception_requires_exact_last_frozen_node(tmp_path):
    import time
    from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch
    state = main.build_runtime_state(Settings(siming_heavenly_mode='active', heavenly_graph_path=str(tmp_path / 'g.db')))
    try:
        owner = coordinator(state)
        graph = state.heavenly_graph
        now = time.time()
        key = owner.admit_event(_authority_destruction_event(), now=now, expires_at=now + 60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        plan = owner.read_plan(key)
        applied = owner.resume_committed(key, now=now)
        assert len(plan.effects.batches) >= 13
        assert owner._provider_plan_pin_is_current(applied.entry, plan)
        batch = plan.effects.batches[-1]
        node = graph.get_node(scope=batch.scope, node_id=batch.nodes[-1].node_id, valid_at=batch.nodes[-1].validity.valid_from)
        changed = node.model_copy(update={'revision': node.revision + 1, 'supersedes_revision': node.revision,
            'attributes': {**node.attributes, 'external_change': True}})
        graph.write_batch(HeavenlyGraphWriteBatch(scope=batch.scope, transaction_id='external:after-prefix',
            idempotency_key='external:after-prefix', nodes=[changed]))
        assert not owner._provider_plan_pin_is_current(applied.entry, plan)
        assert graph.get_node(scope=batch.scope, node_id=node.node_id, valid_at=node.validity.valid_from) == changed
    finally:
        state.close()


@pytest.mark.parametrize('cut', ['none', 'publisher', 'receipt', 'publishing_missing_pipeline', 'unknown_missing_pipeline', 'child', 'child_receipt', 'child_ttl', 'child_ttl_missing'])
def test_completed_provider_plan_freezes_outputs_and_stable_child_deliveries_before_publish(tmp_path, monkeypatch, cut):
    import time
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_event_pipeline import SimingEventPipeline
    from app.services.siming_event_consumer import SimingEventConsumer
    from app.services.siming_event_producer import SimingEventProducer
    from app.services.siming_audit_writer import SimingAuditWriter
    from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    from app.services.siming_continuation import run_siming_provider
    from test_siming_continuation import ThreadProvider, make_candidate, make_visual_fact_event
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'g.db')))
    try:
        state.siming_runtime = SimingRuntime(llm_provider=ThreadProvider([make_candidate(target_environment_id=None)]))
        bus = InMemoryAuthorityEventBus()
        published = []
        bus.subscribe('*', lambda event: published.append(event))
        pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(), runtime=state.siming_runtime,
            producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter(),
            character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=state.character_agent_runtime))
        owner = coordinator(state)
        owner.output_pipeline = pipeline
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now + 60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        owner.resume_committed(key, now=now)
        job = owner.prepare_provider(key, now=now).job
        owner.accept_provider(key, job, run_siming_provider(state.siming_runtime._llm_provider, job.request_json), now=now)
        committed = owner.freeze_result(key, now=now)
        effects = committed.entry.transition.effects
        assert published == []
        publication = [effect for effect in effects if effect.kind == 'publish_event']
        deliveries = [effect for effect in effects if effect.kind == 'character_delivery']
        assert publication and deliveries, owner.read_plan(key).after.result.model_dump()
        assert deliveries[0].payload['delivery']['actor_id'] == 'char_b'
        assert deliveries[0].payload['event']['event_id'] in {item.payload['event']['event_id'] for item in publication}
        assert owner.read_plan(key).after.stage == 'completed'
        if cut in {'publisher', 'publishing_missing_pipeline', 'unknown_missing_pipeline'}:
            original = pipeline._producer.publish_events
            def fail_after_publish(events):
                original(events)
                raise OSError('publisher interrupted')
            monkeypatch.setattr(pipeline._producer, 'publish_events', fail_after_publish)
        if cut == 'receipt':
            original_advance = owner.admissions.advance
            def fail_receipt(*args, **kwargs):
                if any(item.effect_key == publication[0].effect_key for item in kwargs['transition'].receipts):
                    raise OSError('receipt interrupted')
                return original_advance(*args, **kwargs)
            monkeypatch.setattr(owner.admissions, 'advance', fail_receipt)
        if cut not in {'none', 'child', 'child_receipt', 'child_ttl', 'child_ttl_missing'}:
            with pytest.raises(OSError, match='interrupted'):
                owner.resume_committed(key, now=now)
            monkeypatch.undo()
            state.close()
            state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'g.db')))
            # 新协调器只接受原持久回执；不把进程内 bus 记录假装成跨重启证明。
            owner = coordinator(state)
            owner.output_pipeline = pipeline
            count = len(published)
            if cut == 'unknown_missing_pipeline':
                owner.resume_committed(key, now=now)
            if cut.endswith('missing_pipeline'):
                owner.output_pipeline = None
                unavailable = owner.resume_committed(key, now=now)
                assert unavailable.entry.transition.reason in {'publishing:' + publication[0].effect_key,
                    'authority_unknown:' + publication[0].effect_key}
                owner.output_pipeline = pipeline
            recovered = owner.resume_committed(key, now=now)
            assert recovered.entry.state == 'commit_started'
            assert recovered.entry.transition.reason == 'authority_unknown:' + publication[0].effect_key
            assert len(published) == count == 1
            assert not any(item.effect_key == publication[0].effect_key for item in recovered.entry.transition.receipts)
            assert owner.admissions.read_room_head(key.scope).completed_sequence == 0
            return
        outstanding = owner.resume_committed(key, now=now)
        assert outstanding.entry.state == 'commit_started'
        assert outstanding.entry.transition.reason == 'character_admission_unavailable'
        assert {event.event_id for event in published} == {item.payload['event']['event_id'] for item in publication}
        count = len(published)
        owner.resume_committed(key, now=now)
        assert len(published) == count
        assert owner.admissions.read_room_head(key.scope).completed_sequence == 0
        if cut in {'child', 'child_receipt', 'child_ttl', 'child_ttl_missing'}:
            from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
            from app.character_agent.storage.session_store import CharacterAgentSessionStore
            child_path = tmp_path / 'child.sqlite3'
            def children():
                session = CharacterAgentSessionStore(database_path=child_path)
                session.initialize_recovery()
                return session, CharacterCognitionAdmissionService(store=session, assert_owner=lambda: None,
                    validate_source=lambda _: None, activation_is_current=lambda *_: False,
                    delivery_pin_reader=lambda *_: {'source': 1, 'actor': 1})
            session, owner.character_admissions = children()
            try:
                if cut in {'child_receipt', 'child_ttl'}:
                    original_advance = owner.admissions.advance
                    def lose_parent_receipt(*args, **kwargs):
                        if any(item.effect_key == deliveries[0].effect_key for item in kwargs['transition'].receipts):
                            raise OSError('child committed parent interrupted')
                        return original_advance(*args, **kwargs)
                    monkeypatch.setattr(owner.admissions, 'advance', lose_parent_receipt)
                    with pytest.raises(OSError, match='child committed parent interrupted'):
                        owner.resume_committed(key, now=now)
                    assert len(owner.character_admissions.list_pending()) == 1
                    session.close()
                    state.close()
                    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'g.db')))
                    owner = coordinator(state)
                    owner.output_pipeline = pipeline
                    session, owner.character_admissions = children()
                child_writes = session._connection.total_changes
                if cut.startswith('child_ttl'):
                    def no_new_child(**kwargs):
                        raise AssertionError('expiry may only point-read existing child receipt')
                    monkeypatch.setattr(owner.character_admissions, 'admit_delivery', no_new_child)
                final = owner.resume_committed(key, now=now + 61 if cut.startswith('child_ttl') else now)
                if cut.startswith('child_ttl'):
                    assert session._connection.total_changes == child_writes
                if cut == 'child_ttl_missing':
                    assert final.entry.state == 'stale'
                    assert deliveries[0].effect_key in final.entry.transition.reason
                    assert owner.character_admissions.list_pending() == ()
                    assert session.event_count('char_b') == 0 and len(published) == count
                    return
                assert final.entry.state == 'completed'
                assert owner.admissions.read_room_head(key.scope).completed_sequence == 1
                children = owner.character_admissions.list_pending()
                assert len(children) == len(deliveries)
                receipt = next(item.receipt for item in final.entry.transition.receipts if item.effect_key == deliveries[0].effect_key)
                assert receipt == {'child_key': children[0].child_key, 'input_digest': children[0].input_digest}
                assert children[0].state == 'admitted' and session.event_count('char_b') == 0
                assert owner.resume_committed(key, now=now).entry == final.entry
                original_completion = owner.admissions.read(key, revision=committed.entry.result_revision).entry.transition.completion_json
                assert owner.finish_ready(key, job, original_completion,
                    provider_revision=committed.entry.provider_revision, now=now).entry == final.entry
                assert len(published) == count
            finally:
                session.close()
    finally:
        state.close()
