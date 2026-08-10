from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.world_runtime.scheduling import (
    RuntimePopulationPolicy,
    RuntimeWakeUpCandidate,
    select_population_continuity_actor_ids,
)

from .models import DueEvaluationReceipt, WorldModeProfile, WorldModeReceipt


class WorldContinuityRuntime:
    """Explicit request boundary over existing runtime cadence policy."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        mode: WorldModeProfile,
        authorized_actor_refs: frozenset[str] | None = None,
    ) -> None:
        self.store = store
        self.mode = mode
        self.authorized_actor_refs = authorized_actor_refs

    def pause(
        self, *, reason: str, expected_mode_revision: str | None = None
    ) -> WorldModeReceipt:
        return self._transition(
            "pause", reason, expected_mode_revision=expected_mode_revision
        )

    def resume(self, *, expected_mode_revision: str | None = None) -> WorldModeReceipt:
        return self._transition(
            "resume", "explicit-resume", expected_mode_revision=expected_mode_revision
        )

    def evaluate_due(
        self,
        *,
        actor_ref: str,
        obligation_refs: tuple[str, ...],
        overdue_refs: tuple[str, ...] = (),
    ) -> DueEvaluationReceipt:
        if (
            self.authorized_actor_refs is not None
            and actor_ref not in self.authorized_actor_refs
        ):
            return DueEvaluationReceipt(
                zero_write=True, stop_reason="profile_not_active"
            )
        envelopes = tuple(
            GameplayCommandEnvelope(
                command_id=f"due:{self.mode.world_ref}:{actor_ref}:{ref}",
                command_type="population.obligation.evaluate",
                command_version=1,
                principal_ref="world_runtime.cadence",
                actor_ref=actor_ref,
                project_ref=None,
                transaction_id=None,
                idempotency_key=f"due:{self.mode.world_ref}:{actor_ref}:{ref}",
                causation_id=f"cadence:{self.mode.revision}",
                correlation_id=f"world:{self.mode.world_ref}",
                source_ref="world_runtime.cadence",
                submitted_at="explicit-request",
                pinned_revisions={"mode": 1, "policy": 1},
                expected_revisions={},
                payload={
                    "obligation_ref": ref,
                    "survival_mode": self.mode.survival_mode,
                    "overdue": ref in overdue_refs,
                },
            )
            for ref in obligation_refs[: self.mode.batch_limit]
        )
        return DueEvaluationReceipt(
            envelopes=envelopes, zero_write=True, overdue_refs=overdue_refs
        )

    def select_actors(
        self,
        *,
        candidates: list[RuntimeWakeUpCandidate],
        policy: RuntimePopulationPolicy,
    ) -> tuple[str, ...]:
        return tuple(
            select_population_continuity_actor_ids(
                candidates=candidates,
                policy=policy,
                actor_population=len(candidates),
                wake_budget=self.mode.wake_budget,
            )
        )

    def replay_equivalence(self) -> tuple[str, str]:
        replay = GameplayProjectionReplay(
            projector_id="population-continuity", projector_version="1"
        )
        events = self.store.read_events()
        full = replay.full_replay(events)
        index = len(events) // 2
        checkpoint = replay.create_checkpoint(events[:index])
        tail = replay.checkpoint_plus_tail_replay(checkpoint, events[index:])
        return full.projection_hash, tail.projection_hash

    def _transition(
        self, action: str, reason: str, *, expected_mode_revision: str | None = None
    ) -> WorldModeReceipt:
        if (
            expected_mode_revision is not None
            and expected_mode_revision != self.mode.revision
        ):
            return WorldModeReceipt(
                committed=False,
                world_ref=self.mode.world_ref,
                mode_revision=self.mode.revision,
                action="rejected",
                zero_write=True,
                stop_reason="mode_revision_conflict",
            )
        stream = f"world:{self.mode.world_ref}"
        expected = self.store.get_stream_head(stream)
        command_id = f"world:{action}:{self.mode.world_ref}:{expected + 1}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref="world_runtime.cadence",
            stream_id=stream,
            expected_revision=expected,
            event_specs=[
                (
                    f"population.world.{action}",
                    {
                        "world_ref": self.mode.world_ref,
                        "mode_revision": self.mode.revision,
                        "reason": reason,
                        "survival_mode": self.mode.survival_mode,
                    },
                )
            ],
            idempotency_key=command_id,
            causation_id=command_id,
            correlation_id=f"world:{self.mode.world_ref}",
            pinned_revisions={"mode": 1},
        )
        result = self.store.append_batch(batch)
        return WorldModeReceipt(
            committed=result.committed,
            world_ref=self.mode.world_ref,
            mode_revision=self.mode.revision,
            action=action if result.committed else "rejected",
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            zero_write=not result.committed,
            stop_reason=None
            if result.committed
            else (result.failure.error_code if result.failure else "append_rejected"),
        )
