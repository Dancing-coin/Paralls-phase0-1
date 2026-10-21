from __future__ import annotations

from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import AtomicEventBatch, GameplayEvent, IdempotencyRecord
from app.gameplay.prediction_authority import PredictionAuthority, PredictionError
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    ReferenceDataset,
)
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _preview(store: GameplayEventStore, branch_ref: str = "branch:prediction") -> BranchPreviewAuthority:
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    result = authority.preview(
        request=BranchPreviewRequest(
            branch_ref=branch_ref,
            world_ref="world:prediction",
            base_event_digest="sha256:empty",
            base_checkpoint_sequence=0,
            tail_boundary=0,
            deterministic_seed="seed:prediction",
            calibration_ref="calibration:prediction-test",
            privacy_scope="creator_debug",
        ),
        dataset=ReferenceDataset(
            dataset_ref="dataset:prediction-test",
            provenance="test-source",
            license_ref="license:permitted",
            schema_revision="1",
            digest="sha256:prediction-dataset",
            classification="creator_debug",
            allowed_scopes=("creator_debug",),
        ),
        calibration=CalibrationInput(
            calibration_ref="calibration:prediction-test",
            dataset_ref="dataset:prediction-test",
            parameter_mapping_revision="map:prediction-test",
            world_revision="world:prediction-test",
            ruleset_revision="rules:prediction-test",
            privacy_scope="creator_debug",
        ),
        family_inputs=(),
        candidates=(
            BatchIntentCandidate(
                intent_ref="intent:prediction:test",
                profile_ref="character:char_a",
                intent_kind="supply",
                payload={
                    "organization_ref": "organization:bakery",
                    "counterparty_organization_ref": "organization:supplier",
                    "commitment_ref": "commitment:prediction",
                    "organization_grant_refs": [],
                    "budget_reservation_refs": [],
                },
                expected_revisions={"gameplay:organization:organization:bakery": 0},
                priority=1,
                policy_revision="policy:prediction-test@1",
                package_revision="package:prediction-test@1",
                idempotency_key="intent:prediction:test",
                correlation_id="correlation:prediction:test",
                source_ref="planner:test",
                privacy_scope="actor:self",
            ),
        ),
        mode=WorldModeProfile(
            world_ref="world:prediction",
            mode="replay",
            revision="mode:prediction-test@1",
            cadence_class="daily",
            batch_limit=1,
            wake_budget=1,
            catch_up_limit=1,
            allowed_intent_kinds=("supply",),
            degraded_threshold=1,
        ),
    )
    assert result.accepted
    assert authority.record_isolated_branch_snapshot(
        branch_ref=branch_ref,
        expected_revision=0,
        idempotency_key=f"snapshot:{branch_ref}",
        privacy_scope="creator_debug",
    ).committed
    return authority


def test_prediction_surface_remains_isolated_and_promotion_is_explicitly_unsupported() -> None:
    store = GameplayEventStore()
    authority = _preview(store)
    assert authority.production_replay().projection_hash == authority.production_replay(checkpoint_at=0).projection_hash
    promotion = BranchPreviewAuthority.promote("branch:prediction")
    assert not promotion.accepted
    assert promotion.error_code == "branch_promotion_unsupported"
    assert not store.read_events(event_type="gameplay.prediction.confirmed")


def test_prediction_rejects_future_branch_evolution_without_writing() -> None:
    store = GameplayEventStore()
    authority = _preview(store)
    before = store.export_snapshot()
    result = authority.record_isolated_branch_evolution(
        branch_ref="branch:prediction",
        intent_ref="intent:prediction:unknown",
        expected_revision=1,
        idempotency_key="prediction:future-evolution",
        privacy_scope="creator_debug",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "branch_evolution_intent_unsupported"
    assert store.export_snapshot() == before


def test_prediction_durable_reopen_has_no_in_memory_buffer_and_replays_full_tail(tmp_path: Path) -> None:
    path = tmp_path / "prediction-branch.sqlite3"
    store = DurableGameplayEventStore(path)
    try:
        authority = _preview(store)
        first = authority.record_isolated_branch_evolution(
            branch_ref="branch:prediction",
            intent_ref="intent:prediction:test",
            expected_revision=1,
            idempotency_key="prediction:evolution",
            privacy_scope="creator_debug",
        )
        assert first.committed
        expected = authority.durable_branch_projection("branch:prediction")
    finally:
        store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        restored = BranchPreviewAuthority(
            store=reopened,
            registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        )
        assert restored._buffers == {}
        assert restored.durable_branch_projection("branch:prediction") == expected
        assert restored.durable_branch_projection("branch:prediction", checkpoint_at=1) == expected
        duplicate = restored.record_isolated_branch_evolution(
            branch_ref="branch:prediction",
            intent_ref="intent:prediction:test",
            expected_revision=1,
            idempotency_key="prediction:evolution",
            privacy_scope="creator_debug",
        )
        assert duplicate.committed
        assert duplicate.idempotency_status == "duplicate_replayed"
    finally:
        reopened.close()


@pytest.mark.parametrize("privacy_scope", ["project", "authority_only"])
def test_prediction_branch_never_accepts_non_creator_scope(privacy_scope: str) -> None:
    store = GameplayEventStore()
    authority = _preview(store)
    result = authority.record_isolated_branch_snapshot(
        branch_ref="branch:prediction",
        expected_revision=1,
        idempotency_key=f"prediction:scope:{privacy_scope}",
        privacy_scope=privacy_scope,
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "branch_snapshot_privacy_denied"


def _owner_receipt(store: GameplayEventStore, *, key: str = "equip:1"):
    from app.gameplay.equipment_runtime import _digest
    event = GameplayEvent(event_id="owner:e1", event_type="gameplay.equipment.activation_started", schema_version=2,
                          stream_id="gameplay:equipment:actor:1", stream_revision=1, global_sequence=0,
                          transaction_id="owner:tx:1", command_id="equip:1", causation_id="equip:1",
                          correlation_id="equip:1", visibility_policy="actor:self", payload={"actor_ref": "actor:1"})
    return store.append_batch(AtomicEventBatch(transaction_id="owner:tx:1", command_id="equip:1",
        expected_stream_revisions={event.stream_id: 0}, events=[event],
        idempotency_record=IdempotencyRecord(principal_ref="actor_gameplay.equipment_domain", idempotency_key=key, payload_digest="sha256:owner"),
        result_digest=_digest([event.model_copy(update={"stream_revision": 0, "global_sequence": 0}).model_dump()])))


def test_prediction_requires_real_owner_receipt_and_confirms() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    opened = authority.open(prediction_id="pred:1", command_id="equip:1", actor_ref="actor:1", operation="equipment_overlay", idempotency_key="pred:open")
    assert opened.committed
    missing = authority.confirm(prediction_id="pred:1", idempotency_key="pred:confirm:missing", owner_principal="actor_gameplay.equipment_domain", owner_idempotency_key="equip:missing")
    assert not missing.committed and missing.failure.error_code == "prediction_owner_receipt_missing"
    owner = _owner_receipt(store)
    confirmed = authority.confirm(prediction_id="pred:1", idempotency_key="pred:confirm", owner_principal="actor_gameplay.equipment_domain", owner_idempotency_key="equip:1")
    assert confirmed.committed
    state = authority.state("pred:1")
    assert state.status == "confirmed" and state.owner_transaction_id == owner.transaction_id
    with pytest.raises(PredictionError, match="prediction_terminal"):
        authority.revoke(prediction_id="pred:1", idempotency_key="pred:revoke", reason="late")


def test_prediction_changed_duplicate_rejected_and_durable_reopen_replays(tmp_path: Path) -> None:
    path = tmp_path / "prediction-ledger.sqlite3"
    store = DurableGameplayEventStore(path); authority = PredictionAuthority(store=store)
    try:
        first = authority.open(prediction_id="pred:2", command_id="equip:2", actor_ref="actor:2", operation="equipment_overlay", idempotency_key="pred:open")
        assert first.committed
        duplicate = authority.open(prediction_id="pred:2", command_id="equip:2", actor_ref="actor:2", operation="equipment_overlay", idempotency_key="pred:open")
        assert duplicate.idempotency_status == "duplicate_replayed"
        changed = authority.open(prediction_id="pred:2", command_id="equip:2", actor_ref="actor:2", operation="different_overlay", idempotency_key="pred:open")
        assert not changed.committed
        assert changed.failure is not None
    finally:
        store.close()
    reopened = DurableGameplayEventStore(path); restored = PredictionAuthority(store=reopened)
    try:
        assert restored.state("pred:2").status == "pending"
        assert restored.replay("pred:2").status == restored.replay("pred:2", checkpoint_at=1).status == "pending"
    finally:
        reopened.close()


def test_prediction_terminal_exact_retry_and_cross_operation_key_reuse() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    assert authority.open(prediction_id="pred:retry", command_id="cmd:retry", actor_ref="actor:retry", operation="equipment_overlay", idempotency_key="open").committed
    first = authority.revoke(prediction_id="pred:retry", idempotency_key="terminal", reason="stale")
    assert first.committed
    retry = authority.revoke(prediction_id="pred:retry", idempotency_key="terminal", reason="stale")
    assert retry.idempotency_status == "duplicate_replayed"
    changed = authority.expire(prediction_id="pred:retry", idempotency_key="terminal", reason="timeout")
    assert not changed.committed and changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"


def test_prediction_replay_applies_all_tail_events() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    assert authority.open(prediction_id="pred:tail", command_id="cmd:tail", actor_ref="actor:tail", operation="equipment_overlay", idempotency_key="open").committed
    # A malformed second terminal is deliberately rejected by the state reducer;
    # valid lifecycle streams contain one terminal, and the prefix+tail path reads
    # every tail event rather than only tail[0].
    assert authority.revoke(prediction_id="pred:tail", idempotency_key="terminal", reason="stale").committed
    assert authority.replay("pred:tail", checkpoint_at=1).status == "revoked"


def test_prediction_reject_exact_retry_before_terminal_state_check() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    assert authority.open(prediction_id="pred:reject-retry", command_id="cmd", actor_ref="actor", operation="equipment_overlay", idempotency_key="open").committed
    first = authority.reject(prediction_id="pred:reject-retry", idempotency_key="reject", reason="owner_rejected")
    assert first.committed
    retry = authority.reject(prediction_id="pred:reject-retry", idempotency_key="reject", reason="owner_rejected")
    assert retry.idempotency_status == "duplicate_replayed"


def test_prediction_multiple_terminal_stream_fails_closed() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    assert authority.open(prediction_id="pred:corrupt", command_id="cmd", actor_ref="actor", operation="equipment_overlay", idempotency_key="open").committed
    first = authority.revoke(prediction_id="pred:corrupt", idempotency_key="revoke", reason="stale")
    assert first.committed
    # Simulate a corrupted imported stream; the reducer must not silently choose
    # the first terminal event.
    authority._append(prediction_id="pred:corrupt", command_id="cmd:bad", idempotency_key="bad", stream=authority._stream("pred:corrupt"),
                      event_type="gameplay.prediction.expired", payload={"prediction_id": "pred:corrupt", "reason": "bad"}, expected_revision=2)
    with pytest.raises(PredictionError, match="prediction_multiple_terminal_events"):
        authority.state("pred:corrupt")


def test_prediction_confirm_key_cannot_cross_prediction() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    for ref in ("pred:a", "pred:b"):
        assert authority.open(prediction_id=ref, command_id="equip:1", actor_ref="actor:1", operation="equipment_overlay", idempotency_key=f"{ref}:open").committed
    _owner_receipt(store, key="owner:confirm")
    assert authority.confirm(prediction_id="pred:a", idempotency_key="confirm", owner_principal="actor_gameplay.equipment_domain", owner_idempotency_key="owner:confirm").committed
    retry = authority.confirm(prediction_id="pred:b", idempotency_key="confirm", owner_principal="actor_gameplay.equipment_domain", owner_idempotency_key="owner:confirm")
    assert not retry.committed and retry.failure is not None and retry.failure.error_code == "idempotency_key_reused"


def test_equipment_prediction_requires_canonical_equipment_owner_principal() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    assert authority.open(
        prediction_id="pred:owner-principal", command_id="equip:owner-principal",
        actor_ref="actor:1", operation="equipment_overlay", idempotency_key="open",
    ).committed
    event = GameplayEvent(
        event_id="owner:wrong:e1", event_type="gameplay.equipment.activation_started", schema_version=2,
        stream_id="gameplay:equipment:actor:1", stream_revision=1, global_sequence=0,
        transaction_id="owner:wrong:tx", command_id="equip:owner-principal", causation_id="equip:owner-principal",
        correlation_id="equip:owner-principal", visibility_policy="actor:self", payload={"actor_ref": "actor:1"},
    )
    store.append_batch(AtomicEventBatch(
        transaction_id="owner:wrong:tx", command_id="equip:owner-principal",
        expected_stream_revisions={event.stream_id: 0}, events=[event],
        idempotency_record=IdempotencyRecord(
            principal_ref="synthetic.equipment", idempotency_key="owner:wrong",
            payload_digest="sha256:owner",
        ), result_digest="sha256:owner-result",
    ))
    result = authority.confirm(
        prediction_id="pred:owner-principal", idempotency_key="confirm",
        owner_principal="synthetic.equipment", owner_idempotency_key="owner:wrong",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "prediction_owner_principal_invalid"
    assert authority.state("pred:owner-principal").status == "pending"


def test_prediction_open_different_key_is_identity_conflict() -> None:
    store = GameplayEventStore(); authority = PredictionAuthority(store=store)
    assert authority.open(prediction_id="pred:open", command_id="cmd", actor_ref="actor", operation="equipment_overlay", idempotency_key="first").committed
    duplicate = authority.open(prediction_id="pred:open", command_id="cmd", actor_ref="actor", operation="equipment_overlay", idempotency_key="second")
    assert not duplicate.committed and duplicate.failure is not None and duplicate.failure.error_code == "prediction_already_open"
