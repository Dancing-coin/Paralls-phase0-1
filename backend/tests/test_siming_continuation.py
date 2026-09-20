from concurrent.futures import ThreadPoolExecutor
from threading import get_ident

import pytest

from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime
from test_siming_llm_runtime import make_visual_fact_event, make_candidate


class ThreadProvider:
    def __init__(self, candidates=None):
        self.calls = []
        self.candidates = candidates or []

    def generate_candidates(self, **kwargs):
        self.calls.append((get_ident(), kwargs))
        return self.candidates


def test_candidate_freeze_worker_resume_and_serialized_frame():
    from app.services.siming_continuation import run_siming_provider

    provider = ThreadProvider([make_candidate()])
    actor_versions = {"char_b": 1}
    runtime = SimingRuntime(llm_provider=provider, actor_pin_reader=lambda actor: actor_versions.get(actor, 0), source_pin_reader=lambda event: {"valid": True})
    item = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    advance = runtime.prepare_tick(item)
    assert advance.status == "pending"
    assert provider.calls == []
    frozen = runtime.export_turn(advance.job.turn_id)
    assert isinstance(frozen, bytes)
    with ThreadPoolExecutor(max_workers=1) as pool:
        completion = pool.submit(run_siming_provider, provider, advance.job.request_json).result()
    assert provider.calls[0][0] != get_ident()
    finished = runtime.commit_provider_result(advance.job, completion)
    assert finished.status == "completed"
    assert any(output.output_type == "dispatch_intent" for output in finished.result.outputs)
    replay = runtime.commit_provider_result(advance.job, completion)
    assert replay.replayed and replay.result == finished.result
    assert runtime.pending_count == 0


def test_candidate_requires_readers_and_stale_has_no_fallback():
    from app.services.siming_continuation import run_siming_provider

    item = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    with pytest.raises(ValueError, match="pin_reader"):
        SimingRuntime().prepare_tick(item)
    versions = {"char_b": 1}
    provider = ThreadProvider()
    runtime = SimingRuntime(llm_provider=provider, actor_pin_reader=lambda actor: versions.get(actor, 0), source_pin_reader=lambda event: True)
    advance = runtime.prepare_tick(item)
    completion = run_siming_provider(provider, advance.job.request_json)
    versions["char_b"] = 2
    result = runtime.commit_provider_result(advance.job, completion)
    assert result.status == "zero_write" and result.reason == "stale_pin"
    assert result.result is None
    assert runtime.pending_count == 0

@pytest.mark.parametrize("mode", ["empty", "timeout", "invalid"])
def test_candidate_sync_and_staged_domain_results_match(mode):
    from app.services.siming_continuation import run_siming_provider
    from app.services.siming_llm_provider import SimingLlmProviderTimeout, SimingLlmProviderInvalidOutput

    class Provider(ThreadProvider):
        def generate_candidates(self, **kwargs):
            if mode == "timeout":
                raise SimingLlmProviderTimeout("timeout")
            if mode == "invalid":
                raise SimingLlmProviderInvalidOutput("invalid")
            return []

    item = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    expected = SimingRuntime(llm_provider=Provider()).tick([item])
    provider = Provider()
    runtime = SimingRuntime(llm_provider=provider, actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(item)
    actual = runtime.commit_provider_result(pending.job, run_siming_provider(provider, pending.job.request_json))
    assert actual.result == expected
    assert runtime._narrative_core._revision_by_room == {"room_demo": 1}


def test_completion_must_run_on_owner():
    from app.services.siming_continuation import run_siming_provider
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event()))
    completion = run_siming_provider(runtime._llm_provider, pending.job.request_json)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match="owner_thread"):
            pool.submit(runtime.commit_provider_result, pending.job, completion).result()
    assert runtime.pending_count == 1
    assert runtime.commit_provider_result(pending.job, completion).status == "completed"


def test_restore_frame_does_not_replay_prefix_and_rejects_old_token():
    from app.services.siming_continuation import run_siming_provider
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event()))
    frozen = runtime.export_turn(pending.job.turn_id)
    assert runtime.cancel_turn(pending.job.turn_id)
    restored = runtime.restore_turn(frozen)
    assert restored.job.token != pending.job.token
    completion = run_siming_provider(runtime._llm_provider, restored.job.request_json)
    assert runtime.commit_provider_result(pending.job, completion).status == "zero_write"
    assert runtime.commit_provider_result(restored.job, completion).status == "completed"
    assert runtime._narrative_core._revision_by_room == {"room_demo": 1}

@pytest.fixture
def adaptive_state():
    from types import SimpleNamespace
    from test_siming_adaptive_bridge import _bridge_setup, _proposal, _audit
    from app.models.siming_adaptive_bridge import GeneratedAdaptiveBridgeProposalBatch
    from app.services.siming_context_compiler import SimingContextCompiler
    from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
    from app.services.siming_heavenly_runtime_support import SimingHeavenlyRuntimeSupport
    from app.services.siming_story_node_staging import SimingStoryNodeStaging
    from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
    from app.services.siming_adaptive_bridge import SimingAdaptiveBridge
    setup = _bridge_setup()
    bridge = setup.bridge
    memory = SimingHeavenlyMemoryService(setup.graph)
    provider = FakeSimingLlmCandidateProvider([], adaptive_bridge_proposal_batch=GeneratedAdaptiveBridgeProposalBatch(proposals=[_proposal()], audit=_audit()))
    def bridges(context):
        return SimingAdaptiveBridge(graph=setup.graph, compiled_context=context,
            story_runtime=bridge._story_runtime, obligations=bridge._obligations,
            resources=bridge._resources, actor_memory_gateway=bridge._actor_memory_gateway,
            actor_autonomy=lambda _: True)
    support = SimingHeavenlyRuntimeSupport(mode="active", memory=memory,
        compiler=SimingContextCompiler(setup.graph), actor_memory=bridge._actor_memory_gateway,
        story=bridge._story_runtime, obligations=bridge._obligations, resources=bridge._resources,
        staging=SimingStoryNodeStaging(bridge._story_runtime, memory, bridge._obligations),
        bridges=bridges, llm_provider=provider)
    support._seed_node_ids = lambda event: ["fact:letter:destroyed", "obligation:O6"]
    runtime = SimingRuntime(heavenly_support=support, actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    try:
        yield SimpleNamespace(siming_runtime=runtime, graph=setup.graph, scope=setup.scope)
    finally:
        bridge._actor_memory_gateway._runtime.close()


def test_adaptive_worker_only_provider_and_owner_bridge(adaptive_state):
    from app.services.siming_continuation import run_siming_provider
    from test_siming_heavenly_runtime_composition import _destruction_input, _AcceptedBridge
    runtime = adaptive_state.siming_runtime
    support = runtime.heavenly_support
    writes = []
    original = support._bridges
    def make_bridge(context):
        bridge = original(context)
        original_validate = bridge.plan_commit
        def validate(*args, **kwargs):
            writes.append(get_ident())
            return original_validate(*args, **kwargs)
        bridge.plan_commit = validate
        return bridge
    support._bridges = make_bridge
    pending = runtime.prepare_tick(_adaptive_input())
    assert pending.job.stage == "adaptive"
    assert writes == []
    with ThreadPoolExecutor(max_workers=1) as pool:
        completion = pool.submit(run_siming_provider, support._llm_provider, pending.job.request_json).result()
    assert writes == []
    actual = runtime.commit_provider_result(pending.job, completion)
    assert actual.status == "completed"
    assert writes == [get_ident()]
    assert any(item.output_type == "staging_request" for item in actual.result.outputs)
    assert runtime.commit_provider_result(pending.job, completion).replayed
    assert writes == [get_ident()]


@pytest.mark.parametrize("change", ["resource", "fatigue", "actor", "source", "unrelated_actor"])
def test_adaptive_pins_reject_related_changes_only(adaptive_state, change):
    from app.services.siming_continuation import run_siming_provider
    from test_siming_heavenly_runtime_composition import _destruction_input
    runtime = adaptive_state.siming_runtime
    support = runtime.heavenly_support
    versions = {"char_b": 1, "char_c": 1, "unrelated": 1}
    source = {"revision": 1}
    runtime._actor_pin_reader = lambda actor: versions.get(actor, 0)
    runtime._source_pin_reader = lambda event: source
    pending = runtime.prepare_tick(_adaptive_input())
    completion = run_siming_provider(support._llm_provider, pending.job.request_json)
    if change == "resource":
        support._resources.set_cooldown("unified_3d_validation", until=1000)
    elif change == "fatigue":
        support._resources._recent_signatures.append("other")
    elif change == "actor":
        versions["char_c"] += 1
    elif change == "source":
        source["revision"] += 1
    else:
        versions["unrelated"] += 1
    outcome = runtime.commit_provider_result(pending.job, completion)
    assert outcome.status == ("completed" if change == "unrelated_actor" else "zero_write")
    if change != "unrelated_actor":
        assert outcome.reason == "stale_pin" and outcome.result is None


def _adaptive_input():
    from test_siming_heavenly_runtime_composition import _destruction_input
    item = _destruction_input()
    item.source_event.routing.target_ids = ["siming"]
    item.source_event.room_id = "room:throne"
    return item


def test_adaptive_output_cannot_expand_frozen_actor_or_graph_read_set(adaptive_state):
    from app.services.siming_continuation import run_siming_provider, SimingProviderCompletion
    runtime = adaptive_state.siming_runtime
    pending = runtime.prepare_tick(_adaptive_input())
    completion = SimingProviderCompletion.model_validate_json(run_siming_provider(runtime.heavenly_support._llm_provider, pending.job.request_json))
    completion.proposal_batch.proposals[0].attractor_refs.append("not-in-frozen-graph")
    outcome = runtime.commit_provider_result(pending.job, completion.model_dump_json().encode())
    assert outcome.status == "zero_write" and outcome.reason == "outside_frozen_read_set"
    assert runtime.heavenly_support._story.read_runtime_node(scope=adaptive_state.scope, node_id="runtime:bridge:proposal:private-confrontation:1", valid_at=100) is None


def test_adaptive_empty_graph_read_set_does_not_pin_unrelated_nodes(adaptive_state, monkeypatch):
    from app.models.siming_heavenly_graph import NodeLookupQuery
    runtime = adaptive_state.siming_runtime
    support = runtime.heavenly_support
    support._seed_node_ids = lambda _: []
    original = adaptive_state.graph.query_semantic

    def guarded_semantic(query):
        if isinstance(query, NodeLookupQuery) and not query.node_ids and not query.node_types:
            pytest.fail("empty graph read set must not query unrelated semantic nodes")
        return original(query)

    monkeypatch.setattr(adaptive_state.graph, "query_semantic", guarded_semantic)
    pending = runtime.prepare_tick(_adaptive_input())
    frozen = runtime._siming_pending[pending.job.turn_id].pin["heavenly"]
    assert frozen["graph"]["nodes"] == []
    assert frozen["graph"]["relations"] == []
    assert frozen["semantic"]["nodes"] == []
    assert frozen["semantic"]["incomplete"] is None


def test_expired_serialized_frame_cannot_acquire_fresh_lifetime(monkeypatch):
    import json
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event()))
    frozen = runtime.export_turn(pending.job.turn_id)
    runtime.cancel_turn(pending.job.turn_id)
    monkeypatch.setattr("app.services.siming_runtime.time.time", lambda: 10**15)
    assert runtime.restore_turn(frozen).status == "zero_write"

@pytest.mark.parametrize("change", ["node", "relation", "missing_member"])
def test_adaptive_full_graph_pin_includes_revision_and_membership(adaptive_state, change):
    from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch, HeavenlyGraphNode, HeavenlyGraphRelation, GraphValidity
    from test_siming_adaptive_bridge import _provenance
    from app.services.siming_continuation import run_siming_provider
    runtime = adaptive_state.siming_runtime
    scope, graph = adaptive_state.scope, adaptive_state.graph
    support = runtime.heavenly_support
    support._seed_node_ids = lambda _: ["fact:letter:destroyed", "obligation:O6", "missing"]
    pending = runtime.prepare_tick(_adaptive_input())
    completion = run_siming_provider(support._llm_provider, pending.job.request_json)
    frozen_graph = runtime._siming_pending[pending.job.turn_id].pin["heavenly"]["graph"]
    nodes, relations = [], []
    if change == "node":
        existing = next(node for node in frozen_graph["nodes"] if node["node_id"] == "story_obligation:O6")
        node = HeavenlyGraphNode.model_validate(existing)
        node.revision, node.supersedes_revision = 2, 1
        node.attributes["description"] = "corrected non-memory node"
        nodes.append(node)
    elif change == "relation":
        relations.append(HeavenlyGraphRelation(relation_id="new:relation", relation_type="CAUSED_BY", source_node_id="fact:letter:destroyed", target_node_id="story_obligation:O6", scope=scope, validity=GraphValidity(valid_from=100), recorded_at=100, revision=1, provenance=_provenance("new:relation")))
    else:
        nodes.append(HeavenlyGraphNode(node_id="missing", node_type="runtime_story_node", scope=scope, validity=GraphValidity(valid_from=100), recorded_at=100, revision=1, provenance=_provenance("missing")))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id=f"test:{change}", idempotency_key=f"test:{change}", scope=scope, nodes=nodes, relations=relations))
    outcome = runtime.commit_provider_result(pending.job, completion)
    assert outcome.status == "zero_write" and outcome.reason == "stale_pin"
    assert support._story.read_runtime_node(scope=scope, node_id="runtime:bridge:proposal:private-confrontation:1", valid_at=100) is None


def test_interleaved_rooms_keep_explicit_event_and_prepared():
    from app.services.siming_continuation import run_siming_provider
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    recorded = []
    runtime._record_behavior_turn = lambda event, prepared, result: recorded.append((event.event_id, event.room_id, prepared, result.read_model.room_id))
    a = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    b = a.model_copy(deep=True)
    b.source_event.event_id, b.source_event.room_id = "other-source", "other-room"
    b.source_event.payload["established_fact_id"] = "other-source"
    first, second = runtime.prepare_tick(a), runtime.prepare_tick(b)
    for pending in [second, first]:
        outcome = runtime.commit_provider_result(pending.job, run_siming_provider(runtime._llm_provider, pending.job.request_json))
        assert outcome.status == "completed"
    assert recorded == [("other-source", "other-room", None, "other-room"), (a.source_event.event_id, "room_demo", None, "room_demo")]


@pytest.mark.parametrize("termination", ["cancel", "reset", "deadline"])
def test_cancel_reset_deadline_are_zero_write_not_provider_fallback(monkeypatch, termination):
    from app.services.siming_continuation import run_siming_provider
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event()))
    completion = run_siming_provider(runtime._llm_provider, pending.job.request_json)
    before = list(runtime._pending_observatory_messages)
    if termination == "cancel":
        runtime.cancel_turn(pending.job.turn_id)
    elif termination == "reset":
        runtime.reset_turns()
    else:
        monkeypatch.setattr("app.services.siming_runtime.time.monotonic", lambda: pending.job.deadline + 1)
    outcome = runtime.commit_provider_result(pending.job, completion)
    assert outcome.status == "zero_write" and outcome.result is None
    assert runtime._pending_observatory_messages == before
    assert runtime.pending_count == 0


def test_pure_read_pin_exception_releases_pending_and_preserves_error():
    from app.services.siming_continuation import run_siming_provider
    failure = [False]
    def source_reader(event):
        if failure[0]:
            raise OSError("source unavailable")
        return True
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=source_reader)
    item = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    pending = runtime.prepare_tick(item)
    completion = run_siming_provider(runtime._llm_provider, pending.job.request_json)
    failure[0] = True
    with pytest.raises(OSError, match="source unavailable"):
        runtime.commit_provider_result(pending.job, completion)
    assert runtime.pending_count == 0
    failure[0] = False
    assert runtime.prepare_tick(item).status == "pending"


def test_same_correlation_other_scope_cannot_replace_adaptive_prepared(adaptive_state):
    from app.services.siming_continuation import run_siming_provider
    runtime = adaptive_state.siming_runtime
    support = runtime.heavenly_support
    pending = runtime.prepare_tick(_adaptive_input())
    other = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    other.source_event.correlation_id = "corr:destroy:1"
    other_prepared = support.prepare(other)
    assert other_prepared.scope.room_id == "room_demo"
    completion = run_siming_provider(support._llm_provider, pending.job.request_json)
    outcome = runtime.commit_provider_result(pending.job, completion)
    assert outcome.status == "completed"
    request = next(item for item in outcome.result.outputs if item.output_type == "staging_request")
    assert request.room_id == "room:throne"
    assert support._story.read_runtime_node(scope=adaptive_state.scope, node_id="runtime:bridge:proposal:private-confrontation:1", valid_at=100).lifecycle == "selected"


def test_pending_and_receipt_bounds_and_same_room_sync_busy():
    from app.services.siming_continuation import run_siming_provider
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    def item(index):
        result = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
        result.source_event.room_id = f"room:{index}"
        return result
    pending = [runtime.prepare_tick(item(index)) for index in range(4)]
    with pytest.raises(ValueError, match="pending_full"):
        runtime.prepare_tick(item(4))
    with pytest.raises(ValueError, match="room_busy"):
        runtime.tick([item(0)])
    assert runtime.pending_count == 4
    for value in pending:
        runtime.cancel_turn(value.job.turn_id)
    for index in range(40):
        value = runtime.prepare_tick(item(index + 10))
        completion = run_siming_provider(runtime._llm_provider, value.job.request_json)
        assert runtime.commit_provider_result(value.job, completion).status == "completed"
    assert len(runtime._siming_receipts) == 32 and runtime.pending_count == 0


@pytest.mark.parametrize('error_name', ['SimingLlmProviderTimeout', 'SimingLlmProviderInvalidOutput', 'SimingLlmProviderError'])
def test_adaptive_error_completes_no_action_without_legacy_fallback(adaptive_state, error_name):
    from app.services.siming_continuation import run_siming_provider
    from app.services import siming_llm_provider
    runtime = adaptive_state.siming_runtime
    class TimeoutProvider:
        def generate_adaptive_bridge_proposals(self, **kwargs):
            raise getattr(siming_llm_provider, error_name)("unavailable")
    runtime.heavenly_support._llm_provider = TimeoutProvider()
    item = _adaptive_input()
    item.input_type = "visual_fact_event"
    item.source_event.event_type = "visual_fact_event"
    item.source_event.payload.update(fact_type="light_level_drop", established_fact_id=item.source_event.event_id)
    pending = runtime.prepare_tick(item)
    completion = run_siming_provider(runtime.heavenly_support._llm_provider, pending.job.request_json)
    accepted = runtime.validate_completion(pending.job, completion)
    plan = runtime.plan_accepted(runtime.export_turn(pending.job.turn_id), accepted.completion)
    reason = f'llm_unavailable:{error_name}'
    assert plan.after.stage == 'completed'
    assert plan.effects.state_tree is None and plan.effects.narrative_state is None
    assert plan.after.result.outputs[-1].output_type == 'no_action'
    assert plan.after.result.outputs[-1].payload['reason'] == reason
    assert not any(output.output_type in {'dispatch_intent', 'staging_request'} for output in plan.after.result.outputs)
    assert plan.after.result.audit_records[-1].reason == reason
    next_stage = runtime.commit_provider_result(pending.job, completion)
    assert next_stage.status == 'completed' and next_stage.job is None
    assert next_stage.result == plan.after.result
    replay = runtime.commit_provider_result(pending.job, completion)
    assert replay.replayed and replay.result == next_stage.result
    assert runtime._narrative_core._revision_by_room == {}
    assert runtime.pending_count == 0


@pytest.mark.parametrize('mode,owned', [('active', True), ('shadow', True), ('off', True), ('active', False)])
@pytest.mark.parametrize('synchronous', [False, True])
def test_graph_failure_only_stops_active_owned_family(adaptive_state, monkeypatch, mode, owned, synchronous):
    runtime = adaptive_state.siming_runtime
    runtime.heavenly_support.mode = mode
    def unavailable(*args, **kwargs):
        raise RuntimeError('graph unavailable')
    monkeypatch.setattr(runtime.heavenly_support._compiler, 'compile', unavailable)
    item = _adaptive_input() if owned else SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event())
    if synchronous:
        result = runtime.tick([item])
    else:
        plan = runtime.plan_initial(item)
        result = plan.after.result
        assert (plan.effects.state_tree is None) == (mode == 'active' and owned)
    degraded = [output for output in result.outputs if output.payload.get('reason') == 'graph_degraded:RuntimeError']
    assert bool(degraded) == (mode == 'active' and owned)
    if mode == 'active' and owned:
        assert result.outputs[-1].output_type == 'no_action'
        assert not any(output.output_type in {'dispatch_intent', 'staging_request'} for output in result.outputs)
        assert runtime._narrative_core._revision_by_room == {}


def test_population_no_model_path_progresses_when_four_decisions_pending():
    from test_siming_population_capability import GenericDefaultRecordingPopulationCapability, cadence_event
    recorder = GenericDefaultRecordingPopulationCapability()
    runtime = SimingRuntime(population_capability=recorder, actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    for index in range(4):
        event = make_visual_fact_event()
        event.room_id = f"room:{index}"
        runtime.prepare_tick(SimingInput(input_type="visual_fact_event", source_event=event))
    event = cadence_event(cadence_id="cadence:cohort:bakery:W0", selector_revision="selector:cohort-bakery:v1", ruleset_revision="rules:cohort-bakery:v1")
    result = runtime.prepare_tick(SimingInput(input_type="population_cadence_input", source_event=event))
    assert result.status == "completed" and recorder.calls == 1
    assert runtime.pending_count == 4


@pytest.mark.parametrize('staged', [False, True])
def test_population_completion_keeps_input_and_recorded_results_independent(staged):
    from copy import deepcopy
    from app.services.behavior_turn_recorder import BehaviorTurnRecorder
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
    from app.services.siming_population_capability import PopulationSimulationCapability
    from test_siming_population_capability import _b0_cadence_and_read_set, cadence_event

    cadence, read_set = _b0_cadence_and_read_set(4)
    event = cadence_event(**{**cadence.model_dump(mode='json'), 'selector_revision': 'selector:generic:population:v1'})
    event.payload['population_projections'] = [row.model_dump(mode='json') for row in read_set.projections]
    item = SimingInput(input_type='population_cadence_input', source_event=event)
    original = item.model_dump_json()
    graph = InMemoryHeavenlyGraphAdapter()
    runtime = SimingRuntime(population_capability=PopulationSimulationCapability(),
        behavior_turn_recorder=BehaviorTurnRecorder(graph))
    result = runtime.prepare_tick(item).result if staged else runtime.tick([item])
    assert any(' b0=4 ' in row.reason for row in result.audit_records)
    assert runtime.pending_count == 0 and item.model_dump_json() == original
    recorded = deepcopy((result, graph._nodes, graph._idempotency))
    assert graph._nodes
    event.payload['population_projections'][0]['payload']['state_deltas']['fatigue'] = 0.99
    event.payload['population_cadence']['policy_revision'] = 'caller-changed'
    assert (result, graph._nodes, graph._idempotency) == recorded


@pytest.mark.parametrize("change_mapping", [False, True])
def test_injected_policy_registry_is_pinned_and_preserves_sync_semantics(change_mapping):
    from app.services.siming_continuation import run_siming_provider
    from app.services.siming_feature_registry import SimingFeatureRegistry
    from app.services.siming_policy import SimingInterventionPolicy

    registry = SimingFeatureRegistry()
    policy = SimingInterventionPolicy(registry)
    candidate = make_candidate(reason_tags=["information_distribution_sensitive"])
    provider = ThreadProvider([candidate])
    item = SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())
    expected = SimingRuntime(llm_provider=provider, policy=policy).tick([item])
    assert not any(output.output_type == "dispatch_intent" for output in expected.outputs)
    runtime = SimingRuntime(llm_provider=provider, policy=policy,
        actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    assert runtime._feature_registry is not registry
    pending = runtime.prepare_tick(item)
    before_messages = list(runtime._pending_observatory_messages)
    if change_mapping:
        registry.register_policy_mapping("information_distribution", "new_rejected_tag", "new_policy")
    outcome = runtime.commit_provider_result(pending.job, run_siming_provider(provider, pending.job.request_json))
    assert runtime.pending_count == 0
    if change_mapping:
        assert outcome.status == "zero_write" and outcome.reason == "stale_pin"
        assert outcome.result is None
        assert runtime._pending_observatory_messages == before_messages
        assert runtime._narrative_core._revision_by_room == {"room_demo": 1}
    else:
        assert outcome.status == "completed" and outcome.result == expected


def test_adaptive_support_plan_freezes_records_before_any_graph_write(adaptive_state):
    from app.services.siming_continuation import SimingProviderCompletion, run_siming_provider
    from copy import deepcopy
    runtime = adaptive_state.siming_runtime
    source = _adaptive_input()
    pending = runtime.prepare_tick(source)
    support = runtime.heavenly_support
    completion = SimingProviderCompletion.model_validate_json(run_siming_provider(support._llm_provider, pending.job.request_json))
    frame = runtime._siming_pending[pending.job.turn_id]
    before = deepcopy((adaptive_state.graph._nodes, adaptive_state.graph._idempotency))
    plan = support.plan_finish_prepare(frame.heavenly_frame, completion)
    assert (adaptive_state.graph._nodes, adaptive_state.graph._idempotency) == before
    assert plan.prepared.eligible_candidates
    assert len(plan.batches) == 5



def test_selection_plan_uses_frozen_new_node_without_writing_preparation(adaptive_state):
    from copy import deepcopy
    from app.services.siming_continuation import SimingProviderCompletion, run_siming_provider
    runtime = adaptive_state.siming_runtime
    pending = runtime.prepare_tick(_adaptive_input())
    support = runtime.heavenly_support
    completion = SimingProviderCompletion.model_validate_json(run_siming_provider(support._llm_provider, pending.job.request_json))
    plan = support.plan_finish_prepare(runtime._siming_pending[pending.job.turn_id].heavenly_frame, completion)
    node_ref = plan.prepared.eligible_node_refs[0]
    node = next(node for batch in plan.batches for node in batch.nodes if node.node_id == node_ref)
    before = deepcopy((adaptive_state.graph._nodes, adaptive_state.graph._idempotency))
    selected = support.plan_select_for_staging(plan.prepared, node_ref, prior_node=node)
    selected = type(selected).model_validate_json(selected.model_dump_json())
    assert (adaptive_state.graph._nodes, adaptive_state.graph._idempotency) == before
    assert len(selected.batches) == 2
    assert selected.request.node_id == node_ref
    for batch in [*plan.batches, *selected.batches]:
        adaptive_state.graph.write_batch(batch)
    assert support._story.read_runtime_node(scope=node.scope, node_id=node_ref, valid_at=100).lifecycle == 'selected'
    assert support.select_for_staging(plan.prepared, node_ref) == selected.request


def test_siming_behavior_request_freezes_original_correlation_identity():
    from app.models.siming_event import SimingTickResult
    from app.services.behavior_turn_recorder import BehaviorTurnRecorder
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter

    graph = InMemoryHeavenlyGraphAdapter()
    runtime = SimingRuntime(behavior_turn_recorder=BehaviorTurnRecorder(graph))
    event = make_visual_fact_event()
    result = SimingTickResult()
    request = runtime.plan_behavior_turn(event, None, result)
    assert request.idempotency_key == f'siming-behavior-turn:{event.correlation_id}'
    assert request.provenance.source_ref == event.event_id
    assert not graph._nodes
    runtime._record_behavior_turn(event, None, result)
    assert graph.write_batch(runtime._behavior_turn_recorder.plan_record(request)).replayed


def test_completion_validation_is_read_only_before_durable_acceptance():
    from app.services.siming_continuation import run_siming_provider

    versions = {'char_b': 1}
    provider = ThreadProvider([make_candidate()])
    runtime = SimingRuntime(llm_provider=provider, actor_pin_reader=versions.get, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event()))
    frozen = runtime.export_turn(pending.job.turn_id)
    completion = run_siming_provider(provider, pending.job.request_json)
    messages = list(runtime._pending_observatory_messages)
    validated = runtime.validate_completion(pending.job, completion)
    assert validated.status == 'accepted'
    assert runtime.export_turn(pending.job.turn_id) == frozen
    assert runtime._pending_observatory_messages == messages
    assert not runtime._siming_receipts
    versions['char_b'] = 2
    rejected = runtime.validate_completion(pending.job, completion)
    assert rejected.status == 'zero_write' and rejected.reason == 'stale_pin'
    assert runtime.export_turn(pending.job.turn_id) == frozen
    assert runtime.commit_provider_result(pending.job, completion).reason == 'stale_pin'
    assert runtime.pending_count == 0


@pytest.mark.parametrize('mode', ['candidate', 'empty', 'timeout'])
def test_candidate_accepted_plan_is_pure_and_matches_sync_completion(mode):
    from copy import deepcopy
    from app.services.behavior_turn_recorder import BehaviorTurnRecorder
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
    from app.services.siming_continuation import run_siming_provider
    from app.services.siming_llm_provider import SimingLlmProviderTimeout

    class Provider(ThreadProvider):
        def generate_candidates(self, **kwargs):
            if mode == 'timeout':
                raise SimingLlmProviderTimeout('timeout')
            return [make_candidate()] if mode == 'candidate' else []

    graph = InMemoryHeavenlyGraphAdapter()
    runtime = SimingRuntime(llm_provider=Provider(), actor_pin_reader=lambda _: 1,
        source_pin_reader=lambda _: True, behavior_turn_recorder=BehaviorTurnRecorder(graph))
    pending = runtime.prepare_tick(SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event()))
    frozen = runtime.export_turn(pending.job.turn_id)
    completion = run_siming_provider(runtime._llm_provider, pending.job.request_json)
    before = deepcopy((graph._nodes, graph._idempotency, runtime._pending_observatory_messages))
    accepted = runtime.validate_completion(pending.job, completion)
    plan = runtime.plan_accepted(frozen, accepted.completion)
    plan = type(plan).model_validate_json(plan.model_dump_json())
    assert runtime.export_turn(pending.job.turn_id) == frozen
    assert (graph._nodes, graph._idempotency, runtime._pending_observatory_messages) == before
    assert len(plan.effects.batches) == 1
    finished = runtime.commit_provider_result(pending.job, completion)
    assert plan.after.result == finished.result
    assert runtime._pending_observatory_messages[len(before[2]):] == plan.effects.observatory_messages
    assert graph.write_batch(plan.effects.batches[0]).replayed


def test_adaptive_accepted_plan_keeps_all_domain_writes_until_apply(adaptive_state):
    from copy import deepcopy
    from app.services.siming_continuation import run_siming_provider

    runtime = adaptive_state.siming_runtime
    pending = runtime.prepare_tick(_adaptive_input())
    frozen = runtime.export_turn(pending.job.turn_id)
    completion = run_siming_provider(runtime.heavenly_support._llm_provider, pending.job.request_json)
    before = deepcopy((adaptive_state.graph._nodes, adaptive_state.graph._idempotency))
    accepted = runtime.validate_completion(pending.job, completion)
    plan = runtime.plan_accepted(frozen, accepted.completion)
    plan = type(plan).model_validate_json(plan.model_dump_json())
    assert (adaptive_state.graph._nodes, adaptive_state.graph._idempotency) == before
    assert runtime.export_turn(pending.job.turn_id) == frozen
    assert any(output.output_type == 'staging_request' for output in plan.after.result.outputs)
    assert len(plan.effects.batches) >= 7
    finished = runtime.commit_provider_result(pending.job, completion)
    assert finished.result == plan.after.result
    assert all(adaptive_state.graph.write_batch(batch).replayed for batch in plan.effects.batches)


def test_initial_candidate_plan_freezes_narrative_and_derived_state_without_install():
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    item = SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event())
    plan = runtime.plan_initial(item)
    plan = type(plan).model_validate_json(plan.model_dump_json())
    assert plan.after.stage == 'candidate'
    assert runtime.pending_count == 0
    assert runtime._narrative_core._revision_by_room == {}
    assert runtime._state_tree.latest_snapshot is None
    assert runtime._storyline_state.latest_snapshot is None
    assert runtime._obligation_ledger.latest_snapshot is None
    assert runtime._pending_observatory_messages == []
    pending = runtime.prepare_tick(item)
    frame = runtime._siming_pending[pending.job.turn_id]
    assert plan.after.result == frame.result
    assert plan.after.request == frame.request
    restored = SimingRuntime()
    restored.install_planned_state(plan.effects)
    restored.install_planned_state(plan.effects)
    assert restored._narrative_core._revision_by_room == runtime._narrative_core._revision_by_room
    assert restored._state_tree.latest_snapshot == runtime._state_tree.latest_snapshot
    assert restored._storyline_state.latest_snapshot == runtime._storyline_state.latest_snapshot
    assert restored._obligation_ledger.latest_snapshot == runtime._obligation_ledger.latest_snapshot


def test_initial_adaptive_plan_freezes_request_without_registering_pending(adaptive_state):
    from copy import deepcopy
    runtime = adaptive_state.siming_runtime
    before = deepcopy((adaptive_state.graph._nodes, adaptive_state.graph._idempotency))
    plan = runtime.plan_initial(_adaptive_input())
    assert plan.after.stage == 'adaptive'
    assert runtime.pending_count == 0
    assert (adaptive_state.graph._nodes, adaptive_state.graph._idempotency) == before
    pending = runtime.prepare_tick(_adaptive_input())
    frame = runtime._siming_pending[pending.job.turn_id]
    assert plan.after.request == frame.request
    assert plan.after.heavenly_frame == frame.heavenly_frame
    assert plan.after.result == frame.result


@pytest.mark.parametrize('mode', ['off', 'shadow'])
def test_initial_heavenly_non_model_preparation_keeps_planned_records_pure(adaptive_state, mode):
    from copy import deepcopy
    runtime = adaptive_state.siming_runtime
    runtime.heavenly_support.mode = mode
    item = SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event())
    before = deepcopy((adaptive_state.graph._nodes, adaptive_state.graph._idempotency))
    plan = runtime.plan_initial(item)
    assert runtime.pending_count == 0
    assert (adaptive_state.graph._nodes, adaptive_state.graph._idempotency) == before
    pending = runtime.prepare_tick(item)
    frame = runtime._siming_pending[pending.job.turn_id]
    assert plan.after.request == frame.request
    assert plan.after.result == frame.result
    assert all(adaptive_state.graph.write_batch(batch).replayed for batch in plan.effects.batches)


def test_register_planned_turn_preserves_frozen_request_without_replaying_initial(monkeypatch):
    import time
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    plan = runtime.plan_initial(SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event()))
    runtime.install_planned_state(plan.effects)
    before = dict(runtime._narrative_core._revision_by_room)
    monkeypatch.setattr(runtime, '_start_tick', lambda *_: pytest.fail('initial replayed'))
    advance = runtime.register_planned_turn(plan.after.model_dump_json().encode(), expires_at=time.time() + 60)
    assert advance.status == 'pending'
    frame = runtime._siming_pending[advance.job.turn_id]
    assert frame.request == plan.after.request
    assert frame.observed == plan.after.observed
    assert frame.result == plan.after.result
    assert runtime._narrative_core._revision_by_room == before
    assert frame.expires_at <= time.time() + 30
    with pytest.raises(ValueError, match='room_busy'):
        runtime.register_planned_turn(plan.after.model_dump_json().encode(), expires_at=time.time() + 60)
    assert runtime.pending_count == 1
