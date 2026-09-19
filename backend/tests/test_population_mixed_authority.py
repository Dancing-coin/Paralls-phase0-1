"""实际 SQLite 领域回执的只读导出与流式离线复验。"""
import json

import pytest

from scripts.verification import population_mixed_authority as authority
from test_population_domain_cadence import setup, real_pipeline
from test_population_durable_cadence_recovery import _publisher
from app.services.authority_event_bus import InMemoryAuthorityEventBus


def test_authority_export_replays_original_batches_and_owner_receipts_without_writes(tmp_path):
    database = tmp_path / "gameplay.sqlite3"
    world = setup(database, 2)
    bus = InMemoryAuthorityEventBus()
    real_pipeline(world, bus)
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60, budget=100)) is not None
    before = world.store.export_snapshot()
    target = tmp_path / "authority.jsonl"
    authority.export_gameplay(database, target)
    assert world.store.export_snapshot() == before
    options = dict(mode=world.mode.model_dump(mode="json"), actors=list(world.roster.actor_ids), expected_confirmed_tick=60, window_ticks=60)
    result = authority.verify_gameplay(target, **options)
    assert result["confirmed_tick"] == 60 and result["public_windows"] == 1
    assert result["b1_requested"] == result["b1_completed"] == 2
    assert result["pending_b1"] == 0
    # 原 scoped projection 尚未投递也须如实保留，不能把 domain delivered 冒充所有 outbox 清空。
    assert result["pending_outbox_by_topic"] and "population_domain_cadence_event" not in result["pending_outbox_by_topic"]
    raw = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    changed = tmp_path / "changed.jsonl"
    for kind in ("gap", "wrong_owner", "missing_window", "duplicate_transaction"):
        rows = json.loads(json.dumps(raw))
        if kind == "gap":
            rows[0]["batch"]["events"][0]["global_sequence"] += 1
        elif kind == "wrong_owner":
            row = next(row for row in rows if row["type"] == "transaction" and any(
                event["event_type"] == "gameplay.organization.operating_window_due_recorded" for event in row["batch"]["events"]))
            row["batch"]["idempotency_record"]["principal_ref"] = "wrong_owner"
        elif kind == "missing_window":
            rows = [row for row in rows if row["type"] != "population_checkpoint"]
        else:
            rows.insert(1, rows[0])
        changed.write_text("\n".join(json.dumps(row) for row in rows)+"\n", encoding="utf-8")
        with pytest.raises(ValueError):
            authority.verify_gameplay(changed, **options)
    assert world.store.export_snapshot() == before


def test_unselected_due_is_not_hidden_by_only_counting_admitted_owner_requests(tmp_path):
    database = tmp_path / "gameplay.sqlite3"
    world = setup(database, 40)
    bus = InMemoryAuthorityEventBus()
    real_pipeline(world, bus)
    publisher = _publisher(world, bus)
    options = dict(mode=world.mode.model_dump(mode="json"), actors=list(world.roster.actor_ids), window_ticks=60)
    for tick, completed, pending in ((60, 32, 8), (120, 40, 0)):
        assert publisher(world.build_population_cadence(window_start=tick-60, window_end=tick, budget=100)) is not None
        target = tmp_path / f"authority-{tick}.jsonl"
        authority.export_gameplay(database, target)
        result = authority.verify_gameplay(target, **options, expected_confirmed_tick=tick)
        assert result["b1_completed"] == completed and result["pending_b1"] == pending

@pytest.mark.parametrize('field', ['organization', 'due_state', 'fragment'])
def test_completion_requires_original_owner_payload_and_fragment(tmp_path, field):
    database = tmp_path / 'gameplay.sqlite3'
    world = setup(database, 2)
    bus = InMemoryAuthorityEventBus()
    real_pipeline(world, bus)
    publisher = _publisher(world, bus)
    publisher(world.build_population_cadence(window_start=0, window_end=60, budget=100))
    path = tmp_path / 'authority.jsonl'
    authority.export_gameplay(database, path)
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    row = next(row for row in rows if row['type'] == 'transaction' and any(
        event['event_type'] == 'gameplay.organization.operating_window_due_recorded' for event in row['batch']['events']))
    if field == 'fragment':
        row['batch']['owner_fragments'][0]['owner_principal_ref'] = 'wrong-owner'
    else:
        event = next(event for event in row['batch']['events'] if event['event_type'] == 'gameplay.organization.operating_window_due_recorded')
        event['payload']['organization_ref' if field == 'organization' else 'due_state'] = 'wrong-value'
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n', encoding='utf-8')
    with pytest.raises(ValueError):
        authority.verify_gameplay(path, mode=world.mode.model_dump(mode='json'), actors=list(world.roster.actor_ids),
            expected_confirmed_tick=60, window_ticks=60)


def test_closed_window_without_legal_schedule_is_not_pending_b1(tmp_path):
    from test_population_durable_cadence_recovery import _runtime
    from test_population_organization_due_source import window
    from app.gameplay.organization_government_runtime import OrganizationAuthority
    database = tmp_path / 'gameplay.sqlite3'
    world = _runtime(database, ('worker',))
    window(OrganizationAuthority(store=world.store), 'unscheduled')
    bus = InMemoryAuthorityEventBus()
    real_pipeline(world, bus)
    publisher = _publisher(world, bus)
    publisher(world.build_population_cadence(window_start=0, window_end=60, budget=100))
    path = tmp_path / 'authority.jsonl'
    authority.export_gameplay(database, path)
    result = authority.verify_gameplay(path, mode=world.mode.model_dump(mode='json'), actors=list(world.roster.actor_ids),
        expected_confirmed_tick=60, window_ticks=60)
    assert result['pending_b1'] == result['b1_requested'] == result['b1_completed'] == 0

@pytest.mark.parametrize("forged", [False, True])
def test_batch_completion_accepts_original_shared_correlation(tmp_path, forged):
    from app.gameplay.organization_government_runtime import OrganizationAuthority, OperatingWindowDueRequest
    from test_population_organization_due_source import window
    from app.gameplay.event_store import DurableGameplayEventStore
    store = DurableGameplayEventStore(tmp_path/'actual.sqlite3')
    owner = OrganizationAuthority(store=store)
    requests = []
    for index in range(2):
        window(owner, str(index))
        requests.append(OperatingWindowDueRequest(command_id=f'cmd:{index}', idempotency_key=f'key:{index}',
            causation_id=f'cause:{index}', correlation_id=f'cadence:{index}', organization_ref='org:one',
            window_ref=f'window:{index}', expected_stream_revision=2, visibility_scope='project'))
    result = owner.record_operating_windows_due_batch(requests)
    assert result.append_count == 1
    batch = store.get_transaction(result.results[requests[0].command_id].transaction_id)
    if forged:
        batch = batch.model_copy(update={'events': [event.model_copy(update={
            'correlation_id': 'forged', 'causation_id': 'population:forged'}) for event in batch.events]})
    for event, request in zip(batch.events, requests, strict=True):
        if forged:
            with pytest.raises(ValueError):
                authority._verify_due_completion(batch, event, request, original_batch=authority._due_batch_identity(requests))
        else:
            authority._verify_due_completion(batch, event, request, original_batch=authority._due_batch_identity(requests))


def test_completed_windows_release_full_payload_before_final_join(tmp_path, monkeypatch):
    database = tmp_path/'actual.sqlite3'
    world = setup(database, 2)
    bus = InMemoryAuthorityEventBus()
    real_pipeline(world, bus)
    _publisher(world, bus)(world.build_population_cadence(window_start=0, window_end=60, budget=100))
    path = tmp_path/'authority.jsonl'
    authority.export_gameplay(database, path)
    original = authority.project_organization_due
    def checked(schedules, windows, current, heads, **kwargs):
        assert not schedules and not windows and not current
        return original(schedules, windows, current, heads, **kwargs)
    monkeypatch.setattr(authority, 'project_organization_due', checked)
    assert authority.verify_gameplay(path, mode=world.mode.model_dump(mode='json'), actors=list(world.roster.actor_ids),
        expected_confirmed_tick=60, window_ticks=60)['pending_b1'] == 0
