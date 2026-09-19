from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from collections.abc import Mapping

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
from .continuous import B0ContinuousResult, advance_b0_row
from .hot_state import PopulationDueIndex, PopulationHotState
from .siming_contracts import PopulationCadenceInput, PopulationProjection, dump_population_projections
from .roster import PopulationRoster, load_population_roster


@dataclass(frozen=True)
class PopulationCadenceConfirmationReceipt:
    cadence_id: str
    status: str
    window_start: int
    window_end: int
    advanced_count: int
    presentation_due_count: int
    new_due_count: int
    due_count: int
    deferred_count: int
    rejected_count: int
    due_backlog_count: int
    projection_digest: str
    result_digest: str


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
        self._cadence_cache: dict[tuple[object, ...], PopulationCadenceInput] = {}
        self._projection_cache: dict[tuple[object, ...], tuple[PopulationProjection, ...]] = {}
        self.population_hot_state = PopulationHotState(self.roster.actor_ids)
        self._population_due_index = PopulationDueIndex()
        for actor_id in self.roster.actor_ids:
            row = self.population_hot_state.read(actor_id)
            self._population_due_index.schedule(
                actor_id,
                "b0:presentation-threshold",
                int(row["next_due_tick"]),
                int(row["revision"]),
            )
        self._preview_results: dict[tuple[object, ...], tuple[B0ContinuousResult, ...]] = {}
        self._confirmed_receipts: dict[str, PopulationCadenceConfirmationReceipt] = {}
        self._confirmed_fingerprints: dict[str, str] = {}
        self._confirmed_window_end: int | None = None
        self._confirmed_rule_identity: tuple[str, str, str, str] | None = None
        self.last_population_confirmation: PopulationCadenceConfirmationReceipt | None = None

    @property
    def latest_confirmation(self) -> PopulationCadenceConfirmationReceipt | None:
        return self.last_population_confirmation

    def _recovery_context_digest(self) -> str:
        from .recovery import recovery_digest

        return recovery_digest({"mode": self.mode.model_dump(mode="json"),
                                "roster": list(self.roster.actor_ids),
                                "authorized_actor_refs": (sorted(self.authorized_actor_refs)
                                                          if self.authorized_actor_refs is not None else None)})

    def export_recovery_state(self) -> dict[str, object]:
        """导出最近一次完整确认的派生态；不携带全历史 receipts 或预计算缓存。"""
        from .recovery import PopulationRecoveryState

        return PopulationRecoveryState.model_validate_json(
            json.dumps(self._build_recovery_state_payload())
        ).model_dump(mode="json")

    def _build_recovery_state_payload(self) -> dict[str, object]:
        """构造独立快照；调用方须在公开输出或持久化前完整验证。"""
        from .recovery import recovery_digest

        receipt = self.last_population_confirmation
        state = {
            "schema_version": 1,
            "context_digest": self._recovery_context_digest(),
            "confirmed_tick": self._confirmed_window_end,
            "rule_identity": list(self._confirmed_rule_identity) if self._confirmed_rule_identity else None,
            "actors": [{"actor_id": actor_id, **row,
                        **{key: float(row[key]) for key in ("fatigue", "need_pressure", "starvation_credit")}}
                       for actor_id, row in self.population_hot_state.export_rows()],
            "due_entries": [dict(actor_id=actor_id, obligation_id=obligation_id, due_tick=tick, revision=revision)
                            for actor_id, obligation_id, tick, revision in self._population_due_index.export_entries()],
            "last_receipt": asdict(receipt) if receipt is not None else None,
            "last_fingerprint": self._confirmed_fingerprints[receipt.cadence_id] if receipt is not None else None,
        }
        state["state_digest"] = recovery_digest(state)
        return state

    def restore_recovery_state(self, state: dict[str, object]) -> None:
        """先完整验证并构建临时热表，成功后一次安装；不追加权威事实。"""
        from .recovery import PopulationRecoveryState

        parsed = PopulationRecoveryState.model_validate_json(json.dumps(state, allow_nan=False))
        if parsed.context_digest != self._recovery_context_digest():
            raise ValueError("population_recovery_context_mismatch")
        if tuple(actor.actor_id for actor in parsed.actors) != tuple(sorted(self.roster.actor_ids)):
            raise ValueError("population_recovery_roster_mismatch")
        hot = PopulationHotState()
        for actor in parsed.actors:
            hot.upsert(actor.actor_id, actor.model_dump(exclude={"actor_id", "revision"}), actor.revision)
        due = PopulationDueIndex()
        due.rebuild((entry.actor_id, entry.obligation_id, entry.due_tick, entry.revision) for entry in parsed.due_entries)
        self.population_hot_state = hot
        self._population_due_index = due
        self._confirmed_window_end = parsed.confirmed_tick
        self._confirmed_rule_identity = parsed.rule_identity
        self.last_population_confirmation = parsed.last_receipt
        self._confirmed_receipts = ({parsed.last_receipt.cadence_id: parsed.last_receipt}
                                    if parsed.last_receipt is not None else {})
        self._confirmed_fingerprints = ({parsed.last_receipt.cadence_id: parsed.last_fingerprint}
                                        if parsed.last_receipt is not None else {})
        self._cadence_cache.clear()
        self._projection_cache.clear()
        self._preview_results.clear()

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
        stream = f"world:{self.mode.world_ref}"
        events = self.store.read_stream(stream, from_revision=self.store.get_stream_head(stream))
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
        source_heads = {world_stream: source_revision}
        cache_key = (
            cadence_id,
            window_start,
            window_end,
            source_revision,
            policy_revision,
            selector_revision,
            ruleset_revision,
            report_scope,
            budget,
            source_revision,
            tuple(self.roster.actor_ids),
            tuple(sorted(self.authorized_actor_refs or ())),
        )
        cached = self._cadence_cache.get(cache_key)
        if cached is not None:
            return cached
        events = {"stream_heads": source_heads}
        digest = "sha256:" + hashlib.sha256(
            json.dumps(events, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        cadence = PopulationCadenceInput(
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
        self._cadence_cache = {cache_key: cadence}
        return cadence

    def build_population_projections(
        self,
        cadence: PopulationCadenceInput,
        *,
        workers: int = 1,
        batch_size: int = 256,
        population_views: Mapping[str, object] | None = None,
    ) -> tuple[PopulationProjection, ...]:
        """从已确认热状态构造只读 B0 预览；发布前不推进游标。"""
        self._validate_confirmation_context(cadence, pin_rules=False)
        cache_key = self._projection_cache_key(cadence, population_views=population_views)
        cached = self._projection_cache.get(cache_key)
        if cached is not None:
            return cached
        if (
            self._confirmed_window_end == cadence.window_start
            and all(
                key[0] in self._confirmed_receipts
                for key in self._projection_cache
            )
        ):
            # 已确认窗口可由 receipt 重放；新窗口计算前释放其万人预览。
            self._projection_cache.clear()
            self._preview_results.clear()
        evaluated = self.population_hot_state.map_readonly(
            self.roster.actor_ids,
            lambda actor_id, row: advance_b0_row(
                actor_id=actor_id,
                row=row,
                window_start=cadence.window_start,
                window_end=cadence.window_end,
            ),
            workers=workers,
            batch_size=batch_size,
        )
        by_actor = {result.actor_id: result for result in evaluated}
        due_actor_ids = {
            actor_id
            for actor_id, obligation_id, _due_tick in self._population_due_index.due_items(
                cadence.window_end
            )
            if obligation_id == "b0:presentation-threshold"
        }
        actor_ids = self.roster.actor_ids
        window_size = cadence.window_end - cadence.window_start
        start = (cadence.window_start // window_size) % len(actor_ids)
        ordered_actor_ids = actor_ids[start:] + actor_ids[:start]
        results = tuple(by_actor[actor_id] for actor_id in ordered_actor_ids)
        projections = tuple(
            PopulationProjection(
                ref=f"projection:{result.actor_id}:{cadence.window_start}",
                scope="public",
                revision_vector=dict(cadence.base_revision_vector),
                payload={
                    "actor_ref": f"character:{result.actor_id}",
                    "candidate_kind": "routine_work",
                    "behavior_kind": "routine_work",
                    "fidelity_tier": "B0",
                    "from_tick": result.from_tick,
                    "to_tick": result.to_tick,
                    "simulation_tick_cursor": result.to_tick,
                    "actor_revision": result.actor_revision_before,
                    "source_revision_vector": dict(cadence.base_revision_vector),
                    "starvation_credit": result.values["starvation_credit"],
                    "state_deltas": dict(result.values),
                    "presentation_seed": {
                        "task": "daily_routine",
                        "activity_phase": result.values["activity_phase"],
                        "threshold_refs": tuple(
                            f"b0:presentation-threshold:{due_tick}"
                            for due_tick in (
                                result.due_ticks if result.actor_id in due_actor_ids else ()
                            )
                        ),
                    },
                    "due_obligation_refs": (),
                    "scope": "public",
                    "idempotency_key": (
                        f"b0:{cadence.cadence_id}:character:{result.actor_id}"
                    ),
                },
            )
            for result in results
        )
        if population_views:
            enriched: list[PopulationProjection] = []
            for projection in projections:
                actor_ref = str(projection.payload.get("actor_ref") or "")
                view = population_views.get(actor_ref)
                if view is None:
                    enriched.append(projection)
                    continue
                if getattr(view, "consumer", None) != "population":
                    raise ValueError("population_view_required")
                groups = getattr(view, "groups", None)
                if not isinstance(groups, Mapping):
                    raise ValueError("population_view_invalid")
                payload = dict(projection.payload)
                payload["population_state"] = {
                    str(group_id): _thaw_population_value(getattr(envelope, "payload", {}))
                    for group_id, envelope in sorted(groups.items(), key=lambda item: str(item[0]))
                    if isinstance(getattr(envelope, "payload", None), Mapping)
                }
                payload["population_state_source_revision_vector"] = _thaw_population_value(
                    getattr(view, "source_revision_vector", {})
                )
                payload["population_state_checksum"] = str(getattr(view, "view_checksum", ""))
                enriched.append(projection.model_copy(update={"payload": payload}))
            projections = tuple(enriched)
        self._projection_cache = {cache_key: projections}
        self._preview_results = {cache_key: results}
        return projections

    def confirm_population_cadence(
        self, cadence: PopulationCadenceInput
    ) -> PopulationCadenceConfirmationReceipt:
        """在 cadence 已发布后确认同一纯计算结果，重复确认保持幂等。"""
        fingerprint = self._cadence_fingerprint(cadence)
        previous = self._confirmed_receipts.get(cadence.cadence_id)
        if previous is None and self._confirmed_window_end is not None and cadence.window_end <= self._confirmed_window_end:
            from .recovery import durable_population_receipt

            previous = durable_population_receipt(self, cadence)
            if previous is not None:
                return replace(previous, status="idempotent_replay")
        if previous is not None:
            if self._confirmed_fingerprints[cadence.cadence_id] != fingerprint:
                raise ValueError("population_cadence_confirmation_conflict")
            return replace(previous, status="idempotent_replay")
        self._validate_confirmation_context(cadence, pin_rules=True)
        if (
            self._confirmed_window_end is not None
            and cadence.window_start != self._confirmed_window_end
        ):
            raise ValueError("population_cadence_confirmation_conflict")
        projections = self.build_population_projections(cadence)
        cache_key = self._projection_cache_key(cadence)
        results = self._preview_results[cache_key]
        due_items = tuple(
            item
            for item in self._population_due_index.due_items(cadence.window_end)
            if item[1] == "b0:presentation-threshold"
        )
        expected_due_actors = {
            result.actor_id for result in results if result.due_ticks
        }
        if {actor_id for actor_id, _obligation_id, _due_tick in due_items} != expected_due_actors:
            raise ValueError("population_due_index_conflict")
        advanced_count = self.population_hot_state.commit_batch_atomic(
            (
                result.actor_id,
                result.values,
                result.actor_revision_before,
                result.actor_revision_before + 1,
            )
            for result in results
        )
        presentation_due_count = sum(len(result.due_ticks) for result in results)
        consumed_due = self._population_due_index.pop_due(
            cadence.window_end, obligation_id="b0:presentation-threshold"
        )
        if consumed_due != due_items:
            raise ValueError("population_due_index_conflict")
        for result in results:
            self._population_due_index.schedule(
                result.actor_id,
                "b0:presentation-threshold",
                int(result.values["next_due_tick"]),
                result.actor_revision_before + 1,
            )
        backlog = self._population_due_index.due_items(cadence.window_end)
        projection_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                [
                    projection.__dict__
                    for projection in projections
                ],
                check_circular=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        result_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "cadence": fingerprint,
                    "projection_digest": projection_digest,
                    "advanced_count": advanced_count,
                    "presentation_due_count": presentation_due_count,
                    "due_backlog_count": len(backlog),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        receipt = PopulationCadenceConfirmationReceipt(
            cadence_id=cadence.cadence_id,
            status="committed",
            window_start=cadence.window_start,
            window_end=cadence.window_end,
            advanced_count=advanced_count,
            presentation_due_count=presentation_due_count,
            new_due_count=presentation_due_count,
            due_count=presentation_due_count,
            deferred_count=len(backlog),
            rejected_count=0,
            due_backlog_count=len(backlog),
            projection_digest=projection_digest,
            result_digest=result_digest,
        )
        self._confirmed_receipts[cadence.cadence_id] = receipt
        self._confirmed_fingerprints[cadence.cadence_id] = fingerprint
        while len(self._confirmed_receipts) > 2:
            oldest = next(iter(self._confirmed_receipts))
            self._confirmed_receipts.pop(oldest)
            self._confirmed_fingerprints.pop(oldest)
        self._confirmed_window_end = cadence.window_end
        self._confirmed_rule_identity = self._rule_identity(cadence)
        self.last_population_confirmation = receipt
        return receipt

    def due_population_work(self, tick: int) -> tuple[tuple[str, str, int], ...]:
        return self._population_due_index.due_items(tick)

    def claim_due_population_work(
        self, tick: int, *, limit: int | None = None
    ) -> tuple[tuple[str, str, int], ...]:
        return self._population_due_index.pop_due(tick, limit=limit)

    def select_due_population_work(
        self, tick: int, *, limit: int | None = None
    ) -> tuple[tuple[str, str, int], ...]:
        due = self._population_due_index.due_items(tick)
        return due if limit is None else due[:limit]

    def complete_due_population_work(self, actor_id: str, obligation_id: str) -> None:
        self._population_due_index.cancel(actor_id, obligation_id)

    def requeue_due_population_work(
        self,
        actor_id: str,
        obligation_id: str,
        due_tick: int,
        *,
        revision: int,
    ) -> None:
        self._population_due_index.schedule(
            actor_id, obligation_id, due_tick, revision
        )

    def _validate_confirmation_context(
        self, cadence: PopulationCadenceInput, *, pin_rules: bool
    ) -> None:
        world_stream = f"world:{self.mode.world_ref}"
        source_events = self.store.read_stream(
            world_stream,
            from_revision=cadence.cadence_source_revision,
            to_revision=cadence.cadence_source_revision,
        )
        source_event = source_events[0] if len(source_events) == 1 else None
        if (
            cadence.world_ref != self.mode.world_ref
            or cadence.world_mode_revision != self.mode.revision
            or cadence.cadence_source_ref != world_stream
            or cadence.cadence_source_revision < 1
            or cadence.base_revision_vector.get(world_stream)
            != cadence.cadence_source_revision
            or self.store.get_stream_head(world_stream) < cadence.cadence_source_revision
            or source_event is None
            or source_event.event_type != "population.world.resume"
            or source_event.payload.get("world_ref") != self.mode.world_ref
            or source_event.payload.get("mode_revision") != self.mode.revision
            or cadence.report_scope != "public"
            or cadence.window_start < 0
            or cadence.window_end <= cadence.window_start
        ):
            raise ValueError("population_cadence_confirmation_context_invalid")
        if (
            pin_rules
            and self._confirmed_rule_identity is not None
            and self._confirmed_rule_identity != self._rule_identity(cadence)
        ):
            raise ValueError("population_cadence_confirmation_context_invalid")

    @staticmethod
    def _rule_identity(cadence: PopulationCadenceInput) -> tuple[str, str, str, str]:
        return (
            cadence.policy_revision,
            cadence.selector_revision,
            cadence.ruleset_revision,
            cadence.report_scope,
        )

    def _projection_cache_key(
        self,
        cadence: PopulationCadenceInput,
        *,
        population_views: Mapping[str, object] | None = None,
    ) -> tuple[object, ...]:
        return (
            cadence.cadence_id,
            cadence.window_start,
            cadence.window_end,
            tuple(sorted(cadence.base_revision_vector.items())),
            *self._rule_identity(cadence),
            tuple(self.roster.actor_ids),
            tuple(
                sorted(
                    (
                        str(actor_ref),
                        str(getattr(view, "view_checksum", "")),
                        repr(getattr(view, "groups", {})),
                    )
                    for actor_ref, view in (population_views or {}).items()
                )
            ),
        )
    @staticmethod
    def _cadence_fingerprint(cadence: PopulationCadenceInput) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(
                cadence.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

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


def _thaw_population_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_population_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_thaw_population_value(item) for item in value]
    return value
