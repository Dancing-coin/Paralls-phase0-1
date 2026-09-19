"""Siming 原入站修订及 effect 拥有者证明；backend 停止后只读，不重启运行时。"""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from app.models.siming_heavenly_graph import HeavenlyGraphNode, HeavenlyGraphWriteBatch, HeavenlyGraphWriteResult
from app.models.siming_heavenly_memory import SimingAdmissionMemoryEntry, SIMING_ADMISSION_TERMINAL
from app.services.siming_admission import SimingAdmissionService
from app.services.siming_continuation import digest, SimingProviderRequest, SimingProviderCompletion
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from scripts.verification.population_mixed_provider import _hash
from scripts.verification.verify_population_godot_runtime import json_lines


def export_siming(database, target):
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)) as db, target.open('x', encoding='utf-8') as output:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        def write(row):
            output.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n')
        def end(scope, key):
            pending = db.execute('SELECT revision,state,due_at,room_sequence FROM graph_siming_pending WHERE scope_json=? AND entry_id=?', (scope, key)).fetchone()
            write(dict(type='siming_job_end', entry_id=key, pending=None if pending is None else list(pending)))
        previous, plan, proven, revisions, jobs = None, {}, set(), 0, 0
        for scope, key, revision, raw in db.execute("SELECT scope_json,node_id,revision,payload_json FROM graph_nodes WHERE json_extract(payload_json,'$.node_type')='siming_admission' ORDER BY scope_json,node_id,revision"):
            if previous != (scope, key):
                if previous is not None:
                    end(*previous)
                previous, plan, proven = (scope, key), {}, set()
                jobs += 1
            node = json.loads(raw)
            if (json.loads(scope), key, revision) != (node['scope'], node['node_id'], node['revision']):
                raise ValueError('mixed_siming_node_index_mismatch')
            write(dict(type='siming_revision', node=node))
            revisions += 1
            entry = SimingAdmissionMemoryEntry.model_validate(node['attributes'])
            if entry.transition is None:
                continue
            if entry.transition.effects:
                plan = {effect.effect_key:effect for effect in entry.transition.effects}
            for receipt in entry.transition.receipts:
                if receipt.effect_key in proven:
                    continue
                effect = plan[receipt.effect_key]
                proven.add(receipt.effect_key)
                if effect.kind not in {'graph_batch', 'dispatch_record'}:
                    continue
                batch = HeavenlyGraphWriteBatch.model_validate(effect.payload)
                encoded = json.dumps(batch.scope.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))
                stored = db.execute('SELECT payload_hash,result_json FROM graph_idempotency WHERE scope_json=? AND idempotency_key=?', (encoded, batch.idempotency_key)).fetchone()
                if stored is None:
                    raise ValueError('mixed_siming_graph_owner_receipt_missing')
                proof = dict(type='siming_graph_effect', effect_key=effect.effect_key, payload_hash=stored[0], result=json.loads(stored[1]))
                for table, identity, values, field in (('graph_nodes', 'node_id', batch.nodes, 'nodes'), ('graph_relations', 'relation_id', batch.relations, 'relations')):
                    proof[field] = []
                    for value in values:
                        item_scope = json.dumps(value.scope.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))
                        row = db.execute(f'SELECT payload_json FROM {table} WHERE scope_json=? AND {identity}=? AND revision=?', (item_scope, getattr(value, identity), value.revision)).fetchone()
                        if row is None or json.loads(row[0]) != value.model_dump(mode='json'):
                            raise ValueError('mixed_siming_graph_owner_effect_missing_or_changed')
                        proof[field].append(json.loads(row[0]))
                write(proof)
        if previous is not None:
            end(*previous)
        write(dict(type='siming_end', jobs=jobs, revisions=revisions,
            pending=db.execute('SELECT COUNT(*) FROM graph_siming_pending').fetchone()[0]))


def verify_siming(path, *, character_jobs):
    """原 transition 校验+原修订构造+真实graph/child证明；完成父任务不等于完成其子认知。"""
    children = {item['child_key']:item for item in character_jobs}
    if len(children) != len(character_jobs):
        raise ValueError('mixed_siming_duplicate_child')
    api = SimingAdmissionService(None)
    api._write = lambda *args, **kwargs: None
    graph = InMemoryHeavenlyGraphAdapter()  # 只用原 batch hash/entity ref 纯方法，不载入历史。
    jobs, seen, states, pending_count, revisions, graph_count = [], set(), Counter(), 0, 0, 0
    previous, plan, receipts, owners, providers, footer = None, {}, {}, {}, [], None
    for row in json_lines(path):
        category = row['type']
        if footer is not None:
            raise ValueError('mixed_siming_after_footer')
        if category == 'siming_revision':
            node = HeavenlyGraphNode.model_validate(row['node'])
            entry = SimingAdmissionMemoryEntry.model_validate(node.attributes)
            if (node.node_type != 'siming_admission' or node.node_id != entry.entry_id or node.scope != entry.key.scope
                    or node.revision != entry.revision or node.supersedes_revision != (entry.revision-1 if entry.revision > 1 else None)
                    or node.provenance.source_ref != entry.key.source_event_id or node.provenance.producer_system != 'siming_admission'
                    or entry.source.get('event_id') != entry.key.source_event_id or digest(entry.source) != entry.source_digest
                    or entry.expires_at <= entry.admitted_at):
                raise ValueError('mixed_siming_revision_binding_invalid')
            if previous is None:
                if entry.entry_id in seen or entry.revision != 1 or entry.state != 'admitted' or entry.transition is not None:
                    raise ValueError('mixed_siming_original_admission_invalid')
                seen.add(entry.entry_id)
                plan, receipts, owners, providers = {}, {}, {}, []
            else:
                if entry.key != previous.key or entry.revision != previous.revision+1 or previous.state in SIMING_ADMISSION_TERMINAL or entry.transition is None:
                    raise ValueError('mixed_siming_revision_gap_or_terminal_changed')
                transition = entry.transition
                now = max(previous.admitted_at, float(node.recorded_at))
                if transition.state == 'requeued' and transition.reason == 'candidate_timeline_changed':
                    if transition.due_at is None or not node.recorded_at <= transition.due_at < node.recorded_at + 1:
                        raise ValueError('mixed_siming_requeue_time_invalid')
                    now = transition.due_at
                api._validate_transition(previous, transition, now)
                transition_hash = digest(transition.model_dump(mode='json', exclude={'room_head'} if transition.room_head is None else set()))
                expected = api._commit_transition(previous, transition, now, transition_hash).entry
                if entry != expected:
                    raise ValueError('mixed_siming_transition_replay_changed')
                if transition.effects:
                    plan = {effect.effect_key:effect for effect in transition.effects}
                if transition.state == 'provider_pending':
                    request = SimingProviderRequest.model_validate_json(transition.provider.request_json)
                    kwargs = (dict(snapshot=request.snapshot, recent_events=[request.event], recent_audit=[]) if request.stage == 'candidate'
                        else dict(compiled_context=request.compiled_context, correlation_id=request.event.correlation_id))
                    providers.append(dict(stage=request.stage, revision=entry.revision, request_sha256=_hash(kwargs),
                        source_event_id=request.event.event_id, output_sha256=None, error=None))
                if transition.completion_json is not None:
                    completion = SimingProviderCompletion.model_validate_json(transition.completion_json)
                    if not providers:
                        raise ValueError('mixed_siming_completion_without_provider')
                    if providers[-1]['stage'] == 'candidate':
                        from app.models.siming_event import InterventionCandidate
                        result = [InterventionCandidate.model_validate(item.model_dump(include=set(InterventionCandidate.model_fields))) for item in completion.candidates]
                    else:
                        result = completion.proposal_batch
                    providers[-1].update(output_sha256=_hash(result), error=completion.error)
                if transition.state == 'requeued' and transition.reason == 'candidate_timeline_changed':
                    providers[-1].update(rejected_revision=entry.revision, rejection_reason=transition.reason)
                for receipt in transition.receipts:
                    effect = plan[receipt.effect_key]
                    if effect.effect_key in receipts:
                        if receipts[effect.effect_key] != receipt.receipt:
                            raise ValueError('mixed_siming_prior_effect_receipt_changed')
                        continue
                    receipts[effect.effect_key] = receipt.receipt
                    payload = effect.payload
                    if effect.kind in {'graph_batch', 'dispatch_record'}:
                        owners[effect.effect_key] = effect
                        batch = HeavenlyGraphWriteBatch.model_validate(payload)
                        expected_receipt = dict(transaction_id=batch.transaction_id, idempotency_key=batch.idempotency_key, batch_digest=digest(payload))
                    elif effect.kind == 'character_delivery':
                        child = children.get(receipt.receipt.get('child_key'))
                        if (child is None or child['input_digest'] != receipt.receipt.get('input_digest') or child['parent_effect_key'] != effect.effect_key
                                or child['source_kind'] != 'ingest_siming_output' or child['source_event'] != payload['event']
                                or child['payload'] != payload['delivery'] or child['expires_at'] != entry.expires_at):
                            raise ValueError('mixed_siming_character_original_admission_missing')
                        expected_receipt = dict(child_key=child['child_key'], input_digest=child['input_digest'])
                    elif effect.kind == 'runtime_state':
                        expected_receipt = dict(state_digest=digest(payload['state']))
                    elif effect.kind == 'audit_bundle':
                        expected_receipt = dict(audit_digest=digest(payload))
                    elif effect.kind == 'publish_event':
                        expected_receipt = dict(event_id=payload['event']['event_id'], event_digest=digest(payload['event']))
                    elif effect.kind == 'character_delivery_audit':
                        expected_receipt = dict(audit=payload['audit'])
                    else:
                        raise ValueError('mixed_siming_unknown_committed_effect')
                    if receipt.receipt != expected_receipt:
                        raise ValueError('mixed_siming_effect_receipt_mismatch')
            previous = entry
            revisions += 1
        elif category == 'siming_graph_effect':
            effect = owners.pop(row['effect_key'], None)
            if previous is None or effect is None:
                raise ValueError('mixed_siming_graph_proof_unbound')
            batch = HeavenlyGraphWriteBatch.model_validate(effect.payload)
            expected = HeavenlyGraphWriteResult(transaction_id=batch.transaction_id, idempotency_key=batch.idempotency_key, applied=True,
                node_refs=[graph._entity_ref('node', value.scope, value.node_id, value.revision) for value in batch.nodes],
                relation_refs=[graph._entity_ref('relation', value.scope, value.relation_id, value.revision) for value in batch.relations])
            if (row['payload_hash'] != graph._batch_hash(batch) or HeavenlyGraphWriteResult.model_validate(row['result']) != expected
                    or row['nodes'] != [value.model_dump(mode='json') for value in batch.nodes]
                    or row['relations'] != [value.model_dump(mode='json') for value in batch.relations]):
                raise ValueError('mixed_siming_graph_owner_proof_invalid')
            graph_count += 1
        elif category == 'siming_job_end':
            if previous is None or owners or row['entry_id'] != previous.entry_id:
                raise ValueError('mixed_siming_original_owner_proof_missing')
            if previous.state == 'completed' and (not any(effect.kind == 'audit_bundle' for effect in plan.values())
                    or not any(effect.kind == 'runtime_state' and effect.payload['after']['stage'] == 'completed' for effect in plan.values())):
                raise ValueError('mixed_siming_completed_plan_missing')
            pending = None if previous.state in SIMING_ADMISSION_TERMINAL else [previous.revision, previous.state, previous.due_at, previous.room_sequence]
            if row['pending'] != pending:
                raise ValueError('mixed_siming_pending_index_invalid')
            pending_count += pending is not None
            states[previous.state] += 1
            jobs.append(dict(entry_id=previous.entry_id, source=previous.source, state=previous.state,
                reason="" if previous.transition is None else previous.transition.reason,
                admitted_at=previous.admitted_at, expires_at=previous.expires_at, providers=providers))
            previous = None
        elif category == 'siming_end':
            footer = row
        else:
            raise ValueError('mixed_siming_record_kind_invalid')
    if previous is not None or footer != dict(type='siming_end', jobs=len(jobs), revisions=revisions, pending=pending_count):
        raise ValueError('mixed_siming_ledger_coverage_invalid')
    return dict(states=dict(states), pending=pending_count, completed=states['completed'], graph_effects=graph_count, jobs=jobs)
