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
