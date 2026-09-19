"""Character 子入站使用原 session archive，不能以进程内队列冒充持久交付。"""
import pytest

from app.character_agent.storage.session_store import CharacterAgentSessionStore
from test_siming_continuation import make_visual_fact_event


def service(path, *, validate=lambda _: None):
    from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
    store = CharacterAgentSessionStore(database_path=path)
    store.initialize_recovery()
    return store, CharacterCognitionAdmissionService(store=store, assert_owner=lambda: None,
        validate_source=validate, activation_is_current=lambda lock, token: (lock, token) == ('lock', 'token'))


def request(index=0):
    return dict(source_event=make_visual_fact_event(), actor_id='char_a', delivery_id=f'delivery:{index}',
        source_kind='run_background_cognition_tick', payload={}, source_pins={'revision': 1},
        now=100., expires_at=200., producer_ts=42, parent_effect_key='parent:effect')


def test_child_admission_reopens_exactly_and_replay_does_not_extend_expiry(tmp_path):
    path = tmp_path / 'sessions.sqlite3'
    store, admissions = service(path)
    first = admissions.admit(**request())
    assert first.source_event['event_id'] == request()['source_event'].event_id
    assert first.payload == {} and first.state == 'admitted'
    assert store.event_count('char_a') == 0
    store.close()
    store, admissions = service(path)
    try:
        assert admissions.read(first.child_key) == first
        assert admissions.admit(**{**request(), 'now': 201.}) == first
        assert admissions.list_pending(limit=1) == (first,)
        with pytest.raises(ValueError, match='cognition_admission_conflict'):
            admissions.admit(**{**request(), 'expires_at': 300.})
        with pytest.raises(ValueError, match='cognition_admission_conflict'):
            admissions.admit(**{**request(), 'source_pins': {'revision': 2}})
        assert store.event_count('char_a') == 0
    finally:
        store.close()


def test_child_admission_and_pending_pointer_rollback_together(tmp_path):
    store, admissions = service(tmp_path / 'sessions.sqlite3')
    try:
        store._connection.execute("CREATE TRIGGER reject_cognition BEFORE INSERT ON character_session_cognition_heads BEGIN SELECT RAISE(ABORT, 'pending_index_failure'); END")
        with pytest.raises(Exception, match='pending_index_failure'):
            admissions.admit(**request())
        assert store._connection.execute("SELECT count(*) FROM character_session_receipts WHERE kind='cognition_admission'").fetchone()[0] == 0
        assert admissions.list_pending(limit=32) == ()
        store._connection.execute('DROP TRIGGER reject_cognition')
        assert admissions.admit(**request()).state == 'admitted'
    finally:
        store.close()


def test_child_pending_keyset_is_bounded_and_does_not_lose_over_1000(tmp_path):
    path = tmp_path / 'sessions.sqlite3'
    store, admissions = service(path)
    expected = {admissions.admit(**request(index)).child_key for index in range(1007)}
    store.close()
    store, admissions = service(path)
    try:
        seen, cursor = set(), None
        while page := admissions.list_pending(limit=32, cursor=cursor):
            assert len(page) <= 32
            assert not seen.intersection(row.child_key for row in page)
            seen.update(row.child_key for row in page)
            cursor = page[-1].admitted_at, page[-1].child_key
        assert seen == expected
        assert store.event_count('char_a') == 0
    finally:
        store.close()

@pytest.mark.parametrize('path', [None, ':memory:', ''])
def test_child_admission_rejects_non_durable_archive(path):
    from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
    store = CharacterAgentSessionStore(database_path=path)
    store.initialize_recovery()
    try:
        with pytest.raises(ValueError, match='cognition_admission_requires_durable_session'):
            CharacterCognitionAdmissionService(store=store, assert_owner=lambda: None,
                validate_source=lambda _: None, activation_is_current=lambda *_: True)
    finally:
        store.close()


@pytest.mark.parametrize('failure', ['source', 'activation', 'payload', 'expired', 'siming_actor'])
def test_child_admission_rejected_boundary_is_zero_write(tmp_path, failure):
    from types import SimpleNamespace
    def validate(entry):
        if failure == 'source':
            raise ValueError('source_revoked')
    store, admissions = service(tmp_path / 'rejected.sqlite3', validate=validate)
    values = request()
    if failure == 'activation':
        values['activation'] = SimpleNamespace(actor_id='char_a', lock_ref='lock', token='old')
    elif failure == 'payload':
        values['payload'] = {'project_secret': 'must stay provenance only'}
    elif failure == 'expired':
        values['now'] = 200.
    elif failure == 'siming_actor':
        # 不依赖来源校验器补救 delivery 的结构/actor 绑定错误。
        values['source_kind'] = 'ingest_siming_output'
        values['payload'] = {'actor_id': 'char_b'}
    try:
        with pytest.raises(ValueError):
            admissions.admit(**values)
        assert admissions.list_pending() == ()
        assert store._connection.execute("SELECT count(*) FROM character_session_receipts WHERE kind='cognition_admission'").fetchone()[0] == 0
        assert store.event_count('char_a') == 0
    finally:
        store.close()


def test_actual_siming_delivery_is_frozen_without_perception_or_shared_payload(tmp_path):
    from types import SimpleNamespace
    from test_siming_character_dispatch_adapter import make_siming_event
    from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
    event = make_siming_event(target_ids=['char_a'])
    delivery = SimingCharacterDispatchAdapter(runtime=SimpleNamespace(supports_actor=lambda _: True)).prepare_deliveries(event).delivery_inputs[0]
    store, admissions = service(tmp_path / 'siming.sqlite3')
    values = {**request(), 'source_event': event, 'source_kind': 'ingest_siming_output',
        'delivery_id': delivery.delivery_id, 'producer_ts': delivery.producer_ts, 'payload': delivery.model_dump(mode='json'),
        'activation': SimpleNamespace(actor_id='char_a', lock_ref='lock', token='token')}
    try:
        first = admissions.admit(**values)
        values['payload']['presentation_hint'] = 'mutated'
        event.payload['presentation_hint'] = 'mutated source'
        first.payload['presentation_hint'] = 'mutated return'
        restored = admissions.read(first.child_key)
        assert restored.payload['presentation_hint'] == delivery.presentation_hint
        assert restored.source_event['payload']['presentation_hint'] == delivery.presentation_hint
        assert store.event_count('char_a') == 0
    finally:
        store.close()


def test_cognition_receipt_content_corruption_is_rejected(tmp_path):
    import json
    store, admissions = service(tmp_path / 'corrupt.sqlite3')
    first = admissions.admit(**request())
    corrupt = first.model_dump(mode='json')
    corrupt['source_pins']['revision'] = 999
    store._connection.execute("UPDATE character_session_receipts SET receipt_json=? WHERE kind='cognition_admission'", (json.dumps(corrupt),))
    store._connection.commit()
    try:
        with pytest.raises(ValueError, match='cognition_admission_digest_mismatch'):
            admissions.read(first.child_key)
        with pytest.raises(ValueError, match='cognition_admission_digest_mismatch'):
            admissions.list_pending()
    finally:
        store.close()


def test_child_admission_survives_process_exit_before_parent_receipt(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    path = tmp_path / 'hard-exit.sqlite3'
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(Path('backend').resolve()), str(Path('backend/tests').resolve())])}
    code = "import os,sys; from test_character_cognition_admission import service,request; store,admissions=service(sys.argv[1]); admissions.admit(**request()); os._exit(0)"
    subprocess.run([sys.executable, '-c', code, str(path)], env=env, check=True, timeout=20)
    store, admissions = service(path)
    try:
        pending = admissions.list_pending()
        assert len(pending) == 1
        assert admissions.admit(**{**request(), 'now': 101.}) == pending[0]
        assert store.event_count('char_a') == 0
    finally:
        store.close()


def test_public_child_key_and_business_tick_do_not_depend_on_wall_clock(tmp_path):
    from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
    store, admissions = service(tmp_path / 'tick.sqlite3')
    try:
        first = admissions.admit(**request())
        assert first.child_key == CharacterCognitionAdmissionService.key_for(
            source_event_id=request()['source_event'].event_id, actor_id='char_a', delivery_id='delivery:0')
        assert first.producer_ts == 42 and first.admitted_at == 100.
        with pytest.raises(ValueError, match='cognition_admission_conflict'):
            admissions.admit(**{**request(), 'producer_ts': 43})
        assert admissions.read(first.child_key).producer_ts == 42
    finally:
        store.close()


def test_original_admission_without_business_tick_stays_readable_without_inventing_time(tmp_path):
    import hashlib
    import json
    store, admissions = service(tmp_path / 'legacy-tick.sqlite3')
    first = admissions.admit(**request())
    raw = first.model_dump(mode='json')
    raw.pop('producer_ts')
    inputs = {key: value for key, value in raw.items() if key not in {
        'schema_version', 'child_key', 'admitted_at', 'state', 'input_digest'}}
    raw['input_digest'] = hashlib.sha256(json.dumps(inputs, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    store._connection.execute("UPDATE character_session_receipts SET receipt_json=? WHERE kind='cognition_admission'", (json.dumps(raw),))
    store._connection.commit()
    try:
        original = admissions.read(first.child_key)
        assert original.producer_ts is None and original.admitted_at == 100.
        with pytest.raises(ValueError, match='cognition_admission_conflict'):
            admissions.admit(**request())
    finally:
        store.close()

@pytest.mark.parametrize('tick', [None, True, '42'])
def test_new_admission_requires_actual_integer_business_tick(tmp_path, tick):
    store, admissions = service(tmp_path / 'missing-tick.sqlite3')
    try:
        with pytest.raises(ValueError):
            admissions.admit(**{**request(), 'producer_ts': tick})
        assert admissions.list_pending() == ()
    finally:
        store.close()
