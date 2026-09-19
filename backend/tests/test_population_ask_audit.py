from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeStore
from test_ask_normalized_history import incoming, open_store
from scripts.verification.verify_population_long_session_recovery import digest


def test_ask_audit_stream_matches_original_complete_canonical_json(tmp_path):
    from scripts.verification.population_ask_audit import write_audit, verify_audit
    persistence, store = open_store(tmp_path / 'ask.db')
    expected = ActorSceneKnowledgeStore()
    for index in range(50):
        value = incoming(index)
        store.record(value, producer_ts=index // 2)
        expected.upsert(value, producer_ts=index // 2)
    path = tmp_path / 'ask.jsonl'
    proof = write_audit(persistence, 'a', path)
    assert proof == verify_audit(path, 'a')
    assert proof['logical_digest'] == digest([entry.model_dump(mode='json') for entry in expected.entries_for_actor('a')])
    assert proof['entries'] == 1
    assert proof['conflicts'] == 25
    assert proof['revisions'] == 50
    persistence.close()
import json
import pytest


@pytest.mark.parametrize('fault', ['missing','order','prefix','duplicate','source','history','trailing'])
def test_complete_audit_rejects_changed_or_missing_logical_history(tmp_path, fault):
    from scripts.verification.population_ask_audit import write_audit, verify_audit
    persistence, store = open_store(tmp_path / 'source.db')
    for index in range(12):
        store.record(incoming(index), producer_ts=index)
    path = tmp_path / 'ask.jsonl'
    expected = write_audit(persistence, 'a', path)
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    conflict = next(i for i, value in enumerate(records) if value.get('kind') == 'conflicts')
    if fault == 'missing': records.pop(conflict)
    if fault == 'order': records[conflict]['ordinal'] += 1
    if fault == 'prefix': records[conflict]['value']['source_refs']['prefix'] = 9999
    if fault == 'duplicate': records.insert(conflict, records[conflict])
    if fault == 'source': records[conflict]['value']['source_refs']['suffix'][-1] = 'changed'
    if fault == 'history': records[conflict]['value']['reason'] = 'changed'
    if fault == 'trailing': records.append(dict(kind='end'))
    path.write_text(''.join(json.dumps(value) + '\n' for value in records), encoding='utf-8')
    if fault in {'source','history'}:
        assert verify_audit(path, 'a')['logical_digest'] != expected['logical_digest']
    else:
        with pytest.raises(ValueError): verify_audit(path, 'a')
    persistence.close()


def test_audit_preserves_legacy_duplicate_ids_arbitrary_sources_and_resolved_state(tmp_path):
    from copy import deepcopy
    from scripts.verification.population_ask_audit import write_audit
    persistence, store = open_store(tmp_path / 'legacy.db')
    for index in range(6): store.upsert(incoming(index), producer_ts=1)
    value = store.entries_for_actor('a')[0].model_dump(mode='json')
    value['conflicts'].append(deepcopy(value['conflicts'][0]))
    value['conflicts'][0].update(source_refs=['outside', '', 'outside'], source_ref_lineage=['', 'outside', 'outside'], resolved=True, resolved_by_ref='result')
    value['revisions'].append(deepcopy(value['revisions'][0]))
    persistence.write_ask(value, {})
    proof = write_audit(persistence, 'a', tmp_path / 'audit.jsonl')
    assert proof['logical_digest'] == digest([value])
    persistence.close()


def test_explicit_audit_rejects_orphan_and_unknown_parts(tmp_path):
    from scripts.verification.population_ask_audit import write_audit
    persistence, store = open_store(tmp_path / 'orphan.db')
    store.record(incoming(0), producer_ts=0)
    key = persistence.ask_key(store.entries_for_actor('a')[0].model_dump(mode='json'))
    for entry_key, kind, error in [('orphan','source_refs','orphan'), (key,'unknown','unknown')]:
        persistence._connection.execute('INSERT INTO character_session_ask_parts VALUES (?,?,?,?)', (entry_key, kind, 0, '"source"'))
        with pytest.raises(ValueError, match=error): write_audit(persistence, 'a', tmp_path / 'audit.jsonl')
        persistence._connection.execute('DELETE FROM character_session_ask_parts WHERE entry_key=? AND kind=?', (entry_key, kind))
    persistence.close()


def test_audit_hash_uses_public_model_numeric_normalization(tmp_path):
    from scripts.verification.population_ask_audit import write_audit
    persistence, store = open_store(tmp_path / 'numeric.db')
    for index in range(2): store.upsert(incoming(index), producer_ts=index)
    value = store.entries_for_actor('a')[0].model_dump(mode='json')
    value['confidence'] = 1
    for revision in value['revisions']:
        revision['confidence'] = 1
        revision['previous_confidence'] = 0
    persistence.write_ask(value, {})
    expected = [entry.model_dump(mode='json') for entry in store.entries_for_actor('a')]
    assert write_audit(persistence, 'a', tmp_path / 'audit.jsonl')['logical_digest'] == digest(expected)
    persistence.close()


@pytest.mark.parametrize('normalization', ['strings', 'defaults', 'history_sources'])
def test_audit_accepts_original_public_model_coercions_and_defaults(tmp_path, normalization):
    from scripts.verification.population_ask_audit import write_audit
    persistence, store = open_store(tmp_path / 'defaults.db')
    for index in range(2): store.upsert(incoming(index), producer_ts=index)
    value = store.entries_for_actor('a')[0].model_dump(mode='json')
    if normalization == 'strings':
        value['confidence'] = '0.9'
        for revision in value['revisions']:
            revision['producer_ts'] = str(revision['producer_ts'])
            revision['confidence'] = '0.9'
    if normalization == 'defaults':
        value.pop('claim')
        value['freshness'].pop('expires_at')
        for revision in value['revisions']: revision.pop('previous_confidence')
    if normalization == 'history_sources':
        for conflict in value['conflicts']:
            conflict.pop('source_refs')
            conflict.pop('source_ref_lineage')
        for revision in value['revisions']: revision.pop('source_refs')
    persistence.write_ask(value, {})
    expected = [entry.model_dump(mode='json') for entry in store.entries_for_actor('a')]
    assert write_audit(persistence, 'a', tmp_path / 'audit.jsonl')['logical_digest'] == digest(expected)
    persistence.close()
