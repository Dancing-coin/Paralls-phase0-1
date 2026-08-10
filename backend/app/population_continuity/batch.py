from __future__ import annotations

import hashlib
import json

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import (
    SettlementPlan,
    build_multi_stream_atomic_event_batch,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope

from .models import (
    BatchIntentCandidate,
    ContinuityMergeReceipt,
    MergeRejection,
    PopulationBatchPlan,
    WorldModeProfile,
)


def _digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
    )


def _plan_digest(plan: PopulationBatchPlan) -> str:
    normalized = plan.model_copy(
        update={
            "candidates": tuple(
                sorted(
                    plan.candidates,
                    key=lambda item: (
                        -item.priority,
                        item.profile_ref,
                        item.intent_ref,
                    ),
                )
            )
        }
    )
    return _digest(normalized.model_dump(mode="json"))


class PopulationPlanner:
    """Pure proposal generator; it has no store and no append method."""

    def plan(
        self,
        *,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        candidates: tuple[BatchIntentCandidate, ...],
        input_digest: str,
        deterministic_seed: str,
    ) -> PopulationBatchPlan:
        ordered = tuple(
            sorted(
                candidates,
                key=lambda item: (-item.priority, item.profile_ref, item.intent_ref),
            )
        )[: mode.batch_limit]
        return PopulationBatchPlan(
            batch_ref=batch_ref,
            world_ref=world_ref,
            policy_revision=mode.revision,
            package_revision=ordered[0].package_revision if ordered else "package:none",
            deterministic_seed=deterministic_seed,
            input_digest=input_digest,
            budget=mode.wake_budget,
            candidates=ordered,
        )

    def envelopes(
        self, plan: PopulationBatchPlan
    ) -> tuple[GameplayCommandEnvelope, ...]:
        return tuple(self._envelope(plan, candidate) for candidate in plan.candidates)

    @staticmethod
    def _envelope(
        plan: PopulationBatchPlan, candidate: BatchIntentCandidate
    ) -> GameplayCommandEnvelope:
        payload = dict(candidate.payload)
        payload.update(
            {
                "profile_ref": candidate.profile_ref,
                "intent_ref": candidate.intent_ref,
                "claim_refs": list(candidate.claim_refs),
                "policy_revision": candidate.policy_revision,
                "package_revision": candidate.package_revision,
                "expected_revisions": dict(candidate.expected_revisions),
                "batch_plan_digest": _plan_digest(plan),
            }
        )
        return GameplayCommandEnvelope(
            command_id=candidate.intent_ref,
            command_type=f"population.intent.{candidate.intent_kind}",
            command_version=1,
            principal_ref=candidate.source_ref,
            actor_ref=candidate.profile_ref,
            project_ref=plan.world_ref,
            transaction_id=f"transaction:{plan.batch_ref}",
            idempotency_key=candidate.idempotency_key,
            expected_revisions=dict(candidate.expected_revisions),
            causation_id=f"batch:{plan.batch_ref}",
            correlation_id=candidate.correlation_id,
            source_ref=candidate.source_ref,
            submitted_at="population-planner",
            pinned_revisions={"policy": 1, "package": 1},
            payload=payload,
        )


class ContinuityMergeAuthority:
    def __init__(
        self,
        *,
        store: GameplayEventStore,
        registry: CharacterProfileRegistry,
        mode: WorldModeProfile,
    ) -> None:
        self.store = store
        self.registry = registry
        self.mode = mode

    def merge(self, plan: PopulationBatchPlan) -> ContinuityMergeReceipt:
        if plan.policy_revision != self.mode.revision:
            return self._failed(plan, "stale_policy_revision")
        existing = self.store.get_by_idempotency(
            "population.authority", f"merge:{plan.batch_ref}"
        )
        existing_digest = ""
        if existing is not None and existing.committed_event_ids:
            existing_digest = str(
                self.store.get_event(existing.committed_event_ids[0]).payload.get(
                    "batch_plan_digest", ""
                )
            )
        if existing is not None and existing_digest == _plan_digest(plan):
            replay = GameplayProjectionReplay(
                projector_id="population-continuity", projector_version="1"
            ).full_replay(self.store.read_events())
            accepted_refs = tuple(
                item.intent_ref
                for item in sorted(
                    plan.candidates,
                    key=lambda item: (
                        -item.priority,
                        item.profile_ref,
                        item.intent_ref,
                    ),
                )
            )
            return ContinuityMergeReceipt(
                committed=True,
                batch_ref=plan.batch_ref,
                accepted_intent_refs=accepted_refs,
                committed_event_ids=tuple(existing.committed_event_ids),
                revision_vector=dict(existing.resulting_stream_revisions),
                replay_hash=replay.projection_hash,
                scope=("actor:self", "organization:summary", "public"),
                redaction="scope-filtered",
                zero_write=False,
                idempotency_status="duplicate_replayed",
            )
        ordered = sorted(
            plan.candidates,
            key=lambda item: (-item.priority, item.profile_ref, item.intent_ref),
        )
        accepted: list[BatchIntentCandidate] = []
        deferred: list[str] = []
        rejections: list[MergeRejection] = []
        claims: set[str] = set()
        for candidate in ordered:
            if (
                candidate.policy_revision != self.mode.revision
                or candidate.package_revision != plan.package_revision
            ):
                return self._failed(plan, "stale_stream")
            if candidate.intent_kind not in self.mode.allowed_intent_kinds:
                return self._failed(plan, "intent_kind_denied")
            try:
                self.registry.profile_ref(candidate.profile_ref)
            except KeyError:
                return self._failed(plan, "profile_not_registered")
            if candidate.privacy_scope not in self.mode.allowed_privacy_scopes:
                return self._failed(plan, "privacy_denial")
            if any(
                self.store.get_stream_head(stream) != revision
                for stream, revision in candidate.expected_revisions.items()
            ):
                return self._failed(plan, "revision_conflict")
            if claims.intersection(candidate.claim_refs):
                deferred.append(candidate.intent_ref)
                rejections.append(
                    MergeRejection(
                        intent_ref=candidate.intent_ref,
                        error_code="contention_deferred",
                        retriable=True,
                        claim_refs=candidate.claim_refs,
                    )
                )
                continue
            claims.update(candidate.claim_refs)
            accepted.append(candidate)
        if not accepted:
            return ContinuityMergeReceipt(
                committed=False,
                batch_ref=plan.batch_ref,
                deferred_intent_refs=tuple(deferred),
                rejections=tuple(rejections),
                zero_write=True,
                stop_reason="no_accepted_intents",
            )
        event_specs: dict[str, list[tuple[str, dict[str, object]]]] = {}
        expected: dict[str, int] = {}
        for candidate in accepted:
            envelope = PopulationPlanner()._envelope(plan, candidate)
            SettlementPlan.from_command_envelope(envelope)
            stream = str(
                candidate.payload.get(
                    "stream_ref", f"population:{candidate.profile_ref}"
                )
            )
            event_specs.setdefault(stream, []).append(
                (
                    str(
                        candidate.payload.get(
                            "event_type", "population.intent.proposed"
                        )
                    ),
                    dict(envelope.payload),
                )
            )
            expected[stream] = candidate.expected_revisions.get(
                stream, self.store.get_stream_head(stream)
            )
        batch = build_multi_stream_atomic_event_batch(
            command_id=f"merge:{plan.batch_ref}",
            principal_ref="population.authority",
            expected_revisions=expected,
            event_specs=event_specs,
            idempotency_key=f"merge:{plan.batch_ref}",
            causation_id=f"batch:{plan.batch_ref}",
            correlation_id=plan.batch_ref,
            pinned_revisions={"policy": 1, "package": 1},
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return self._failed(
                plan, result.failure.error_code if result.failure else "append_rejected"
            )
        replay = GameplayProjectionReplay(
            projector_id="population-continuity", projector_version="1"
        ).full_replay(self.store.read_events())
        return ContinuityMergeReceipt(
            committed=True,
            batch_ref=plan.batch_ref,
            accepted_intent_refs=tuple(item.intent_ref for item in accepted),
            deferred_intent_refs=tuple(deferred),
            rejections=tuple(rejections),
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            replay_hash=replay.projection_hash,
            scope=("actor:self", "organization:summary", "public"),
            redaction="scope-filtered",
            zero_write=False,
            idempotency_status=result.idempotency_status,
        )

    @staticmethod
    def _failed(plan: PopulationBatchPlan, reason: str) -> ContinuityMergeReceipt:
        return ContinuityMergeReceipt(
            committed=False,
            batch_ref=plan.batch_ref,
            zero_write=True,
            stop_reason=reason,
        )
