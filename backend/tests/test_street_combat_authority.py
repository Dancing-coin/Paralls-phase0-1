from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.embodied_interaction import ActionAttempt
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


def attempt(key: str, actor: str = "street_bandage", target: str = "char_a", **changes: object) -> ActionAttempt:
    payload: dict[str, object] = {
        "attempt_id": f"attempt:{key}",
        "actor_ref": f"character:{actor}",
        "action_instance_id": f"action:{key}",
        "semantic_action_id": "action:melee.unarmed_punch",
        "target_refs": [f"character:{target}"],
        "contact_marker_id": "short_punch_contact_window",
        "physics_tick": 100,
        "physics_evidence_refs": [f"contact:{key}"],
        "authority_route": "esm",
        "expected_revisions": {},
        "idempotency_key": f"street:{key}",
        "command_version": "v1",
        "causation_id": f"cause:{key}",
        "correlation_id": f"corr:{key}",
        "source": "player",
        "privacy_scope": "public",
    }
    payload.update(changes)
    return ActionAttempt.model_validate(payload)


def test_street_combat_rejects_far_target_without_damage() -> None:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("char_a", (-5.0, 0.2, -10.0), physics_tick=60)
    result = service.settle_street_combat(attempt("far"))
    assert result.outcome == "rejected"
    assert result.failed_code == "target_out_of_range"
    assert service.street_actor_state("char_a")["hp"] == 100
    assert service.mutation_count == 0


def test_street_combat_hit_duplicate_stale_and_recovery() -> None:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=60)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=60)
    first = service.settle_street_combat(attempt("hit"))
    assert first.outcome == "committed"
    assert first.committed_projection["target_hp"] == 80
    duplicate = service.settle_street_combat(attempt("hit"))
    assert duplicate.transaction_id == first.transaction_id
    assert service.street_actor_state("char_a")["hp"] == 80
    stale = service.settle_street_combat(attempt("stale", expected_revisions={"actor:character:street_bandage": 0}))
    assert stale.outcome == "rejected"
    assert stale.failed_code == "revision_conflict"
    recovery = service.settle_street_combat(attempt("recover"))
    assert recovery.outcome == "committed"
    assert service.street_actor_state("char_a")["hp"] == 60
    assert service.mutation_count == 2


def test_street_short_punch_updates_authoritative_stamina_once() -> None:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=60)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=60)
    strike = attempt("short-punch", semantic_action_id="action:melee.short_punch")
    result = service.settle_street_combat(strike)
    assert result.outcome == "committed"
    assert result.committed_projection["actor_stamina"] == 92
    assert service.street_actor_state("street_bandage")["stamina"] == 92


def test_street_sword_slash_uses_imported_action_and_authority_contact() -> None:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=60)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=60)
    strike = attempt("sword-slash", semantic_action_id="action:melee.sword_slash")
    result = service.settle_street_combat(strike)
    assert result.outcome == "committed"
    assert result.committed_projection["semantic_action_id"] == "action:melee.sword_slash"
    assert result.committed_projection["actor_stamina"] == 86
    assert service.settle_street_combat(strike).transaction_id == result.transaction_id
    assert service.street_actor_state("street_bandage")["stamina"] == 86


def test_street_pose_rejects_teleport_and_client_damage() -> None:
    service = EmbodiedAuthoritySettlementService()
    assert not service.record_street_pose("street_bandage", (-20.0, 0.2, -21.0), physics_tick=1)
    assert service.street_actor_state("street_bandage")["position"] == (0.0, 0.2, -10.0)
    with pytest.raises(ValidationError):
        attempt("client-truth", damage=20)
