"""冻结大字段仍须约束任务身份、完整正文和事务边界。"""
import json

import pytest

from app.character_agent.services.cognition_admission import _digest
from app.character_agent.services.cognition_frame import freeze_fields
from test_character_cognition_coordinator import setup


def prepare(tmp_path):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    return rt, admissions, coordinator, child, handle, pending


@pytest.mark.parametrize('failure', ['missing', 'changed'])
def test_bad_frozen_body_blocks_progress_consumption_and_startup_stage_proof(tmp_path, failure):
    rt, admissions, coordinator, child, handle, pending = prepare(tmp_path)
    try:
        db = rt._session_store._connection
        if failure == 'missing':
            db.execute("DELETE FROM character_session_receipts WHERE kind='cognition_frame'")
        else:
            db.execute("UPDATE character_session_receipts SET receipt_json='{}' WHERE kind='cognition_frame'")
        db.commit()
        writes = db.total_changes
        for call in (lambda: admissions.read_progress(child.child_key),
                lambda: rt._cognition_frame_value(pending.frame, 'context'),
                lambda: rt._session_store.read_current_cognition_stage('char_a'),
                lambda: coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})):
            with pytest.raises(ValueError, match='cognition_frame_payload_missing_or_changed'):
                call()
        assert db.total_changes == writes
    finally:
        rt.close()


@pytest.mark.parametrize('failure', ['actor', 'child', 'origin', 'both'])
def test_valid_progress_digest_does_not_authorize_a_foreign_or_ambiguous_reference(tmp_path, failure):
    rt, admissions, _, child, _, pending = prepare(tmp_path)
    try:
        raw = pending.model_dump(mode='json')
        frame = raw['frame']
        if failure == 'actor':
            frame['context_ref']['actor_id'] = 'char_b'
        elif failure == 'child':
            frame['child_key'] = frame['context_ref']['child_key'] = 'different-child'
        elif failure == 'origin':
            frame['context_ref']['origin_stage'] = []
        else:
            frame['context'] = {}
        raw['progress_digest'] = _digest({k: v for k, v in raw.items() if k != 'progress_digest'})
        db = rt._session_store._connection
        db.execute("UPDATE character_session_receipts SET receipt_json=? WHERE kind='cognition_progress' AND receipt_key=?",
            (json.dumps(raw), f'{child.child_key}/progress:{pending.revision}'))
        db.commit()
        with pytest.raises(ValueError, match='cognition_frame_reference_invalid'):
            admissions.read_progress(child.child_key)
    finally:
        rt.close()


def test_new_missing_reference_is_rejected_before_any_progress_write(tmp_path):
    rt, admissions, _, child, _ = setup(tmp_path)
    try:
        frame = dict(actor_id='char_a', child_key=child.child_key, stage='entry', context_ref=dict(
            actor_id='char_a', child_key=child.child_key, origin_stage='l2', field='context', digest='0'*64))
        writes = rt._session_store._connection.total_changes
        with pytest.raises(ValueError, match='cognition_frame_payload_missing_or_changed'):
            admissions.advance_progress(key=child.child_key, expected_revision=0, stage='entry', status='commit_started',
                frame=frame, plan=dict(before=frame, after=frame, events=[]), now=110.)
        assert rt._session_store._connection.total_changes == writes
        assert admissions.read_progress(child.child_key) is None
    finally:
        rt.close()


def test_legacy_inline_context_resumes_into_new_l3_reference_without_rewriting_history(tmp_path, monkeypatch):
    from app.character_agent.services import cognition_coordinator
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    monkeypatch.setattr(cognition_coordinator, 'freeze_fields', lambda store, frame, **kwargs:
        dict(frame, **kwargs['fields']) if kwargs['origin_stage'] == 'l2' else freeze_fields(store, frame, **kwargs))
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    assert 'context' in pending.frame and 'context_ref' not in pending.frame
    coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})
    coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
    coordinator.resume_l2(child.child_key, activation=handle, now=115.)
    original = rt._session_store.read_receipt_json('char_a', kind='cognition_stage', key=child.child_key+'/l2/effects')
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    try:
        l3 = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
        assert l3.frame['context'] == pending.frame['context']
        assert l3.frame['l3_prepared_ref']['origin_stage'] == 'l3'
        from app.character_agent.planning.l3_planner import PreparedCharacterIntentPlan
        restored = PreparedCharacterIntentPlan.from_json_value(rt._cognition_frame_value(l3.frame, 'l3_prepared'))
        assert restored.request_json.decode() == l3.request_json
        assert rt._session_store.read_receipt_json('char_a', kind='cognition_stage', key=child.child_key+'/l2/effects') == original
    finally:
        rt.close()
