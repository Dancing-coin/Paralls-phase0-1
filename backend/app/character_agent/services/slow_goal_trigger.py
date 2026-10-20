"""Derive bounded slow-goal triggers from committed actor-private outcomes.

This module is deliberately data-only.  It never promotes L2 hints and never
creates a goal or domain effect; callers must persist the source event before
passing the returned contract to cognition admission.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping


_FAILURE_STATUSES = {"rejected", "failed", "blocked"}
_TRIGGER_KINDS = {
    "repeated_failure",
    "complex_information_failure",
    "high_risk_information_failure",
    "persistent_information_failure",
}


def derive_goal_proposal_trigger(
    payload: Mapping[str, object],
    *,
    history: Iterable[Mapping[str, object]],
    frame_digest: str,
    goal_revision: int,
    source_event_id: str,
) -> dict[str, object] | None:
    """Return an admission-ready trigger contract for a qualifying outcome.

    Only actor-private settlement facts are considered.  A repeated failure is
    two prior failures plus the current failure for the same action profile.
    Explicit high-risk/complex/persistent markers are accepted when committed
    by the owner.  ``goal_hints`` and model confidence are intentionally
    ignored.
    """
    if not source_event_id or not frame_digest or type(goal_revision) is not int or goal_revision < 0:
        return None
    status = str(payload.get("settlement_status", "") or "")
    if status not in _FAILURE_STATUSES:
        return None
    action_profile = str(payload.get("action_profile", "") or "")
    prior = [item for item in history if isinstance(item, Mapping)
             and str(item.get("settlement_status", "") or "") in _FAILURE_STATUSES
             and (not action_profile or str(item.get("action_profile", "") or "") == action_profile)]
    marker = str(payload.get("slow_goal_trigger_kind", "") or "")
    if marker not in _TRIGGER_KINDS:
        marker = "repeated_failure" if len(prior) >= 2 else ""
    if not marker:
        return None
    evidence_refs = [str(item.get("result_id", "") or "") for item in [*prior[-2:], payload]]
    evidence_refs = list(dict.fromkeys(ref for ref in evidence_refs if ref))
    return {
        "eligible": True,
        "trigger_kind": marker,
        "trigger_source_ref": source_event_id,
        "frame_digest": frame_digest,
        "goal_revision": goal_revision,
        "evidence_refs": evidence_refs,
        "source_scope": "actor_private_settlement",
    }


__all__ = ["derive_goal_proposal_trigger"]
