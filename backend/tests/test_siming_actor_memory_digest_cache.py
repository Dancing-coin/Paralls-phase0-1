import sqlite3
from types import SimpleNamespace

import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.models.siming_actor_memory_read import ActorMemoryReadRequest, ActorMemoryRevisionVector
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.siming_continuation import digest
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from test_character_graph_memory_read_cache import seed
from test_character_graph_memory_store import _event, _scope


def gateway_for(graph):
    memory = seed(graph)
    runtime = object.__new__(CharacterAgentRuntime)
    runtime._memory_store = CharacterMemoryStoreRouter(light_store=CharacterAgentMemoryStore(),
        graph_store=memory, heavy_actor_ids=frozenset({'char_b'}))
    runtime._l1 = SimpleNamespace(get_snapshot=lambda actor: None)
    return ActorMemoryReadGateway(runtime), memory


def request(**changes):
    return ActorMemoryReadRequest(actor_id='char_b', story_branch_id='branch:main', valid_at=1000, **changes)


def original_digest(gateway, value):
    return digest(gateway.read(value).model_dump(mode='json'))


def test_memory_digest_reuses_committed_graph_read_across_light_reads(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, memory = gateway_for(graph)
        value = request()
        expected = original_digest(gateway, value)
        original, calls = gateway.read, []

        def counted(value):
            calls.append(value.actor_id)
            return original(value)

        monkeypatch.setattr(gateway, 'read', counted)
        assert gateway.read_digest(value) == expected
        returned = original(value)
        returned.bundle.event_memories[0].summary = 'caller mutation'
        assert gateway.read_digest(value) == expected
        light = value.model_copy(update={'actor_id': 'char_c'})
        assert gateway.read_digest(light) == original_digest(gateway, light)
        assert gateway.read_digest(value) == expected
        assert calls.count('char_b') == 1
    finally:
        graph.close()


@pytest.mark.parametrize('external', [False, True])
def test_memory_digest_observes_new_graph_commits(tmp_path, external):
    path = tmp_path/'graph.sqlite3'
    graph = SQLiteHeavenlyGraphAdapter(path)
    other = SQLiteHeavenlyGraphAdapter(path) if external else None
    try:
        gateway, memory = gateway_for(graph)
        writer = seed(other) if external else memory
        prior = gateway.read_digest(request())
        writer.write_event(_event('character_perceived_event', 'evt:new', 200, {'summary': 'changed'}))
        current = gateway.read_digest(request())
        assert current == original_digest(gateway, request()) and current != prior
    finally:
        if other is not None:
            other.close()
        graph.close()


@pytest.mark.parametrize('commit', [False, True])
def test_memory_digest_does_not_cache_uncommitted_or_rolled_back_reads(tmp_path, commit):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, _ = gateway_for(graph)
        value = request()
        prior = gateway.read_digest(value)
        graph._connection.execute('BEGIN IMMEDIATE')
        graph._connection.execute("UPDATE graph_nodes SET payload_json=json_set(payload_json,"
            "'$.attributes.record.summary','temporary') WHERE json_extract(payload_json,'$.node_type')='actor_memory:event'")
        assert gateway.read_digest(value) == original_digest(gateway, value) != prior
        graph._connection.commit() if commit else graph._connection.rollback()
        assert gateway.read_digest(value) == original_digest(gateway, value)
        assert (gateway.read_digest(value) == prior) is (not commit)
    finally:
        graph.close()


def test_memory_digest_preserves_request_time_vector_and_branch_checks(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, _ = gateway_for(graph)
        assert gateway.read_digest(request()) == original_digest(gateway, request())
        for value in (request().model_copy(update={'valid_at': 99}),
                request(expected_revision_vector=ActorMemoryRevisionVector(event='mismatch'))):
            assert gateway.read_digest(value) == original_digest(gateway, value)
        with pytest.raises(ValueError, match='story branch'):
            gateway.read_digest(request().model_copy(update={'story_branch_id': 'branch:wrong'}))
    finally:
        graph.close()


def test_memory_digest_rechecks_commit_during_cached_hit(tmp_path, monkeypatch):
    path = tmp_path/'graph.sqlite3'
    graph, other = SQLiteHeavenlyGraphAdapter(path), SQLiteHeavenlyGraphAdapter(path)
    try:
        gateway, _ = gateway_for(graph)
        writer = seed(other)
        prior = gateway.read_digest(request())
        assert gateway.read_digest(request()) == prior
        reader = gateway._runtime.memory_record_read_token
        calls = []

        def changed(actor):
            calls.append(actor)
            if len(calls) == 2:
                writer.write_event(_event('character_perceived_event', 'evt:hit', 200, {'summary': 'new'}))
            return reader(actor)

        monkeypatch.setattr(gateway._runtime, 'memory_record_read_token', changed)
        assert gateway.read_digest(request()) == original_digest(gateway, request()) != prior
    finally:
        other.close()
        graph.close()


def test_memory_digest_does_not_store_read_changed_during_calculation(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, memory = gateway_for(graph)
        value = request()
        prior = original_digest(gateway, value)
        reader = gateway.read
        calls = []

        def changed(value):
            result = reader(value)
            calls.append(value)
            if len(calls) == 1:
                memory.write_event(_event('character_perceived_event', 'evt:miss', 200, {'summary': 'new'}))
            return result

        monkeypatch.setattr(gateway, 'read', changed)
        assert gateway.read_digest(value) == prior
        assert gateway.read_digest(value) == original_digest(gateway, value) != prior
    finally:
        graph.close()


def test_memory_digest_observes_same_connection_schema_failure(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, _ = gateway_for(graph)
        prior = gateway.read_digest(request())
        graph._connection.execute('DROP TABLE graph_nodes')
        assert gateway.read_digest(request()) == original_digest(gateway, request()) != prior
    finally:
        graph.close()


def test_memory_digest_without_source_token_always_reads_fresh():
    calls = []
    def read(actor, **kwargs):
        calls.append(actor)
        return CharacterAgentMemoryStore().retrieval_record_bundle(actor)
    gateway = ActorMemoryReadGateway(SimpleNamespace(get_memory_record_bundle=read))
    assert gateway.read_digest(request()) == gateway.read_digest(request())
    assert calls == ['char_b', 'char_b']


def test_memory_digest_does_not_retain_temporary_incomplete_read(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, _ = gateway_for(graph)
        def unavailable(*args, **kwargs):
            raise sqlite3.OperationalError('temporary query failure')
        with monkeypatch.context() as failure:
            failure.setattr(graph, '_query_entities', unavailable)
            partial = gateway.read_digest(request())
        expected = original_digest(gateway, request())
        assert expected != partial
        assert gateway.read_digest(request()) == expected
    finally:
        graph.close()


@pytest.mark.parametrize('external', [False, True])
def test_memory_digest_observes_correction_without_new_history_head(tmp_path, external):
    path = tmp_path/'graph.sqlite3'
    graph = SQLiteHeavenlyGraphAdapter(path)
    other = SQLiteHeavenlyGraphAdapter(path) if external else None
    try:
        gateway, _ = gateway_for(graph)
        prior = original_digest(gateway, request())
        assert gateway.read_digest(request()) == prior
        connection = other._connection if other is not None else graph._connection
        with connection:
            connection.execute("UPDATE graph_nodes SET payload_json=json_set(payload_json,"
                "'$.attributes.record.summary','corrected') WHERE json_extract(payload_json,'$.node_type')='actor_memory:event'")
        assert gateway.read_digest(request()) == original_digest(gateway, request()) != prior
    finally:
        if other is not None:
            other.close()
        graph.close()


def test_memory_digest_observes_scope_resolver_rebinding(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, memory = gateway_for(graph)
        prior = original_digest(gateway, request())
        assert gateway.read_digest(request()) == prior
        memory._scope_resolver = lambda actor: _scope(actor).model_copy(update={'world_id': 'world:other'})
        assert gateway.read_digest(request()) == original_digest(gateway, request()) != prior
    finally:
        graph.close()


def test_memory_digest_does_not_reuse_another_graph_with_same_native_token(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'first.sqlite3')
    other = SQLiteHeavenlyGraphAdapter(tmp_path/'second.sqlite3')
    try:
        gateway, memory = gateway_for(graph)
        second = CharacterGraphMemoryStore(other, scope_resolver=_scope)
        second.bind_session_reader(lambda actor: [])
        second.write_event(_event('character_perceived_event', 'evt:first', 100, {'summary': 'different graph'}))
        assert other.read_cache_token() == graph.read_cache_token()
        prior = original_digest(gateway, request())
        assert gateway.read_digest(request()) == prior
        second.retrieval_record_bundle('char_b', story_branch_id='branch:main', valid_at=1000)
        gateway._runtime._memory_store._graph = second
        assert gateway.read_digest(request()) == original_digest(gateway, request()) != prior
    finally:
        other.close()
        graph.close()


def test_memory_digest_large_expected_vector_is_not_retained(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path/'graph.sqlite3')
    try:
        gateway, _ = gateway_for(graph)
        value = request(expected_revision_vector=ActorMemoryRevisionVector(event='x'*20_000))
        expected = original_digest(gateway, value)
        original, calls = gateway.read, []
        def counted(value):
            calls.append(value)
            return original(value)
        monkeypatch.setattr(gateway, 'read', counted)
        assert gateway.read_digest(value) == gateway.read_digest(value) == expected
        assert len(calls) == 2 and gateway._digest_cache is None
    finally:
        graph.close()
