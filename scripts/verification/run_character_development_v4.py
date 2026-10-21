"""Prepare and run development v4 only after a frozen independent review gate.

Reads the sanitized development input and authored role profiles only. No
calibration, final, holdout, legacy grading, or development policy is opened.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from time import monotonic
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.planning.l3_planner import CandidateCompiler
from prepare_character_evaluation import ACTORS, ROLE_REFS, _projection, _frame

TRACKS = ('autonomous_decision', 'explicit_instruction_diagnostic')
UNVERIFIED = ('runtime_legality', 'owner_permission', 'actual_speech', 'execution_receipt')
CHAR_D_UNKNOWN = ('personality_numeric_values', 'cognitive_facets', 'hard_limits',
                  'compute_defaults', 'authority_owner_binding')


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _role_projection(repo: Path, actor: str) -> dict[str, Any]:
    # Supply only source identity metadata to the existing profile loader.
    # In particular the old authored char_d compute caps are not evidence.
    role = {'source_refs': ROLE_REFS[actor], 'status': 'isolated_diagnostic_only',
            'source_caps': {}, 'unresolved': list(CHAR_D_UNKNOWN)}
    projection = _projection({'roles': {actor: role}}, actor, repo)
    projection.pop('source_caps', None)
    projection['source_refs'] = [ref for ref in projection['source_refs'] if 'development-policy' not in ref]
    if actor == 'char_d':
        projection['unresolved'] = list(CHAR_D_UNKNOWN)
    else:
        projection['unresolved'] = list(dict.fromkeys(projection['unresolved'] + ['authority_owner_binding']))
    return projection


def prepare_v4(*, repo: Path, reviewer_input: dict[str, Any]) -> dict[str, Any]:
    if reviewer_input.get('schema') != 'development-reviewer-input-v4' or reviewer_input.get('split') != 'development':
        raise ValueError('development_v4_sanitized_input_required')
    contract = reviewer_input.get('candidate_description_contract', {})
    if (contract.get('frozen') is not True
            or contract.get('version') != CandidateCompiler.HISTORICAL_DESCRIPTION_CONTRACT_REVISION
            or contract.get('compiler_sha256') not in {
                file_sha(repo / 'backend/app/character_agent/planning/l3_planner.py'),
                'ed3013c95fc4653a9cd1c7169298304739ae1b7ed02c5f244edc25a4ecff0b43',
            }):
        raise ValueError('development_v4_description_contract_not_frozen_or_changed')
    scenarios = reviewer_input.get('scenarios', [])
    if len(scenarios) != 12 or len({s['scenario_id'] for s in scenarios}) != 12:
        raise ValueError('development_v4_requires_12_unique_scenarios')
    if len({s['trajectory_group'] for s in scenarios}) != 12:
        raise ValueError('development_v4_trajectory_collision')
    records = []
    cohort_counts = {'description_frozen_regression': 0, 'role_sensitive': 0}
    provider = LayaSystemOneProvider(endpoint='http://127.0.0.1:8765')
    for scenario in scenarios:
        kind, cohort = scenario['question_kind'], scenario['cohort']
        if kind not in TRACKS or cohort not in cohort_counts:
            raise ValueError('development_v4_track_or_cohort_invalid')
        cohort_counts[cohort] += 1
        facts = scenario['facts']
        compiled = CandidateCompiler(description_contract_revision=CandidateCompiler.HISTORICAL_DESCRIPTION_CONTRACT_REVISION).compile(candidates=scenario['candidate_records'],
            envelope={'max_candidate_intents': 3}, visible_targets=set(facts['visible_targets']))
        if len(compiled.universe) != 3 or len(compiled.presented) != 3 or compiled.pruned or compiled.diagnostics:
            raise ValueError('development_v4_candidate_coverage_defect')
        if compiled.digest != scenario['mapping_digest']:
            raise ValueError('development_v4_reviewed_mapping_changed')
        reviewed = scenario['candidates']
        generated = [{key: item[field] for key, field in
            [('label', 'wire_label'), ('candidate_id', 'candidate_id'), ('target_refs', 'target_refs'), ('description', 'description')]}
            for item in compiled.presented]
        if generated != [{key: item[key] for key in ('label', 'candidate_id', 'target_refs', 'description')} for item in reviewed]:
            raise ValueError('development_v4_reviewed_description_changed')
        for offset, actor in enumerate(ACTORS):
            projection = _role_projection(repo, actor)
            conditions = copy.deepcopy(scenario.get('role_conditions', {}).get(actor, {}))
            conditions['unavailable_fields'] = list(dict.fromkeys(conditions.get('unavailable_fields', []) + projection['unresolved']))
            frame_scenario = {'scenario_id': scenario['scenario_id'], **facts}
            frame = _frame(actor, frame_scenario, 4000 + len(records) + offset, projection)
            # Preserve the same sourced conditions in both the auditable frame
            # and the provider-visible snapshot, without inventing profile axes.
            frame['runtime_state']['cards'][0]['payload'].update(
                role_visible_conditions=conditions,
                common_constraints=scenario.get('common_constraints', ''))
            frame['frame_digest'] = digest({key: value for key, value in frame.items() if key != 'frame_digest'})
            request = CharacterModelGateway().prepare_run_request(task_kind='l3_planning', route_override='laya', context={
                'actor_id': actor, 'control_mode': 'agent_full_auto',
                'snapshot': {'event': facts['event'], 'question': facts['question'],
                    'visible_target_refs': facts['visible_targets'],
                    'role_visible_conditions': conditions,
                    'common_constraints': scenario.get('common_constraints', ''),
                    'source_semantics': {'unknown_unavailable': projection['unresolved'],
                        **{field: 'unverified' for field in UNVERIFIED}}},
                'effective_profile': projection['effective_profile'],
                'candidate_intents': compiled.wire_labels, 'frozen_candidates': compiled.presented,
                'candidate_mapping': compiled.by_wire_label, 'candidate_digest': compiled.digest,
                'provider_revision': provider.PROVIDER_REVISION,
                'frame': CharacterMindFrame.model_validate(frame),
                'capability_envelope': {}, 'cognition_policy': {},
            })
            request = json.loads(CharacterModelGateway.freeze_prepared_request(request))
            wire = provider.build_wire_request(request)
            sources = {ref: file_sha(repo / ref) for ref in projection['source_refs'] if (repo / ref).is_file()}
            # Fragment references also receive their underlying file revision.
            condition_ref = str(conditions.get('source_ref', '')).split('#', 1)[0]
            if (repo / condition_ref).is_file():
                actual_sha = file_sha(repo / condition_ref)
                if conditions.get('source_sha256') and conditions['source_sha256'] != actual_sha:
                    raise ValueError('development_v4_role_source_changed')
                sources[condition_ref] = actual_sha
            transforms = {name: file_sha(repo / name) for name in (
                'scripts/verification/run_character_development_v4.py',
                'scripts/verification/prepare_character_evaluation.py',
                'backend/app/character_agent/planning/l3_planner.py',
                'backend/app/character_agent/gateway/model_gateway.py',
                'backend/app/character_agent/gateway/laya_provider.py',
                'backend/app/character_agent/profile/personality_projection.py')}
            records.append({'scenario_id': scenario['scenario_id'], 'actor_id': actor,
                'split': 'development', 'trajectory_group': scenario['trajectory_group'],
                'question_kind': kind, 'cohort': cohort, 'role_visible_conditions': conditions,
                'role_projection': projection, 'frame': frame,
                'provider_request': request, 'wire_request': wire,
                'input_digest': digest(request), 'wire_request_digest': digest(wire),
                'source_revisions': sources, 'transformation_revisions': transforms,
                'complete_u': [item['wire_label'] for item in compiled.universe],
                'controlled_p': compiled.wire_labels, 'candidate_mapping': compiled.by_wire_label,
                'candidate_digest': compiled.digest, 'candidate_order': compiled.wire_labels,
                'cropped': compiled.pruned, 'runtime_quality_denominator_eligible': False})
    if cohort_counts != {'description_frozen_regression': 4, 'role_sensitive': 8}:
        raise ValueError('development_v4_cohort_coverage_defect')
    return {'schema': 'development-v4-frozen-inputs', 'reviewer_input_digest': digest(reviewer_input),
        'provider_revision': provider.PROVIDER_REVISION, 'records': records,
        'action_target_quality_denominator': 0, 'sealed_sources_read': False}


def validate(package: dict[str, Any], *, reviewer_input_path: Path,
             truth: dict[str, Any], repo: Path) -> list[tuple[dict, dict]]:
    if (truth.get('independent_review_approved') is not True
            or truth.get('reviewer_independent_approval') is not True):
        raise ValueError('development_v4_independent_review_not_approved')
    if truth.get('lead_audit_approval') is not True or truth.get('formal_truth_usable') is not True:
        raise ValueError('development_v4_formal_truth_not_usable')
    if truth.get('accidental_exposure') != []:
        raise ValueError('development_v4_review_exposure_retired')
    approved_path = str(reviewer_input_path.resolve())
    if truth.get('read_log') != [approved_path]:
        raise ValueError('development_v4_review_read_log_invalid')
    audit = truth.get('approval_audit', {})
    if audit.get('read_log_checked') is not True or audit.get('accidental_exposure_checked') is not True:
        raise ValueError('development_v4_external_independence_audit_required')
    if str(truth.get('input_sha256', '')).removeprefix('sha256:') != file_sha(reviewer_input_path):
        raise ValueError('development_v4_review_input_sha_changed')
    inputs = json.loads(reviewer_input_path.read_text(encoding='utf-8'))
    reproduced = prepare_v4(repo=repo, reviewer_input=inputs)
    if package != reproduced:
        raise ValueError('development_v4_frozen_package_changed')
    judgments = truth.get('judgments', [])
    keys = [(j.get('scenario_id'), j.get('actor_id')) for j in judgments]
    expected = {(r['scenario_id'], r['actor_id']) for r in reproduced['records']}
    if len(keys) != 48 or len(set(keys)) != 48 or set(keys) != expected:
        raise ValueError('development_v4_review_coverage_invalid')
    by_key = dict(zip(keys, judgments))
    verified = []
    for row in reproduced['records']:
        judgment = by_key[(row['scenario_id'], row['actor_id'])]
        if judgment.get('question_kind') != row['question_kind']:
            raise ValueError('development_v4_review_track_changed')
        if any(judgment.get(field) != 'unverified' for field in UNVERIFIED):
            raise ValueError('development_v4_review_promoted_unverified_execution')
        for field in ('pair_sources', 'unacceptable_reasons', 'unknowns'):
            if not isinstance(judgment.get(field), list):
                raise ValueError('development_v4_review_incomplete')
        pairs = judgment.get('acceptable_pairs')
        available_pairs = [[candidate['action_family'], candidate['target_refs']['target']]
                           for candidate in row['candidate_mapping'].values()]
        if not isinstance(pairs, list) or any(pair not in available_pairs for pair in pairs):
            raise ValueError('development_v4_review_pair_outside_frozen_candidates')
        if len({tuple(pair) for pair in pairs}) != len(pairs):
            raise ValueError('development_v4_review_duplicate_pair')
        # Empty sets are recorded as unjudgeable, never silently scored.
        for pair in pairs:
            if not any(source.get('pair') == pair and (source.get('source') or source.get('source_refs'))
                       for source in judgment['pair_sources'] if isinstance(source, dict)):
                raise ValueError('development_v4_acceptable_pair_source_missing')
        if judgment.get('required_role_difference') is True and not judgment.get('role_difference_sources'):
            raise ValueError('development_v4_role_difference_source_missing')
        verified.append((row, judgment))
    return verified


def summarize(results: list[dict], *, stopped: str | None, input_digest: str, truth_digest: str) -> dict:
    def counts():
        return {'reviewed_denominator': 0, 'formal_denominator': 0, 'passed': 0,
            'failed_or_provider_error': 0, 'unjudgeable': 0, 'valid_response_denominator': 0}
    tracks = {track: counts() for track in TRACKS}
    cohorts = {cohort: {track: counts() for track in TRACKS}
        for cohort in ('description_frozen_regression', 'role_sensitive')}
    roles = {}
    for row in results:
        eligible = row['formal_denominator_eligible']
        for track in (tracks[row['question_kind']], cohorts[row['cohort']][row['question_kind']]):
            track['reviewed_denominator'] += 1
            track['valid_response_denominator'] += int(row['mapped_candidate'] is not None)
            if not eligible:
                track['unjudgeable'] += 1
            else:
                # Every approved, evaluable attempted row stays in the
                # denominator; transport failures cannot improve its result.
                track['formal_denominator'] += 1
                track['passed'] += int(row['offline_pass'] is True)
                track['failed_or_provider_error'] += int(row['offline_pass'] is not True)
        role = roles.setdefault(row['actor_id'], {'calls': 0,
            'unknown_unavailable': row['trace']['role_projection']['unresolved'], 'formal_denominator': 0})
        role['calls'] += 1
        role['formal_denominator'] += int(eligible)
    times = sorted(row['latency_ms'] for row in results)
    def percentile(fraction):
        return times[max(0, math.ceil(len(times) * fraction) - 1)] if times else None
    role_sensitive = [r for r in results if r['cohort'] == 'role_sensitive']
    return {'status': 'stopped_on_input_defect' if stopped else 'development_v4_completed',
        'stop_reason': stopped, 'input_digest': input_digest, 'truth_digest': truth_digest,
        'reviewer_independent_approval': True, 'lead_audit_approval': True,
        'formal_truth_usable': True, 'provider_calls': len(results), 'tracks': tracks, 'cohorts': cohorts,
        'role_sensitive_formal_denominator': sum(r['formal_denominator_eligible'] for r in role_sensitive),
        'role_sensitive_scenarios': len({r['scenario_id'] for r in role_sensitive}),
        'required_role_difference_denominator': len({r['scenario_id'] for r in role_sensitive
            if r['offline_review'].get('required_role_difference') is True}),
        'action_target_quality_denominator': 0, 'roles': roles,
        'provider_errors': sum(r['error_kind'] == 'provider_error' for r in results),
        'mapping_rejections': sum(r['error_kind'] == 'mapping_rejection' for r in results),
        'latency_ms': {'count': len(times), 'min': min(times) if times else None,
            'max': max(times) if times else None, 'p50': percentile(.5), 'p95': percentile(.95)},
        'unable_to_judge': [{'scenario_id': r['scenario_id'], 'actor_id': r['actor_id'],
            'reason': r['rejection_reason'] or 'independent_review_scope_not_evaluable'} for r in results if r['offline_pass'] is None],
        'calibration': 'blocked', 'A-Cognition': 'development_evidence_only_not_accepted',
        'A-Embodied': 'not_evaluated', 'Godot': 'not_evaluated', 'Harness_all': 'not_claimed',
        'sealed_sources_read': False}


def run(package: dict[str, Any], *, reviewer_input_path: Path, truth: dict[str, Any],
        repo: Path, output_dir: Path, endpoint: str, timeout_seconds: float = 120.0) -> dict:
    verified = validate(package, reviewer_input_path=reviewer_input_path, truth=truth, repo=repo)
    destination = output_dir.resolve()
    if destination == repo.resolve() or repo.resolve() in destination.parents:
        raise ValueError('development_v4_evidence_must_be_repository_external')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('development_v4_evidence_destination_must_be_empty')
    destination.mkdir(parents=True, exist_ok=True)
    frozen_truth_digest = digest(truth)
    input_sha = file_sha(reviewer_input_path)
    for name, value in [('frozen-development-package.json', package), ('frozen-independent-truth.json', truth)]:
        (destination / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    provider = LayaSystemOneProvider(endpoint=endpoint, timeout_seconds=timeout_seconds)
    gateway = CharacterModelGateway(provider=provider)
    results, stopped = [], None
    with (destination / 'results.jsonl').open('x', encoding='utf-8') as evidence:
        for row, judgment in verified:
            if file_sha(reviewer_input_path) != input_sha or digest(truth) != frozen_truth_digest:
                stopped = 'runtime_review_input_or_truth_changed'
                break
            request, wire = row['provider_request'], row['wire_request']
            if digest(request) != row['input_digest'] or provider.build_wire_request(request) != wire:
                stopped = 'runtime_frozen_request_changed'
                break
            provider.last_call = None
            started = monotonic()
            eligible = judgment.get('evaluable') is True and bool(judgment['acceptable_pairs'])
            mapped_result, candidate, error, error_kind, passed, diagnostic_pass = None, None, None, None, None, None
            try:
                mapped_result = gateway.complete_prepared_request(gateway.freeze_prepared_request(request))
                candidate = row['candidate_mapping'].get(mapped_result.get('selected_intent'))
                if not candidate:
                    raise ValueError('runtime_candidate_mapping_rejection')
                if judgment['acceptable_pairs']:
                    diagnostic_pass = [candidate['action_family'], candidate['target_refs']['target']] in judgment['acceptable_pairs']
                    if eligible:
                        passed = diagnostic_pass
            except (ValueError, KeyError, TypeError) as exc:
                error = str(exc)
                error_kind = 'mapping_rejection' if (provider.last_call or {}).get('response') is not None else 'provider_error'
            call = provider.last_call or {}
            if call.get('request') != wire:
                stopped = 'runtime_actual_wire_changed'
                passed = None
            result = {**row, 'raw_response': call.get('response'), 'mapped_result': mapped_result,
                'mapped_candidate': candidate, 'actual_wire_request': call.get('request'),
                'latency_ms': call.get('latency_ms') or round((monotonic() - started) * 1000, 3),
                'error_kind': error_kind, 'rejection_reason': error, 'offline_pass': passed,
                'diagnostic_acceptable_set_match': diagnostic_pass, 'formal_denominator_eligible': eligible,
                'offline_review': judgment, 'independent_truth_digest': frozen_truth_digest,
                'action_target_quality_eligible': False,
                'trace': {'source_revisions': row['source_revisions'], 'role_projection': row['role_projection'],
                    'effective_profile': row['role_projection']['effective_profile'], 'mind_frame': row['frame'],
                    'candidate_descriptions': row['candidate_mapping'], 'frozen_wire': wire,
                    'laya_response': call.get('response'), 'offline_review': judgment}}
            evidence.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
            evidence.flush()
            os.fsync(evidence.fileno())
            results.append(result)
            if stopped:
                break
    summary = summarize(results, stopped=stopped, input_digest=digest(package), truth_digest=frozen_truth_digest)
    (destination / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewer-input', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--truth', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--timeout-seconds', type=float, default=120.0)
    args = parser.parse_args()
    inputs = json.loads(args.reviewer_input.read_text(encoding='utf-8'))
    if args.prepare_only:
        if args.package.exists():
            raise ValueError('development_v4_package_destination_exists')
        args.package.parent.mkdir(parents=True, exist_ok=True)
        package = prepare_v4(repo=ROOT, reviewer_input=inputs)
        args.package.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': 'development_v4_prepared', 'records': len(package['records'])}))
        return 0
    if not args.truth or not args.output_dir or not args.endpoint:
        parser.error('run requires --truth, --output-dir and --endpoint')
    summary = run(json.loads(args.package.read_text(encoding='utf-8')),
        reviewer_input_path=args.reviewer_input, truth=json.loads(args.truth.read_text(encoding='utf-8')),
        repo=ROOT, output_dir=args.output_dir, endpoint=args.endpoint, timeout_seconds=args.timeout_seconds)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary['stop_reason'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
