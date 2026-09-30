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


def test_registry_exposes_typed_package_admission_and_rejects_raw_clip_lookup():
    source=(ROOT/'scripts/character/CharacterEmbodimentAssetRegistry.gd').read_text(encoding='utf-8')
    for token in ('admit_action_package', 'manifest_digest', 'skeleton_mapping', 'marker', 'raw_clip_lookup', 'rejection_reason', 'fallback_mode'):
        assert token in source


def test_semantic_presentation_ingress_runs_typed_admission_before_playback():
    source=(ROOT/'scripts/character/RolePresentationAdapter.gd').read_text(encoding='utf-8')
    ingress=source.split('func apply_input(input: Dictionary) -> Dictionary:', 1)[1]

    assert 'admit_action_package' in ingress
    for token in ('manifest_digest', 'canonical_skeleton_mapping_ref', 'marker_id', 'raw_clip_lookup'):
        assert token in ingress
    assert ingress.index('admit_action_package') < ingress.index('play_qualified_profile')
