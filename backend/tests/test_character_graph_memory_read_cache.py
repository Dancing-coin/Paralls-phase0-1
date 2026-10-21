import sqlite3
import random
import string

import pytest

from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from test_character_graph_memory_store import _event, _scope


def seed(graph):
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    store.bind_session_reader(lambda _: [])
    store.write_event(_event('character_perceived_event', 'evt:first', 100, {'summary': 'closed'}))
    return store


def read(store, *, valid_at=1000):
    return store.retrieval_record_bundle('char_b', story_branch_id='branch:main', valid_at=valid_at)


def test_sqlite_graph_memory_reuses_same_committed_read_and_returns_independent_records(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        store = seed(graph)
        original, calls = graph.query_semantic, []

        def tracked(query):
            calls.append(query)
            return original(query)

        monkeypatch.setattr(graph, 'query_semantic', tracked)
        first = read(store)
        expected = first.model_dump(mode='json')
        assert len(calls) == 5
        first.event_memories[0].summary = 'caller changed result'
        second = read(store)
        assert second.model_dump(mode='json') == expected
        assert len(calls) == 5, 'same committed pin read repeated all graph memory queries'
        second.observation_memories.clear()
        assert read(store).model_dump(mode='json') == expected
    finally:
        graph.close()


@pytest.mark.parametrize('external', [False, True])
def test_sqlite_graph_memory_cache_observes_same_and_external_connection_writes(tmp_path, external):
    path = tmp_path/'graph.sqlite3'
    graph = SQLiteHeavenlyGraphAdapter(path)
    other = SQLiteHeavenlyGraphAdapter(path) if external else None
    try:
        store = seed(graph)
        assert len(read(store).event_memories) == 1
        writer = seed(other) if other is not None else store
        writer.write_event(_event('character_perceived_event', 'evt:second', 200, {'summary': 'opened'}))
        expected = read(CharacterGraphMemoryStore(graph, scope_resolver=_scope))
        assert read(store) == expected
        assert len(expected.event_memories) == 2
    finally:
        if other is not None:
            other.close()
        graph.close()


@pytest.mark.parametrize('commit', [False, True])
def test_sqlite_graph_memory_never_caches_uncommitted_or_rolled_back_records(tmp_path, commit):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        store = seed(graph)
        baseline = read(store)
        connection = graph._connection
        connection.execute('BEGIN IMMEDIATE')
        connection.execute("UPDATE graph_nodes SET payload_json=json_set(payload_json,"
            "'$.attributes.record.summary','temporary') WHERE json_extract(payload_json,'$.node_type')='actor_memory:event'")
        assert read(store).event_memories[0].summary == 'temporary'
        if commit:
            connection.commit()
        else:
            connection.rollback()
        current = read(store)
        assert current == read(CharacterGraphMemoryStore(graph, scope_resolver=_scope))
        assert current.event_memories[0].summary == ('temporary' if commit else baseline.event_memories[0].summary)
    finally:
        graph.close()


def test_sqlite_graph_memory_cache_preserves_time_branch_and_materialized_reads(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        store = seed(graph)
        current = read(store)
        assert not read(store, valid_at=99).event_memories
        assert read(store) == current
        with pytest.raises(ValueError, match='story branch'):
            store.retrieval_record_bundle('char_b', story_branch_id='branch:other', valid_at=1000)
        with graph.historical_read():
            assert read(store) == current
        assert read(store) == current
    finally:
        graph.close()


def test_sqlite_graph_memory_does_not_cache_a_temporary_incomplete_query(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        store = seed(graph)
        expected = read(CharacterGraphMemoryStore(graph, scope_resolver=_scope))

        def unavailable(*args, **kwargs):
            raise sqlite3.OperationalError('temporary query failure')

        with monkeypatch.context() as failure:
            failure.setattr(graph, '_query_entities', unavailable)
            assert not read(store).event_memories
        assert read(store) == expected
    finally:
        graph.close()


def test_sqlite_graph_memory_cache_does_not_hide_same_connection_schema_failure(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        store = seed(graph)
        assert read(store).event_memories
        graph._connection.execute('DROP TABLE graph_nodes')
        assert not read(store).event_memories
    finally:
        graph.close()


def test_sqlite_graph_memory_rechecks_external_commit_during_cached_result_decode(tmp_path, monkeypatch):
    path = tmp_path/'graph.sqlite3'
    graph, other = SQLiteHeavenlyGraphAdapter(path), SQLiteHeavenlyGraphAdapter(path)
    try:
        store = seed(graph)
        writer = seed(other)
        assert len(read(store).event_memories) == 1
        original, decoded = CharacterMemoryRecordBundle.model_validate_json, []

        def decode(payload):
            bundle = original(payload)
            decoded.append(True)
            writer.write_event(_event('character_perceived_event', 'evt:during-hit', 200, {'summary': 'changed'}))
            return bundle

        monkeypatch.setattr(CharacterMemoryRecordBundle, 'model_validate_json', decode)
        actual = read(store)
        assert decoded == [True]
        assert len(actual.event_memories) == 2
        assert actual == read(CharacterGraphMemoryStore(graph, scope_resolver=_scope))
    finally:
        other.close()
        graph.close()


def test_sqlite_graph_memory_cache_declines_large_incompressible_records(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
        store.bind_session_reader(lambda _: [])
        summary = ''.join(random.Random(31).choices(string.ascii_letters + string.digits, k=300_000))
        store.write_event(_event('character_perceived_event', 'evt:large', 100, {'summary': summary}))
        original, calls = graph.query_semantic, []

        def tracked(query):
            calls.append(query)
            return original(query)

        monkeypatch.setattr(graph, 'query_semantic', tracked)
        first = read(store)
        assert read(store) == first
        assert len(calls) == 10, 'oversized memory must not stay resident in the read cache'
    finally:
        graph.close()
