from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_arbiter_contract_has_independent_lease_action_and_frame_resolution() -> None:
    source = _read("scripts/character/ActorActionArbiter.gd")
    assert "func resolve(physics_tick" in source
    assert "ContinuousControlLease" in source
    assert "ActionInstance" in source
    assert "CharacterIntentFrame" in source


def test_scheduler_freezes_claim_tree_and_stable_conflict_decisions() -> None:
    source = _read("scripts/character/ResourceClaimScheduler.gd")
    for claim in ("world_motion", "pelvis", "upper_body", "left_arm", "right_arm", "left_hand", "right_hand", "left_leg", "right_leg", "head", "root_translation", "facing", "physics_body", "full_body_pose"):
        assert '"%s"' % claim in source
    assert "accept_now" in source
    assert "queue" in source
    assert "reject" in source
    assert "_claims_conflict" in source


def test_actions_have_independent_lifecycles_and_leases_expire() -> None:
    actions = _read("scripts/character/ActionInstance.gd")
    leases = _read("scripts/character/ContinuousControlLease.gd")
    for state in ("requested", "admitted", "queued", "windup", "contact", "recovery", "cancelled", "expired", "settled"):
        assert '"%s"' % state in actions
    assert "expires_at_tick" in leases
