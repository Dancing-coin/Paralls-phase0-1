"""受信洪灾参与内容；保护声明不冒充库存、关系或道路事实。"""
from .simulation_contracts import ParticipationPolicy


FLOOD_ACTORS = ("character:char_a", "character:char_b", "character:char_c")
FLOOD_MODULES = ("identity", "needs", "schedule", "household", "supply", "situation", "affect", "behavior")


def _check_actor(actor_ref):
    if actor_ref not in FLOOD_ACTORS:
        raise ValueError("flood_actor_unknown")


def flood_participation_policies(*, actor_ref: str, scenario_revision: str) -> tuple[ParticipationPolicy, ...]:
    _check_actor(actor_ref)
    if scenario_revision != "flood:v1":
        raise ValueError("flood_rules_unknown")
    tiers = ("B2", "B3") if actor_ref == FLOOD_ACTORS[0] else (
        ("B3",) if actor_ref == FLOOD_ACTORS[2] else ("B0", "B1", "B2", "B3"))
    common = dict(revision="1", allowed_modules=FLOOD_MODULES,
        forbidden_dimensions=("household.members", "identity.protected_refs", "private_memory"),
        upgrade_triggers=("care_obligation", "road_review", "player_proximity"),
        b0_expiry_tick=7200, review_tick=10800)
    return (
        ParticipationPolicy(policy_ref="policy:farmer@1", allowed_tiers=("B0", "B1", "B2", "B3"), **common),
        ParticipationPolicy(policy_ref=f"policy:individual:{actor_ref}", allowed_tiers=tiers, **common),
        ParticipationPolicy(policy_ref=scenario_revision, allowed_tiers=("B0", "B1", "B2", "B3"), **common),
        ParticipationPolicy(policy_ref=f"policy:protection:{actor_ref}", allowed_tiers=tiers, **common),
    )


def flood_module_states(*, actor_ref: str):
    _check_actor(actor_ref)
    care = actor_ref == FLOOD_ACTORS[0]
    protected = ("policy:care:char_a", "policy:key-seeds:char_a", "policy:old-friend:char_a") if care else ()
    return {
        "identity": {"profile_ref": actor_ref, "protected_refs": protected},
        "needs": {"fatigue": 0.2, "need_pressure": 0.1, "revision": 0},
        "schedule": {"routine_allowed": True, "confirmed_refs": ()},
        "household": {"care_obligation": care, "protected_refs": protected},
        "supply": {"shortage": care}, "situation": {"road_risk": 0.4},
        "affect": {"public_pressure": 0.1}, "behavior": {"routine_allowed": True},
    }
