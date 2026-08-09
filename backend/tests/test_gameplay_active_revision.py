from __future__ import annotations

import pytest


def test_active_revision_profiles_are_explicit_and_disabled_has_no_effects() -> None:
    from app.gameplay.active_world_revision import ActiveWorldRevisionAuthority, WorldProfile

    authority = ActiveWorldRevisionAuthority()
    assert authority.profile_effects(WorldProfile.DISABLED) == ()
    assert authority.profile_effects(WorldProfile.NARRATIVE) == ("narrative",)
    assert authority.profile_effects(WorldProfile.LIGHTWEIGHT) == ("narrative", "lightweight")
    assert authority.profile_effects(WorldProfile.SIMULATION) == ("narrative", "lightweight", "simulation")


def test_activation_lock_conflict_and_session_pinning_fail_closed() -> None:
    from app.gameplay.active_world_revision import ActiveWorldRevisionAuthority, RevisionCandidate

    authority = ActiveWorldRevisionAuthority()
    candidate = RevisionCandidate(revision_ref="world:demo:v2", dependencies=(), conflicts=())
    authority.stage(candidate, lock_ref="lock:one")

    with pytest.raises(ValueError, match="active_revision_lock_conflict"):
        authority.stage(candidate, lock_ref="lock:two")

    active = authority.activate("world:demo:v2", tick=42)
    assert authority.pin_session("session:one", active.digest) == active.digest
    with pytest.raises(ValueError, match="session_revision_pinned"):
        authority.pin_session("session:one", "sha256:different")


def test_incompatible_dependency_is_rejected_without_activation() -> None:
    from app.gameplay.active_world_revision import ActiveWorldRevisionAuthority, RevisionCandidate

    authority = ActiveWorldRevisionAuthority()
    with pytest.raises(ValueError, match="package_dependency_conflict"):
        authority.stage(RevisionCandidate(revision_ref="world:bad", dependencies=("missing:dep",), conflicts=()))
    assert authority.active_revision is None
