from sys import getsizeof

import pytest
from pydantic import ValidationError

from app.models.siming_event import SimingTickResult
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_runtime import SimingRuntime
from test_siming_population_capability import (
    RecordingPopulationCapability,
    cadence_event,
    read_set,
)


def population_turn(runtime, event):
    inputs = read_set()
    cycle = RecordingPopulationCapability().run_cycle(inputs.cadence, inputs)
    runtime._record_population_behavior_turn(event, inputs.cadence, inputs, cycle, SimingTickResult())


@pytest.mark.parametrize('population_first', [False, True])
@pytest.mark.parametrize('correlation', ['corr:one', 'corr:\u00e9', 'corr:e\u0301'])
def test_both_behavior_paths_preserve_first_audit_across_scopes(population_first, correlation):
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


class ExistingTurns:
    def has_recorded_turn(self, request):
        return True

    def record(self, request):
        raise AssertionError('an existing turn must not be recorded again')


def test_two_hours_of_population_correlations_use_less_than_1600000_bytes():
    runtime = SimingRuntime(behavior_turn_recorder=ExistingTurns())
    event = cadence_event()
    for window in range(7200):
        for suffix in ('', ':domain'):
            correlation = f'population-runtime:cadence:world:bakery-district:{window}{suffix}'
            population_turn(runtime, event.model_copy(update={'correlation_id': correlation}))
    cache = runtime._recorded_behavior_turn_correlations
    assert len(cache) == 14400
    retained_bytes = getsizeof(cache) + sum(getsizeof(key) for key in cache)
    assert retained_bytes < 1_600_000


def test_canonically_equivalent_unicode_correlations_remain_distinct():
    runtime = SimingRuntime(behavior_turn_recorder=ExistingTurns())
    for correlation in ('corr:\u00e9', 'corr:e\u0301'):
        population_turn(runtime, cadence_event().model_copy(update={'correlation_id': correlation}))
    assert len(runtime._recorded_behavior_turn_correlations) == 2


def test_population_prefix_and_embedded_nuls_cannot_alias_other_correlations():
    runtime = SimingRuntime(behavior_turn_recorder=ExistingTurns())
    for correlation in ('same', '\x00same', '\x01same',
                        'population-runtime:cadence:same',
                        'population-runtime:cadence:\x00same',
                        'population-runtime:cadence:\x01same'):
        population_turn(runtime, cadence_event().model_copy(update={'correlation_id': correlation}))
    assert len(runtime._recorded_behavior_turn_correlations) == 6


@pytest.mark.parametrize('correlation', ['corr:\ud800', 'corr:\ud801'])
def test_invalid_surrogate_is_rejected_before_cache_admission(correlation):
    runtime = SimingRuntime(behavior_turn_recorder=ExistingTurns())
    with pytest.raises(ValidationError, match='string_unicode'):
        population_turn(runtime, cadence_event().model_copy(update={'correlation_id': correlation}))
    assert not runtime._recorded_behavior_turn_correlations
