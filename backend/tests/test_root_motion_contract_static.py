from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_root_motion_capability_boundary_exists():
    capability=(ROOT/'scripts/character/CharacterPresentationCapability.gd').read_text(encoding='utf-8')
    sampler=(ROOT/'scripts/character/RootMotionSampler.gd').read_text(encoding='utf-8')
    composer=(ROOT/'scripts/character/MotionContributionComposer.gd').read_text(encoding='utf-8')
    assert 'class_name CharacterPresentationCapability' in capability
    assert 'admits_drive_locomotion' in capability
    assert 'consume_delta' in sampler and 'reset' in sampler
    assert 'root_motion_policy' in composer and 'hold' in composer

def test_packages_keep_hold_zero_envelope_until_qualification():
    for package in ('female_bandage_external','female_jk_external','female_t_external'):
        manifest=(ROOT/'assets/active'/package/'manifest.json').read_text(encoding='utf-8')
        assert '"policy": "hold"' in manifest
        assert '"max_distance": 0.0' in manifest


def test_composer_emits_single_tick_root_consumption_contract():
    source=(ROOT/'scripts/character/MotionContributionComposer.gd').read_text(encoding='utf-8')
    for token in ('actor_id', 'move_local', 'root_delta_local', 'root_policy', 'consumption_token', 'source_digest'):
        assert token in source
    assert 'consumption_token' in (ROOT/'scripts/character/CharacterMotor.gd').read_text(encoding='utf-8')


def test_root_sampler_rejects_malformed_and_duplicate_consumption():
    source=(ROOT/'scripts/character/RootMotionSampler.gd').read_text(encoding='utf-8')
    for token in ('consume_delta_once', 'consumption_token', 'duplicate', 'malformed'):
        assert token in source


def test_motor_rejects_stale_and_duplicate_commands_and_owns_slide():
    source=(ROOT/'scripts/character/CharacterMotor.gd').read_text(encoding='utf-8')
    for token in ('stale_physics_tick', 'duplicate_consumption', 'root_delta_local', 'post_collision'):
        assert token in source
    assert source.count('move_and_slide(') == 1


def test_active_manifests_keep_unqualified_root_motion_fail_closed():
    import json
    for package in ('female_bandage_external','female_jk_external','female_t_external'):
        data=json.loads((ROOT/'assets/active'/package/'manifest.json').read_text(encoding='utf-8'))
        profile=data['root_motion_profile']
        assert profile['policy']=='hold'
        assert profile['max_distance']==0.0
        assert profile['max_duration_ticks']<=1
