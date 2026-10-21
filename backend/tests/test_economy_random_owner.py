from pathlib import Path

from app.gameplay.economy_random_policy import (
    EconomyRandomPolicy, RandomCandidate, SUPPORTED_ALGORITHM_REVISION,
    SUPPORTED_SEED_POLICY_REVISION,
)
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyRuntimeError
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.economy_random_policy import random_payload_digest, validate_anchored_random_payload
import pytest
from app.gameplay.random_business_admission import RandomBusinessSource


def _source() -> RandomBusinessSource:
    return RandomBusinessSource(
        demand_ref="demand:festival", demand_revision="r1", kind="lottery",
        issuer_ref="content-publisher:stage3", fact_owner_ref="actor_gameplay.economy_domain",
        actor_scope=("character:char_a",), world_scope=("world:main",), timeline_scope=("timeline:main",),
        valid_from_world_tick=0, valid_until_world_tick=20,
        candidate_registry_ref="registry:festival", candidate_registry_revision="r1",
        algorithm_revision=SUPPORTED_ALGORITHM_REVISION, seed_policy_revision=SUPPORTED_SEED_POLICY_REVISION,
        source_digest="sha256:" + "1" * 64,
        read_principals=("actor_gameplay.economy_domain",),
        receipt_lookup_ref="economy:random-receipts", revocation_owner_ref="content-owner:stage3",
    )


def _policy() -> EconomyRandomPolicy:
    return EconomyRandomPolicy(
        policy_ref="registry:festival", policy_revision="r1", kind="lottery",
        candidates=(RandomCandidate(candidate_ref="candidate:a", result_ref="result:a", weight=1),
                    RandomCandidate(candidate_ref="candidate:b", result_ref="result:b", weight=1)),
    )


def test_random_owner_durable_reopen_exact_retry_and_authority_receipt(tmp_path: Path) -> None:
    path = tmp_path / "economy-random.db"
    store = DurableGameplayEventStore(path)
    owner = EconomyAuthorityService(store=store)
    first = owner.settle_random_business(
        operation_ref="draw:1", kind="lottery", target_ref="character:char_a",
        world_ref="world:main", timeline_ref="timeline:main", source=_source(), policy=_policy(),
        world_tick=5, idempotency_key="random:1", command_id="cmd:random:1",
    )
    assert first.committed
    event = store.get_event(first.committed_event_ids[0])
    assert event.visibility_policy == "authority_only"
    assert event.payload["seed"] and event.payload["result_ref"] and event.payload["receipt_ref"]
    assert owner.lookup_random_business_receipt(idempotency_key="random:1", scope="authority").transaction_id == first.transaction_id
    store.close()

    reopened = DurableGameplayEventStore(path)
    restored = EconomyAuthorityService(store=reopened)
    exact = restored.settle_random_business(
        operation_ref="draw:1", kind="lottery", target_ref="character:char_a",
        world_ref="world:main", timeline_ref="timeline:main", source=_source(), policy=_policy(),
        world_tick=5, idempotency_key="random:1", command_id="cmd:random:1",
    )
    assert exact.committed and exact.idempotency_status == "duplicate_replayed"
    assert len([e for e in reopened.read_events() if e.event_type == "gameplay.economy.random_result_committed@1"]) == 1
    reopened.close()


def test_random_owner_changed_duplicate_and_private_receipt_are_rejected(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "economy-random-negative.db")
    owner = EconomyAuthorityService(store=store)
    assert owner.settle_random_business(
        operation_ref="draw:1", kind="lottery", target_ref="character:char_a",
        world_ref="world:main", timeline_ref="timeline:main", source=_source(), policy=_policy(),
        world_tick=5, idempotency_key="random:1", command_id="cmd:random:1",
    ).committed
    changed = owner.settle_random_business(
        operation_ref="draw:changed", kind="lottery", target_ref="character:char_a",
        world_ref="world:main", timeline_ref="timeline:main", source=_source(), policy=_policy(),
        world_tick=5, idempotency_key="random:1", command_id="cmd:changed",
    )
    assert not changed.committed and changed.failure.error_code == "idempotency_key_reused"
    try:
        owner.lookup_random_business_receipt(idempotency_key="random:1", scope="actor")
    except EconomyRuntimeError as exc:
        assert str(exc) == "economy_random_receipt_scope_denied"
    else:
        raise AssertionError("private random receipt leaked")
    store.close()


def _draw(store, name, target="character:char_a"):
    source = _source().model_copy(update={"actor_scope": ("character:char_a", "character:char_b")})
    return EconomyAuthorityService(store=store).settle_random_business(
        operation_ref=name, kind="lottery", target_ref=target,
        world_ref="world:main", timeline_ref="timeline:main", source=source, policy=_policy(),
        world_tick=5, idempotency_key=f"key:{name}", command_id=f"cmd:{name}",
        effect_ref="effect:lottery", draw_index=0, window_ref="window:5",
    )


def test_anchor_reuse_and_order_independence_without_resampling(monkeypatch) -> None:
    store = GameplayEventStore()
    assert _draw(store, "initial").committed
    snapshot = store.export_snapshot()
    left = GameplayEventStore.from_snapshot(snapshot)
    right = GameplayEventStore.from_snapshot(snapshot)
    def no_entropy(_size):
        raise AssertionError("existing anchor must not resample")
    monkeypatch.setattr("app.gameplay.economy_runtime.secrets.token_bytes", no_entropy)
    a1 = _draw(left, "a")
    assert _draw(left, "b", "character:char_b").committed
    assert _draw(right, "b", "character:char_b").committed
    a2 = _draw(right, "a")
    assert left.get_event(a1.committed_event_ids[0]).payload["seed"] == right.get_event(a2.committed_event_ids[0]).payload["seed"]
    assert len([item for item in left.read_events() if "entropy_anchor" in item.event_type]) == 1


def test_tampered_and_redigested_receipt_rejected_against_transaction() -> None:
    store = GameplayEventStore()
    first = _draw(store, "first")
    event = store.get_event(first.committed_event_ids[0])
    altered = dict(event.payload)
    altered["seed"] = "00" * 32
    altered["result_digest"] = random_payload_digest(altered)
    store._events_by_id[event.event_id] = event.model_copy(update={"payload": altered})
    with pytest.raises(EconomyRuntimeError, match="receipt_invalid"):
        EconomyAuthorityService(store=store).lookup_random_business_receipt(idempotency_key="key:first", scope="authority")


def test_tampered_anchor_rejected_on_next_draw() -> None:
    store = GameplayEventStore()
    assert _draw(store, "first").committed
    anchor = next(event for event in store.read_events() if "entropy_anchor" in event.event_type)
    store._events_by_id[anchor.event_id] = anchor.model_copy(update={"visibility_policy": "project"})
    # Store iteration and point lookup must agree, and projection rejects visibility changes.
    store._events = [store._events_by_id[item.event_id] for item in store._events]
    with pytest.raises(EconomyRuntimeError, match="anchor_invalid"):
        _draw(store, "second")


@pytest.mark.parametrize("fault", ["missing_validation", "result_stream", "result_schema",
                                    "anchor_stream", "anchor_schema"])
def test_random_projection_rejects_unverifiable_committed_events(fault: str) -> None:
    store = GameplayEventStore()
    assert _draw(store, "projector-scope").committed
    events = store.read_events()
    anchor = next(event for event in events if event.event_type.endswith("random_entropy_anchor_created@1"))
    result = next(event for event in events if event.event_type.endswith("random_result_committed@1"))
    if fault == "missing_validation":
        payload = dict(result.payload)
        payload.pop("anchor_ref")
        payload.pop("candidate_policy")
        result = result.model_copy(update={"payload": payload})
    elif fault == "result_stream":
        result = result.model_copy(update={"stream_id": "gameplay:other"})
    elif fault == "result_schema":
        result = result.model_copy(update={"schema_version": 99})
    elif fault == "anchor_stream":
        anchor = anchor.model_copy(update={"stream_id": "gameplay:other"})
    else:
        anchor = anchor.model_copy(update={"schema_version": 99})
    with pytest.raises((EconomyRuntimeError, ValueError), match="economy_random_(result|anchor|payload)_invalid"):
        EconomyProjector().rebuild([anchor, result])


@pytest.mark.parametrize("field", ["algorithm_revision", "seed_policy_revision"])
def test_anchored_replay_rejects_unknown_revisions(field: str) -> None:
    store = GameplayEventStore()
    first = _draw(store, "revision")
    event = store.get_event(first.committed_event_ids[0])
    payload = dict(event.payload)
    payload[field] = "unsupported:revision"
    payload["result_digest"] = random_payload_digest(payload)
    with pytest.raises(ValueError, match="revision_unsupported|context_conflict"):
        validate_anchored_random_payload(payload, anchor_seed=bytes.fromhex(
            store.get_event(next(e.event_id for e in store.read_events() if "entropy_anchor" in e.event_type)).payload["seed"]
        ))
