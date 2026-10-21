from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.character_agent.models.mind_frame import CharacterMindFrame, MentalFactorProjectionCard, MindFrameLayer
from app.character_agent.planning.l3_planner import CandidateCompiler
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.profile.models import CharacterProfile
from app.character_agent.profile.personality_projection import PersonalityProjectionResolver
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
PROVIDER_REVISION='laya:68804629e8ccd9d616d48a40e87de9fabbeae069:1720e3e3357cfe1e281542e223f8273b0890ca34'
ACTORS=('char_a','char_b','char_c','char_d')
ROLE_REFS={a:['docs/10月分析/角色/13-角色能力图谱、认知包络与动态算力设计.md#12'] for a in ACTORS[:3]}; ROLE_REFS['char_d']=ROLE_REFS['char_a']+['docs/10月分析/角色/13-角色能力图谱、认知包络与动态算力设计.md#22']
def load_yaml(path:Path)->dict[str,Any]:
 v=yaml.safe_load(path.read_text(encoding='utf-8'))
 if not isinstance(v,dict): raise ValueError(f'invalid_yaml:{path}')
 return v
def _sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _check_pins(repo:Path, policy:dict[str,Any])->None:
 for pin in policy.get('source_pins',[]):
  p=repo/str(pin.get('path',''))
  if not p.is_file() or _sha(p)!=str(pin.get('sha256','')): raise ValueError(f"source_changed:{pin.get('path','')}")
def _frame(actor:str,s:dict[str,Any],turn:int,projection:dict[str,Any])->dict[str,Any]:
 refs=projection['source_refs']; frame=CharacterMindFrameBuilder().build_frame(actor_id=actor,producer_ts=turn,effective_profile=projection['effective_profile'],snapshot={'event':s['event'],'visible_target_refs':s['visible_targets'],'question':s['question']},event_inbox=[{'scenario_id':s['scenario_id'],'event':s['event'],'question':s['question']}])
 frame=frame.model_copy(update={'turn_id':f"evaluation-turn:{actor}:{s['scenario_id']}",'policy_revision':'policy:diagnostic-preparation-v3','source_refs':tuple(refs),'runtime_state':MindFrameLayer(cards=[MentalFactorProjectionCard(factor_type='perception_context',layer='runtime_state',summary=s['event'],payload={'visible_targets':s['visible_targets'],'question':s['question']},source_refs=[f"fixture:scenario:{s['scenario_id']}"])])})
 payload=frame.model_dump(mode='json',exclude={'frame_digest'}); digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(); return frame.model_copy(update={'frame_digest':digest}).model_dump(mode='json')
def _candidates(s:dict[str,Any],actor:str)->list[dict[str,Any]]:
 target,contact=s['objects'][0],s['contact']; refs=ROLE_REFS[actor]+[f"fixture:scenario:{s['scenario_id']}"]
 def one(action,target_ref): return {'candidate_id':f'{action}:{target_ref}','wire_label':f'{action}:{target_ref}','action_family':action,'target_refs':{'target':target_ref},'required_conditions':{'visibility':'satisfied'},'target_visibility':'visible','target_provenance':[f"fixture-visible:{s['scenario_id']}"],'affordance_result':{'status':'available','source':'authored_fixture'},'owner_route':'unassigned','source_refs':refs,'revision_pins':{'scenario_revision':'four-role-preparation-v1'}}
 return [one('observe',target),one('ask_probe',contact),one('defer',target)]
def _projection(policy,actor,repo=ROOT):
 role=policy['roles'][actor]
 if actor!='char_d':
  path=repo/'assets'/'characters'/'profiles'/f'{actor}.yaml'
  profile=CharacterProfile.model_validate(load_yaml(path)).model_dump(mode='json',exclude_unset=True)
  allowed={'identity_core','personality_layer','trait_vector_layer','capability_constraint_layer','virtue_value_layer','style_expression_bias_layer','conversation_personality_layer','need_hierarchy_layer','temperament_response_layer'}
  profile={k:v for k,v in profile.items() if k in allowed}
  profile['personality_projection']=PersonalityProjectionResolver().resolve(profile)
  return {'status':'schema_validated_authored_profile','runtime_admission':False,'source_refs':[str(path.relative_to(repo)).replace('\\','/')]+role['source_refs'],'source_revision':_sha(path),'effective_profile':profile,'unresolved':['cognitive_facets','hard_limits','compute_defaults'],'schema':'CharacterProfile','visibility':'own_character_and_provider_allowlisted_summary'}
 authored=load_yaml(repo/'backend/tests/fixtures/character_evaluation/char_d_authored/profile.yaml')
 if authored.get('actor_id') != actor or not authored.get('canonical_name') or authored.get('schema_mapping',{}).get('runtime_admission') is not False:
  raise ValueError('invalid_isolated_authored_profile')
 return {'status':role['status'],'runtime_admission':False,'source_refs':['backend/tests/fixtures/character_evaluation/char_d_authored/profile.yaml','backend/tests/fixtures/character_evaluation/char_d_authored/dossier.yaml','backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml']+role['source_refs'],'source_caps':role['source_caps'],'effective_profile':{'identity_core':{'character_id':authored['actor_id'],'canonical_name':authored['canonical_name']}},'unresolved':role['unresolved'],'schema_status':'partial_authored_fixture_not_full_CharacterProfile','source_revision':_sha(repo/'backend/tests/fixtures/character_evaluation/char_d_authored/profile.yaml')}

def _char_d_schema_manifest(repo: Path, fixture: Path) -> list[dict[str, Any]]:
    """Record authored char_d fields without pretending missing runtime fields exist."""
    profile = fixture.parent / 'char_d_authored' / 'profile.yaml'
    dossier = fixture.parent / 'char_d_authored' / 'dossier.yaml'
    revisions = {str(p): _sha(repo / p) for p in (
        'backend/tests/fixtures/character_evaluation/char_d_authored/profile.yaml',
        'backend/tests/fixtures/character_evaluation/char_d_authored/dossier.yaml',
        'backend/tests/fixtures/character_evaluation/char_d_authored/sources.yaml',
    )}
    rows = [
        ('actor_id', 'CharacterProfile.identity_core.character_id', 'profile.yaml', True, 'isolated_fixture'),
        ('canonical_name', 'CharacterProfile.identity_core.canonical_name', 'profile.yaml', True, 'isolated_fixture'),
        ('authoring_status', 'CharacterProfile.metadata.authoring_status', 'profile.yaml', True, 'isolated_fixture'),
        ('personality_numeric_values', 'CharacterProfile.personality_layer.big_five/facets', 'profile.yaml', False, 'unknown/unavailable'),
        ('cognitive_facets', 'CharacterProfile.cognitive_capability_layer', 'profile.yaml', False, 'unknown/unavailable'),
        ('hard_limits', 'CapabilityEnvelope.hard_limits', 'profile.yaml', False, 'unknown/unavailable'),
        ('compute_defaults', 'CognitionPolicy.compute_defaults', 'profile.yaml', False, 'unknown/unavailable'),
        ('dossier_id', 'CharacterDossier.dossier_id', 'dossier.yaml', True, 'isolated_fixture'),
        ('schema_version', 'CharacterDossier.schema_version', 'dossier.yaml', True, 'isolated_fixture'),
        ('capability_seed_schema_values', 'CharacterDossier.capability_seed_profile', 'dossier.yaml', False, 'unknown/unavailable'),
        ('authority_owner_binding', 'CharacterDossier.authority_profile.owner_binding', 'dossier.yaml', False, 'unknown/unavailable'),
        ('embodiment_asset_binding', 'CharacterDossier.embodiment_profile.asset_binding', 'dossier.yaml', False, 'unknown/unavailable'),
    ]
    authored = {**load_yaml(profile), **load_yaml(dossier)}
    out = []
    for name, path, source, required, status in rows:
        value_present = name in authored or (name == 'actor_id' and authored.get('actor_id') == 'char_d')
        out.append({'field': name, 'source': f'backend/tests/fixtures/character_evaluation/char_d_authored/{source}',
                    'schema_path': path, 'revision': revisions[f'backend/tests/fixtures/character_evaluation/char_d_authored/{source}'],
                    'privacy_visibility': 'isolated_fixture_only' if status == 'isolated_fixture' else 'unknown/unavailable',
                    'required': required, 'status': status if value_present or status != 'isolated_fixture' else 'unknown/unavailable',
                    'present': bool(value_present) if status == 'isolated_fixture' else False})
    return out

def _acceptable_action(actor: str, scenario: dict[str, Any], pair: list[str], corpus: dict[str, Any]) -> dict[str, Any]:
    action, target = pair
    return {'action_id': action, 'target_refs': {'target': target},
            'source_refs': list(dict.fromkeys(ROLE_REFS[actor] + list(corpus.get('source_refs', [])) +
                ['backend/app/character_agent/planning/l3_planner.py', 'backend/app/character_agent/execution/l4_executor.py'])),
            'candidate_compiler_revision': 'CandidateCompiler:current',
            'visibility': 'visible_fixture', 'target_status': 'authored_only_unverified',
            'execution_contract': 'unverified_owner_admission',
            'review_reason': 'source_review_required_before_quality_use'}
def prepare(repo:Path,fixture:Path,*,policy=None,corpus=None,splits=None):
    policy = policy or load_yaml(fixture / 'development-policy.yaml')
    corpus = corpus or load_yaml(fixture / 'development.yaml')
    _check_pins(repo, policy)
    scenarios = list(corpus['scenarios'])
    seen: dict[str, str] = {}
    if splits is not None and set(splits) & {'final', 'independent_holdout'}:
        raise ValueError('sealed_split_not_available')
    for scenario in scenarios:
        split = str(scenario['split'])
        group = str(scenario['trajectory_group'])
        if splits is not None and split in splits and split in {'final', 'independent_holdout'}:
            raise ValueError('sealed_split_not_available')
        if group in seen and seen[group] != split:
            raise ValueError(f'trajectory_leakage:{group}')
        seen[group] = split
        if split != 'development':
            raise ValueError('development_only_source_required')
        if not scenario.get('visible_targets'):
            raise ValueError(f"fixture_target_not_visible:{scenario['scenario_id']}")

    records: list[dict[str, Any]] = []
    grading: list[dict[str, Any]] = []
    for scenario in scenarios:
        if splits is not None and scenario['split'] not in splits:
            continue
        for offset, actor in enumerate(ACTORS):
            reference_u = list(scenario['reference_u'])
            compiled = CandidateCompiler(description_contract_revision="candidate-semantics:v4:1").compile(
                candidates=_candidates(scenario, actor),
                envelope={
                    'allowed_action_families': policy['candidate_contract']['allowed_action_families'],
                    'max_candidate_intents': 3,
                },
                visible_targets=set(scenario['visible_targets']),
            )
            if [str(item.get('wire_label')) for item in compiled.universe] != reference_u:
                raise ValueError(f"reference_u_mismatch:{scenario['scenario_id']}:{actor}")
            projection = _projection(policy, actor, repo)
            frame = _frame(actor, scenario, 1000 + offset, projection)
            request = CharacterModelGateway().prepare_run_request(
                task_kind='l3_planning', route_override='laya',
                context={
                    'actor_id': actor,
                    'control_mode': 'agent_full_auto',
                    'snapshot': {'event': scenario['event'], 'question': scenario['question'], 'visible_target_refs': scenario['visible_targets'], 'source_semantics': {'unknown_unavailable':projection['unresolved'], **({'isolated_authored_source_caps':projection['source_caps']} if actor=='char_d' else {})}},
                    'effective_profile': projection['effective_profile'],
                    'candidate_intents': compiled.wire_labels,
                    'frozen_candidates': compiled.presented,
                    'candidate_mapping': compiled.by_wire_label,
                    'candidate_digest': compiled.digest,
                    'provider_revision': PROVIDER_REVISION,
                    'frame': CharacterMindFrame.model_validate(frame),
                    'capability_envelope': {},
                    'cognition_policy': {},
                },
            )
            request = json.loads(CharacterModelGateway.freeze_prepared_request(request))
            wire_request = LayaSystemOneProvider(endpoint='http://127.0.0.1:8765').build_wire_request(request)
            acceptable = [_acceptable_action(actor, scenario, pair, corpus) for pair in scenario['review']['acceptable_pairs']]
            grade = {
                'acceptable_pairs': scenario['review']['acceptable_pairs'],
                'reviewer': None,
                'authored_by': corpus['author'],
                'independent_review_approved': False,
                'truth_status': 'preserved_authored_development_action_set_diagnostic_only',
                'original_reviewer_rationale': 'unavailable_in_development_only_v2_package',
                'review_date': corpus['review_date'],
                'rationale': scenario['review']['rationale'],
            }
            records.append({
                'scenario_id': scenario['scenario_id'],
                'split': scenario['split'],
                'trajectory_group': scenario['trajectory_group'],
                'actor_id': actor,
                'frame': frame,
                'private_projection': {'status': 'not_used_public_fixture'},
                'source_ref': list(dict.fromkeys(corpus.get('source_refs', []) + ROLE_REFS[actor])),
                'frozen_mind_frame': frame,
                'visible_evidence': {'event': scenario['event'], 'question': scenario['question'], 'targets': scenario['visible_targets']},
                'complete_u': reference_u,
                'controlled_p': compiled.wire_labels,
                'candidate_manifest': {'universe': reference_u, 'controlled': compiled.wire_labels,
                    'candidate_order': compiled.wire_labels, 'cropped': [], 'compiler_revision': 'CandidateCompiler:current'},
                'reference_u_match': True,
                'target_state': {
                    'evidence_kind': 'authored_fixture',
                    'runtime_legality': 'unverified',
                    'legal_target': False,
                    'visible_targets': scenario['visible_targets'],
                },
                'role_projection': projection,
                'provider_request': request,
                'wire_request': wire_request,
                'wire_request_digest': _digest(wire_request),
                'input_digest': _digest(request),
                'source_revisions': {ref: _sha(repo/ref) for ref in projection['source_refs'] if (repo/ref).is_file()},
                'transformation_revisions': {ref: _sha(repo/ref) for ref in ('scripts/verification/prepare_character_evaluation.py','backend/app/character_agent/gateway/model_gateway.py','backend/app/character_agent/gateway/laya_provider.py','backend/app/character_agent/planning/l3_planner.py','backend/app/character_agent/profile/personality_projection.py')},
                'runtime_quality_denominator_eligible': False,
                'base_selection': {'controlled_error': False, 'status': 'not_run'},
                'character_performance': {'seed': 401, 'status': 'not_run'},
            })
            grading.append({'scenario_id': scenario['scenario_id'], 'actor_id': actor, 'acceptable_action_set': acceptable, 'truth_source':'backend/tests/fixtures/character_evaluation/four_role_preparation/development.yaml', 'truth_source_digest':_sha(fixture/'development.yaml'), **grade})
    char_d_manifest = _char_d_schema_manifest(repo, fixture)
    input_checks = []
    provider = LayaSystemOneProvider(endpoint='http://127.0.0.1:8765')
    for row in records:
        wire = provider.build_wire_request(row['provider_request'])
        checks = {
            'development_only': row['split'] == 'development',
            'source_revision_present': bool(row['source_revisions']),
            'schema_parse_and_authored_fields_only': bool(row['role_projection']['source_revision']),
            'unknown_fields_preserved': not row['provider_request']['context']['capability_envelope'] and not row['provider_request']['context']['cognition_policy'],
            'wire_matches_frozen_request': wire == row['wire_request'] and _digest(wire) == row['wire_request_digest'],
            'labels_match_controlled_p': list(wire['questions']['choice']['criteria']) == row['controlled_p'],
            'no_grading_fields': not any(field in json.dumps(wire,ensure_ascii=False) for field in ('acceptable_pairs','acceptable_action','reviewer','rationale','life_memory_backbone')),
        }
        input_checks.append({'scenario_id':row['scenario_id'],'actor_id':row['actor_id'],'checks':checks,'passed':all(checks.values())})
    return {
        'revision': 'four-role-development-v3-shared-runtime-serializer',
        'source_corpus_digest': _sha(fixture/'development.yaml'),
        'source_package_sha256': corpus['source_package_sha256'],
        'conversion_path': ['development-only-v2-records','development.yaml','CharacterProfile.model_validate/exclude_unset + PersonalityProjectionResolver','CharacterMindFrameBuilder','CandidateCompiler','CharacterModelGateway.prepare_run_request/freeze_prepared_request','LayaSystemOneProvider.build_wire_request'],
        'input_checks': input_checks,
        'status': 'diagnostic_inputs_prepared',
        'preflight': {'development_ready': len(records) == 16 and all(item['passed'] for item in input_checks), 'calibration_ready': False, 'final_ready': False,
                      'development_ready_reasons': ['all_16_source_schema_visibility_unknown_isolation_and_full_wire_checks_passed'] if len(records)==16 and all(item['passed'] for item in input_checks) else ['input_check_failed'],
                      'calibration_blockers': ['candidate_policy_not_frozen', 'thresholds_not_frozen', 'exposed_calibration_version_ineligible_independent_rebuild_required'],
                      'final_blockers': ['calibration_not_run', 'independent_holdout_split_reserved_not_observed', 'final_labels_sealed']},
        'char_d_schema_manifest': char_d_manifest,
        'question_manifest': [{'scenario_id': s['scenario_id'], 'source_refs': corpus.get('source_refs', []), 'split': s['split'],
            'target_status': 'authored_visible_unverified', 'legal_target': False,
            'diagnostic_only': True, 'acceptable_action_count': len(s['review']['acceptable_pairs'])} for s in scenarios],
        'split_manifest': {'development': sorted({s['trajectory_group'] for s in scenarios if s['split'] == 'development'}),
            'calibration': sorted({s['trajectory_group'] for s in scenarios if s['split'] == 'calibration'}), 'final': [], 'independent_holdout': []},
        'metric_denominator_manifest': {'candidate_coverage': 'all prepared rows', 'conditional_selection_quality': 'legal_target=true and acceptable member presented',
            'end_to_end_selection_quality': 'legal_target=true', 'diagnostic_or_safety_only': 'legal_target=false; excluded from action+target quality'},
        'records': records,
        'grading': grading,
        'provider_calls': 0,
        'final_labels_read': False,
        'A-Cognition': 'blocked',
        'A-Embodied': 'blocked',
        'thresholds': {**policy['thresholds'], 'status': 'not_frozen', 'approved': False},
        'calibration': {**policy['calibration'], 'status':'exposed_version_ineligible_for_blind_calibration', 'rebuild_required': True, 'rebuild_rule':'independent_new_questions_no_rename_shuffle_or_reuse'},
        'independent_holdout': policy['independent_holdout'],
    }

def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def main():
 p=argparse.ArgumentParser(); p.add_argument('--fixture',type=Path,default=Path('backend/tests/fixtures/character_evaluation/four_role_preparation')); p.add_argument('--output-dir',type=Path); a=p.parse_args(); payload=prepare(ROOT,a.fixture); text=json.dumps(payload,ensure_ascii=False,indent=2)+'\n';
 if a.output_dir:
  a.output_dir.mkdir(parents=True, exist_ok=True)
  (a.output_dir/'preparation-package.json').write_text(text, encoding='utf-8')
  for key, filename in (('char_d_schema_manifest','char_d-schema-manifest.json'),('question_manifest','question-manifest.json'),('split_manifest','split-manifest.json'),('metric_denominator_manifest','metric-denominator-manifest.json')):
   (a.output_dir/filename).write_text(json.dumps(payload[key],ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
 print(text,end=''); return 0
if __name__=='__main__':raise SystemExit(main())

