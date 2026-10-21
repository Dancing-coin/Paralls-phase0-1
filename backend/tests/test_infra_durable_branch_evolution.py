from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    ReferenceDataset,
    _event_digest,
)
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.models import BatchIntentCandidate


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _authority(store: GameplayEventStore, *, branch_ref: str = "branch:evolution", base_event_digest: str = "sha256:empty", base_checkpoint_sequence: int = 0, snapshot_key: str = "snapshot:evolution") -> BranchPreviewAuthority:
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    assert authority.preview(
        request=BranchPreviewRequest(
            branch_ref=branch_ref,
            world_ref="world:bakery",
            base_event_digest=base_event_digest,
            base_checkpoint_sequence=base_checkpoint_sequence,
            tail_boundary=base_checkpoint_sequence,
            deterministic_seed="seed:evolution",
            calibration_ref="calibration:1",
            privacy_scope="creator_debug",
        ),
        dataset=ReferenceDataset(
            dataset_ref="dataset:prices:1",
            provenance="fixture",
            license_ref="license:permitted",
            schema_revision="1",
            digest="sha256:dataset",
            classification="creator_debug",
            allowed_scopes=("creator_debug",),
        ),
        calibration=CalibrationInput(
            calibration_ref="calibration:1",
            dataset_ref="dataset:prices:1",
            parameter_mapping_revision="map:1",
            world_revision="world:1",
            ruleset_revision="rules:1",
            privacy_scope="creator_debug",
        ),
        family_inputs=(),
        candidates=(
            BatchIntentCandidate(
                intent_ref="intent:evolution:one",
                profile_ref="character:char_a",
                intent_kind="supply",
                payload={
                    "organization_ref": "organization:bakery",
                    "counterparty_organization_ref": "organization:supplier",
                    "commitment_ref": "commitment:evolution",
                    "organization_grant_refs": [],
                    "budget_reservation_refs": [],
                },
                expected_revisions={"gameplay:organization:organization:bakery": 0},
                priority=1,
                policy_revision="mode:1",
                package_revision="package:1",
                idempotency_key="intent:evolution:one",
                correlation_id="corr:evolution:one",
                source_ref="planner",
                privacy_scope="actor:self",
            ),
        ),
        mode=WorldModeProfile(
            world_ref="world:bakery",
            mode="replay",
            revision="mode:1",
            cadence_class="daily",
            batch_limit=1,
            wake_budget=1,
            catch_up_limit=1,
            allowed_intent_kinds=("work",),
            degraded_threshold=1,
        ),
    ).accepted
    assert authority.record_isolated_branch_snapshot(
        branch_ref=branch_ref,
        expected_revision=0,
        idempotency_key=snapshot_key,
        privacy_scope="creator_debug",
    ).committed
    return authority


def test_durable_branch_evolution_appends_existing_branch_stream_and_rebuilds() -> None:
    store = GameplayEventStore()
    authority = _authority(store)
    result = authority.record_isolated_branch_evolution(
        branch_ref="branch:evolution",
        intent_ref="intent:evolution:one",
        expected_revision=1,
        idempotency_key="evolution:one",
        privacy_scope="creator_debug",
    )
    rebuilt = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)).durable_branch_projection("branch:evolution")
    assert result.committed
    assert rebuilt["applied_owner_consequence_intent_refs"] == ("intent:evolution:one",)
    assert len(store.read_stream("gameplay:branch_preview:branch:evolution")) == 2
    assert BranchPreviewAuthority(store=store, registry=authority.registry).production_replay().projection_hash == BranchPreviewAuthority(store=store, registry=authority.registry).production_replay(checkpoint_at=0).projection_hash


def test_durable_branch_evolution_rejects_scope_or_missing_step_without_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    before = store.export_snapshot()
    missing = authority.record_isolated_branch_evolution(branch_ref="branch:missing", intent_ref="intent:missing", expected_revision=0, idempotency_key="evolution:missing", privacy_scope="creator_debug")
    private = authority.record_isolated_branch_evolution(branch_ref="branch:missing", intent_ref="intent:missing", expected_revision=0, idempotency_key="evolution:private", privacy_scope="project")
    assert missing.failure is not None and missing.failure.error_code == "branch_evolution_snapshot_missing"
    assert private.failure is not None and private.failure.error_code == "branch_evolution_privacy_denied"
    assert store.export_snapshot() == before


def test_durable_branch_evolution_is_idempotent_and_revisioned() -> None:
    store = GameplayEventStore()
    authority = _authority(store)
    first = authority.record_isolated_branch_evolution(branch_ref="branch:evolution", intent_ref="intent:evolution:one", expected_revision=1, idempotency_key="evolution:idempotent", privacy_scope="creator_debug")
    duplicate = authority.record_isolated_branch_evolution(branch_ref="branch:evolution", intent_ref="intent:evolution:one", expected_revision=1, idempotency_key="evolution:idempotent", privacy_scope="creator_debug")
    before = store.export_snapshot()
    stale = authority.record_isolated_branch_evolution(branch_ref="branch:evolution", intent_ref="intent:evolution:one", expected_revision=1, idempotency_key="evolution:stale", privacy_scope="creator_debug")
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before


def test_durable_branch_evolution_checkpoint_tail_matches_fresh_replay() -> None:
    store = GameplayEventStore()
    authority = _authority(store)
    assert authority.record_isolated_branch_evolution(branch_ref="branch:evolution", intent_ref="intent:evolution:one", expected_revision=1, idempotency_key="evolution:replay", privacy_scope="creator_debug").committed
    fresh = BranchPreviewAuthority(store=store, registry=authority.registry)
    full = fresh.durable_branch_projection("branch:evolution")
    tail = fresh.durable_branch_projection("branch:evolution", checkpoint_at=1)
    assert full["projection_hash"] == tail["projection_hash"]


def test_durable_branch_evolution_rejects_changed_duplicate_without_write() -> None:
    store = GameplayEventStore()
    first_authority = _authority(store)
    assert first_authority.record_isolated_branch_evolution(
        branch_ref="branch:evolution",
        intent_ref="intent:evolution:one",
        expected_revision=1,
        idempotency_key="evolution:changed",
        privacy_scope="creator_debug",
    ).committed
    second_authority = _authority(store, branch_ref="branch:evolution:other", base_event_digest=_event_digest(store.read_events()), base_checkpoint_sequence=len(store.read_events()), snapshot_key="snapshot:evolution:other")
    before = store.export_snapshot()
    changed = second_authority.record_isolated_branch_evolution(
        branch_ref="branch:evolution:other",
        intent_ref="intent:evolution:one",
        expected_revision=1,
        idempotency_key="evolution:changed",
        privacy_scope="creator_debug",
    )
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_branch_evolution_real_durable_reopen_recovers_receipt_and_full_tail(tmp_path: Path) -> None:
    path = tmp_path / "branch-evolution.sqlite3"
    store = DurableGameplayEventStore(path)
    try:
        authority = _authority(store)
        committed = authority.record_isolated_branch_evolution(
            branch_ref="branch:evolution",
            intent_ref="intent:evolution:one",
            expected_revision=1,
            idempotency_key="evolution:durable-reopen",
            privacy_scope="creator_debug",
        )
        assert committed.committed
        before_projection = authority.durable_branch_projection("branch:evolution")
        before_events = store.read_events()
        before_receipt = store.get_by_idempotency(
            authority._PRINCIPAL, "evolution:durable-reopen"
        )
    finally:
        store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        restored = BranchPreviewAuthority(
            store=reopened,
            registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
        )
        assert restored._buffers == {}
        full = restored.durable_branch_projection("branch:evolution")
        tail = restored.durable_branch_projection("branch:evolution", checkpoint_at=1)
        assert full == tail == before_projection
        assert full["applied_owner_consequence_intent_refs"] == ("intent:evolution:one",)
        assert reopened.read_events() == before_events
        assert reopened.get_by_idempotency(
            restored._PRINCIPAL, "evolution:durable-reopen"
        ) == before_receipt

        duplicate = restored.record_isolated_branch_evolution(
            branch_ref="branch:evolution",
            intent_ref="intent:evolution:one",
            expected_revision=1,
            idempotency_key="evolution:durable-reopen",
            privacy_scope="creator_debug",
        )
        assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
        assert duplicate.committed_event_ids == committed.committed_event_ids
        assert reopened.read_events() == before_events
        assert restored.production_replay().projection_hash == restored.production_replay(
            checkpoint_at=0
        ).projection_hash
    finally:
        reopened.close()
