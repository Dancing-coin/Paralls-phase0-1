from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_registry_admission_probe_exists_and_is_fail_closed():
    probe=ROOT/'scripts/verification/CharacterAssetAdmissionProgressiveProbe.gd'
    assert probe.exists()
    source=probe.read_text(encoding='utf-8')
    for token in ('package_not_qualified','semantic_action_unavailable','wrong_digest','qualified'):
        assert token in source

def test_business_action_requests_use_package_and_semantic_action_id():
    source=(ROOT/'scripts/street_combat/StreetCombatCoordinator.gd').read_text(encoding='utf-8')
    assert 'RolePresentationAdapter.new(_registry, skin)' in source
    assert 'package_id' in source and 'semantic_action_id' in source
    assert 'clip_ref' not in source
