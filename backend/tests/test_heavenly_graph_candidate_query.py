"""当前候选 SQL 必须保留原双时间 winner，并减少无关历史的 VM 工作。"""
import pytest
from heavenly_graph_contract import graph_node as base_node, graph_scope as base_scope
from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch, HeavenlyNodeQuery, GraphSemanticMetadata
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


TYPES = [f'actor_memory:{name}' for name in ('event', 'observation', 'knowledge', 'social', 'higher_order')]


def graph_scope():
    return base_scope().model_copy(update={'graph_namespace': 'actor_private', 'owner_actor_id': 'a'})


def graph_node(**kwargs):
    return base_node(**kwargs).model_copy(update={'scope': graph_scope(), 'node_type': TYPES[0],
        'semantic_metadata': GraphSemanticMetadata(visibility_scope='actor_private', policy_revision='policy:test', scope_digest='scope:test')})


def append(graph, nodes, key):
    assert graph.write_batch(HeavenlyGraphWriteBatch(transaction_id=key, idempotency_key=key, scope=graph_scope(), nodes=nodes)).applied


def measured(graph, query):
    steps, statements = [], []
    graph._connection.set_progress_handler(lambda: steps.append(1) or 0, 1)
    graph._connection.set_trace_callback(statements.append)
    try:
        result = graph.query_nodes(query)
    finally:
        graph._connection.set_progress_handler(None, 0)
        graph._connection.set_trace_callback(None)
    return result, len(steps), statements


@pytest.mark.parametrize('types', [[TYPES[0]], TYPES])
def test_actual_current_getter_vm_ignores_unrelated_history_after_same_prefix(tmp_path, types):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'graph.db')
    try:
        append(graph, [graph_node(node_id=f'a:{i:04}').model_copy(update={'node_type': TYPES[i % 5]}) for i in range(50)], 'initial')
        query = HeavenlyNodeQuery(scope=graph_scope(), valid_at=100, node_types=types, limit=5)
        expected, before, _ = measured(graph, query)
        append(graph, [graph_node(node_id=f'z:{i:04}').model_copy(update={'node_type':'actor_memory:unrelated'}) for i in range(1000)], 'history')
        prior = graph_node(node_id='z:0000').model_copy(update={'node_type':'actor_memory:unrelated'})
        for revision in range(2, 42):
            prior = prior.model_copy(update={'revision':revision, 'supersedes_revision':revision-1, 'recorded_at':revision+12})
            append(graph, [prior], f'old-version:{revision}')
        actual, after, statements = measured(graph, query)
        assert actual == expected
        print(dict(types=len(types), before_vm=before, after_vm=after))
        assert after < before * 2
        assert any('graph_nodes_candidates' in row[3] for sql in statements if 'SELECT' in sql.upper()
                   for row in graph._connection.execute('EXPLAIN QUERY PLAN ' + sql))
    finally:
        graph.close()


def test_typed_candidates_equal_original_winner_and_full_history(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'semantics.db')
    try:
        first = graph_node(node_id='a')
        append(graph, [first, graph_node(node_id='b'), graph_node(node_id='c')], 'first')
        second = first.model_copy(update={'revision':2, 'supersedes_revision':1, 'recorded_at':20, 'node_type':TYPES[1],
            'validity':first.validity.model_copy(update={'valid_from':20, 'valid_to':40})})
        append(graph, [second], 'second')
        third = second.model_copy(update={'revision':3, 'supersedes_revision':2, 'node_type':TYPES[2],
            'validity':second.validity.model_copy(update={'valid_from':30})})
        append(graph, [third], 'third')
        fourth = third.model_copy(update={'revision':4, 'supersedes_revision':3, 'recorded_at':30,
            'validity':third.validity.model_copy(update={'valid_from':50, 'valid_to':None}),
            'semantic_metadata':third.semantic_metadata.model_copy(update={'derivation_kind':'retraction'})})
        append(graph, [fourth], 'fourth')
        for valid in (15,25,35,45,60):
            for recorded in (None,15,20,25,35):
                for types in ([TYPES[0]], [TYPES[1]], TYPES, [TYPES[0],TYPES[0],TYPES[1]]):
                    for ids in ([], ['a','c']):
                        query = HeavenlyNodeQuery(scope=graph_scope(), valid_at=valid, recorded_at=recorded,
                            node_types=types, node_ids=ids, limit=2)
                        expected = graph.query_nodes(query.model_copy(update={'limit':None}))[:2]
                        assert graph.query_nodes(query) == expected
                        with graph.historical_read():
                            assert graph.query_nodes(query) == expected
        history = HeavenlyNodeQuery(scope=graph_scope(), valid_at=35, node_types=TYPES, limit=None)
        actual = graph.query_node_history(history)
        with graph.historical_read(): assert graph.query_node_history(history) == actual
        assert [node.revision for node in actual if node.node_id == 'a'] == [1,2,3]
    finally:
        graph.close()


def test_exact_node_lookup_matches_materialized_history_without_general_query(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'exact.db')
    try:
        first = graph_node(node_id='exact')
        append(graph, [first], 'first')
        second = first.model_copy(update={'revision': 2, 'supersedes_revision': 1, 'recorded_at': 20,
            'validity': first.validity.model_copy(update={'valid_from': 20, 'valid_to': 40})})
        append(graph, [second], 'second')
        coordinates = ((15, None), (25, None), (45, None), (25, 15), (25, 25))
        expected = {}
        with graph.historical_read():
            for valid_at, recorded_at in coordinates:
                expected[(valid_at, recorded_at)] = graph.get_node(
                    node_id='exact', scope=graph_scope(), valid_at=valid_at, recorded_at=recorded_at)

        monkeypatch.setattr(graph, '_query_entities', lambda *_args, **_kwargs: pytest.fail('general query used'))
        for valid_at, recorded_at in coordinates:
            assert graph.get_node(
                node_id='exact', scope=graph_scope(), valid_at=valid_at, recorded_at=recorded_at
            ) == expected[(valid_at, recorded_at)]
    finally:
        graph.close()


def test_typed_query_large_type_list_and_sqlite_limits_use_original_fallback(tmp_path):
    import sqlite3
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'limits.db')
    try:
        append(graph, [graph_node(node_id='a')], 'first')
        types = [*TYPES, *[f'actor_memory:other:{i}' for i in range(600)]]
        query = HeavenlyNodeQuery(scope=graph_scope(), valid_at=20, node_types=types, limit=10)
        assert graph.query_nodes(query) == graph.query_nodes(query.model_copy(update={'limit':None}))
        graph._connection.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 2)
        assert len(graph.query_nodes(query.model_copy(update={'node_types':TYPES}))) == 1
        graph._connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 20)
        assert len(graph.query_nodes(query.model_copy(update={'node_types':TYPES}))) == 1
    finally:
        graph.close()


def test_candidate_schema_upgrade_is_atomic_and_reopen_requires_index(tmp_path, monkeypatch):
    import sqlite3
    from app.services.siming_heavenly_graph_port import HeavenlyGraphError
    path = tmp_path / 'upgrade.db'
    graph = SQLiteHeavenlyGraphAdapter(path)
    append(graph, [graph_node(node_id='a')], 'first')
    expected = graph.query_nodes(HeavenlyNodeQuery(scope=graph_scope(),valid_at=20,node_types=TYPES))
    graph.close()
    with sqlite3.connect(path) as db:
        db.execute('DROP INDEX graph_nodes_candidates')
        db.execute('UPDATE schema_version SET version=6')
    with monkeypatch.context() as patch:
        patch.setattr(SQLiteHeavenlyGraphAdapter, '_CANDIDATE_INDEX_SQL', 'CREATE INDEX graph_nodes_candidates ON absent(scope_json)')
        with pytest.raises(sqlite3.OperationalError): SQLiteHeavenlyGraphAdapter(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version FROM schema_version').fetchone()[0] == 6
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='graph_nodes_candidates'").fetchall()
    graph = SQLiteHeavenlyGraphAdapter(path)
    assert graph.query_nodes(HeavenlyNodeQuery(scope=graph_scope(),valid_at=20,node_types=TYPES)) == expected
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(path)
    graph.close()
    with sqlite3.connect(path) as db: db.execute('DROP INDEX graph_nodes_candidates')
    with pytest.raises(HeavenlyGraphError, match='graph_nodes_candidates_missing'): SQLiteHeavenlyGraphAdapter(path)


def test_nullable_legacy_recorded_sort_does_not_resurrect_null_candidate(tmp_path):
    import json
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'null.db')
    try:
        first = graph_node(node_id='a')
        append(graph, [first], 'first')
        append(graph, [first.model_copy(update={'revision':2, 'supersedes_revision':1, 'recorded_at':15})], 'second')
        payload = first.model_dump(mode='json')
        payload.pop('recorded_at')
        graph._connection.execute('UPDATE graph_nodes SET payload_json=? WHERE revision=1', (json.dumps(payload),))
        graph._connection.commit()
        query = HeavenlyNodeQuery(scope=graph_scope(),valid_at=20,node_types=TYPES,limit=10)
        assert [node.revision for node in graph.query_nodes(query)] == [2]
        assert graph.query_nodes(query) == graph.query_nodes(query.model_copy(update={'limit':None}))
    finally:
        graph.close()


def test_candidate_filter_preserves_close_discard_defaults_and_facade_window(tmp_path, monkeypatch):
    import json
    from app.models.siming_heavenly_graph import GraphBranchForkRequest, GraphBranchLifecycleRequest, GraphReaderContext, NodeLookupQuery
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'branch.db')
    scope = base_scope()
    try:
        assert graph.write_batch(HeavenlyGraphWriteBatch(transaction_id='nodes',idempotency_key='nodes',scope=scope,
            nodes=[base_node(node_id='a'),base_node(node_id='b',source_ref='wanted')])).applied
        # 原schema缺metadata采用authority默认，不能被SQL NULL排除。
        for rowid, payload in graph._connection.execute('SELECT rowid,payload_json FROM graph_nodes').fetchall():
            value=json.loads(payload);value.pop('semantic_metadata')
            graph._connection.execute('UPDATE graph_nodes SET payload_json=? WHERE rowid=?',(json.dumps(value),rowid))
        graph._connection.commit()
        assert len(graph.query_nodes(HeavenlyNodeQuery(scope=scope,valid_at=20,node_types=['world_fact'],limit=5))) == 2
        graph.fork_branch(GraphBranchForkRequest(source_scope=scope,target_branch_id='branch:query',
            fork_valid_at=20,fork_recorded_at=20,source_revision_vector=graph.scope_revision_vector(scope)))
        branch=scope.model_copy(update={'story_branch_id':'branch:query'})
        graph.lifecycle_branch(GraphBranchLifecycleRequest(branch_scope=branch,operation='close_node',node_id='a',
            expected_revision_vector=graph.scope_revision_vector(branch),valid_at=30,recorded_at=30))
        graph.lifecycle_branch(GraphBranchLifecycleRequest(branch_scope=branch,operation='discard',
            expected_revision_vector=graph.scope_revision_vector(branch),valid_at=50,recorded_at=50))
        for valid,recorded in ((15,20),(25,25),(35,25),(35,35),(55,45),(55,55)):
            query=HeavenlyNodeQuery(scope=branch,valid_at=valid,recorded_at=recorded,node_types=['world_fact'],limit=1)
            assert graph.query_nodes(query)==graph.query_nodes(query.model_copy(update={'limit':None}))[:1]
        context=GraphReaderContext(reader_principal='reader',allowed_visibility_scopes=('public',),
            world_id=scope.world_id,session_id=scope.session_id,story_branch_id=scope.story_branch_id,
            valid_at=20,policy_revision='policy:legacy')
        query=NodeLookupQuery(scope=scope,context=context,node_types=['world_fact','world_fact'],source_refs=['wanted'],limit=1)
        actual=graph.query_semantic(query)
        monkeypatch.setattr(graph,'_query_current_typed_nodes',lambda query,types: graph._query_entities(query.model_copy(update={'limit':None}),nodes=True)[:query.limit])
        assert actual==graph.query_semantic(query)
        assert [node.node_id for node in actual.nodes]==['b']
    finally:
        graph.close()
