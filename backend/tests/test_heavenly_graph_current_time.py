"""当前时间索引必须与原完整查询相同，普通读取不再扫描历史。"""
import sqlite3

import pytest

from heavenly_graph_contract import graph_node, graph_relation, graph_scope
from app.models.siming_heavenly_graph import (
    GraphBranchForkRequest, GraphBranchLifecycleRequest, GraphSemanticMetadata,
    HeavenlyGraphWriteBatch, HeavenlyNodeQuery, HeavenlyRelationQuery,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore

MAX_TIME = 2**63 - 1


def oracle(graph, scope):
    nodes = graph.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=MAX_TIME, limit=None))
    relations = graph.query_relations(HeavenlyRelationQuery(scope=scope, valid_at=MAX_TIME, limit=None))
    return (max((node.validity.valid_from for node in nodes), default=0),
            max((entity.recorded_at for entity in [*nodes, *relations]), default=0))


@pytest.mark.parametrize('durable', [False, True])
def test_time_bounds_preserve_current_selection_and_branch_semantics(tmp_path, durable):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'graph.db') if durable else InMemoryHeavenlyGraphAdapter()
    scope = graph_scope()
    serial = 0

    def check():
        assert graph.scope_current_time_bounds(scope) == oracle(graph, scope)

    def append(nodes=(), relations=()):
        nonlocal serial
        serial += 1
        batch = HeavenlyGraphWriteBatch(transaction_id=f'tx:{serial}', idempotency_key=f'key:{serial}',
                                       scope=scope, nodes=list(nodes), relations=list(relations))
        assert graph.write_batch(batch).applied
        check()
        assert graph.write_batch(batch).replayed
        check()

    try:
        check()
        first = graph_node(node_id='a', valid_from=30, recorded_at=40)
        second = graph_node(node_id='b', valid_from=20, recorded_at=35)
        append([first, second])
        relation = graph_relation(relation_id='r', source_node_id='a', target_node_id='b', valid_from=60, recorded_at=70)
        append(relations=[relation])
        assert graph.scope_current_time_bounds(scope) == (30, 70)  # relation不能抬高node valid时间。
        first = first.model_copy(update={'revision': 2, 'supersedes_revision': 1,
            'validity': first.validity.model_copy(update={'valid_from': 10})})
        append([first])
        assert graph.scope_current_time_bounds(scope) == (20, 70)
        first = first.model_copy(update={'revision': 3, 'supersedes_revision': 2, 'recorded_at': 80,
            'validity': first.validity.model_copy(update={'valid_to': MAX_TIME})})
        append([first])  # 新的有限区间不遮盖仍在MAX_TIME有效的旧版本。
        assert graph.scope_current_time_bounds(scope) == (20, 70)
        first = first.model_copy(update={'revision': 4, 'supersedes_revision': 3, 'recorded_at': 90,
            'validity': first.validity.model_copy(update={'valid_to': MAX_TIME + 1})})
        append([first])
        assert graph.scope_current_time_bounds(scope) == (20, 90)
        first = first.model_copy(update={'revision': 5, 'supersedes_revision': 4,
            'semantic_metadata': GraphSemanticMetadata(derivation_kind='retraction')})
        append([first])
        assert graph.scope_current_time_bounds(scope) == (20, 70)
        relation = relation.model_copy(update={'revision': 2, 'supersedes_revision': 1,
            'semantic_metadata': GraphSemanticMetadata(derivation_kind='redaction')})
        append(relations=[relation])
        assert graph.scope_current_time_bounds(scope) == (20, 35)
        # recorded_at原模型没有int64上限，新索引不能暗自收窄。
        append([graph_node(node_id='big', valid_from=15, recorded_at=10**30 + 7)])
        assert graph.scope_current_time_bounds(scope) == (20, 10**30 + 7)
        fork = graph.fork_branch(GraphBranchForkRequest(source_scope=scope, target_branch_id='branch:test',
            fork_valid_at=100, fork_recorded_at=10**30 + 8, source_revision_vector=graph.scope_revision_vector(scope)))
        branch = scope.model_copy(update={'story_branch_id': 'branch:test'})
        assert fork.applied and graph.scope_current_time_bounds(branch) == oracle(graph, branch)
        graph.lifecycle_branch(GraphBranchLifecycleRequest(branch_scope=branch, operation='close_node', node_id='big',
            expected_revision_vector=graph.scope_revision_vector(branch), valid_at=100, recorded_at=10**30 + 9))
        # 关闭节点的marker不可见，但原closes_branch_node关系仍参与recorded时间。
        assert graph.scope_current_time_bounds(branch) == oracle(graph, branch) == (20, 10**30 + 9)
        graph.lifecycle_branch(GraphBranchLifecycleRequest(branch_scope=branch, operation='discard',
            expected_revision_vector=graph.scope_revision_vector(branch), valid_at=MAX_TIME, recorded_at=10**30 + 10))
        assert graph.scope_current_time_bounds(branch) == (0, 0)
        check()
        if durable:
            graph.close()
            graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'graph.db')
            check()
            assert graph.scope_current_time_bounds(branch) == (0, 0)
    finally:
        if durable:
            graph.close()


def test_memory_time_lookup_uses_fixed_rows_after_cold_reopen(tmp_path, monkeypatch):
    scope, path = graph_scope(), tmp_path / 'many.db'
    graph = SQLiteHeavenlyGraphAdapter(path)
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id='many', idempotency_key='many', scope=scope,
        nodes=[graph_node(node_id=f'node:{i}', valid_from=i, recorded_at=i + 1) for i in range(1000)]))
    expected = oracle(graph, scope)
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(path)
    try:
        def forbid(*args, **kwargs):
            raise AssertionError('ordinary current-time lookup decoded history')
        monkeypatch.setattr(graph, 'query_nodes', forbid)
        monkeypatch.setattr(graph, 'query_relations', forbid)
        monkeypatch.setattr(graph, '_load_full', forbid)
        steps, statements = [], []
        graph._connection.set_progress_handler(lambda: steps.append(1) or 0, 1)
        graph._connection.set_trace_callback(statements.append)
        store = CharacterGraphMemoryStore(graph, scope_resolver=lambda _: scope)
        assert (store._latest_valid_time(scope), store._latest_recorded_at(scope)) == expected
        graph._connection.set_progress_handler(None, 0)
        graph._connection.set_trace_callback(None)
        assert len(steps) < 200
        for statement in statements:
            plan = graph._connection.execute('EXPLAIN QUERY PLAN ' + statement).fetchall()
            assert not any('SCAN ' in row[3] or 'TEMP B-TREE' in row[3] for row in plan), plan
        assert not graph._nodes and not graph._relations
    finally:
        graph.close()


def test_time_index_transaction_and_one_time_migration(tmp_path, monkeypatch):
    path, scope = tmp_path / 'atomic.db', graph_scope()
    graph = SQLiteHeavenlyGraphAdapter(path)
    def batch(index):
        return HeavenlyGraphWriteBatch(transaction_id=f'tx:{index}', idempotency_key=f'key:{index}', scope=scope,
            nodes=[graph_node(node_id=f'n:{index}', valid_from=index, recorded_at=index + 1)])
    graph.write_batch(batch(1))
    before = graph.scope_revision_vector(scope)
    graph._connection.execute("CREATE TRIGGER fail_time BEFORE INSERT ON graph_current_times BEGIN SELECT RAISE(ABORT,'time failed'); END")
    with pytest.raises(sqlite3.IntegrityError, match='time failed'):
        graph.write_batch(batch(2))
    assert graph.scope_revision_vector(scope) == before
    assert graph.scope_current_time_bounds(scope) == (1, 2)
    assert not graph.has_idempotency_key(scope=scope, idempotency_key='key:2')
    assert graph.get_node(node_id='n:2', scope=scope, valid_at=10) is None
    graph._connection.execute('DROP TRIGGER fail_time')
    assert graph.write_batch(batch(2)).applied
    graph.close()
    with sqlite3.connect(path) as db:
        db.execute('UPDATE schema_version SET version=5')
        db.execute('DROP TABLE graph_current_times')
        db.execute(f"CREATE TRIGGER fail_upgrade BEFORE INSERT ON schema_version WHEN NEW.version={SQLiteHeavenlyGraphAdapter.SCHEMA_VERSION} BEGIN SELECT RAISE(ABORT,'upgrade failed'); END")
    with pytest.raises(sqlite3.IntegrityError, match='upgrade failed'):
        SQLiteHeavenlyGraphAdapter(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version FROM schema_version').fetchone() == (5,)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='graph_current_times'").fetchall() == []
        db.execute('DROP TRIGGER fail_upgrade')
    graph = SQLiteHeavenlyGraphAdapter(path)
    assert graph.scope_current_time_bounds(scope) == oracle(graph, scope) == (2, 3)
    graph.close()
    def forbid(*args, **kwargs):
        raise AssertionError('ordinary reopen rebuilt current time index')
    monkeypatch.setattr(SQLiteHeavenlyGraphAdapter, '_rebuild_current_times', forbid)
    graph = SQLiteHeavenlyGraphAdapter(path)
    assert graph.scope_current_time_bounds(scope) == (2, 3)
    graph.close()


def test_shared_memory_writers_match_original_full_query_oracle(tmp_path):
    from test_character_graph_memory_store import _event, _scope
    indexed = SQLiteHeavenlyGraphAdapter(tmp_path / 'indexed.db')
    original = SQLiteHeavenlyGraphAdapter(tmp_path / 'oracle.db')
    original.scope_current_time_bounds = lambda scope: oracle(original, scope)
    try:
        writers = [[CharacterGraphMemoryStore(graph, scope_resolver=_scope) for _ in range(2)]
                   for graph in (indexed, original)]
        events = [
            _event('social_cognition_event', 'evt:later', 200, {'entity_id': 'char_a'}),
            _event('higher_order_belief_event', 'evt:earlier', 100, {
                'subject_actor_id': 'char_a', 'proposition_key': 'letter:destroyed',
                'meta_belief': 'char_a knows', 'confidence': 0.8}),
            _event('social_cognition_event', 'evt:newer', 300, {'entity_id': 'char_a'}),
        ]
        for index, event in enumerate(events):
            for pair in writers:
                pair[index % 2].write_event(event)
            for table in ('graph_nodes', 'graph_relations', 'graph_idempotency'):
                assert indexed._connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall() == original._connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
        assert writers[0][0].retrieval_bundle('char_b') == writers[1][0].retrieval_bundle('char_b')
    finally:
        indexed.close()
        original.close()


@pytest.mark.parametrize('name', ['graph_current_times', 'graph_current_times_recorded'])
def test_missing_time_index_fails_closed_without_rebuilding_on_reopen(tmp_path, name):
    from app.services.siming_heavenly_graph_port import HeavenlyGraphError
    path = tmp_path / 'missing.db'
    graph = SQLiteHeavenlyGraphAdapter(path)
    graph.close()
    with sqlite3.connect(path) as db:
        db.execute(f'DROP {"TABLE" if name == "graph_current_times" else "INDEX"} {name}')
    with pytest.raises(HeavenlyGraphError, match='graph_current_times_missing'):
        SQLiteHeavenlyGraphAdapter(path)
