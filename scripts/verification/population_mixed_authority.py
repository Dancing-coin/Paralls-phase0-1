"""停止写入后流式导出原 Gameplay 事务；离线复验不重开 runtime、不物化历史 payload。"""
from collections import Counter
from contextlib import closing
import json
import hashlib
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayOutboxEntry, ProjectionCheckpoint, OwnerAuthorizedFragment
from app.gameplay.event_store import GameplayEventStore, load_durable_json
from app.gameplay.organization_government_runtime import OrganizationAuthority, OperatingWindowDueRequest
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.recovery import parse_population_checkpoint, recovery_digest
from app.population_continuity.organization_due_source import OrganizationWindowDueSource, project_organization_due, _instant
from scripts.verification.verify_population_godot_runtime import json_lines


def export_gameplay(database: Path, target: Path):
    """调用者须先停止自己拥有的 backend；只读原文件，每次保留一个事务。"""
    count = 0
    with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro", uri=True)) as connection, target.open("x", encoding="utf-8") as stream:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        observed_at = datetime.now(timezone.utc).isoformat()
        def write(row):
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+"\n")
        for sequence, transaction, principal, key, digest, refresh, raw, result in connection.execute(
                "SELECT sequence,transaction_id,principal_ref,idempotency_key,payload_digest,refresh_state,batch,result FROM transactions ORDER BY sequence"):
            batch = load_durable_json(raw)
            # SQL索引与原事件体必须同一事实；不能只复制transactions而漏掉原events损坏。
            for event in batch["events"]:
                row = connection.execute("SELECT global_sequence,event_id,stream_id,stream_revision,transaction_id,value FROM events WHERE event_id=?", (event["event_id"],)).fetchone()
                if row is None or row[:5] != tuple(event[name] for name in ("global_sequence", "event_id", "stream_id", "stream_revision", "transaction_id")) or json.loads(row[5]) != event:
                    raise ValueError("mixed_authority_event_index_mismatch")
            outbox = []
            for row in connection.execute("SELECT id,delivery_state,topic,global_sequence,transaction_id,event_id,value FROM outbox WHERE transaction_id=? ORDER BY id", (transaction,)):
                entry = load_durable_json(row[6])
                if row[:6] != tuple(entry[name] for name in ("outbox_id", "delivery_state", "topic", "global_sequence", "transaction_id", "event_id")):
                    raise ValueError("mixed_authority_outbox_index_mismatch")
                outbox.append(entry)
            write(dict(type="transaction", index=[sequence, transaction, principal, key, digest], batch=batch,
                result=load_durable_json(result), outbox=outbox, refresh_state=refresh))
            count += 1
            for event in batch["events"]:
                if event["event_type"] == "population.cadence.admitted":
                    cadence = event["payload"]["cadence"]
                    row = connection.execute("SELECT id,projector_id,global_sequence,value FROM checkpoints WHERE id=?", (
                        f"population-receipt:{cadence['world_ref']}:{cadence['cadence_id']}",)).fetchone()
                    checkpoint = None if row is None else load_durable_json(row[3])
                    if row is not None and row[:3] != tuple(checkpoint[name] for name in ("checkpoint_id", "projector_id", "last_global_sequence")):
                        raise ValueError("mixed_authority_checkpoint_index_mismatch")
                    write(dict(type="population_checkpoint", event_id=event["event_id"], checkpoint=checkpoint))
        for stream_id, revision in connection.execute("SELECT stream_id,revision FROM stream_heads ORDER BY stream_id"):
            write(dict(type="stream_head", stream_id=stream_id, revision=revision))
        write(dict(type="ledger_end", transactions=count, observed_at=observed_at,
            authority_head=int(connection.execute("SELECT value FROM metadata WHERE key='last_global_sequence'").fetchone()[0]),
            event_count=connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            outbox_count=connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0],
            pending_outbox_by_topic=dict(connection.execute("SELECT topic,COUNT(*) FROM outbox WHERE delivery_state <> 'delivered' GROUP BY topic")),
            pending_projection_refresh=connection.execute("SELECT COUNT(*) FROM transactions WHERE refresh_state='pending'").fetchone()[0]))
    return dict(transactions=count)


def _due_batch_identity(requests):
    ordered = sorted(requests, key=lambda item: item.command_id)
    digest = hashlib.sha256(json.dumps([item.model_dump(mode='json') for item in ordered],
        sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return 'organization-window-due-batch:' + digest, ordered[0].correlation_id


def _verify_due_completion(batch, event, request, *, original_batch=None):
    stream = 'gameplay:organization:window:' + request.window_ref
    payload = dict(window_ref=request.window_ref, organization_ref=request.organization_ref, status='closed',
        due_state='recorded', owner_intent_idempotency_key=request.idempotency_key,
        owner_intent_digest=OrganizationAuthority._operating_window_due_intent_digest(request))
    if (event.stream_id != stream or event.payload != payload or event.visibility_policy != request.visibility_scope
            or event.stream_revision != request.expected_stream_revision + 1):
        raise ValueError('mixed_b1_completion_binding_invalid')
    if batch.idempotency_record.idempotency_key.startswith('organization-window-due-batch:'):
        if original_batch is None or batch.idempotency_record.idempotency_key != original_batch[0]:
            raise ValueError('mixed_b1_original_batch_missing')
        expected = OwnerAuthorizedFragment(fragment_id=f'fragment:{request.command_id}',
            owner_principal_ref=OrganizationAuthority._PRINCIPAL, source_rule_ref='inf:organization-operating-window@1',
            expected_revisions={stream: request.expected_stream_revision}, read_set_revisions={stream: request.expected_stream_revision},
            pinned_revisions={'organization_window_policy': 1}, event_specs={stream: ((event.event_type, payload),)},
            event_visibility_policies={stream: (request.visibility_scope,)})
        matching = [fragment for fragment in batch.owner_fragments if stream in fragment.event_specs]
        if (matching != [expected] or event.correlation_id != original_batch[1]
                or event.causation_id != 'population:' + original_batch[1]):
            raise ValueError('mixed_b1_owner_fragment_invalid')
    elif (batch.idempotency_record.idempotency_key != request.idempotency_key
            or batch.command_id != request.command_id or event.causation_id != request.causation_id
            or event.correlation_id != request.correlation_id):
        raise ValueError('mixed_b1_completion_identity_invalid')
    actual = [row for row in batch.outbox_entries if row.event_id == event.event_id]
    if len(actual) != 1 or (actual[0].topic, actual[0].audience, actual[0].payload_projection) != (
            'world.organization_window.scoped_projection', request.visibility_scope,
            dict(organization_ref=request.organization_ref, window_ref=request.window_ref, status='closed', due_recorded=True)):
        raise ValueError('mixed_b1_completion_projection_invalid')


def verify_gameplay(path: Path, *, mode, actors, expected_confirmed_tick, window_ticks):
    """复用原原子提交准备逻辑与receipt schema；仅保留索引身份和未完成原意图。"""
    mode = WorldModeProfile.model_validate(mode)
    if type(window_ticks) is not int or window_ticks <= 0 or type(expected_confirmed_tick) is not int or expected_confirmed_tick <= 0:
        raise ValueError("mixed_authority_window_configuration_invalid")
    context = recovery_digest(dict(mode=mode.model_dump(mode="json"), roster=actors, authorized_actor_refs=None))
    heads, transactions, identities, event_ids, outbox_ids = {}, set(), set(), set(), set()
    pending_outbox, pending_refresh = Counter(), 0
    pending_b1, completed_b1, domain_digests = {}, set(), {}
    batch_envelopes = {}
    schedules, windows, current_windows, source_heads = {}, {}, {}, {}
    source = OrganizationWindowDueSource(store=None, world_ref=mode.world_ref, roster=SimpleNamespace(actor_ids=tuple(actors)))
    global_sequence = confirmed = public_windows = requested_b1 = 0
    last_public = None
    phase, footer = "transactions", None
    for row in json_lines(path):
        category = row["type"]
        if footer is not None:
            raise ValueError("mixed_authority_data_after_footer")
        if category == "transaction":
            if phase != "transactions" or last_public is not None:
                raise ValueError("mixed_authority_checkpoint_missing_or_order_invalid")
            batch = AtomicEventBatch.model_validate_json(json.dumps(row["batch"], allow_nan=False))
            actual = AppendBatchResult.model_validate_json(json.dumps(row["result"], allow_nan=False))
            identity = batch.idempotency_record
            key = identity.principal_ref, identity.idempotency_key
            if key in identities:
                raise ValueError("mixed_authority_idempotency_duplicate")
            prepared = GameplayEventStore._prepare_append(batch, existing_record=None, existing_result=None,
                stream_heads={ref:heads.get(ref, 0) for ref in batch.expected_stream_revisions.keys() | batch.read_stream_revisions.keys()},
                transaction_exists=batch.transaction_id in transactions,
                existing_event_ids=event_ids.intersection(event.event_id for event in batch.events),
                existing_outbox_ids=outbox_ids.intersection(entry.outbox_id for entry in batch.outbox_entries),
                last_global_sequence=global_sequence)
            if not isinstance(prepared, tuple) or prepared != (batch, actual):
                raise ValueError("mixed_authority_atomic_batch_or_result_invalid")
            expected_index = [batch.events[-1].global_sequence, batch.transaction_id, identity.principal_ref, identity.idempotency_key, identity.payload_digest]
            if row["index"] != expected_index or type(row["index"][0]) is not int:
                raise ValueError("mixed_authority_transaction_index_mismatch")
            current_outbox = {item["outbox_id"]:GameplayOutboxEntry.model_validate(item) for item in row["outbox"]}
            if len(current_outbox) != len(row["outbox"]) or set(current_outbox) != {entry.outbox_id for entry in batch.outbox_entries}:
                raise ValueError("mixed_authority_outbox_membership_invalid")
            for original in batch.outbox_entries:
                current = current_outbox[original.outbox_id]
                mutable = {"delivery_state", "attempt_count", "last_error"}
                if current.model_dump(exclude=mutable) != original.model_dump(exclude=mutable):
                    raise ValueError("mixed_authority_outbox_content_changed")
                if current.delivery_state != "delivered":
                    pending_outbox[current.topic] += 1
            refresh = row["refresh_state"]
            eligible = bool(batch.outbox_entries or batch.projection_refresh_hints)
            if ((eligible and refresh not in {"pending", "done"}) or (not eligible and refresh is not None)
                    or (refresh == "done" and any(entry.delivery_state != "delivered" for entry in current_outbox.values()))):
                raise ValueError("mixed_authority_refresh_state_invalid")
            pending_refresh += refresh == "pending"
            identities.add(key)
            transactions.add(batch.transaction_id)
            event_ids.update(event.event_id for event in batch.events)
            outbox_ids.update(current_outbox)
            heads.update(actual.resulting_stream_revisions)
            global_sequence = batch.events[-1].global_sequence
            for event in batch.events:
                prior_closed = windows.get(event.payload.get("window_ref"))
                source_heads[event.stream_id] = event.stream_revision
                if event.stream_id.startswith('gameplay:organization:window:'):
                    current_windows[event.stream_id.removeprefix('gameplay:organization:window:')] = event.event_id
                if identity.principal_ref == OrganizationAuthority._PRINCIPAL:
                    source._apply(event, schedules, windows)
                if event.event_type == "population.cadence.admitted":
                    if last_public is not None or identity.principal_ref != "world_runtime.cadence":
                        raise ValueError("mixed_public_authority_invalid")
                    cadence = event.payload["cadence"]
                    if identity.idempotency_key != "population-runtime:"+cadence["cadence_id"]:
                        raise ValueError("mixed_public_idempotency_invalid")
                    last_public = event, current_outbox
                elif event.event_type == "gameplay.organization.operating_window_due_recorded":
                    ref = event.payload["window_ref"]
                    if ref not in pending_b1 or ref in completed_b1 or identity.principal_ref != OrganizationAuthority._PRINCIPAL:
                        raise ValueError("mixed_b1_original_intent_missing_or_duplicate")
                    request = pending_b1.pop(ref)
                    if (prior_closed is None or prior_closed.stream_revision != request.expected_stream_revision
                            or prior_closed.payload.get("organization_ref") != request.organization_ref):
                        raise ValueError("mixed_b1_closed_source_invalid")
                    _verify_due_completion(batch, event, request, original_batch=(identity.idempotency_key, batch_envelopes[identity.idempotency_key]) if identity.idempotency_key in batch_envelopes else None)
                    completed_b1.add(ref)
        elif category == "population_checkpoint":
            if last_public is None or row["event_id"] != last_public[0].event_id or row["checkpoint"] is None:
                raise ValueError("mixed_public_checkpoint_missing")
            event, outbox = last_public
            checkpoint = ProjectionCheckpoint.model_validate(row["checkpoint"])
            # 原函数直接核验事件、outbox、checkpoint/context/kernel摘要，无需重建全人口热表。
            world = SimpleNamespace(mode=mode, roster=SimpleNamespace(actor_ids=actors),
                _recovery_context_digest=lambda:context,
                store=SimpleNamespace(get_event={event.event_id:event}.__getitem__, get_outbox=outbox.__getitem__))
            data = parse_population_checkpoint(world, checkpoint)
            if data.cadence.window_start != confirmed or data.cadence.window_end != confirmed+window_ticks:
                raise ValueError("mixed_public_window_gap_or_duplicate")
            confirmed, public_windows = data.cadence.window_end, public_windows+1
            record = event.payload
            domain = record.get("domain_authority_event")
            if domain is not None:
                domain_id = record["domain_admission_cadence_id"]
                digest = recovery_digest(domain)
                if domain_id in domain_digests:
                    if domain_digests[domain_id] != digest:
                        raise ValueError("mixed_b1_original_domain_changed")
                else:
                    if domain_id != data.cadence.cadence_id:
                        raise ValueError("mixed_b1_original_domain_missing")
                    payload = domain["payload"]
                    projections = {item["ref"]:item for item in payload["population_projections"]}
                    owners = set()
                    original_requests = []
                    for projection_ref, raw in payload["population_owner_requests"].items():
                        request = OperatingWindowDueRequest.model_validate(raw)
                        original_requests.append(request)
                        projection = projections[projection_ref]
                        projected = projection["payload"]
                        actor = projected["actor_ref"].removeprefix("character:")
                        if actor not in actors or request.window_ref in pending_b1 or request.window_ref in completed_b1:
                            raise ValueError("mixed_b1_actor_or_duplicate_admission_invalid")
                        stream = "gameplay:organization:window:"+request.window_ref
                        if (projected["window_ref"] != request.window_ref or projected["organization_ref"] != request.organization_ref
                                or request.expected_stream_revision != heads.get(stream)
                                or request.expected_stream_revision != projection["revision_vector"].get(stream)):
                            raise ValueError("mixed_b1_original_projection_binding_invalid")
                        owners.add(actor)
                        pending_b1[request.window_ref] = request
                        requested_b1 += 1
                    if not owners or len(owners) > 32:
                        raise ValueError("mixed_b1_window_budget_invalid")
                    batch_key, correlation = _due_batch_identity(original_requests)
                    batch_envelopes[batch_key] = correlation
                    domain_digests[domain_id] = digest
            last_public = None
        elif category == "stream_head":
            phase = "heads"
            if type(row["revision"]) is not int or heads.pop(row["stream_id"], None) != row["revision"]:
                raise ValueError("mixed_authority_stream_head_invalid")
        elif category == "ledger_end":
            footer = row
        else:
            raise ValueError("mixed_authority_record_kind_invalid")
    observed_at = footer['observed_at'] if footer is not None else None
    _instant(observed_at)
    # 历史 head 只保留身份；仅未完成 closed 来源把本轮已持有的原事件交给 join。
    current = {ref: event for ref, event in windows.items() if current_windows.get(ref) == event.event_id}
    due, _ = project_organization_due(schedules, windows, current, source_heads,
        window_end=confirmed, observed_at=observed_at, scope='organization:summary')
    expected_footer = dict(type="ledger_end", transactions=len(transactions), authority_head=global_sequence, observed_at=observed_at,
        event_count=len(event_ids), outbox_count=len(outbox_ids), pending_outbox_by_topic=dict(pending_outbox),
        pending_projection_refresh=pending_refresh)
    if (heads or last_public is not None or footer != expected_footer or confirmed != expected_confirmed_tick
            or len(event_ids) != global_sequence):
        raise ValueError("mixed_authority_coverage_or_footer_invalid")
    return dict(authority_head=global_sequence, transactions=len(transactions), public_windows=public_windows,
        confirmed_tick=confirmed, b1_requested=requested_b1, b1_completed=len(completed_b1),
        pending_b1=len(set(pending_b1) | {projection.payload['window_ref'] for projection in due}),
        pending_outbox_by_topic=dict(pending_outbox), pending_projection_refresh=pending_refresh)
