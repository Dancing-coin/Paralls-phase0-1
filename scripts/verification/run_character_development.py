"""Opt-in real development calls; never opens calibration or sealed labels."""
from __future__ import annotations

import argparse
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
from prepare_character_evaluation import prepare

FIXTURE = Path('backend/tests/fixtures/character_evaluation/four_role_preparation')


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def validate_package(package: dict[str, Any], *, repo: Path,
                     provider: LayaSystemOneProvider) -> list[tuple[dict, dict]]:
    """Reproduce development inputs and offline labels before any network call."""
    if package.get('preflight', {}).get('development_ready') is not True:
        raise ValueError('development_not_ready')
    if package.get('final_labels_read') is not False:
        raise ValueError('sealed_labels_not_confirmed')
    records, grading = package.get('records', []), package.get('grading', [])
    if len(records) != 16 or len(grading) != 16:
        raise ValueError('development_requires_16_frozen_rows')
    reference = prepare(repo, repo / FIXTURE)
    expected = {(row['scenario_id'], row['actor_id']): row for row in reference['records']}
    truth = {(row['scenario_id'], row['actor_id']): row for row in reference['grading']}
    supplied_truth = {(row['scenario_id'], row['actor_id']): row for row in grading}
    if len(supplied_truth) != 16 or supplied_truth != truth:
        raise ValueError('development_truth_source_defect')
    seen, verified = set(), []
    for row in records:
        key = (row['scenario_id'], row['actor_id'])
        if row.get('split') != 'development' or key in seen or key not in expected:
            raise ValueError('development_row_identity_defect')
        seen.add(key)
        frozen = expected[key]
        # Reproduction validates projections, privacy, U/P, mapping and source pins
        # together. It uses only the development source generator.
        for field in ('provider_request', 'wire_request', 'input_digest', 'wire_request_digest',
                      'source_revisions', 'transformation_revisions', 'frame', 'frozen_mind_frame',
                      'role_projection', 'complete_u', 'controlled_p', 'candidate_manifest',
                      'target_state', 'runtime_quality_denominator_eligible'):
            if row.get(field) != frozen.get(field):
                raise ValueError(f'development_frozen_defect:{key}:{field}')
        request = row['provider_request']
        if digest(request) != row['input_digest']:
            raise ValueError('development_request_digest_defect')
        wire = provider.build_wire_request(request)
        if wire != row['wire_request'] or digest(wire) != row['wire_request_digest']:
            raise ValueError('development_wire_digest_defect')
        if request['context'].get('provider_revision') != provider.PROVIDER_REVISION:
            raise ValueError('development_provider_revision_defect')
        verified.append((row, supplied_truth[key]))
    return verified


def _summary(results: list[dict], *, valid_inputs: int, package_digest: str,
             stopped: str | None) -> dict:
    times = sorted(row['latency_ms'] for row in results if row['latency_ms'] is not None)
    def percentile(p):
        return times[max(0, math.ceil(len(times) * p) - 1)] if times else None
    roles = {}
    for row in results:
        roles.setdefault(row['actor_id'], {'calls': 0, 'unavailable_fields': row['unavailable_fields']})['calls'] += 1
    scored = [row for row in results if row['diagnostic_safety_pass'] is not None]
    return {'status': 'stopped_on_defect' if stopped else 'development_completed',
        'stop_reason': stopped, 'package_digest': package_digest, 'valid_inputs': valid_inputs,
        'provider_calls': len(results), 'successful_mappings': sum(bool(r['mapped_candidate']) for r in results),
        'diagnostic_safety_denominator': len(scored),
        'diagnostic_safety_passed': sum(row['diagnostic_safety_pass'] for row in scored),
        'diagnostic_safety_truth_status': 'provisional_authored_development_set_not_independent_gold',
        'action_target_quality_denominator': 0, 'role_sensitive_evaluation_denominator': 0,
        'role_sensitive_coverage_limit': 'All four scenarios test common diagnostic/safety behavior; sourced role conditions reach wire but these questions cannot establish role-sensitive quality.',
        'provider_errors': sum(row['error_kind'] == 'provider_error' for row in results),
        'mapping_rejections': sum(row['error_kind'] == 'mapping_rejection' for row in results),
        'latency_ms': {'count': len(times), 'min': min(times) if times else None,
            'max': max(times) if times else None, 'p50': percentile(.5), 'p95': percentile(.95)},
        'roles': roles, 'thresholds_frozen': False, 'A-Cognition': 'not_accepted',
        'A-Embodied': 'not_evaluated', 'final_labels_read': False,
        'calibration': 'exposed_version_ineligible_independent_rebuild_required'}


def run(package: dict[str, Any], *, repo: Path, output_dir: Path, endpoint: str,
        timeout_seconds: float = 120.0) -> dict:
    provider = LayaSystemOneProvider(endpoint=endpoint, timeout_seconds=timeout_seconds)
    verified = validate_package(package, repo=repo, provider=provider)
    destination = output_dir.resolve()
    if destination == repo.resolve() or repo.resolve() in destination.parents:
        raise ValueError('development_evidence_must_be_repository_external')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('development_evidence_destination_must_be_empty')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'frozen-development-package.json').write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    results, stopped = [], None
    gateway = CharacterModelGateway(provider=provider)
    with (destination / 'results.jsonl').open('x', encoding='utf-8') as evidence:
        for row, grade in verified:
            request, wire = row['provider_request'], row['wire_request']
            # Detect package changes between preflight and invocation without resending
            # any corrected version into an existing result set.
            if digest(request) != row['input_digest'] or provider.build_wire_request(request) != wire:
                stopped = 'runtime_discovered_input_defect'
                break
            provider.last_call = None
            started = monotonic()
            mapped_result, mapped_candidate, error, error_kind, passed = None, None, None, None, None
            try:
                mapped_result = gateway.complete_prepared_request(gateway.freeze_prepared_request(request))
                selected = mapped_result.get('selected_intent')
                mapped_candidate = request['context']['candidate_mapping'].get(selected)
                if not mapped_candidate:
                    stopped = 'runtime_discovered_candidate_mapping_defect'
                    raise ValueError(stopped)
                actual = [mapped_candidate['action_family'], mapped_candidate['target_refs']['target']]
                passed = actual in grade['acceptable_pairs']
            except (ValueError, KeyError, TypeError) as exc:
                error = str(exc)
                error_kind = 'mapping_rejection' if (provider.last_call or {}).get('response') is not None else 'provider_error'
            call = provider.last_call or {}
            result = {'scenario_id': row['scenario_id'], 'actor_id': row['actor_id'], 'split': 'development',
                'input_digest': row['input_digest'], 'complete_request_digest': digest(request),
                'wire_request_digest': row['wire_request_digest'], 'provider_request': request,
                'wire_request': wire, 'source_revisions': row['source_revisions'],
                'transformation_revisions': row['transformation_revisions'], 'frame': row['frozen_mind_frame'],
                'policy_revision': row['frame']['policy_revision'], 'provider_revision': provider.PROVIDER_REVISION,
                'candidate_digest': request['context']['candidate_digest'],
                'complete_u': row['complete_u'], 'controlled_p': row['controlled_p'],
                'crop_reasons': row['candidate_manifest']['cropped'],
                'wire_label_mapping': request['context']['candidate_mapping'],
                'unavailable_fields': row['role_projection']['unresolved'],
                'raw_response': call.get('response'), 'mapped_result': mapped_result,
                'mapped_candidate': mapped_candidate, 'rejection_reason': error, 'error_kind': error_kind,
                'latency_ms': call.get('latency_ms') or round((monotonic() - started) * 1000, 3),
                'actual_wire_request': call.get('request'), 'diagnostic_safety_pass': passed,
                'action_target_quality_eligible': False, 'offline_grading': grade}
            if call.get('request') != wire:
                stopped = 'runtime_discovered_actual_wire_defect'
            evidence.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
            evidence.flush()
            os.fsync(evidence.fileno())
            results.append(result)
            if stopped:
                break
    summary = _summary(results, valid_inputs=len(verified), package_digest=digest(package), stopped=stopped)
    (destination / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--timeout-seconds', type=float, default=120.0)
    args = parser.parse_args()
    summary = run(json.loads(args.package.read_text(encoding='utf-8')), repo=ROOT,
        output_dir=args.output_dir, endpoint=args.endpoint, timeout_seconds=args.timeout_seconds)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary['stop_reason'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
