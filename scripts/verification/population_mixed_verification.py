"""混合单局原始证据离线入口；所有通过条件从原包和账本复算。"""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from app.gameplay.models import AtomicEventBatch
from app.population_continuity.recovery import PopulationRecoveryState, PopulationRecoveryCheckpoint, recovery_digest
from app.population_continuity.roster import PopulationRoster
from scripts.verification.population_godot_runner import ROOT, source_manifest
from scripts.verification.verify_population_godot_runtime import json_lines, read_json
from scripts.verification.verify_population_service_isolation import raw_artifacts
from scripts.verification.population_mixed_evidence import (
    number, equal_number, replay_requests, replay_responses, replay_providers, replay_windows, replay_ws_faults,
)


def link_authority(path, rows, actors, final, children, *, config):
    """把采集时的 fixture/公开窗口关联到原 Gameplay 事实和原 Character 子入站。"""
    from app.character_agent.profile.registry import CharacterProfileRegistry
    from app.gameplay.production_package_registry import build_production_package_registry
    from app.population_continuity.activation_policy import ActivationPolicy
    from app.population_continuity.conflict_activation import prepare_conflict_activation
    from scripts.verification.population_mixed_fixture import install_conflict_fixture_package
    from scripts.verification.population_mixed_load import MixedLoadSchedule

    schedule = MixedLoadSchedule(config['population'], config['seed'], config['mode'])
    fixtures, windows, b2, b2_keys = {}, {}, {}, {}
    expected_b2_keys = [f"mixed:{len(actors)}:{config['seed']}:{config['mode']}:initial",
        *[event.transaction_id for event in schedule.events(config['seconds']) if event.kind == 'siming_model']]
    captured_b2 = []
    for row in rows:
        if row['type'] == 'window':
            if row['phase'] != ('measurement' if row['target_tick'] <= config['seconds']*1000//schedule.window_ms else 'drain'):
                raise ValueError('mixed_window_phase_invalid')
            for fixture in row['fixtures']:
                for item in fixture['rows']:
                    for field in ('closed_event_id', 'schedule_event_id'):
                        fixtures[item[field]] = item, field
            for key in row['result']['published_cadence_ids']:
                if key in windows:
                    raise ValueError('mixed_duplicate_public_window')
                windows[key] = row['previous_tick'], row['target_tick']
        elif row['type'] == 'b2_fixture':
            captured_b2.append(row['key'])
            if {wake['actor_id'] for wake in row['sources']} != {'char_b', 'char_c'} or len(row['sources']) != 2:
                raise ValueError('mixed_b2_fixture_actor_coverage_invalid')
            for wake in row['sources']:
                identity = wake['source_event_id'], wake['actor_id']
                if identity in b2:
                    raise ValueError('mixed_b2_fixture_duplicate')
                b2[identity] = wake
                b2_keys[wake['source_event_id']] = row['key']+':b2'
    if captured_b2 != expected_b2_keys:
        raise ValueError('mixed_b2_source_schedule_incomplete')
    wanted = {key[0] for key in b2}
    sources, batches, heads, cadences, last = {}, {}, {}, {}, None
    for row in json_lines(path):
        if row['type'] == 'transaction':
            batch = AtomicEventBatch.model_validate_json(json.dumps(row['batch']))
            for event in batch.events:
                if event.event_id in fixtures:
                    item, field = fixtures.pop(event.event_id)
                    expected_type = 'gameplay.organization.'+('work_order_recorded' if field == 'schedule_event_id' else 'operating_window_closed')
                    if (event.event_type != expected_type or event.payload.get('operating_window_ref' if field == 'schedule_event_id' else 'window_ref') != item['window_ref']
                            or (field == 'schedule_event_id' and event.payload.get('recipient_ref') != 'character:'+item['actor_id'])
                            or (field == 'closed_event_id' and event.payload.get('closes_at_tick') != item['due_tick'])):
                        raise ValueError('mixed_fixture_authority_binding_invalid')
                if event.event_id in wanted:
                    sources[event.event_id], batches[event.transaction_id] = event, batch
                if event.event_type == 'population.cadence.admitted':
                    cadence = event.payload['cadence']
                    if windows.pop(cadence['cadence_id'], None) != (cadence['window_start'], cadence['window_end']):
                        raise ValueError('mixed_public_capture_authority_mismatch')
                    cadences[cadence['cadence_id']] = cadence
        elif row['type'] == 'stream_head':
            if row['stream_id'].startswith('gameplay:social:case:'):
                heads[row['stream_id']] = row['revision']
        elif row['type'] == 'population_checkpoint':
            last = PopulationRecoveryCheckpoint.model_validate_json(json.dumps(row['checkpoint']['state']))
    if fixtures or windows or sources.keys() != wanted or last is None:
        raise ValueError('mixed_original_fixture_or_window_missing')
    recovery = PopulationRecoveryState.model_validate_json(json.dumps(final['recovery_state']))
    context = recovery_digest(dict(mode=final['mode'], roster=actors, authorized_actor_refs=None))
    if (recovery.confirmed_tick != final['confirmed_tick'] or recovery.state_digest != final['state_digest']
            or [actor.actor_id for actor in recovery.actors] != sorted(actors) or recovery.context_digest != context
            or recovery.last_receipt != last.receipt or recovery.last_fingerprint != last.fingerprint):
        raise ValueError('mixed_final_original_receipt_mismatch')
    packages = build_production_package_registry(ROOT)
    install_conflict_fixture_package(packages)
    profiles = CharacterProfileRegistry.from_directory(ROOT / 'assets/characters/profiles')
    store = SimpleNamespace(get_event=sources.__getitem__, get_transaction=batches.get, get_stream_head=heads.get)
    for identity, wake in b2.items():
        event = sources[identity[0]]
        if event.correlation_id != b2_keys[event.event_id] or event.payload['case_ref'] != 'case:'+b2_keys[event.event_id]+'@1':
            raise ValueError('mixed_b2_original_fixture_identity_invalid')
        original = prepare_conflict_activation(store=store, package_registry=packages, profiles=profiles,
            policy=ActivationPolicy(), source_event_id=identity[0], actor_id=identity[1], budget=4)
        if json.loads(json.dumps(asdict(original))) != wake:
            raise ValueError('mixed_b2_original_wake_changed')
    admitted, budget, completed = set(), {}, 0
    for child in children:
        # 原 session 调度来源已由 Character 账本复验，不能计为 Social B2 工作量。
        if child['source_kind'] != 'run_background_cognition_tick' or 'scheduled_session' in child['source_pins']:
            continue
        identity = child['source_event']['event_id'], child['actor_id']
        wake = b2.get(identity)
        cadence = child['source_pins'].get('population_cadence', {})
        if (wake is None or identity in admitted or child['delivery_id'] != wake['candidate_key']
                or child['source_event'] != sources[identity[0]].model_dump(mode='json')
                or child['source_pins'].get('population_wake') != wake or child['payload'] or child['parent_effect_key']
                or cadences.get(cadence.get('cadence_id')) != cadence or child['producer_ts'] != cadence['window_end']):
            raise ValueError('mixed_b2_original_child_binding_invalid')
        selected = budget.setdefault(cadence['cadence_id'], set())
        if child['actor_id'] in selected or len(selected) >= 4:
            raise ValueError('mixed_b2_public_window_budget_invalid')
        selected.add(child['actor_id'])
        admitted.add(identity)
        completed += child['state'] == 'completed'
    return dict(public_windows=len(cadences), b2_expected=len(b2), b2_admitted=len(admitted), b2_completed=completed,
        b2_complete=completed == len(b2), confirmed_tick=recovery.confirmed_tick)


def _verify_sqlite_handler(fault, requests):
    busy = [row for row in requests if row['key'] == fault['key'] and row['kind'] == 'sqlite_busy']
    if len(busy) != 1:
        raise ValueError('mixed_sqlite_handler_missing')
    busy = busy[0]
    release = [row for row in requests if row['kind'] == 'sqlite_release' and row['ordinal'] == busy['ordinal']]
    expected = dict(acquired_at=fault['acquired_at'], released_at=fault['released_at'])
    if (len(release) != 1 or any(row.get('status') != 'handler_finished' or row.get('result') != expected
            for row in [busy, *release])
            or not max(busy['expected_at'], busy['issued_at']) <= number(fault['acquired_at'])
            <= number(fault['released_at']) <= busy['finished_at']
            or fault['released_at'] > release[0]['finished_at']):
        raise ValueError('mixed_sqlite_handler_binding_invalid')


def temporal_evidence(rows, config, client, server_requests, siming):
    """原 heartbeat 和故障全集；timeout 关联同一原任务，不能拿别的成功任务顶替。"""
    from scripts.verification.population_mixed_load import MixedLoadSchedule
    origin, end = client['origin'], client['load_end']
    equal_number(server_requests['origin'], origin)
    equal_number(server_requests['load_end'], end)
    driver = [row for row in rows if row['type'] == 'driver_clock_origin']
    if len(driver) != 1 or not origin <= number(driver[0]['at']) < end:
        raise ValueError('mixed_driver_load_interval_invalid')
    measured = [row for row in rows if row['type'] == 'window' and row['phase'] == 'measurement']
    if not measured or not (number(measured[0]['started_at']) < end and number(measured[-1]['finished_at']) >= origin):
        raise ValueError('mixed_measurement_load_interval_invalid')
    beats = [row for row in rows if row['type'] == 'heartbeat']
    if len(beats) != config['seconds']//10:
        raise ValueError('mixed_heartbeat_coverage_invalid')
    previous = origin
    last_tick = 0
    for ordinal, row in enumerate(beats, 1):
        equal_number(row['expected_at'], origin+10*ordinal)
        previous = number(row['at'], minimum=max(previous, origin+10*ordinal))
        last_tick = number(row['last_confirmed_tick'], integer=True, minimum=last_tick)
        available = [window['sample']['confirmed_tick'] for window in rows if window['type'] == 'window' and window['finished_at'] <= row['at']]
        if last_tick > max(available, default=0):
            raise ValueError('mixed_heartbeat_unconfirmed_tick')
        if row['execution']['failure'] is not None or number(row['execution']['queue_depth'], integer=True) > 128:
            raise ValueError('mixed_heartbeat_runtime_failed')
        if number(row['provider_active'], integer=True) > 4:
            raise ValueError('mixed_heartbeat_provider_bound_invalid')
    schedule = MixedLoadSchedule(config['population'], config['seed'], config['mode'])
    events = list(schedule.events(config['seconds']))
    armed = [row for row in rows if row['type'] == 'provider_timeout_armed']
    injected = [row for row in rows if row['type'] == 'provider_timeout_injected']
    expected = [event for event in events if event.kind == 'provider_timeout']
    if [row['key'] for row in armed] != [event.transaction_id for event in expected] or len(injected) != len(expected):
        raise ValueError('mixed_timeout_fault_coverage_invalid')
    calls = {row['ordinal']:row for row in rows if row['type'] == 'provider_result'}
    recovered = []
    for event, arm, fault in zip(expected, armed, injected):
        call = calls.get(fault['ordinal'])
        if (arm['key'] != fault['key'] or number(arm['at']) < origin+event.at_ms/1000
                or number(fault['at']) < arm['at'] or call is None or call['fault_key'] != fault['key']
                or call['family'] != 'siming' or not call['started_at'] <= fault['at'] <= call['finished_at']):
            raise ValueError('mixed_timeout_original_call_missing')
        matches = [job for job in siming['jobs'] if any(binding['request_sha256'] == call['request_sha256']
            and binding['source_event_id'] in call['source_event_ids'] and binding['error'] == 'SimingLlmProviderTimeout'
            for binding in job['providers'])]
        recovered.append(len(matches) == 1 and matches[0]['state'] == 'completed')
    busy = [row for row in rows if row['type'] == 'sqlite_busy']
    expected_busy = [event.transaction_id for event in events if event.kind == 'sqlite_busy']
    if [row['key'] for row in busy] != expected_busy:
        raise ValueError('mixed_sqlite_fault_coverage_invalid')
    for fault in busy:
        _verify_sqlite_handler(fault, server_requests['requests'])
    return dict(heartbeats=len(beats), timeout_faults=len(expected), timeout_recovered=all(recovered), sqlite_faults=len(busy))


def verify_character_provider_calls(jobs, calls):
    for job in jobs:
        for binding in job['providers']:
            if binding['output_sha256'] is None and binding.get('error') is None:
                continue
            if not any(call['family'] == 'character' and call['request_sha256'] == binding['request_sha256']
                    and call.get('output_sha256') == binding['output_sha256']
                    and call.get('error') == binding.get('error') for call in calls):
                raise ValueError('mixed_character_original_provider_result_missing')


def verify_siming_provider_calls(jobs, calls):
    # 每个已返回的原尝试须对应独立调用，重排前后相同 payload 不能共用一次结果。
    remaining = list(calls)
    for job in jobs:
        for binding in job['providers']:
            if binding['output_sha256'] is None or binding['error']:
                continue
            index = next((index for index, call in enumerate(remaining)
                if call['family'] == 'siming' and call['request_sha256'] == binding['request_sha256']
                and call.get('output_sha256') == binding['output_sha256']), None)
            if index is None:
                raise ValueError('mixed_siming_original_provider_result_missing')
            remaining.pop(index)


def siming_job_finished_safely(job, calls):
    if job['state'] == 'completed':
        return True
    if job['state'] != 'stale' or not job.get('reason', '').startswith('stale_pin'):
        return False
    event_id = job['source']['event_id']
    return any(call['family'] == 'siming' and call['qualified_success']
        and event_id in call['source_event_ids'] for call in calls)


def process_evidence(directory, config, server, rows, *, backend_pid, interval):
    """复算原角色关联、父循环采样和父子资源，保留原 owner 全部验收。"""
    from statistics import median
    from scripts.verification.population_mixed_backend import merge_process_observations
    from scripts.verification.verify_population_service_isolation import _writer_boundaries
    def load(name):
        return read_json((directory / name).read_text(encoding='utf-8'))
    parent, owner, ready, drained = [load(name + '.json') for name in
        ('parent-observed', 'owner-observed', 'owner-ready', 'owner-drained')]
    if (merge_process_observations(parent, owner, ready) != server or parent['parent_pid'] != backend_pid
            or parent['interval'] != interval or parent['population'] != config['population']
            or parent['provider_mode'] != config['provider_mode']
            or drained != dict(owner_pid=parent['owner_pid'], errors=[])):
        raise ValueError('mixed_process_original_evidence_mismatch')
    pid = parent['owner_pid']
    names = [name for _, _, name in _writer_boundaries()]
    if (parent['writer_boundaries'] != names or owner['writer_boundaries'] != names or parent['writer_calls'] != {}
            or any(type(row.get('process_id')) is not int or row['process_id'] != pid for row in rows)):
        raise ValueError('mixed_process_writer_or_owner_invalid')
    for key in ('owner_threads', 'mutation_threads'):
        identities = owner[key]
        if (not isinstance(identities, list) or len(identities) != 1 or not isinstance(identities[0], list)
                or len(identities[0]) != 2 or identities[0][0] != pid
                or any(type(value) is not int or value <= 0 for value in identities[0])):
            raise ValueError('mixed_process_thread_identity_invalid')
    samples = list(json_lines(directory / 'parent.jsonl'))
    resources = [row for row in samples if row['type'] == 'resources']
    beats = [row for row in samples if row['type'] == 'heartbeat']
    if (len(samples) != len(resources) + len(beats) or len(beats) != config['seconds']//10
            or [row['phase'] for row in resources] != ['start', 'after_drain']):
        raise ValueError('mixed_process_heartbeat_coverage_invalid')
    start, end = resources
    windows = [row for row in rows if row['type'] == 'window']
    drains = [row for row in rows if row['type'] == 'drain']
    if (not windows or not drains or not interval['origin'] <= number(start['at']) <= windows[0]['started_at']
            or number(end['at']) < max(interval['load_end'], windows[-1]['finished_at'], number(drains[-1]['at']))):
        raise ValueError('mixed_process_resource_interval_invalid')
    previous_at = previous_cpu = 0
    generation = None
    for sample in samples:
        previous_at = number(sample['at'], minimum=previous_at)
        previous_cpu = number(sample['cpu_seconds'], minimum=previous_cpu)
        number(sample['rss_bytes'], integer=True, minimum=1)
        state, credit = sample['runtime_process'], sample['runtime_process']['execution_credit']
        if (type(sample['process_id']) is not int or sample['process_id'] != backend_pid
                or state['status'] != 'ok' or state['child_pid'] != pid
                or not isinstance(state['process_generation'], str) or not state['process_generation']
                or generation not in (None, state['process_generation'])
                or number(state['ipc_capacity'], integer=True) != 128
                or number(state['notification_capacity'], integer=True) != 128
                or any(number(state[key+'_capacity'], integer=True) != 128
                    or number(state[key], integer=True) > 128 for key in ('runtime_pending', 'transport_pending'))
                or state['runtime_pending'] + state['transport_pending'] > 128
                or number(state['ipc_pending'], integer=True) > 128 or number(state['pending_send'], integer=True) > 128
                or number(credit['capacity'], integer=True) != 128 or number(credit['current'], integer=True) > 128
                or number(credit['peak'], integer=True) > 128 or credit['peak'] < credit['current']):
            raise ValueError('mixed_process_sample_invalid')
        generation = state['process_generation']
    terminal = end['runtime_process']
    if (any(terminal[key] != 0 for key in ('ipc_pending', 'pending_send', 'runtime_pending', 'transport_pending'))
            or terminal['execution_credit']['current'] != 0):
        raise ValueError('mixed_process_tail_pending')
    owner_beats = [row for row in rows if row['type'] == 'heartbeat']
    if len(owner_beats) != len(beats):
        raise ValueError('mixed_process_heartbeat_pair_missing')
    paired = []
    for ordinal, (row, owner_beat) in enumerate(zip(beats, owner_beats), 1):
        equal_number(row['expected_at'], interval['origin'] + ordinal * 10)
        equal_number(owner_beat['expected_at'], row['expected_at'])
        if row['at'] < row['expected_at'] or number(owner_beat['at']) < row['expected_at']:
            raise ValueError('mixed_process_heartbeat_clock_invalid')
        paired.append(dict(at=max(row['at'], owner_beat['at']),
            rss_bytes=row['rss_bytes'] + number(owner_beat['rss_bytes'], integer=True, minimum=1)))
    growth, rss_passed = None, True
    if config['seconds'] >= 7200:
        bounds = ((interval['origin'], interval['origin'] + 1800), (interval['load_end'] - 1800, interval['load_end']))
        medians = []
        for first, last in bounds:
            values = [row['rss_bytes'] for row in paired if first <= row['at'] <= last]
            if not values:
                raise ValueError('mixed_process_rss_wall_coverage_missing')
            medians.append(median(values))
        initial, final = medians
        growth = dict(first_median_bytes=initial, last_median_bytes=final, growth_bytes=final-initial,
            allowed_bytes=max(32*1024*1024, initial*.1), scope='paired_current_rss_on_same_10_second_grid')
        rss_passed = growth['growth_bytes'] <= growth['allowed_bytes']
    return dict(parent_pid=backend_pid, owner_pid=pid, parent_heartbeats=len(beats),
        parent_cpu_seconds=end['cpu_seconds']-start['cpu_seconds'],
        parent_observed_seconds=end['at']-start['at'],
        peak_rss_bytes=max(row['rss_bytes'] for row in samples) + max(row['sample']['rss_bytes'] for row in windows),
        rss_peak_scope='sum_of_role_observed_peaks', rss_growth=growth, rss_growth_passed=rss_passed,
        ready_mode=ready['mode'])


def verify_case(directory: Path, *, expected_commit: str, require_formal=True):
    def load(name):
        return read_json((directory / name).read_text(encoding='utf-8'))
    manifest, config = load('manifest.json'), load('run.json')
    if (manifest.get('schema_version') != 1 or manifest.get('profile') != 'population-mixed-soak'
            or manifest.get('base_commit') != expected_commit or manifest.get('source') != source_manifest()
            or config != manifest.get('config')):
        raise ValueError('mixed_evidence_identity_invalid')
    if require_formal and (config.get('provider_mode') != 'live' or manifest.get('source_dirty_paths') != []):
        raise ValueError('mixed_formal_live_clean_source_required')
    if require_formal:
        from scripts.verification.aggregate_population_closure import _identity
        if _identity(expected_commit)[0] != manifest['source']:
            raise ValueError('mixed_formal_current_source_required')
    if (type(manifest.get('backend_exit_code')) is not int or manifest['backend_exit_code'] != 0
            or manifest.get('errors') != [] or manifest.get('collection_finished') is not True):
        raise ValueError('mixed_collection_incomplete')
    required = {'run.json', 'roster.json', 'start', 'stop', 'client.json', 'server.json', 'server-requests.json',
        'server.jsonl', 'responses.jsonl', 'process.log', 'final-state.json', 'authority.jsonl', 'character.jsonl', 'siming.jsonl',
        'owner-ready.json', 'owner-observed.json', 'owner-drained.json', 'parent-observed.json', 'parent.jsonl'}
    raw = raw_artifacts(directory)
    if not required <= raw.keys() or raw != manifest.get('raw_artifacts') or 'ready.json' in raw:
        raise ValueError('mixed_raw_artifacts_invalid')
    actors = list(PopulationRoster.model_validate(load('roster.json')).actor_ids)
    if len(actors) != config['population'] or config['population'] not in (100, 1000, 10000):
        raise ValueError('mixed_population_invalid')
    environment = manifest['environment']
    if (environment.get('provider_mode') != config['provider_mode'] or environment.get('godot') != 'not_run'
            or any(not environment.get(key) for key in ('python', 'sqlite', 'os', 'cpu', 'logical_cpus', 'architecture', 'packages'))):
        raise ValueError('mixed_environment_evidence_missing')
    client, server_requests, server, final = (load(name) for name in ('client.json', 'server-requests.json', 'server.json', 'final-state.json'))
    if load('start') != dict(origin=client['origin'], load_end=client['load_end']):
        raise ValueError('mixed_load_interval_invalid')
    if (datetime.fromisoformat(manifest['finished_at'])-datetime.fromisoformat(manifest['started_at'])).total_seconds() < config['seconds']:
        raise ValueError('mixed_wall_duration_invalid')
    client_traffic = replay_requests(client, config, side='client')
    server_traffic = replay_requests(server_requests, config, side='server')
    rows = list(json_lines(directory / 'server.jsonl'))
    processes = process_evidence(directory, config, server, rows, backend_pid=manifest['backend_pid'],
        interval=dict(origin=client['origin'], load_end=client['load_end']))
    if processes.pop('ready_mode') != final['mode']:
        raise ValueError('mixed_process_owner_mode_changed')
    windows = replay_windows(rows, config, actors)
    responses = replay_responses(json_lines(directory / 'responses.jsonl'), client['requests'])
    faults = replay_ws_faults(json_lines(directory / 'responses.jsonl'), client['requests'], actors, responses.pop('healthy_snapshots'))
    providers = replay_providers(rows, client['requests'], server)
    from scripts.verification.population_mixed_authority import verify_gameplay
    from scripts.verification.population_mixed_cognition import verify_character
    from scripts.verification.population_mixed_siming import verify_siming
    authority = verify_gameplay(directory / 'authority.jsonl', mode=final['mode'], actors=actors,
        expected_confirmed_tick=number(final['confirmed_tick'], integer=True, minimum=1), window_ticks=1)
    if authority['authority_head'] != final['authority_head']:
        raise ValueError('mixed_final_authority_head_mismatch')
    if (not final['drain']['b1_drained'] or final['drain'].get('timed_out') or final['confirmed_tick'] < final['drain']['required_tick']):
        raise ValueError('mixed_final_drain_incomplete')
    drains = [row for row in rows if row['type'] == 'drain']
    if (not drains or {key:value for key,value in drains[-1].items() if key not in {'type', 'at', 'process_id'}} != final['drain']
            or number(drains[-1]['at']) < client['load_end']
            or final['drain']['confirmed_tick'] != final['confirmed_tick']):
        raise ValueError('mixed_final_drain_observation_mismatch')
    from scripts.verification.verify_population_mixed_soak import drain_complete
    character = verify_character(directory / 'character.jsonl')
    siming = verify_siming(directory / 'siming.jsonl', character_jobs=character['jobs'])
    flow = link_authority(directory / 'authority.jsonl', rows, actors, final, character['jobs'], config=config)
    temporal = temporal_evidence(rows, config, client, server_requests, siming)
    calls = [row for row in rows if row['type'] == 'provider_result']
    scheduled_siming = [task for task in client['requests'] if task['kind'] == 'siming_model']
    siming_complete = True
    for task in scheduled_siming:
        matches = [job for job in siming['jobs'] if job['source']['event_id'] == task.get('result', {}).get('source_event_id')]
        siming_complete = len(matches) == 1 and siming_job_finished_safely(matches[0], calls) and siming_complete
        if matches:
            source = matches[0]['source']
            if source['correlation_id'] != task['key'] or source['producer_ts'] != task['result']['producer_ts']:
                raise ValueError('mixed_siming_scheduled_source_changed')
    verify_siming_provider_calls(siming['jobs'], calls)
    verify_character_provider_calls(character['jobs'], calls)
    checks = dict(complete_traffic=client_traffic['complete_traffic'] and server_traffic['complete_traffic'],
        runtime_drained=drain_complete(final['drain']) and final['drain'].get('proven') is True
            and final['drain'].get('limitations') == [],
        writer_isolated=server['max_writers'] == 1 and len(server['owner_threads']) == 1
            and server['owner_threads'] == server['mutation_threads'] and server['active_writers'] == {} and server['errors'] == [],
        provider_isolated=providers['isolated'], live_configuration=config['provider_mode'] == 'live',
        first_three_live=config['seconds'] < 180 or providers['first_three_live_tasks_passed'],
        cache_bounds=windows['cache_bounds_passed'], rss_growth=windows['rss_growth_passed'] and processes['rss_growth_passed'],
        authority_drained=authority['pending_b1'] == 0 and not authority['pending_outbox_by_topic'].get('population_domain_cadence_event'),
        b2_completed=flow['b2_complete'], character_drained=character['schema_present'] and character['pending'] == 0 and not character['states'].get('stale'),
        siming_completed=siming_complete and siming['pending'] == 0
            and all(siming_job_finished_safely(job, calls) for job in siming['jobs']),
        fault_recovered=windows['sqlite_recovery_passed'] and temporal['timeout_recovered'] and providers['pending_timeout'] is None)
    return dict(passed=require_formal and all(checks.values()) and windows['performance_passed'],
        integrity_passed=all(checks.values()), performance_passed=windows['performance_passed'], checks=checks,
        config=config, environment=manifest['environment'], interval=dict(origin=client['origin'], load_end=client['load_end']),
        endpoint=manifest['endpoint'], backend_pid=manifest['backend_pid'], windows=windows, authority=authority, flow=flow,
        temporal=temporal, responses=responses, faults=faults, providers=providers, processes=processes,
        character_states=character['states'], siming_states=siming['states'])
