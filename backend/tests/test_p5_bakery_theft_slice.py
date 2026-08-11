from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayFailure, ProjectionCheckpoint, ReplayResult
from app.gameplay.survival_runtime import SurvivalMode
from backend.tests.test_p5_investigation_conflict import (
    ALARM_STREAM,
    CONFLICT_STREAM,
    INVESTIGATION_STREAM,
    KNOWLEDGE_STREAM,
    RELATIONSHIP_REF,
    STATUS_STREAM,
    _command as _conflict_command,
    _registry as _conflict_registry,
    _request as _conflict_request,
    _status_fragment,
)
from backend.tests.test_p5_quest_evidence import (
    _command as _quest_command,
    _default_evidence_ref,
    _evidence_stream_ref,
    _quest_stream_ref,
    _registry as _quest_registry,
    _request as _quest_request,
)
from backend.tests.test_p5_social_knowledge import (
    _knowledge_payload,
    _knowledge_stream_ref,
    _record_command as _social_command,
    _registry as _social_registry,
    _relationship_payload,
    _request as _social_request,
)


def _load_slice() -> object:
    try:
        from app.gameplay.p5.bakery_theft_slice import BakeryTheftInvestigationSlice
    except Exception as exc:  # pragma: no cover - explicit RED guard
        pytest.fail(f"production break: bakery theft slice module missing: {exc}")
    return BakeryTheftInvestigationSlice


@pytest.fixture
def social_registry():
    return _social_registry()


@pytest.fixture
def quest_registry():
    return _quest_registry()


@pytest.fixture
def conflict_registry():
    return _conflict_registry()


@pytest.fixture
def store() -> GameplayEventStore:
    return GameplayEventStore()


@pytest.fixture
def slice_authority(
    social_registry,
    quest_registry,
    conflict_registry,
    store: GameplayEventStore,
):
    return _load_slice()(
        social_registry=social_registry,
        quest_registry=quest_registry,
        conflict_registry=conflict_registry,
        store=store,
    )


def _success_bundle(*, request_id: str = "request:p5d:1") -> dict[str, object]:
    relationship_fact = _relationship_payload(
        target_ref="character:thief:beta",
        evidence_ref=f"evidence:{request_id}:relation",
        provenance_source_ref=f"source:{request_id}:relation",
    )
    knowledge_fact = _knowledge_payload(
        fact_ref="fact:clue:bread-knife",
        knower_ref="character:investigator:alpha",
        subject_ref="character:thief:beta",
        visibility="actor:character:investigator:alpha",
        evidence_ref=f"evidence:{request_id}:clue",
        provenance_source_ref=f"source:{request_id}:clue",
        observation_ref="observation:skill:street-stealth",
    )
    social_revisions = {
        str(relationship_fact["relationship_ref"]): 0,
        _knowledge_stream_ref(
            knower_ref=str(knowledge_fact["knower_ref"]),
            fact_ref=str(knowledge_fact["fact_ref"]),
        ): 0,
    }
    return {
        "relationship_fact": relationship_fact,
        "knowledge_fact": knowledge_fact,
        "social_command": _social_command(
            request_id=request_id,
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=social_revisions,
            read_revisions=social_revisions,
        ),
        "social_request": _social_request(
            _social_registry(),
            request_id=request_id,
            relationship_fact=relationship_fact,
            knowledge_fact=knowledge_fact,
            expected_revisions=social_revisions,
            read_revisions=social_revisions,
        ),
        "quest_command": _quest_command(
            request_id=request_id,
            evidence_ref=_default_evidence_ref(request_id),
            payload_updates={"satisfied_prerequisite_fact_refs": ("fact:case:open",)},
        ),
        "quest_request": _quest_request(
            _quest_registry(),
            request_id=request_id,
            evidence_ref=_default_evidence_ref(request_id),
        ),
        "conflict_command": _conflict_command(request_id=request_id),
        "conflict_request": _conflict_request(_conflict_registry(), request_id=request_id),
    }


def test_import_guard_loads_bakery_theft_investigation_slice() -> None:
    slice_type = _load_slice()
    assert slice_type.__name__ == "BakeryTheftInvestigationSlice"


def test_success_commits_private_clue_public_relation_skill_observation_and_quest_transition(
    slice_authority,
    store: GameplayEventStore,
) -> None:
    bundle = _success_bundle()

    result = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    assert result.social_result.resolution.result_kind == "committed_success"
    assert result.quest_result.resolution.result_kind == "committed_success"
    assert result.conflict_result.resolution.result_kind == "committed_success"
    assert result.social_result.receipt is not None and result.social_result.receipt.committed
    assert result.quest_result.receipt is not None and result.quest_result.receipt.committed
    assert result.conflict_result.receipt is not None and result.conflict_result.receipt.committed
    assert result.survival_mode == SurvivalMode.DISABLED

    events = store.read_events()
    assert [event.event_type for event in events] == [
        "gameplay.social.relationship_fact_recorded",
        "gameplay.social.knowledge_observed",
        "gameplay.quest.evidence_registered",
        "gameplay.quest.objective_transitioned",
        "gameplay.investigation.observation_resolved",
        "gameplay.conflict.attempt_resolved",
    ]
    assert events[0].visibility_policy == "public"
    assert events[1].visibility_policy == "actor:character:investigator:alpha"
    assert events[1].payload["observation_ref"] == "observation:skill:street-stealth"
    assert events[3].payload["transition_ref"] == "transition:quest:evidence_registered"


def test_hidden_clue_rejects_with_structured_zero_write_and_keeps_store_empty(
    slice_authority,
    store: GameplayEventStore,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:hidden")
    invalid_knowledge_fact = dict(bundle["knowledge_fact"])
    invalid_knowledge_fact["visibility"] = "public"
    social_revisions = {
        str(bundle["relationship_fact"]["relationship_ref"]): 0,
        _knowledge_stream_ref(
            knower_ref=str(invalid_knowledge_fact["knower_ref"]),
            fact_ref=str(invalid_knowledge_fact["fact_ref"]),
        ): 0,
    }

    result = slice_authority.resolve(
        social_command=_social_command(
            request_id="request:p5d:hidden",
            relationship_fact=bundle["relationship_fact"],
            knowledge_fact=invalid_knowledge_fact,
            expected_revisions=social_revisions,
            read_revisions=social_revisions,
        ),
        social_request=_social_request(
            _social_registry(),
            request_id="request:p5d:hidden",
            relationship_fact=bundle["relationship_fact"],
            knowledge_fact=invalid_knowledge_fact,
            expected_revisions=social_revisions,
            read_revisions=social_revisions,
        ),
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_hidden_clue_visibility_invalid"
    assert result.social_result.receipt is None
    assert result.quest_result.receipt is None
    assert result.conflict_result.receipt is None
    assert store.read_events() == []


def test_stealth_alarm_commits_adverse_outcome_and_registered_nonlethal_alerted_consequence(
    slice_authority,
    store: GameplayEventStore,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:alarm")

    result = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=_conflict_command(
            request_id="request:p5d:alarm",
            resistance_ref="resistance:guard-alert",
            alarm_ref="alarm:bakery",
            status_revision_ref="status:alerted",
        ),
        conflict_request=_conflict_request(
            _conflict_registry(),
            request_id="request:p5d:alarm",
            resistance_ref="resistance:guard-alert",
            alarm_ref="alarm:bakery",
            status_revision_ref="status:alerted",
        ),
        owner_fragments=(_status_fragment(),),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    assert result.conflict_result.resolution.result_kind == "committed_adverse_outcome"
    assert result.conflict_result.receipt is not None and result.conflict_result.receipt.committed
    assert "gameplay.conflict.alarm_raised" in [event.event_type for event in store.read_events()]
    assert "gameplay.status_tag.applied" in [event.event_type for event in store.read_events()]
    authority_view = slice_authority.view_for(recipient_ref="authority:auditor", now="2026-08-11T00:00:00Z")
    assert any(
        consequence["payload"].get("status_tag_ref") == "status:alerted"
        for consequence in authority_view["conflict"]["consequences"]
    )


def test_public_private_view_split_keeps_hidden_clue_and_private_knowledge_out_of_public_view(
    slice_authority,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:view")
    slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    public_view = slice_authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
    private_view = slice_authority.view_for(recipient_ref="character:investigator:alpha", now="2026-08-11T00:00:00Z")

    assert public_view["social"]["knowledge_facts"] == ()
    assert "hidden_clue_ref" not in public_view["conflict"]["investigations"][0]
    assert private_view["social"]["knowledge_facts"][0]["fact_ref"] == "fact:clue:bread-knife"
    assert private_view["conflict"]["investigations"][0]["hidden_clue_ref"] == "fact:clue:bread-knife"
    assert public_view["projection_hash"] != private_view["projection_hash"]


def test_authority_only_quest_view_is_hidden_from_non_authority_recipients_and_visible_to_authority(
    slice_authority,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:quest-view")
    slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    public_view = slice_authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
    participant_view = slice_authority.view_for(
        recipient_ref="character:investigator:alpha",
        now="2026-08-11T00:00:00Z",
    )
    authority_view = slice_authority.view_for(recipient_ref="authority:auditor", now="2026-08-11T00:00:00Z")

    assert public_view["quest"]["evidence_events"] == ()
    assert public_view["quest"]["objective_events"] == ()
    assert participant_view["quest"]["evidence_events"] == ()
    assert participant_view["quest"]["objective_events"] == ()
    assert [event["event_type"] for event in authority_view["quest"]["evidence_events"]] == [
        "gameplay.quest.evidence_registered",
    ]
    assert [event["event_type"] for event in authority_view["quest"]["objective_events"]] == [
        "gameplay.quest.objective_transitioned",
    ]


def test_conflict_append_preserves_settlement_produced_event_order_and_sequences_in_store(
    slice_authority,
    store: GameplayEventStore,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:order")

    result = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=_conflict_command(
            request_id="request:p5d:order",
            resistance_ref="resistance:guard-alert",
            alarm_ref="alarm:bakery",
            status_revision_ref="status:alerted",
        ),
        conflict_request=_conflict_request(
            _conflict_registry(),
            request_id="request:p5d:order",
            resistance_ref="resistance:guard-alert",
            alarm_ref="alarm:bakery",
            status_revision_ref="status:alerted",
        ),
        owner_fragments=(_status_fragment(),),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    assert result.conflict_result.receipt is not None and result.conflict_result.receipt.committed
    conflict_event_ids = list(result.conflict_result.receipt.committed_event_ids)
    expected_conflict_sequences = list(
        range(
            len(result.social_result.receipt.committed_event_ids) + len(result.quest_result.receipt.committed_event_ids) + 1,
            len(result.social_result.receipt.committed_event_ids)
            + len(result.quest_result.receipt.committed_event_ids)
            + len(conflict_event_ids)
            + 1,
        )
    )

    assert [
        (event.event_id, event.global_sequence)
        for event in store.read_transactions()[-1].events
    ] == list(zip(conflict_event_ids, expected_conflict_sequences, strict=False))
    assert [
        (event.event_id, event.global_sequence)
        for event in store.read_events()[-len(conflict_event_ids):]
    ] == list(zip(conflict_event_ids, expected_conflict_sequences, strict=False))


def test_duplicate_recovery_replays_prior_component_receipts_without_appending(
    slice_authority,
    store: GameplayEventStore,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:duplicate")
    first = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )
    before = len(store.read_transactions())

    duplicate = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    assert first.social_result.receipt is not None and first.social_result.receipt.committed
    assert duplicate.social_result.receipt is not None
    assert duplicate.social_result.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.quest_result.receipt is not None
    assert duplicate.quest_result.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.conflict_result.receipt is not None
    assert duplicate.conflict_result.receipt.idempotency_status == "duplicate_replayed"
    assert len(store.read_transactions()) == before


def test_late_conflict_append_failure_rolls_back_social_and_quest_writes(
    slice_authority,
    store: GameplayEventStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:late-failure")
    store.set_write_readiness(False)
    original_append = store.append_batch
    append_count = 0

    def fail_conflict_append(batch):
        nonlocal append_count
        append_count += 1
        if append_count == 3:
            store.set_write_readiness(False)
            return AppendBatchResult(
                committed=False,
                transaction_id=batch.transaction_id,
                command_id=batch.command_id,
                idempotency_status="rejected",
                failure=GameplayFailure(
                    error_code="simulated_conflict_append_failure",
                    message="conflict authority failed after earlier component commits",
                    failed_stage="append_batch",
                ),
            )
        store.set_write_readiness(True)
        return original_append(batch)

    monkeypatch.setattr(store, "append_batch", fail_conflict_append)
    result = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )

    assert append_count == 3
    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "simulated_conflict_append_failure"
    assert store.read_events() == []
    assert store.read_transactions() == []
    assert store.write_ready is False


def test_full_and_checkpoint_tail_replay_match_after_followup_commit(
    slice_authority,
) -> None:
    first = _success_bundle(request_id="request:p5d:replay:1")
    committed = slice_authority.resolve(
        social_command=first["social_command"],
        social_request=first["social_request"],
        quest_command=first["quest_command"],
        quest_request=first["quest_request"],
        conflict_command=first["conflict_command"],
        conflict_request=first["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )
    assert committed.conflict_result.receipt is not None and committed.conflict_result.receipt.committed

    prefix = slice_authority.replay_full(now="2026-08-11T00:00:00Z")
    checkpoint = ProjectionCheckpoint(
        checkpoint_id="checkpoint:p5d:1",
        projector_id="projector:p5:bakery-theft-slice",
        projector_version="v1",
        projection_schema_version=1,
        source_revision_vector=prefix.source_revision_vector,
        last_global_sequence=prefix.last_global_sequence,
        state=prefix.state,
        applied_event_ids=list(prefix.applied_event_ids),
        projection_hash=prefix.projection_hash,
        registry_revision="registry:p5d:bakery-theft:v1",
        active_patch_set_revision="patch:p5d:v1",
        world_config_revision="world:p5d:v1",
    )

    second_knowledge = _knowledge_payload(
        fact_ref="fact:clue:flour-trail",
        knower_ref="character:investigator:alpha",
        subject_ref="character:thief:beta",
        visibility="actor:character:investigator:alpha",
        evidence_ref="evidence:request:p5d:replay:2:clue",
        provenance_source_ref="source:request:p5d:replay:2:clue",
        observation_ref="observation:checkpoint-tail",
    )
    second_social_revisions = {
        _knowledge_stream_ref(
            knower_ref=str(second_knowledge["knower_ref"]),
            fact_ref=str(second_knowledge["fact_ref"]),
        ): 0,
    }
    second_conflict_revisions = {
        INVESTIGATION_STREAM: 1,
        CONFLICT_STREAM: 1,
        ALARM_STREAM: 0,
        STATUS_STREAM: 0,
    }
    second_read_set = {
        INVESTIGATION_STREAM: 1,
        CONFLICT_STREAM: 1,
        ALARM_STREAM: 0,
        STATUS_STREAM: 0,
        RELATIONSHIP_REF: 0,
        KNOWLEDGE_STREAM: 0,
    }

    second = slice_authority.resolve(
        social_command=_social_command(
            request_id="request:p5d:replay:2",
            relationship_fact=None,
            knowledge_fact=second_knowledge,
            expected_revisions=second_social_revisions,
            read_revisions=second_social_revisions,
        ),
        social_request=_social_request(
            _social_registry(),
            request_id="request:p5d:replay:2",
            relationship_ref=str(first["relationship_fact"]["relationship_ref"]),
            knowledge_fact=second_knowledge,
            expected_revisions=second_social_revisions,
            read_revisions=second_social_revisions,
        ),
        quest_command=_quest_command(
            request_id="request:p5d:replay:2",
            evidence_ref=_default_evidence_ref("request:p5d:replay:2"),
            quest_instance_ref="quest-instance-2",
            payload_updates={"satisfied_prerequisite_fact_refs": ("fact:case:open",)},
        ),
        quest_request=_quest_request(
            _quest_registry(),
            request_id="request:p5d:replay:2",
            evidence_ref=_default_evidence_ref("request:p5d:replay:2"),
            quest_instance_ref="quest-instance-2",
        ),
        conflict_command=_conflict_command(request_id="request:p5d:replay:2").model_copy(
            update={
                "expected_revisions": second_conflict_revisions,
                "read_set_revisions": second_read_set,
            },
            deep=True,
        ),
        conflict_request=_conflict_request(_conflict_registry(), request_id="request:p5d:replay:2").model_copy(
            update={
                "expected_revisions": {"entries": second_conflict_revisions},
                "read_set_revisions": {"entries": second_read_set},
            },
            deep=True,
        ),
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T01:00:00Z",
    )
    assert second.conflict_result.receipt is not None and second.conflict_result.receipt.committed

    full = slice_authority.replay_full(now="2026-08-11T01:00:00Z")
    tail = slice_authority.replay_checkpoint_tail(checkpoint=checkpoint, now="2026-08-11T01:00:00Z")

    assert isinstance(full, ReplayResult)
    assert isinstance(tail, ReplayResult)
    assert tail.succeeded is True
    assert tail.state == full.state
    assert tail.projection_hash == full.projection_hash

    corrupted = checkpoint.model_copy(update={"applied_event_ids": ["event:tampered"]}, deep=True)
    corrupted_tail = slice_authority.replay_checkpoint_tail(checkpoint=corrupted, now="2026-08-11T01:00:00Z")

    assert corrupted_tail.succeeded is False
    assert corrupted_tail.failure is not None
    assert corrupted_tail.failure.error_code == "p5_checkpoint_incompatible"


def test_survival_disabled_and_narrative_modes_are_write_equivalent_and_reversible(
    social_registry,
    quest_registry,
    conflict_registry,
) -> None:
    slice_type = _load_slice()
    disabled_store = GameplayEventStore()
    narrative_store = GameplayEventStore()
    disabled = slice_type(
        social_registry=social_registry,
        quest_registry=quest_registry,
        conflict_registry=conflict_registry,
        store=disabled_store,
    )
    narrative = slice_type(
        social_registry=social_registry,
        quest_registry=quest_registry,
        conflict_registry=conflict_registry,
        store=narrative_store,
    )
    bundle = _success_bundle(request_id="request:p5d:survival")

    disabled_result = disabled.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.DISABLED,
        now="2026-08-11T00:00:00Z",
    )
    narrative_result = narrative.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.NARRATIVE,
        now="2026-08-11T00:00:00Z",
    )

    assert disabled_result.survival_mode == SurvivalMode.DISABLED
    assert narrative_result.survival_mode == SurvivalMode.NARRATIVE
    assert [event.event_type for event in disabled_store.read_events()] == [event.event_type for event in narrative_store.read_events()]
    assert disabled.replay_full(now="2026-08-11T00:00:00Z").state == narrative.replay_full(now="2026-08-11T00:00:00Z").state
    assert _evidence_stream_ref(_default_evidence_ref("request:p5d:survival")) in disabled.replay_full(now="2026-08-11T00:00:00Z").source_revision_vector
    assert _quest_stream_ref("quest-instance-1") in narrative.replay_full(now="2026-08-11T00:00:00Z").source_revision_vector


def test_unsupported_survival_mode_returns_typed_zero_write_and_leaves_store_empty(
    slice_authority,
    store: GameplayEventStore,
) -> None:
    bundle = _success_bundle(request_id="request:p5d:survival-unsupported")

    result = slice_authority.resolve(
        social_command=bundle["social_command"],
        social_request=bundle["social_request"],
        quest_command=bundle["quest_command"],
        quest_request=bundle["quest_request"],
        conflict_command=bundle["conflict_command"],
        conflict_request=bundle["conflict_request"],
        owner_fragments=(),
        reward_fragments=(),
        survival_mode=SurvivalMode.LIGHTWEIGHT,
        now="2026-08-11T00:00:00Z",
    )

    assert result.resolution.result_kind == "rejected_zero_write"
    assert result.resolution.failure_code == "p5_survival_mode_unsupported"
    assert result.social_result.receipt is None
    assert result.quest_result.receipt is None
    assert result.conflict_result.receipt is None
    assert store.read_events() == []
