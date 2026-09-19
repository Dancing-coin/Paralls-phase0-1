"""停止 backend 后只读导出 Character 原子回执；离线只保留当前子任务的阶段数据。"""
from collections import Counter
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from app.character_agent.services.cognition_admission import (
    CharacterCognitionAdmissionService, CharacterCognitionProgress, _digest,
)
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from scripts.verification.verify_population_godot_runtime import json_lines


def verify_scheduled_source(entry, proof):
    """将调度子任务绑定到原 session 行与同事务保存的完整接纳批次。"""
    from app.character_agent.services.scheduled_cognition import ScheduledCognitionSource
    from app.population_continuity.activation_policy import ActivationPolicy
    if not isinstance(proof, dict) or set(proof) != {'row', 'event', 'batch'}:
        raise ValueError('mixed_scheduled_source_missing')
    event, batch = proof['event'], proof['batch']
    if (not isinstance(event, dict) or proof['row'] != [event.get(name) for name in
            ('actor_id', 'event_index', 'event_id', 'event_type')] or event != entry.source_event
            or not isinstance(batch, dict) or set(batch) != {'source_digest', 'child_keys'}
            or batch['source_digest'] != _digest(event) or not isinstance(batch['child_keys'], list)
            or not all(isinstance(key, str) and key for key in batch['child_keys'])
            or len(set(batch['child_keys'])) != len(batch['child_keys'])
            or entry.child_key not in batch['child_keys'] or entry.parent_effect_key):
        raise ValueError('mixed_scheduled_source_conflict')
    reader = SimpleNamespace(read_event=lambda actor, *, event_id:
        event if (actor, event_id) == (event['actor_id'], event['event_id']) else None)
    ScheduledCognitionSource(runtime=SimpleNamespace(_session_store=reader), policy=ActivationPolicy()).validate(entry)
    return event['actor_id'], event['event_id']


def export_character(database, target):
    """不初始化 store、不迁移；缺少 schema 原样导出缺证据状态。"""
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)) as db, target.open('x', encoding='utf-8') as output:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        def write(row):
            output.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n')
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='character_session_cognition_heads'").fetchone()
        if not exists:
            write(dict(type='character_end', schema_present=False, jobs=0, admissions=0, progress=0, stages=0, scheduled_batches=0))
            return
        jobs = 0
        for head in db.execute('SELECT child_key,actor_id,admitted_at,stage_revision,pending FROM character_session_cognition_heads ORDER BY child_key'):
            key, actor, _, revision, _ = head
            admission = db.execute("SELECT receipt_json FROM character_session_receipts WHERE actor_id=? AND kind='cognition_admission' AND receipt_key=?", (actor, key)).fetchone()
            if admission is None:
                raise ValueError('mixed_character_admission_missing')
            header = dict(type='character_admission', head=list(head), admission=json.loads(admission[0]))
            if 'scheduled_session' in header['admission']['source_pins']:
                entry = CharacterCognitionAdmissionService._validated(header['admission'])
                source = entry.source_event
                row = db.execute('SELECT actor_id,event_index,event_id,event_type,payload_json FROM character_session_events WHERE actor_id=? AND event_id=?',
                    (source.get('actor_id'), source.get('event_id'))).fetchone()
                batch = db.execute("SELECT receipt_json FROM character_session_receipts WHERE actor_id=? AND kind='scheduled_cognition' AND receipt_key=?",
                    (source.get('actor_id'), source.get('event_id'))).fetchone()
                if row is None or batch is None:
                    raise ValueError('mixed_scheduled_original_source_missing')
                header['scheduled_source'] = dict(row=list(row[:4]), event=json.loads(row[4]), batch=json.loads(batch[0]))
                verify_scheduled_source(entry, header['scheduled_source'])
            write(header)
            for index in range(1, revision+1):
                row = db.execute("SELECT receipt_json FROM character_session_receipts WHERE actor_id=? AND kind='cognition_progress' AND receipt_key=?", (actor, f'{key}/progress:{index}')).fetchone()
                if row is None:
                    raise ValueError('mixed_character_progress_missing')
                write(dict(type='character_progress', progress=json.loads(row[0])))
            for receipt_key, raw in db.execute("SELECT receipt_key,receipt_json FROM character_session_receipts WHERE actor_id=? AND kind='cognition_stage' AND receipt_key>=? AND receipt_key<? ORDER BY receipt_key", (actor, key+'/', key+'0')):
                receipt = json.loads(raw)
                events = []
                for event in receipt['events']:
                    row = db.execute('SELECT actor_id,event_index,event_id,event_type,payload_json FROM character_session_events WHERE actor_id=? AND event_id=?', (actor, event['event_id'])).fetchone()
                    if row is None or row[:4] != tuple(event[name] for name in ('actor_id', 'event_index', 'event_id', 'event_type')) or json.loads(row[4]) != event:
                        raise ValueError('mixed_character_event_index_mismatch')
                    events.append(json.loads(row[4]))
                write(dict(type='character_stage', key=receipt_key, receipt=receipt, events=events))
            write(dict(type='character_job_end', child_key=key))
            jobs += 1
        # 独立导出每个 scheduled 批次，即使其 child head/admission 已被清理。
        for actor_id, receipt_key, receipt_json in db.execute("SELECT actor_id,receipt_key,receipt_json FROM character_session_receipts WHERE kind='scheduled_cognition' ORDER BY actor_id,receipt_key"):
            batch = json.loads(receipt_json)
            write(dict(type='scheduled_batch', actor_id=actor_id, receipt_key=receipt_key, batch=batch))
        counts = dict(db.execute("SELECT kind,COUNT(*) FROM character_session_receipts WHERE kind IN ('cognition_admission','cognition_progress','cognition_stage') GROUP BY kind"))
        write(dict(type='character_end', schema_present=True, jobs=jobs, admissions=counts.get('cognition_admission', 0),
            progress=counts.get('cognition_progress', 0), stages=counts.get('cognition_stage', 0),
            scheduled_batches=db.execute("SELECT COUNT(*) FROM character_session_receipts WHERE kind='scheduled_cognition'").fetchone()[0]))


def verify_character(path):
    """复用原 progress 状态机和 stage 回执构造；返回关联元数据，不能单独证明 B2 或真模型通过。"""
    counts, states, jobs, seen, claimed_events = Counter(), Counter(), [], set(), set()
    scheduled_groups = {}
    current, footer = None, None
    # 无数据库/目录参数，只用原纯回执构造和事件校验，不恢复 Character runtime。
    session = CharacterAgentSessionStore()
    try:
        for row in json_lines(path):
            kind = row['type']
            if footer is not None:
                raise ValueError('mixed_character_after_footer')
            if kind == 'scheduled_batch':
                batch = row.get('batch')
                if not isinstance(batch, dict) or not isinstance(batch.get('child_keys'), list) or not batch.get('child_keys'):
                    raise ValueError('mixed_scheduled_batch_invalid')
                identity = (str(row.get('actor_id')), str(row.get('receipt_key')))
                if batch.get('source_digest') is None:
                    raise ValueError('mixed_scheduled_batch_missing_source')
                existing = scheduled_groups.get(identity)
                if existing is not None:
                    if existing.get('declared') or existing['batch'] != batch:
                        raise ValueError('mixed_scheduled_batch_conflict')
                    existing['declared'] = True
                else:
                    scheduled_groups[identity] = dict(batch=batch, children=set(), declared=True)
            elif kind == 'character_admission':
                if current is not None:
                    raise ValueError('mixed_character_job_end_missing')
                entry = CharacterCognitionAdmissionService._validated(row['admission'])
                if 'scheduled_session' in entry.source_pins:
                    identity = verify_scheduled_source(entry, row.get('scheduled_source'))
                    batch = row['scheduled_source']['batch']
                    group = scheduled_groups.setdefault(identity, dict(batch=batch, children=set()))
                    if group['batch'] != batch:
                        raise ValueError('mixed_scheduled_group_conflict')
                    group['children'].add(entry.child_key)
                elif 'scheduled_source' in row:
                    raise ValueError('mixed_scheduled_source_unexpected')
                head = row['head']
                if (entry.child_key in seen or len(head) != 5 or head[:3] != [entry.child_key, entry.actor_id, entry.admitted_at]
                        or type(head[3]) is not int or head[3] < 0 or type(head[4]) is not int or head[4] not in (0, 1)):
                    raise ValueError('mixed_character_head_invalid')
                seen.add(entry.child_key)
                history = {}
                # 原状态机只写本任务的临时进度字典；原始 SQLite 始终只读。
                store = SimpleNamespace(initialize_cognition_admissions=lambda: None,
                    read_cognition_admission=lambda key: entry.model_dump(mode='json') if key == entry.child_key else None,
                    read_cognition_progress=lambda key, revision=None: history.get(max(history, default=0) if revision is None else revision),
                    save_cognition_progress=lambda value, expected_revision: history.__setitem__(value['revision'], value))
                api = CharacterCognitionAdmissionService(store=store, assert_owner=lambda: None,
                    validate_source=lambda _: None, activation_is_current=lambda *_: False)
                current = dict(entry=entry, head=head, history=history, api=api, required=set(), allowed={}, receipts={}, providers={})
                counts['admissions'] += 1
            elif kind == 'character_progress':
                if current is None or current['receipts']:
                    raise ValueError('mixed_character_progress_order_invalid')
                progress = CharacterCognitionProgress.model_validate(row['progress'])
                previous = current['api'].read_progress(entry.child_key)
                if (progress.child_key != entry.child_key or progress.actor_id != entry.actor_id
                        or progress.input_digest != entry.input_digest or progress.revision != len(history)+1
                        or progress.progress_digest != _digest(progress.model_dump(mode='json', exclude={'progress_digest'}))):
                    raise ValueError('mixed_character_progress_binding_invalid')
                replay = current['api'].advance_progress(key=entry.child_key, expected_revision=len(history),
                    now=entry.admitted_at, **progress.model_dump(exclude={'schema_version', 'child_key', 'actor_id', 'input_digest', 'revision', 'progress_digest'}))
                if replay != progress:
                    raise ValueError('mixed_character_progress_replay_changed')
                if progress.status == 'commit_started':
                    stage_key = entry.child_key + ('/entry' if progress.stage == 'entry' else '/'+progress.stage+'/effects')
                    plan = progress.plan
                    current['allowed'][stage_key] = dict(actor_id=entry.actor_id, key=stage_key,
                        **{name:plan[name] for name in ('expected_revision', 'events', 'before', 'after')})
                if progress.status in {'stage_ready', 'completed'}:
                    stage_key = entry.child_key + ('/entry' if progress.stage == 'entry' else '/'+progress.stage+'/effects')
                    current['required'].add(stage_key)
                if progress.status == 'provider_pending':
                    current['providers'][progress.stage] = dict(stage=progress.stage,
                        request_sha256=sha256(progress.request_json.encode('utf-8')).hexdigest(), output_sha256=None, error=None)
                    if progress.stage == 'l2':
                        key = entry.child_key+'/l2/request'
                        current['required'].add(key)
                        current['allowed'][key] = dict(actor_id=entry.actor_id, key=key,
                            events=[dict(event_type='l2_reasoning_request', producer_ts=entry.producer_ts, payload=json.loads(progress.request_json))],
                            before=previous.frame, after=progress.frame)
                if progress.completion is not None:
                    binding = current['providers'].get(progress.stage)
                    if binding is None:
                        raise ValueError('mixed_character_completion_without_provider')
                    completion = progress.completion
                    if set(completion) == {'output'}:
                        binding['output_sha256'] = _digest(completion['output'])
                    elif (set(completion) == {'error', 'fallback'} and isinstance(completion['fallback'], dict)
                            and isinstance(completion['error'], dict) and set(completion['error']) == {'type', 'message'}
                            and isinstance(completion['error']['type'], str) and completion['error']['type']
                            and isinstance(completion['error']['message'], str)):
                        # 失败回执关联原失败调用；fallback不冒充provider产生的output。
                        binding['error'] = completion['error']['type']
                    else:
                        raise ValueError('mixed_character_provider_completion_invalid')
                counts['progress'] += 1
            elif kind == 'character_stage':
                if current is None or len(history) != current['head'][3]:
                    raise ValueError('mixed_character_stage_order_invalid')
                key, receipt = row['key'], row['receipt']
                expected_plan = current['allowed'].get(key)
                if key in current['receipts'] or expected_plan is None:
                    raise ValueError('mixed_character_stage_unbound')
                plan = receipt['plan']
                if any(plan.get(name) != value for name, value in expected_plan.items()):
                    raise ValueError('mixed_character_stage_plan_conflict')
                expected = session._cognition_stage_receipt(**plan)
                if receipt != expected or row['events'] != expected['events']:
                    raise ValueError('mixed_character_stage_event_missing_or_conflicting')
                for event in row['events']:
                    identity = entry.actor_id, event['event_index']
                    if identity in claimed_events:
                        raise ValueError('mixed_character_stage_event_duplicate')
                    claimed_events.add(identity)
                current['receipts'][key] = receipt
                counts['stages'] += 1
            elif kind == 'character_job_end':
                if current is None or row['child_key'] != entry.child_key or len(history) != current['head'][3]:
                    raise ValueError('mixed_character_job_coverage_invalid')
                if not current['required'] <= current['receipts'].keys():
                    raise ValueError('mixed_character_original_stage_receipt_missing')
                latest = current['api'].read_progress(entry.child_key)
                state = latest.status if latest is not None else 'admitted'
                if current['head'][4] != int(state not in {'completed', 'stale'}):
                    raise ValueError('mixed_character_pending_index_invalid')
                states[state] += 1
                jobs.append(dict(child_key=entry.child_key, actor_id=entry.actor_id, delivery_id=entry.delivery_id,
                    source_kind=entry.source_kind, source_event=entry.source_event, source_pins=entry.source_pins,
                    input_digest=entry.input_digest, parent_effect_key=entry.parent_effect_key, payload=entry.payload,
                    producer_ts=entry.producer_ts, admitted_at=entry.admitted_at, expires_at=entry.expires_at,
                    state=state, providers=list(current['providers'].values())))
                current = None
            elif kind == 'character_end':
                footer = row
            else:
                raise ValueError('mixed_character_record_kind_invalid')
        if current is not None or footer is None or type(footer.get('schema_present')) is not bool:
            raise ValueError('mixed_character_footer_missing')
        expected = dict(type='character_end', schema_present=footer['schema_present'], jobs=len(jobs),
            admissions=counts['admissions'], progress=counts['progress'], stages=counts['stages'], scheduled_batches=len(scheduled_groups))
        if footer != expected or (not footer['schema_present'] and jobs):
            raise ValueError('mixed_character_ledger_coverage_invalid')
        if any(not group.get('declared') or set(group['batch']['child_keys']) != group['children'] for group in scheduled_groups.values()):
            raise ValueError('mixed_scheduled_group_incomplete')
        return dict(schema_present=footer['schema_present'], states=dict(states), completed=states['completed'],
            pending=len(jobs)-states['completed']-states['stale'], jobs=jobs)
    finally:
        session.close()
