from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import ProjectionCheckpoint
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.action_consequence_runtime import WorldDeathConfirmationIntent
from app.gameplay.p5.contracts import canonical_sha256_digest
from test_action_conflict_window import (
    EVENT_STREAM,
    ROLE_REF,
    SOURCE_STREAM,
    _graph,
    _intent,
    _registry,
    _seed_source,
    _snapshot,
)


def _window_command(index: int) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:action-window:{index}",
        command_type="gameplay.conflict.resolve_action_window",
        command_version=1,
        principal_ref="authority:p5:investigation-conflict",
        actor_ref="character:survivor:alpha",
        project_ref="project:action-window",
        transaction_id=f"transaction:action-window:{index}",
        idempotency_key=f"idempotency:action-window:{index}",
        expected_revisions={EVENT_STREAM: index * 5},
        read_set_revisions={SOURCE_STREAM: 1},
        causation_id=f"causation:action-window:{index}",
        correlation_id="correlation:action-window:replay",
        source_ref="source:action-window:replay",
        submitted_at="2026-09-05T00:00:00Z",
        pinned_revisions={},
        payload={},
    )


def test_three_windows_full_and_checkpoint_tail_replay_match() -> None:
    store = GameplayEventStore()
    _seed_source(store)
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    for index in range(3):
        intent = _intent().model_copy(
            update={
                "attempt_ref": f"attempt:bakery-theft:{index}",
                "window_index": index,
                "window_start_tick": index,
                "window_end_tick": index + 1,
            },
            deep=True,
        )
        result = authority.resolve_action_window(
            command=_window_command(index),
            intent=intent,
            graph=_graph(),
            spatial_snapshot=_snapshot(),
            role_ref=ROLE_REF,
            now="2026-09-05T00:00:00Z",
        )
        assert result.committed

    full = authority.replay_full(now="2026-09-05T00:00:00Z")
    prefix_events = store.read_events(limit=8)
    prefix_state = authority._projection_state(prefix_events)
    checkpoint = ProjectionCheckpoint(
        checkpoint_id="checkpoint:action-window:1",
        projector_id="projector:p5:investigation-conflict",
        projector_version="v1",
        projection_schema_version=1,
        source_revision_vector=dict(prefix_state["source_revision_vector"]),
        last_global_sequence=int(prefix_state["last_global_sequence"]),
        state=prefix_state,
        applied_event_ids=list(prefix_state["applied_event_ids"]),
        projection_hash=canonical_sha256_digest(prefix_state),
        registry_revision=_registry().registry_revision,
    )
    tail = authority.replay_checkpoint_tail(checkpoint=checkpoint, now="2026-09-05T00:00:00Z")
    assert full.succeeded and tail.succeeded
    assert full.projection_hash == tail.projection_hash
    assert full.state == tail.state


def test_explicit_world_death_confirmation_accept_and_reject_are_separate() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:conflict:encounter:death"
    source = store.append_batch(
        build_atomic_event_batch(
            command_id="case-death",
            principal_ref="authority:p5:investigation-conflict",
            stream_id=source_stream,
            expected_revision=0,
            event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor:alpha", "terminal_kind": "case_death"}),),
            idempotency_key="case-death",
            causation_id="case-death",
            correlation_id="case-death",
        )
    )
    source_event = store.get_event(source.committed_event_ids[0])
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    for confirmed, suffix in ((True, "confirm"), (False, "reject")):
        command = GameplayCommandEnvelope(
            command_id=f"death-{suffix}",
            command_type="gameplay.conflict.confirm_world_death",
            command_version=1,
            principal_ref="authority:p5:investigation-conflict",
            actor_ref="character:survivor:alpha",
            project_ref="project:case",
            transaction_id=f"transaction:death-{suffix}",
            idempotency_key=f"death-{suffix}",
            expected_revisions={source_stream: 1 if suffix == "confirm" else 2},
            causation_id="case-death",
            correlation_id="case-death",
            source_ref=source_event.event_id,
            submitted_at="now",
        )
        result = authority.confirm_world_death(
            command=command,
            intent=WorldDeathConfirmationIntent(
                source_event_id=source_event.event_id,
                target_actor_ref="character:survivor:alpha",
                expected_source_revision=1,
                confirmation_ref=f"confirmation:case:{suffix}",
                confirmed=confirmed,
                policy_revision="policy:death@1",
            ),
        )
        if confirmed:
            assert result.committed
        else:
            assert not result.committed
            assert result.error_code == "world_death_source_revision_stale"
