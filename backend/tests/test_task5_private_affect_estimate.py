from app.character_agent.memory.relational_memory import CharacterRelationalMemory
from app.gameplay.relationship_private_estimate import ActorPrivateAffectEstimateAuthority


def _authority() -> ActorPrivateAffectEstimateAuthority:
    return ActorPrivateAffectEstimateAuthority(memory=CharacterRelationalMemory())


def test_fear_and_morale_are_actor_private_and_replace_previous_estimate() -> None:
    authority = _authority()
    fear = authority.record(
        actor_id="char:a",
        estimate_kind="fear",
        value=0.75,
        source_event_id="combat:event:1",
        producer_ts=10,
    )
    morale = authority.record(
        actor_id="char:a",
        estimate_kind="morale",
        value=0.25,
        source_event_id="combat:event:1",
        producer_ts=10,
    )
    assert fear.committed and morale.committed
    rows = authority.recall(requester_actor_id="char:a", owner_actor_id="char:a")
    assert {row["belief_type"] for row in rows} == {"fear_estimate", "morale_estimate"}
    authority.record(
        actor_id="char:a",
        estimate_kind="fear",
        value=0.5,
        source_event_id="combat:event:2",
        producer_ts=11,
    )
    fear_rows = [row for row in authority.recall(requester_actor_id="char:a", owner_actor_id="char:a") if row["belief_type"] == "fear_estimate"]
    assert len(fear_rows) == 1
    assert fear_rows[0]["value"] == "0.5"


def test_private_estimate_cannot_be_read_by_another_actor() -> None:
    authority = _authority()
    authority.record(
        actor_id="char:a",
        estimate_kind="fear",
        value=0.4,
        source_event_id="combat:event:1",
        producer_ts=1,
    )
    assert authority.recall(requester_actor_id="char:b", owner_actor_id="char:a") == ()


def test_invalid_scope_value_kind_and_source_are_zero_write() -> None:
    authority = _authority()
    for kwargs, reason in (
        ({"visibility_scope": "project"}, "private_estimate_visibility_invalid"),
        ({"value": 1.1}, "private_estimate_value_invalid"),
        ({"estimate_kind": "threat"}, "private_estimate_kind_invalid"),
        ({"source_event_id": ""}, "private_estimate_source_missing"),
    ):
        params = {
            "actor_id": "char:a",
            "estimate_kind": "fear",
            "value": 0.5,
            "source_event_id": "combat:event:1",
            "producer_ts": 1,
        }
        params.update(kwargs)
        result = authority.record(**params)
        assert not result.committed
        assert result.stop_reason == reason
    assert authority.recall(requester_actor_id="char:a", owner_actor_id="char:a") == ()


def test_private_estimate_does_not_create_shared_relationship_or_target_fact() -> None:
    authority = _authority()
    authority.record(
        actor_id="char:a",
        estimate_kind="morale",
        value=0.9,
        source_event_id="combat:event:1",
        producer_ts=1,
    )
    rows = authority.recall(requester_actor_id="char:a", owner_actor_id="char:a")
    assert all(row["entity_id"] == "char:a" for row in rows)
    assert all(row["belief_type"] in {"fear_estimate", "morale_estimate"} for row in rows)
