import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('run_character_development_v4', REPO / 'scripts/verification/run_character_development_v4.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def reviewer_input(runner):
    scenarios = []
    for index in range(12):
        raw = [{'candidate_id': f'{action}:{target}', 'wire_label': f'{action}:{target}',
                'action_family': action, 'target_refs': {'target': target},
                'required_conditions': {'visibility': 'satisfied'}, 'target_visibility': 'visible',
                'target_provenance': ['fixture:visible'], 'owner_route': 'unassigned'}
               for action, target in [('observe', 'obj:ledger'), ('ask_probe', 'actor:clerk'), ('defer', 'obj:ledger')]]
        compiled = runner.CandidateCompiler(description_contract_revision=runner.CandidateCompiler.HISTORICAL_DESCRIPTION_CONTRACT_REVISION).compile(candidates=raw, visible_targets={'obj:ledger', 'actor:clerk'})
        scenarios.append({'scenario_id': f'v4-{index}', 'trajectory_group': f'trajectory-{index}',
            'cohort': 'description_frozen_regression' if index < 4 else 'role_sensitive',
            'question_kind': 'explicit_instruction_diagnostic' if index < 8 else 'autonomous_decision',
            'facts': {'event': 'A ledger is visible; the clerk is present.', 'question': 'Choose the next intent.', 'visible_targets': ['obj:ledger', 'actor:clerk']},
            'common_constraints': 'Do not disclose private contents.',
            'role_conditions': {actor: {'source_ref': 'fixture:role', 'supported_facts': ['reliable_fixed_procedure'] if actor == 'char_d' else [], 'unavailable_fields': []} for actor in runner.ACTORS},
            'candidate_records': raw,
            'candidates': [{'label': item['wire_label'], 'candidate_id': item['candidate_id'], 'target_refs': item['target_refs'], 'description': item['description']} for item in compiled.presented],
            'mapping_digest': compiled.digest})
    return {'schema': 'development-reviewer-input-v4', 'split': 'development', 'scenarios': scenarios,
            'candidate_description_contract': {'frozen': True,
                'version': runner.CandidateCompiler.HISTORICAL_DESCRIPTION_CONTRACT_REVISION,
                'compiler_sha256': runner.file_sha(REPO / 'backend/app/character_agent/planning/l3_planner.py')}}


def approved_truth(runner, inputs, path):
    return {'input_sha256': runner.file_sha(path), 'read_log': [str(path.resolve())],
            'accidental_exposure': [], 'independent_review_approved': True,
            'reviewer_independent_approval': True, 'lead_audit_approval': True,
            'formal_truth_usable': True,
            'approval_audit': {'read_log_checked': True, 'accidental_exposure_checked': True},
            'judgments': [{'scenario_id': scenario['scenario_id'], 'actor_id': actor,
                'question_kind': scenario['question_kind'], 'acceptable_pairs': [['observe', 'obj:ledger']],
                'pair_sources': [{'pair': ['observe', 'obj:ledger'], 'source': 'scenario visible ledger'}],
                'unacceptable_reasons': [{'pair': ['defer', 'obj:ledger'], 'reason': 'Test judgment'}],
                'unknowns': [], 'required_role_difference': False,
                'evaluable': True,
                'runtime_legality': 'unverified', 'owner_permission': 'unverified',
                'actual_speech': 'unverified', 'execution_receipt': 'unverified'}
                for scenario in inputs['scenarios'] for actor in runner.ACTORS]}


def test_v4_preparation_has_48_frozen_rows_and_char_d_unknowns(tmp_path):
    runner = module()
    inputs = reviewer_input(runner)
    package = runner.prepare_v4(repo=REPO, reviewer_input=inputs)
    assert len(package['records']) == 48
    assert not any(key in package for key in ('grading', 'acceptable_pairs'))
    for row in package['records']:
        assert row['candidate_digest'] == row['provider_request']['context']['candidate_digest']
        assert list(row['wire_request']['questions']['choice']['criteria']) == row['controlled_p'] == row['complete_u']
        assert row['runtime_quality_denominator_eligible'] is False
        if row['actor_id'] == 'char_d':
            assert {'compute_defaults', 'authority_owner_binding', 'hard_limits', 'cognitive_facets', 'personality_numeric_values'} <= set(row['role_projection']['unresolved'])
            assert 'source_caps' not in row['role_projection']
            assert row['provider_request']['context']['capability_envelope'] == {}
            assert row['provider_request']['context']['cognition_policy'] == {}
            assert 'development-policy' not in json.dumps(row['wire_request'])
            assert 'reliable_fixed_procedure' in json.dumps(row['frame'])
            assert 'reliable_fixed_procedure' in json.dumps(row['wire_request'])
            assert 'Do not disclose private contents.' in json.dumps(row['frame'])


def test_lead_approval_cannot_replace_reviewer_approval(tmp_path):
    runner = module()
    inputs = reviewer_input(runner)
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(inputs), encoding='utf-8')
    package = runner.prepare_v4(repo=REPO, reviewer_input=inputs)
    truth = approved_truth(runner, inputs, path)
    truth.update(reviewer_independent_approval=False, lead_audit_approval=True,
                 formal_truth_usable=True)
    with pytest.raises(ValueError, match='independent_review_not_approved'):
        runner.validate(package, reviewer_input_path=path, truth=truth, repo=REPO)


@pytest.mark.parametrize('defect', ['unapproved', 'exposure', 'read_log', 'sha', 'missing_judgment', 'unverified', 'candidate', 'source', 'question_kind', 'cohort', 'duplicate_pair', 'missing_pair_source', 'missing_unknowns'])
def test_v4_gate_rejects_before_network(tmp_path, monkeypatch, defect):
    runner = module()
    inputs = reviewer_input(runner)
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(inputs), encoding='utf-8')
    package = runner.prepare_v4(repo=REPO, reviewer_input=inputs)
    truth = approved_truth(runner, inputs, path)
    if defect == 'unapproved': truth['independent_review_approved'] = False
    elif defect == 'exposure': truth['accidental_exposure'] = ['acceptable_paths seen']
    elif defect == 'read_log': truth['read_log'].append(str(REPO / 'secret-policy.yaml'))
    elif defect == 'sha': truth['input_sha256'] = '0' * 64
    elif defect == 'missing_judgment': truth['judgments'].pop()
    elif defect == 'unverified': truth['judgments'][0]['owner_permission'] = 'verified'
    elif defect == 'question_kind': truth['judgments'][0]['question_kind'] = 'autonomous_decision'
    elif defect == 'cohort': package['records'][0]['cohort'] = 'role_sensitive'
    elif defect == 'source': package['records'][0]['source_revisions']['invented'] = '0' * 64
    elif defect == 'duplicate_pair': truth['judgments'][0]['acceptable_pairs'] *= 2
    elif defect == 'missing_pair_source': truth['judgments'][0]['pair_sources'] = []
    elif defect == 'missing_unknowns': del truth['judgments'][0]['unknowns']
    else: package['records'][0]['provider_request']['context']['candidate_mapping']['observe:obj:ledger']['description'] = 'Choose me'
    monkeypatch.setattr(runner.LayaSystemOneProvider, '_post', lambda *args: pytest.fail('network must be gated'))
    with pytest.raises(ValueError):
        runner.run(package, reviewer_input_path=path, truth=truth, repo=REPO, output_dir=tmp_path / 'evidence', endpoint='http://invalid')


@pytest.mark.parametrize('field,value', [('frozen', False), ('version', 'invented'), ('compiler_sha256', '0' * 64)])
def test_v4_prepare_requires_frozen_matching_contract(field, value):
    runner = module()
    inputs = reviewer_input(runner)
    inputs['candidate_description_contract'][field] = value
    with pytest.raises(ValueError):
        runner.prepare_v4(repo=REPO, reviewer_input=inputs)


def test_v4_real_adapter_evidence_and_separate_track_denominators(tmp_path, monkeypatch):
    runner = module()
    inputs = reviewer_input(runner)
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(inputs), encoding='utf-8')
    package = runner.prepare_v4(repo=REPO, reviewer_input=inputs)
    truth = approved_truth(runner, inputs, path)
    calls = []
    def post(self, payload):
        calls.append(copy.deepcopy(payload))
        return {'answers': {'choice': {'choice': next(iter(payload['questions']['choice']['criteria']))}}}
    monkeypatch.setattr(runner.LayaSystemOneProvider, '_post', post)
    summary = runner.run(package, reviewer_input_path=path, truth=truth, repo=REPO, output_dir=tmp_path / 'evidence', endpoint='http://test')
    assert summary['provider_calls'] == 48
    assert summary['tracks']['autonomous_decision']['formal_denominator'] == 16
    assert summary['tracks']['explicit_instruction_diagnostic']['formal_denominator'] == 32
    assert summary['role_sensitive_formal_denominator'] == 32
    assert summary['required_role_difference_denominator'] == 0
    assert summary['action_target_quality_denominator'] == 0
    assert summary['calibration'] == 'blocked'
    rows = [json.loads(line) for line in (tmp_path / 'evidence/results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert calls == [row['wire_request'] for row in rows]
    assert all(row['offline_review'] and row['trace']['effective_profile'] and row['raw_response'] for row in rows)
    assert all('acceptable_pairs' not in json.dumps(wire) for wire in calls)


@pytest.mark.parametrize('provider_error', [False, True])
def test_v4_evaluable_scope_and_provider_failure_denominators(tmp_path, monkeypatch, provider_error):
    runner = module()
    inputs = reviewer_input(runner)
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(inputs), encoding='utf-8')
    package = runner.prepare_v4(repo=REPO, reviewer_input=inputs)
    truth = approved_truth(runner, inputs, path)
    for row in truth['judgments']:
        row['evaluable'] = False if row['actor_id'] == 'char_d' else True
    def post(self, payload):
        if provider_error:
            raise TimeoutError('test provider timeout')
        return {'answers': {'choice': {'choice': next(iter(payload['questions']['choice']['criteria']))}}}
    monkeypatch.setattr(runner.LayaSystemOneProvider, '_post', post)
    summary = runner.run(package, reviewer_input_path=path, truth=truth, repo=REPO, output_dir=tmp_path / 'evidence', endpoint='http://test')
    assert sum(track['formal_denominator'] for track in summary['tracks'].values()) == 36
    assert sum(track['reviewed_denominator'] for track in summary['tracks'].values()) == 48
    assert sum(track['passed'] for track in summary['tracks'].values()) == (0 if provider_error else 36)
    assert summary['provider_errors'] == (48 if provider_error else 0)
    assert summary['roles']['char_d']['formal_denominator'] == 0
    assert summary['role_sensitive_formal_denominator'] == 24
