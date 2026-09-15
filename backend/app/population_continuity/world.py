from __future__ import annotations

import hashlib
import json

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
from .siming_contracts import PopulationCadenceInput, PopulationProjection
from .roster import PopulationRoster, load_population_roster


class WorldContinuityRuntime:
    """Explicit request boundary over existing runtime cadence policy."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        mode: WorldModeProfile,
        authorized_actor_refs: frozenset[str] | None = None,
        roster: PopulationRoster | None = None,
    ) -> None:
        self.store = store
        self.mode = mode
        self.authorized_actor_refs = authorized_actor_refs
        self.roster = roster if roster is not None else load_population_roster()

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

    def is_paused(self) -> bool:
        """读取最近一次已提交的世界模式边界，不写入世界真相。"""
        events = self.store.read_stream(f"world:{self.mode.world_ref}")
        return bool(events and events[-1].event_type == "population.world.pause")

    def build_population_cadence(
        self,
        *,
        window_start: int,
        window_end: int,
        cadence_id: str | None = None,
        policy_revision: str = "policy:population:v1",
        selector_revision: str = "selector:generic:population:v1",
        ruleset_revision: str = "rules:population:v1",
        report_scope: str = "public",
        budget: int | None = None,
    ) -> PopulationCadenceInput:
        """Build one deterministic window from the committed world stream."""
        if window_end <= window_start:
            raise ValueError("population_cadence_window_invalid")
        world_stream = f"world:{self.mode.world_ref}"
        source_revision = self.store.get_stream_head(world_stream)
        if source_revision <= 0:
            raise ValueError("population_cadence_source_missing")
        events = [event.model_dump(mode="json") for event in self.store.read_events()]
        digest = "sha256:" + hashlib.sha256(
            json.dumps(events, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PopulationCadenceInput(
            cadence_id=cadence_id or f"cadence:{self.mode.world_ref}:{window_start}",
            world_ref=self.mode.world_ref,
            world_mode_ref=f"world-mode:{self.mode.world_ref}",
            world_mode_revision=self.mode.revision,
            cadence_source_ref=world_stream,
            cadence_source_revision=source_revision,
            window_start=window_start,
            window_end=window_end,
            base_checkpoint_ref=f"checkpoint:population:{self.mode.world_ref}:{source_revision}",
            base_checkpoint_digest=digest,
            base_revision_vector={world_stream: source_revision},
            policy_revision=policy_revision,
            selector_revision=selector_revision,
            ruleset_revision=ruleset_revision,
            deterministic_seed=f"seed:{self.mode.world_ref}:{window_start}",
            catch_up_limit=self.mode.catch_up_limit,
            budget=self.mode.batch_limit if budget is None else budget,
            report_scope=report_scope,
        )

    def build_population_projections(
        self, cadence: PopulationCadenceInput
    ) -> tuple[PopulationProjection, ...]:
        """Build deterministic B0 routine inputs for the bounded resident roster."""
        actors = self.roster.actor_ids
        window_size = cadence.window_end - cadence.window_start
        window_index = cadence.window_start // window_size
        start = window_index % len(actors)
        ordered = actors[start:] + actors[:start]
        return tuple(
            PopulationProjection(
                ref=f"projection:{actor}:{cadence.window_start}",
                scope="public",
                revision_vector=dict(cadence.base_revision_vector),
                payload={
                    "actor_ref": f"character:{actor}",
                    "candidate_kind": "routine_work",
                    "fidelity_tier": "B0",
                    "starvation_credit": 1.0 - (index / len(actors)),
                    "state_deltas": {
                        "dynamic_state": {"stress_load": 0.0},
                    },
                    "presentation_seed": {"task": "daily_routine"},
                },
            )
            for index, actor in enumerate(ordered)
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
