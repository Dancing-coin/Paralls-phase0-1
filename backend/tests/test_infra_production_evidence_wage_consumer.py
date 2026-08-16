from __future__ import annotations

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay import econ1_economy_runtime
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import WorkerContributionRef
from app.gameplay.replay import GameplayProjectionReplay
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile
from app.population_continuity.source_inputs import ProductionCompletedEvidenceInput


def _contribution() -> WorkerContributionRef:
    return WorkerContributionRef(actor_ref="character:char_b", assignment_ref="assignment:baker", work_order_ref="work:bread", evidence_refs=("evidence:input:bread:1",), contribution_digest="sha256:contribution:bread:1")


def _source() -> tuple[GameplayEventStore, ConstructionProductionAuthority, ProductionCompletedEvidenceInput]:
    store = GameplayEventStore(); authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="oven", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={}, output_item="item:bread", duration_ticks=2)
    assert authority.settle_facility_acquisition(plot=Plot(plot_ref="plot:bakery", jurisdiction_ref="jurisdiction:bakery", owner_ref="org:bakery"), facility=facility, command_id="facility:acquire", idempotency_key="facility:acquire", causation_id="cause", correlation_id="corr").committed
    assert authority.settle_start_run(facility=facility, recipe=recipe, run_ref="run:bread:1", tick=1, command_id="run:start", idempotency_key="run:start", causation_id="cause", correlation_id="corr", worker_contribution_refs=(_contribution(),)).committed
    assert authority.settle_finish_run(authority.projector().runs["run:bread:1"], tick=3, recipe=recipe, command_id="run:finish", idempotency_key="run:finish", causation_id="cause", correlation_id="corr").committed
    evidence_ref = "evidence:production-completed:run:bread:1:sha256:contribution:bread:1"
    assert authority.record_completed_work_evidence(run_ref="run:bread:1", contribution=_contribution(), evidence_ref=evidence_ref, observed_at="2026-08-13T00:00:00Z", command_id="evidence:1", idempotency_key="evidence:1", causation_id="cause", correlation_id="corr").committed
    return store, authority, ProductionCompletedEvidenceInput.freeze(recipient_ref="character:char_b", observed_at="2026-08-13T00:01:00Z", view=authority.completed_evidence_view_for(recipient_ref="character:char_b"))


def _mode() -> WorldModeProfile:
    return WorldModeProfile(world_ref="world:bakery", mode="simulation", revision="policy:1", cadence_class="daily", batch_limit=1, wake_budget=1, catch_up_limit=1, allowed_intent_kinds=("work",), degraded_threshold=1, allowed_privacy_scopes=("actor:self",))


def _candidate(**overrides: object) -> BatchIntentCandidate:
    values: dict[str, object] = {"intent_ref": "intent:wage:1", "profile_ref": "character:char_b", "intent_kind": "work", "payload": {"organization_ref": "org:bakery", "wage_obligation_ref": "wage:bread:1", "wage_amount_minor": 75, "wage_policy_revision": "policy:wage:1"}, "expected_revisions": {}, "policy_revision": "policy:1", "package_revision": "package:1", "idempotency_key": "intent:wage:1", "correlation_id": "corr", "source_ref": "production", "privacy_scope": "actor:self"}
    values.update(overrides)
    return BatchIntentCandidate(**values)


def _plan(store: GameplayEventStore, source: ProductionCompletedEvidenceInput, **candidate_overrides: object):
    wage_stream = "gameplay:economy:wage:character:char_b"
    expected_revisions = candidate_overrides.pop("expected_revisions", {wage_stream: store.get_stream_head(wage_stream)})
    candidate = _candidate(expected_revisions=expected_revisions, **candidate_overrides)
    return PopulationPlanner().plan_production_evidence_wage(store=store, batch_ref="batch:wage:1", world_ref="world:bakery", mode=_mode(), production_evidence_input=source, candidate=candidate, base_event_digest="sha256:base", tail_boundary=len(store.read_events()), active_revision_refs=("policy:wage:1",), deterministic_seed="seed", report_scope="actor:self")


def test_inf4z_wage_consumer_freezes_matching_worker_scoped_production_source() -> None:
    store, _, source = _source(); planned = _plan(store, source)
    assert planned.accepted is True
    assert planned.plan.production_evidence_input_digest == source.input_digest
    assert planned.plan.production_evidence_refs == source.evidence_refs


def test_inf4z_wage_consumer_commits_economy_owner_envelope_fragment_with_source_pins() -> None:
    store, _, source = _source(); planned = _plan(store, source)
    receipt = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode()).merge_production_evidence_wage(planned.plan)
    assert receipt.committed and receipt.owner_receipt_ref == EconomyAuthority._PRINCIPAL
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.economy.wage_accrued"
    assert event.visibility_policy == "actor:character:char_b"
    assert event.payload["production_evidence_projection_digest"] == source.projection_digest
    assert event.payload["production_evidence_source_event_refs"] == source.source_event_refs
    batch = store.read_transactions()[-1]
    assert batch.pinned_revisions["wage_policy:policy:wage:1"] == 1
    assert batch.read_stream_revisions == source.source_revision_vector
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "actor:character:char_b"
    assert outbox.payload_projection == {
        "accrual_ref": "wage:bread:1",
        "evidence_ref": source.evidence_refs[0],
    }


def test_inf4z_wage_consumer_uses_economy_envelope_and_settlement_plan(monkeypatch) -> None:
    store, _, source = _source(); planned = _plan(store, source)
    seen: list[object] = []
    original = econ1_economy_runtime.SettlementPlan.from_command_envelope

    def observe(command):
        seen.append(command)
        return original(command)

    monkeypatch.setattr(econ1_economy_runtime.SettlementPlan, "from_command_envelope", observe)
    receipt = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode()).merge_production_evidence_wage(planned.plan)

    assert receipt.committed
    assert len(seen) == 1
    command = seen[0]
    assert command.principal_ref == EconomyAuthority._PRINCIPAL
    assert command.actor_ref == "character:char_b"
    assert command.expected_revisions == {"gameplay:economy:wage:character:char_b": 0}
    assert command.read_set_revisions == source.source_revision_vector


def test_inf4z_wage_consumer_rejects_forged_source_without_write() -> None:
    store, _, source = _source(); forged = source.model_copy(update={"projection_digest": "sha256:forged"})
    result = _plan(store, forged)
    assert result.accepted is False
    assert result.error_code == "source_projection_digest_mismatch"
    assert len(store.read_events()) == 4


def test_inf4z_wage_consumer_rejects_stale_source_without_write() -> None:
    store, authority, source = _source()
    assert authority.settle_maintenance_obligation(authority.projector().runs["run:bread:1"], obligation_ref="obligation:maintenance:1", command_id="maintenance:1", idempotency_key="maintenance:1", causation_id="cause", correlation_id="corr").committed
    result = _plan(store, source)
    assert result.accepted is False
    assert result.error_code == "source_revision_stale"
    assert len(store.read_events()) == 5


def test_inf4z_wage_consumer_rejects_forged_evidence_rows_without_write() -> None:
    store, _, source = _source()
    forged = source.model_copy(update={"evidence_rows": ({"evidence_ref": source.evidence_refs[0], "actor_ref": "character:other"},)})

    result = _plan(store, forged)

    assert result.accepted is False
    assert result.error_code == "source_projection_digest_mismatch"
    assert len(store.read_events()) == 4


def test_inf4z_wage_consumer_rejects_privacy_mismatch_without_write() -> None:
    store, _, source = _source()

    result = _plan(store, source, privacy_scope="public")

    assert result.accepted is False
    assert result.error_code == "production_wage_privacy_denied"
    assert len(store.read_events()) == 4


def test_inf4z_wage_consumer_rejects_stale_wage_revision_without_write() -> None:
    store, _, source = _source()

    result = _plan(store, source, expected_revisions={"gameplay:economy:wage:character:char_b": 1})

    assert result.accepted is False
    assert result.error_code == "production_wage_revision_conflict"
    assert len(store.read_events()) == 4


def test_inf4z_wage_consumer_duplicate_and_replay_are_owner_scoped() -> None:
    store, _, source = _source(); planned = _plan(store, source)
    merge = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode())
    first = merge.merge_production_evidence_wage(planned.plan); duplicate = merge.merge_production_evidence_wage(planned.plan)
    events = store.read_events(); replay = GameplayProjectionReplay(projector_id="production-wage", projector_version="1")
    assert first.committed and duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(replay.create_checkpoint(events[:4]), events[4:]).projection_hash


def test_inf4z_wage_consumer_changed_duplicate_is_zero_write() -> None:
    store, _, source = _source(); planned = _plan(store, source)
    merge = ContinuityMergeAuthority(store=store, registry=CharacterProfileRegistry(profiles_by_actor_id={}), mode=_mode())
    assert merge.merge_production_evidence_wage(planned.plan).committed
    changed = planned.plan.model_copy(
        update={"candidates": (_candidate(payload={"organization_ref": "org:bakery", "wage_obligation_ref": "wage:bread:1", "wage_amount_minor": 100, "wage_policy_revision": "policy:wage:1"}, expected_revisions={"gameplay:economy:wage:character:char_b": 0}),)},
        deep=True,
    )

    result = merge.merge_production_evidence_wage(changed)

    assert result.committed is False
    assert result.stop_reason == "idempotency_key_reused"
    assert len(store.read_events()) == 5
