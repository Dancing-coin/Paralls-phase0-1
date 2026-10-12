from sys import getsizeof

import pytest
from pydantic import ValidationError

from app.models.siming_event import SimingTickResult
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_runtime import SimingRuntime
from test_siming_behavior_correlation_retention import ExistingTurns, population_turn
from test_siming_population_capability import cadence_event


def retained_bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = getsizeof(value)
    if isinstance(value, dict):
        return size + sum(retained_bytes(key, seen) + retained_bytes(item, seen)
            for key, item in value.items())
    if isinstance(value, (set, tuple)):
        return size + sum(retained_bytes(item, seen) for item in value)
    return size


def test_real_public_and_organization_correlations_retain_less_than_1100000_bytes():
    runtime = SimingRuntime(behavior_turn_recorder=ExistingTurns())
    event = cadence_event()
    for window in range(7200):
        for correlation in (f'population-runtime:cadence:world:bakery-district:{window}',
                            f'cadence:world:bakery-district:{window}:organization-due'):
            population_turn(runtime, event.model_copy(update={'correlation_id': correlation}))
    assert len(runtime._recorded_behavior_turn_correlations) == 14400
    assert retained_bytes((runtime._recorded_behavior_turn_correlations,
        getattr(runtime, '_behavior_correlation_prefixes', {}))) < 1_100_000


class CountingExistingTurns(ExistingTurns):
    def __init__(self):
        self.requests = []
        self.fail_once = False

    def has_recorded_turn(self, request):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError('recorder_unavailable')
        self.requests.append(request)
        return True


def record(runtime, correlation, population):
    event = cadence_event().model_copy(update={'correlation_id': correlation})
    if population:
        population_turn(runtime, event)
    else:
        runtime._record_behavior_turn(event, None, SimingTickResult())


@pytest.mark.parametrize('population_first', [False, True])
def test_lossless_numeric_keys_deduplicate_only_identical_correlations(population_first):
    recorder = CountingExistingTurns()
    runtime = SimingRuntime(behavior_turn_recorder=recorder)
    correlations = [
        'population-runtime:cadence:world:a:0', 'cadence:world:a:0',
        'population-runtime:cadence:world:a:1', 'population-runtime:cadence:world:b:1',
        'population-runtime:cadence:world:a:1:domain', 'cadence:world:a:1:organization-due',
        'cadence:world:a:1:domain', 'cadence:world:a:01', 'cadence:world:a:+1',
        'cadence:world:a:-1', 'cadence:world:a:١', 'cadence:world:a:1:é',
        'cadence:world:a:1:e\u0301', 'cadence:world:a\x00:1', 'cadence:world:a:1:\x00',
        'cadence:world:a:1:', 'cadence:world:a:1:0', 'cadence:world:a:1:00',
        'cadence:world:a:' + '9' * 5000,
        *[f'cadence:prefix:{index}:1:due' for index in range(80)],
    ]
    for correlation in correlations:
        record(runtime, correlation, population_first)
    for correlation in reversed(correlations):
        record(runtime, correlation, not population_first)
    assert [request.provenance.correlation_id for request in recorder.requests] == correlations
    assert len(runtime._recorded_behavior_turn_correlations) == len(correlations)


@pytest.mark.parametrize('population', [False, True])
def test_failed_recorder_does_not_admit_correlation_and_retry_records_it(population):
    recorder = CountingExistingTurns()
    recorder.fail_once = True
    runtime = SimingRuntime(behavior_turn_recorder=recorder)
    correlation = 'population-runtime:cadence:world:retry:12:due'
    with pytest.raises(RuntimeError, match='recorder_unavailable'):
        record(runtime, correlation, population)
    assert not runtime._recorded_behavior_turn_correlations
    assert not getattr(runtime, '_behavior_correlation_prefixes', {})
    record(runtime, correlation, not population)
    record(runtime, correlation, population)
    assert len(recorder.requests) == 1


def test_invalid_unicode_does_not_admit_numeric_prefix():
    runtime = SimingRuntime(behavior_turn_recorder=ExistingTurns())
    with pytest.raises(ValidationError, match='string_unicode'):
        record(runtime, 'population-runtime:cadence:world:\ud800:12', True)
    assert not runtime._recorded_behavior_turn_correlations
    assert not getattr(runtime, '_behavior_correlation_prefixes', {})


@pytest.mark.parametrize('population_first', [False, True])
@pytest.mark.parametrize('correlation', ['population-runtime:cadence:world:a:17',
    'cadence:world:a:17:organization-due', 'cadence:world:a:17:é'])
def test_compacted_correlation_preserves_first_persisted_anchor(population_first, correlation):
    graph = InMemoryHeavenlyGraphAdapter()
    scope = lambda event: HeavenlyGraphScope(world_id='world:demo', session_id='session:demo',
        story_branch_id='branch:main', scene_id=event.scene_id)
    runtime = SimingRuntime(behavior_turn_recorder=BehaviorTurnRecorder(graph),
        behavior_turn_scope_resolver=scope)
    first = cadence_event().model_copy(update={'correlation_id': correlation})
    later = first.model_copy(update={'event_id': 'event:later', 'scene_id': 'scene:later'})
    ordinary = lambda event: runtime._record_behavior_turn(event, None, SimingTickResult())
    if population_first:
        population_turn(runtime, first)
        ordinary(later)
    else:
        ordinary(first)
        population_turn(runtime, later)
    suffix = ':population-compact:v1' if population_first else ''
    anchor_id = f'behavior-turn:siming:{correlation}{suffix}'
    anchor = graph.get_node_revision(node_id=anchor_id, scope=scope(first), revision=1)
    assert anchor.provenance.source_ref == first.event_id
    assert anchor.attributes['correlation_id'] == correlation
    assert graph.get_node_revision(node_id=anchor_id, scope=scope(later), revision=1) is None
