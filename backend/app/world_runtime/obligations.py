from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Literal, Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayEvent, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import AppendDerivedSettlementRecipe
from app.gameplay.shared_contracts import ScheduledObligation, SettlementReceipt


class ObligationSettlementResult(StrictGameplayModel):
    committed: bool
    idempotency_status: Literal["new_commit", "duplicate_replayed", "rejected"] = "rejected"
    committed_event_ids: tuple[str, ...] = ()
    receipt: SettlementReceipt | None = None
    error_code: str | None = None


class ObligationSettlementPlan(StrictGameplayModel):
    ready: bool = False
    idempotency_status: Literal["new_commit", "duplicate_replayed", "rejected"] = "rejected"
    owner_commit_batch: AtomicEventBatch | None = None
    duplicate_result: AppendBatchResult | None = None
    receipt: SettlementReceipt | None = None
    error_code: str | None = None


class ObligationLifecycleRegistration(StrictGameplayModel):
    model_config = {"extra": "forbid", "frozen": True}

    policy_ref: str
    policy_revision: str
    owner_ref: str
    stream_pattern: str
    settled_event_type: str
    cancelled_event_type: str | None = None
    visibility_scope: Literal["project", "authority_only"]
    opened_event_type: str = "gameplay.construction_production.run_started"
    retry_event_type: str | None = None
    compensated_event_type: str | None = None
    additional_compensated_event_types: tuple[str, ...] = ()
    expired_event_type: str | None = None
    allowed_event_types: tuple[str, ...] = ()
    requires_committed_open: bool = False
    requires_expired_event_on_settle: bool = False

    def event_type_for(self, operation: str) -> str | None:
        """Return the closed event family admitted for one lifecycle operation.

        The operation name is intentionally a small closed vocabulary. Callers
        may inspect this contract, but they still need the registered owner to
        build the matching fragment and commit it through its own authority.
        """
        return {
            "settle": self.settled_event_type,
            "cancel": self.cancelled_event_type,
            "expire": self.expired_event_type,
            "retry": self.retry_event_type,
            "compensate": self.compensated_event_type,
        }.get(operation)


class ObligationLifecycleContractRegistry:
    """Closed policy admission for lifecycle readers and settlement assembly."""

    @staticmethod
    def closed_registrations() -> tuple[ObligationLifecycleRegistration, ...]:
        registrations = (
            ObligationLifecycleRegistration(
                policy_ref="policy:construction_due_completion",
                policy_revision="1",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_pattern="gameplay:construction_production:{facility_ref}",
                opened_event_type="gameplay.construction_production.run_started",
                settled_event_type="gameplay.construction_production.obligation_settled",
                cancelled_event_type="gameplay.construction_production.obligation_cancelled",
                allowed_event_types=(
                    "gameplay.construction_production.run_finished",
                    "gameplay.construction_production.obligation_settled",
                    "gameplay.construction_production.obligation_cancelled",
                ),
                visibility_scope="project",
                requires_committed_open=True,
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:construction_maintenance_state_expiry@1",
                policy_revision="1",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_pattern="gameplay:construction_production:{facility_ref}",
                opened_event_type="gameplay.construction_production.maintenance_state_obligation_opened",
                settled_event_type="gameplay.construction_production.maintenance_state_obligation_settled",
                cancelled_event_type="gameplay.construction_production.maintenance_state_obligation_cancelled",
                expired_event_type="gameplay.construction_production.maintenance_state_expired",
                allowed_event_types=(
                    "gameplay.construction_production.maintenance_state_expired",
                    "gameplay.construction_production.maintenance_state_obligation_settled",
                    "gameplay.construction_production.maintenance_state_dispelled",
                    "gameplay.construction_production.maintenance_state_obligation_cancelled",
                ),
                visibility_scope="project",
                requires_committed_open=True,
                requires_expired_event_on_settle=True,
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:ecology_frost_crop_state_expiry@1",
                policy_revision="1",
                owner_ref="authority:ecology",
                stream_pattern="gameplay:ecology:{region_ref}",
                opened_event_type="gameplay.ecology.crop_state_obligation_opened",
                settled_event_type="gameplay.ecology.crop_state_obligation_settled",
                cancelled_event_type="gameplay.ecology.crop_state_obligation_cancelled",
                expired_event_type="gameplay.ecology.crop_state_expired",
                allowed_event_types=(
                    "gameplay.ecology.crop_state_expired",
                    "gameplay.ecology.crop_state_obligation_settled",
                    "gameplay.ecology.crop_state_obligation_cancelled",
                ),
                visibility_scope="project",
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:ecology_drought_state_expiry@1",
                policy_revision="1",
                owner_ref="authority:ecology",
                stream_pattern="gameplay:ecology:{region_ref}",
                opened_event_type="gameplay.ecology.drought_state_obligation_opened",
                settled_event_type="gameplay.ecology.drought_state_obligation_settled",
                expired_event_type="gameplay.ecology.drought_state_expired",
                allowed_event_types=(
                    "gameplay.ecology.drought_state_applied",
                    "gameplay.ecology.drought_state_obligation_opened",
                    "gameplay.ecology.drought_state_expired",
                    "gameplay.ecology.drought_state_obligation_settled",
                ),
                visibility_scope="project",
                requires_committed_open=True,
                requires_expired_event_on_settle=True,
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:economy_scheduled_account_transfer@1",
                policy_revision="1",
                owner_ref="actor_gameplay.economy_domain",
                stream_pattern="gameplay:economy",
                opened_event_type="gameplay.economy.scheduled_transfer_obligation_opened",
                settled_event_type="gameplay.economy.scheduled_transfer_obligation_settled",
                cancelled_event_type="gameplay.economy.scheduled_transfer_obligation_cancelled",
                expired_event_type="gameplay.economy.scheduled_transfer_obligation_expired",
                allowed_event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.scheduled_transfer_obligation_settled",
                    "gameplay.economy.scheduled_transfer_obligation_cancelled",
                    "gameplay.economy.scheduled_transfer_obligation_expired",
                ),
                visibility_scope="authority_only",
                requires_committed_open=True,
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:economy_tax_due@1",
                policy_revision="1",
                owner_ref="actor_gameplay.economy_domain",
                stream_pattern="gameplay:economy",
                opened_event_type="gameplay.economy.tax_obligation_opened",
                settled_event_type="gameplay.economy.tax_obligation_settled",
                cancelled_event_type="gameplay.economy.tax_obligation_cancelled",
                expired_event_type="gameplay.economy.tax_obligation_expired",
                allowed_event_types=(
                    "gameplay.economy.tax_due_recorded",
                    "gameplay.economy.tax_obligation_opened",
                    "gameplay.economy.tax_obligation_settled",
                    "gameplay.economy.tax_obligation_cancelled",
                    "gameplay.economy.tax_obligation_expired",
                ),
                visibility_scope="authority_only",
                requires_committed_open=True,
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:economy_wage_accrual",
                policy_revision="1",
                owner_ref="actor_gameplay.econ1_economy_domain",
                stream_pattern="gameplay:economy:wage:{worker_ref}",
                opened_event_type="gameplay.economy.wage_obligation_opened",
                settled_event_type="gameplay.economy.wage_obligation_settled",
                cancelled_event_type="gameplay.economy.wage_obligation_cancelled",
                retry_event_type="gameplay.economy.wage_obligation_retry_scheduled",
                compensated_event_type="gameplay.economy.wage_obligation_compensated",
                additional_compensated_event_types=("gameplay.economy.wage_accrual_compensated",),
                expired_event_type="gameplay.economy.wage_obligation_expired",
                allowed_event_types=(
                    "gameplay.economy.wage_accrued",
                    "gameplay.economy.wage_obligation_settled",
                    "gameplay.economy.wage_obligation_cancelled",
                    "gameplay.economy.wage_obligation_retry_scheduled",
                    "gameplay.economy.wage_accrual_compensated",
                    "gameplay.economy.wage_obligation_compensated",
                    "gameplay.economy.wage_obligation_expired",
                ),
                visibility_scope="project",
            ),
            ObligationLifecycleRegistration(
                policy_ref="policy:survival_state_expiry",
                policy_revision="1",
                owner_ref="actor_gameplay.survival_domain",
                stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened",
                settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled",
                retry_event_type="gameplay.survival.obligation_retry_scheduled",
                compensated_event_type="gameplay.survival.obligation_compensated",
                allowed_event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                    "gameplay.survival.state_expired",
                    "gameplay.survival.obligation_settled",
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                    "gameplay.survival.obligation_retry_scheduled",
                    "gameplay.survival.state_compensated",
                    "gameplay.survival.obligation_compensated",
                ),
                visibility_scope="project",
            ),
        )
        return tuple(sorted(registrations, key=lambda item: item.policy_ref))

    @classmethod
    def require(cls, *, policy_ref: str, policy_revision: str) -> ObligationLifecycleRegistration:
        for registration in cls.closed_registrations():
            if registration.policy_ref == policy_ref and registration.policy_revision == policy_revision:
                return registration
        raise ValueError("obligation_lifecycle_registration_unregistered")

    @classmethod
    def permits(cls, registration: ObligationLifecycleRegistration) -> bool:
        try:
            canonical = cls.require(
                policy_ref=registration.policy_ref,
                policy_revision=registration.policy_revision,
            )
        except ValueError:
            return False
        required_fields = (
            "owner_ref",
            "stream_pattern",
            "opened_event_type",
            "settled_event_type",
            "visibility_scope",
        )
        optional_terminal_fields = (
            "cancelled_event_type",
            "retry_event_type",
            "compensated_event_type",
            "expired_event_type",
        )
        return (
            all(getattr(registration, field) == getattr(canonical, field) for field in required_fields)
            and all(
                getattr(registration, field) is None or getattr(registration, field) == getattr(canonical, field)
                for field in optional_terminal_fields
            )
            and (
                not registration.allowed_event_types
                or set(registration.allowed_event_types).issubset(set(canonical.allowed_event_types))
            )
            and set(registration.additional_compensated_event_types).issubset(
                set(canonical.additional_compensated_event_types)
            )
            and (not registration.requires_committed_open or canonical.requires_committed_open)
            and (not registration.requires_expired_event_on_settle or canonical.requires_expired_event_on_settle)
        )


class ObligationLifecycleRecord(StrictGameplayModel):
    model_config = {"extra": "forbid", "frozen": True}

    obligation_id: str
    owner_ref: str
    policy_ref: str
    policy_revision: str
    stream_id: str
    due_tick: int
    status: Literal["open", "due", "retry", "settled", "cancelled", "expired", "compensated"]
    visibility_scope: Literal["project", "authority_only"]
    source_revision: int
    source_refs: tuple[str, ...] = ()


class ObligationLifecycleView(StrictGameplayModel):
    model_config = {"extra": "forbid", "frozen": True}

    open: dict[str, ObligationLifecycleRecord] = {}
    terminal: dict[str, ObligationLifecycleRecord] = {}
    source_revision_vector: dict[str, int] = {}

    def at_tick(self, tick: int, *, catch_up_limit: int) -> "ObligationLifecycleView":
        """Derive a bounded due view from the shared clock without writing."""
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            raise ValueError("obligation_due_tick_invalid")
        if (
            not isinstance(catch_up_limit, int)
            or isinstance(catch_up_limit, bool)
            or catch_up_limit < 0
        ):
            raise ValueError("obligation_catch_up_limit_invalid")
        due_ids = {
            record.obligation_id
            for record in sorted(
                (
                    record
                    for record in self.open.values()
                    if record.status in {"open", "retry"} and record.due_tick <= tick
                ),
                key=lambda item: (item.due_tick, item.obligation_id),
            )[:catch_up_limit]
        }
        return self.model_copy(
            update={
                "open": {
                    obligation_id: (
                        record.model_copy(update={"status": "due"}, deep=True)
                        if obligation_id in due_ids
                        else record
                    )
                    for obligation_id, record in self.open.items()
                }
            },
            deep=True,
        )

    def due_at(self, tick: int) -> tuple[ObligationLifecycleRecord, ...]:
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            raise ValueError("obligation_due_tick_invalid")
        return tuple(
            record.model_copy(update={"status": "due"}, deep=True)
            for record in sorted(self.open.values(), key=lambda item: (item.due_tick, item.obligation_id))
            if record.status in {"open", "retry"} and record.due_tick <= tick
        )

    def to_scheduled_obligations(self) -> tuple[ScheduledObligation, ...]:
        """Materialize owner-neutral due inputs from committed lifecycle records."""
        return tuple(
            ScheduledObligation(
                obligation_id=record.obligation_id,
                owner_ref=record.owner_ref,
                due_tick=record.due_tick,
                policy_revision=record.policy_revision,
                status=record.status,
                source_refs=record.source_refs or (
                    record.policy_ref,
                    f"stream:{record.stream_id}",
                ),
                idempotency_key=f"lifecycle:{record.policy_ref}:{record.obligation_id}",
                expected_revisions={
                    record.stream_id: self.source_revision_vector.get(
                        record.stream_id,
                        record.source_revision,
                    )
                },
                visibility_scope=record.visibility_scope,
            )
            for record in sorted(self.open.values(), key=lambda item: (item.due_tick, item.obligation_id))
        )


class ObligationLifecycleProjection:
    """Read-only lifecycle reconstructed from registered owner events."""

    def __init__(self, registrations: tuple[ObligationLifecycleRegistration, ...]) -> None:
        self._registrations = {
            (item.policy_ref, item.policy_revision): item
            for item in registrations
            if ObligationLifecycleContractRegistry.permits(item)
        }

    def rebuild(self, events: list[GameplayEvent]) -> ObligationLifecycleView:
        return self._apply(ObligationLifecycleView(), events)

    def create_checkpoint(self, events: list[GameplayEvent]) -> ObligationLifecycleView:
        """Return an event-derived checkpoint without materializing due state."""
        return self.rebuild(events)

    def replay_at(
        self,
        events: list[GameplayEvent],
        *,
        tick: int,
        catch_up_limit: int,
    ) -> ObligationLifecycleView:
        return self.rebuild(events).at_tick(tick, catch_up_limit=catch_up_limit)

    def checkpoint_plus_tail_at(
        self,
        checkpoint: ObligationLifecycleView,
        tail_events: list[GameplayEvent],
        *,
        tick: int,
        catch_up_limit: int,
    ) -> ObligationLifecycleView:
        if any(record.status not in {"open", "retry"} for record in checkpoint.open.values()):
            raise ValueError("obligation_lifecycle_checkpoint_due_invalid")
        return self._apply(checkpoint, tail_events).at_tick(
            tick,
            catch_up_limit=catch_up_limit,
        )

    def _apply(
        self,
        checkpoint: ObligationLifecycleView,
        events: list[GameplayEvent],
    ) -> ObligationLifecycleView:
        open_records = dict(checkpoint.open)
        terminal_records = dict(checkpoint.terminal)
        revisions = dict(checkpoint.source_revision_vector)
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if any(
                ObligationSettlementCoordinator._stream_matches(registration.stream_pattern, event.stream_id)
                for registration in self._registrations.values()
            ):
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            registration = self._registration_for_open_event(event)
            if registration is not None:
                payload = event.payload
                obligation_id = str(payload.get("obligation_id") or payload.get("due_obligation_id") or "")
                due_tick = payload.get("due_tick", payload.get("finish_tick"))
                if not obligation_id or not isinstance(due_tick, int) or isinstance(due_tick, bool) or due_tick < 0:
                    raise ValueError("obligation_lifecycle_open_payload_invalid")
                record = ObligationLifecycleRecord(
                    obligation_id=obligation_id,
                    owner_ref=registration.owner_ref,
                    policy_ref=registration.policy_ref,
                    policy_revision=registration.policy_revision,
                    stream_id=event.stream_id,
                    due_tick=due_tick,
                    status="open",
                    visibility_scope=registration.visibility_scope,
                    source_revision=event.stream_revision,
                    source_refs=self._source_refs_for_open_event(registration=registration, event=event),
                )
                open_records[obligation_id] = record
                terminal_records.pop(obligation_id, None)
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            registration = self._registration_for_retry_event(event)
            if registration is not None:
                obligation_id = str(event.payload.get("obligation_id", ""))
                prior = open_records.get(obligation_id)
                due_tick = event.payload.get("next_due_tick")
                if not obligation_id or prior is None or not isinstance(due_tick, int) or isinstance(due_tick, bool) or due_tick < prior.due_tick:
                    raise ValueError("obligation_lifecycle_retry_payload_invalid")
                open_records[obligation_id] = prior.model_copy(
                    update={"status": "retry", "due_tick": due_tick, "source_revision": event.stream_revision}, deep=True
                )
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            registration, status = self._registration_for_terminal_event(event)
            if registration is None or status is None:
                continue
            obligation_id = str(event.payload.get("obligation_id", ""))
            current = open_records.pop(obligation_id, None)
            if status in {"settled", "compensated"} and current is None:
                current = terminal_records.get(obligation_id)
            if not obligation_id or current is None or current.owner_ref != registration.owner_ref:
                raise ValueError("obligation_lifecycle_terminal_without_open")
            terminal_records[obligation_id] = current.model_copy(
                update={"status": status, "source_revision": event.stream_revision}, deep=True
            )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return ObligationLifecycleView(
            open=dict(sorted(open_records.items())),
            terminal=dict(sorted(terminal_records.items())),
            source_revision_vector=dict(sorted(revisions.items())),
        )

    @staticmethod
    def _source_refs_for_open_event(
        *,
        registration: ObligationLifecycleRegistration,
        event: GameplayEvent,
    ) -> tuple[str, ...]:
        refs = [registration.policy_ref, f"opening_event:{event.event_id}"]
        for key in ("source_event_id", "source_ref", "run_ref", "state_ref", "region_ref", "actor_ref"):
            value = event.payload.get(key)
            if isinstance(value, str) and value:
                refs.append(value)
        refs.append(f"stream:{event.stream_id}")
        return tuple(dict.fromkeys(refs))

    def _registration_for_open_event(self, event: GameplayEvent) -> ObligationLifecycleRegistration | None:
        policy_ref = event.payload.get("policy_ref") or event.payload.get("due_policy_ref")
        policy_revision = event.payload.get("policy_revision") or event.payload.get("due_policy_revision")
        if not isinstance(policy_ref, str) or not isinstance(policy_revision, str):
            return None
        registration = self._registrations.get((policy_ref, policy_revision))
        if registration is None or event.event_type != registration.opened_event_type:
            return None
        return registration if ObligationSettlementCoordinator._stream_matches(registration.stream_pattern, event.stream_id) else None

    def _registration_for_retry_event(self, event: GameplayEvent) -> ObligationLifecycleRegistration | None:
        return next(
            (
                registration
                for registration in self._registrations.values()
                if registration.event_type_for("retry") == event.event_type
                and ObligationSettlementCoordinator._stream_matches(registration.stream_pattern, event.stream_id)
            ),
            None,
        )

    def _registration_for_terminal_event(
        self, event: GameplayEvent
    ) -> tuple[ObligationLifecycleRegistration | None, Literal["settled", "cancelled", "expired", "compensated"] | None]:
        for registration in self._registrations.values():
            if not ObligationSettlementCoordinator._stream_matches(registration.stream_pattern, event.stream_id):
                continue
            if event.event_type == registration.event_type_for("settle"):
                return registration, "settled"
            if registration.event_type_for("cancel") is not None and event.event_type == registration.event_type_for("cancel"):
                return registration, "cancelled"
            if registration.event_type_for("expire") == event.event_type:
                return registration, "expired"
            if event.event_type in {
                registration.event_type_for("compensate"),
                *registration.additional_compensated_event_types,
            }:
                return registration, "compensated"
        return None, None


class ObligationSettlementCoordinator:
    """Read-only obligation validator/planner.

    It never owns a commit path and never calls
    ``GameplayEventStore.append_batch``. Existing authorities submit a planned
    batch through their own ``commit_obligation_batch`` method.
    """

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        authorized_owners: frozenset[str] | None = None,
        lifecycle_registrations: tuple[ObligationLifecycleRegistration, ...] = (),
    ) -> None:
        self.store = store
        self.authorized_owners = authorized_owners
        self._receipts: dict[str, SettlementReceipt] = {}
        self._registrations = {
            (item.policy_ref, item.policy_revision): self._registration_with_required_admission(item)
            for item in lifecycle_registrations
            if ObligationLifecycleContractRegistry.permits(item)
        }

    @classmethod
    def from_closed_registry(
        cls,
        *,
        store: GameplayEventStore,
        authorized_owners: frozenset[str] | None = None,
    ) -> "ObligationSettlementCoordinator":
        """Construct a planner against the canonical closed owner contracts."""
        return cls(
            store=store,
            authorized_owners=authorized_owners,
            lifecycle_registrations=ObligationLifecycleContractRegistry.closed_registrations(),
        )

    def settle(
        self,
        *,
        obligation: ScheduledObligation,
        fragments: tuple[OwnerAuthorizedFragment, ...],
        principal_ref: str,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None = None,
    ) -> ObligationSettlementResult:
        """Compatibility admission surface; it never executes an owner plan.

        Owners must obtain a batch through :meth:`plan_settle` and submit that
        batch through their own ``commit_obligation_batch`` method.  Retaining
        this method lets stale callers receive a structured zero-write failure
        while the finite owner rows are migrated.
        """
        plan = self.plan_settle(
            obligation=obligation,
            fragments=fragments,
            principal_ref=principal_ref,
        )
        return self._compatibility_plan_result(plan, obligation=obligation, owner_commit=owner_commit)

    def plan_settle(
        self,
        *,
        obligation: ScheduledObligation,
        fragments: tuple[OwnerAuthorizedFragment, ...],
        principal_ref: str,
    ) -> ObligationSettlementPlan:
        """Validate and materialize an owner-only settlement batch without writing."""
        registration = self._registration_for(obligation)
        if obligation.status not in {"open", "due", "retry", "retryable"}:
            return self._plan_failed("obligation_not_settleable")
        if registration is None:
            return self._plan_failed("obligation_policy_unregistered")
        if obligation.retry_policy and not (
            obligation.status == "retry"
            and registration is not None
            and registration.event_type_for("retry") is not None
        ):
            return self._plan_failed("obligation_retry_unsupported")
        if obligation.compensation_policy and not (
            registration is not None and registration.event_type_for("compensate") is not None
        ):
            return self._plan_failed("obligation_compensation_unsupported")
        if not fragments:
            return self._plan_failed("owner_fragments_required")
        if registration is not None and obligation.owner_ref != registration.owner_ref:
            return self._plan_failed("obligation_registration_owner_mismatch")
        if any(fragment.owner_principal_ref != obligation.owner_ref for fragment in fragments):
            return self._plan_failed("owner_fragment_mismatch")
        if registration is not None and not self._registration_stream_matches(registration, obligation):
            return self._plan_failed("obligation_registration_stream_mismatch")
        if registration is not None and obligation.visibility_scope != registration.visibility_scope:
            return self._plan_failed("obligation_registration_visibility_mismatch")
        if any(not self._fragment_matches_obligation(fragment, obligation) for fragment in fragments):
            return self._plan_failed("obligation_fragment_revision_mismatch")
        if not self._fragment_event_types_allowed(registration, fragments):
            return self._plan_failed("obligation_fragment_event_unregistered")
        if not self._fragment_visibility_allowed(registration, fragments):
            return self._plan_failed("obligation_fragment_visibility_mismatch")
        if registration is not None and not any(
            event_type == registration.event_type_for("settle")
            for fragment in fragments
            for events in fragment.event_specs.values()
            for event_type, _payload in events
        ):
            return self._plan_failed("obligation_lifecycle_event_missing")
        if registration is not None and registration.requires_expired_event_on_settle:
            if registration.event_type_for("expire") is None or not any(
                event_type == registration.event_type_for("expire")
                for fragment in fragments
                for events in fragment.event_specs.values()
                for event_type, _payload in events
            ):
                return self._plan_failed("obligation_lifecycle_event_missing")
        if self.authorized_owners is not None and any(fragment.owner_principal_ref not in self.authorized_owners for fragment in fragments):
            return self._plan_failed("owner_fragment_unauthorized")
        try:
            batch = AppendDerivedSettlementRecipe.from_fragments(
                command_id=f"obligation:{obligation.obligation_id}",
                idempotency_principal_ref=principal_ref,
                idempotency_key=obligation.idempotency_key,
                causation_id=obligation.obligation_id,
                correlation_id=f"obligation:{obligation.obligation_id}",
                fragments=fragments,
            ).batch
            batch = self._with_obligation_idempotency(self._with_outbox(batch, obligation, visibility_scope=registration.visibility_scope if registration else obligation.visibility_scope), operation="settle", obligation=obligation)
        except ValueError as exc:
            return self._plan_failed(str(exc))
        existing = self.store.get_by_idempotency(principal_ref, obligation.idempotency_key)
        if existing is not None and existing.committed:
            record = self.store.get_idempotency_record(principal_ref, obligation.idempotency_key)
            if record is None or record.payload_digest != batch.idempotency_record.payload_digest:
                return self._plan_failed("idempotency_key_reused")
            return self._planned_duplicate(
                result=existing,
                obligation=obligation,
                key=obligation.idempotency_key,
            )
        if (
            registration is not None
            and registration.requires_committed_open
            and not self._has_cancellable_source_event(obligation, registration)
        ):
            return self._plan_failed("obligation_lifecycle_not_open")
        if any(self.store.get_stream_head(stream) != revision for stream, revision in obligation.expected_revisions.items()):
            return self._plan_failed("revision_conflict")
        return ObligationSettlementPlan(
            ready=True,
            idempotency_status="new_commit",
            owner_commit_batch=batch,
        )

    def plan_retry(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
    ) -> ObligationSettlementPlan:
        """Validate and materialize an owner-only retry batch without writing."""
        registration = self._registration_for(obligation)
        if registration is None or registration.event_type_for("retry") is None:
            return self._plan_failed("obligation_retry_unsupported")
        policy = obligation.retry_policy
        attempt, maximum = policy.get("attempt"), policy.get("max_attempts")
        if (
            obligation.status not in {"open", "due", "retry"}
            or not isinstance(attempt, int)
            or isinstance(attempt, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or attempt < 1
            or maximum < attempt
            or fragment.owner_principal_ref != registration.owner_ref
            or not self._registration_stream_matches(registration, obligation)
            or not self._fragment_matches_obligation(fragment, obligation)
            or not self._fragment_event_types_allowed(registration, (fragment,))
            or not self._fragment_visibility_allowed(registration, (fragment,))
            or not self._has_cancellable_source_event(obligation, registration)
        ):
            return self._plan_failed("obligation_retry_rejected")
        if not any(
            event_type == registration.event_type_for("retry")
            for events in fragment.event_specs.values()
            for event_type, _payload in events
        ):
            return self._plan_failed("obligation_lifecycle_event_missing")
        key = f"{obligation.idempotency_key}:retry:{attempt}"
        try:
            batch = AppendDerivedSettlementRecipe.from_fragments(
                command_id=f"obligation:retry:{obligation.obligation_id}",
                idempotency_principal_ref=principal_ref,
                idempotency_key=key,
                causation_id=obligation.obligation_id,
                correlation_id=f"obligation:{obligation.obligation_id}:retry",
                fragments=(fragment,),
            ).batch
            batch = self._with_obligation_idempotency(
                self._with_outbox(batch, obligation, visibility_scope=registration.visibility_scope),
                operation="retry",
                obligation=obligation,
            )
        except ValueError as exc:
            return self._plan_failed(str(exc))
        existing = self.store.get_by_idempotency(principal_ref, key)
        if existing is not None and existing.committed:
            if not self._idempotency_payload_matches(principal_ref=principal_ref, key=key, batch=batch):
                return self._plan_failed("idempotency_key_reused")
            return self._planned_duplicate(result=existing, obligation=obligation, key=key)
        if any(self.store.get_stream_head(stream) != revision for stream, revision in obligation.expected_revisions.items()):
            return self._plan_failed("revision_conflict")
        return ObligationSettlementPlan(
            ready=True,
            idempotency_status="new_commit",
            owner_commit_batch=batch,
        )

    def retry(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None = None,
    ) -> ObligationSettlementResult:
        plan = self.plan_retry(
            obligation=obligation,
            fragment=fragment,
            principal_ref=principal_ref,
        )
        return self._compatibility_plan_result(plan, obligation=obligation, owner_commit=owner_commit)

    def plan_compensate(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
    ) -> ObligationSettlementPlan:
        """Validate and materialize a settled-only owner compensation batch without writing."""
        registration = self._registration_for(obligation)
        if registration is None or registration.event_type_for("compensate") is None:
            return self._plan_failed("obligation_compensation_unsupported")
        key = f"{obligation.idempotency_key}:compensate"
        try:
            batch = AppendDerivedSettlementRecipe.from_fragments(
                command_id=f"obligation:compensate:{obligation.obligation_id}",
                idempotency_principal_ref=principal_ref,
                idempotency_key=key,
                causation_id=obligation.obligation_id,
                correlation_id=f"obligation:{obligation.obligation_id}:compensate",
                fragments=(fragment,),
            ).batch
            batch = self._with_obligation_idempotency(
                self._with_outbox(batch, obligation, visibility_scope=registration.visibility_scope),
                operation="compensate",
                obligation=obligation,
            )
        except ValueError as exc:
            return self._plan_failed(str(exc))
        existing = self.store.get_by_idempotency(principal_ref, key)
        if existing is not None and existing.committed:
            if not self._idempotency_payload_matches(principal_ref=principal_ref, key=key, batch=batch):
                return self._plan_failed("idempotency_key_reused")
            return self._planned_duplicate(result=existing, obligation=obligation, key=key)
        lifecycle = ObligationLifecycleProjection(tuple(self._registrations.values())).rebuild(self.store.read_events())
        committed = lifecycle.terminal.get(obligation.obligation_id)
        if (
            obligation.status != "settled"
            or not obligation.compensation_policy
            or committed is None
            or committed.status != "settled"
            or committed.owner_ref != registration.owner_ref
            or fragment.owner_principal_ref != registration.owner_ref
            or not self._registration_stream_matches(registration, obligation)
            or not self._fragment_matches_obligation(fragment, obligation)
            or not self._fragment_event_types_allowed(registration, (fragment,))
            or not self._fragment_visibility_allowed(registration, (fragment,))
        ):
            return self._plan_failed("obligation_compensation_rejected")
        if not any(
            event_type in {
                registration.event_type_for("compensate"),
                *registration.additional_compensated_event_types,
            }
            for events in fragment.event_specs.values()
            for event_type, _payload in events
        ):
            return self._plan_failed("obligation_lifecycle_event_missing")
        if any(self.store.get_stream_head(stream) != revision for stream, revision in obligation.expected_revisions.items()):
            return self._plan_failed("revision_conflict")
        return ObligationSettlementPlan(
            ready=True,
            idempotency_status="new_commit",
            owner_commit_batch=batch,
        )

    def compensate(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None = None,
    ) -> ObligationSettlementResult:
        plan = self.plan_compensate(
            obligation=obligation,
            fragment=fragment,
            principal_ref=principal_ref,
        )
        return self._compatibility_plan_result(plan, obligation=obligation, owner_commit=owner_commit)

    def plan_cancel(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
        reason_ref: str,
        idempotency_key: str | None = None,
        idempotency_context: Mapping[str, Any] | None = None,
    ) -> ObligationSettlementPlan:
        """Validate and materialize an owner-only cancellation batch without writing."""
        registration = self._registration_for(obligation)
        if registration is None:
            return self._plan_failed("obligation_policy_unregistered")
        if registration.event_type_for("cancel") is None:
            return self._plan_failed("obligation_cancel_unsupported")
        if obligation.status not in {"open", "due"} or not reason_ref:
            return self._plan_failed("obligation_not_cancellable")
        if fragment.owner_principal_ref != registration.owner_ref:
            return self._plan_failed("owner_fragment_mismatch")
        if not self._registration_stream_matches(registration, obligation):
            return self._plan_failed("obligation_registration_stream_mismatch")
        if obligation.visibility_scope != registration.visibility_scope:
            return self._plan_failed("obligation_registration_visibility_mismatch")
        if not self._fragment_matches_obligation(fragment, obligation):
            return self._plan_failed("obligation_fragment_revision_mismatch")
        if not self._fragment_event_types_allowed(registration, (fragment,)):
            return self._plan_failed("obligation_fragment_event_unregistered")
        if not self._fragment_visibility_allowed(registration, (fragment,)):
            return self._plan_failed("obligation_fragment_visibility_mismatch")
        if not any(
            event_type == registration.event_type_for("cancel")
            for events in fragment.event_specs.values()
            for event_type, _payload in events
        ):
            return self._plan_failed("obligation_lifecycle_event_missing")
        cancellation_key = idempotency_key or f"{obligation.idempotency_key}:cancel:{reason_ref}"
        try:
            batch = AppendDerivedSettlementRecipe.from_fragments(
                command_id=f"obligation:cancel:{obligation.obligation_id}",
                idempotency_principal_ref=principal_ref,
                idempotency_key=cancellation_key,
                causation_id=obligation.obligation_id,
                correlation_id=f"obligation:{obligation.obligation_id}:cancel",
                fragments=(fragment,),
            ).batch
            batch = self._with_obligation_idempotency(
                self._with_outbox(batch, obligation, visibility_scope=registration.visibility_scope),
                operation="cancel",
                obligation=obligation,
                idempotency_context=idempotency_context,
            )
        except ValueError as exc:
            return self._plan_failed(str(exc))
        existing = self.store.get_by_idempotency(principal_ref, cancellation_key)
        if existing is not None and existing.committed:
            if not self._idempotency_payload_matches(principal_ref=principal_ref, key=cancellation_key, batch=batch):
                return self._plan_failed("idempotency_key_reused")
            return self._planned_duplicate(result=existing, obligation=obligation, key=cancellation_key)
        if any(self.store.get_stream_head(stream) != revision for stream, revision in obligation.expected_revisions.items()):
            return self._plan_failed("revision_conflict")
        if not self._has_cancellable_source_event(obligation, registration):
            return self._plan_failed("obligation_lifecycle_not_open")
        return ObligationSettlementPlan(
            ready=True,
            idempotency_status="new_commit",
            owner_commit_batch=batch,
        )

    def cancel(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
        reason_ref: str,
        idempotency_key: str | None = None,
        idempotency_context: Mapping[str, Any] | None = None,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None = None,
    ) -> ObligationSettlementResult:
        plan = self.plan_cancel(
            obligation=obligation,
            fragment=fragment,
            principal_ref=principal_ref,
            reason_ref=reason_ref,
            idempotency_key=idempotency_key,
            idempotency_context=idempotency_context,
        )
        return self._compatibility_plan_result(plan, obligation=obligation, owner_commit=owner_commit)

    def plan_expire(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
        reason_ref: str,
    ) -> ObligationSettlementPlan:
        """Validate and materialize an owner-only expiry batch without writing."""
        registration = self._registration_for(obligation)
        if registration is None or registration.event_type_for("expire") is None:
            return self._plan_failed("obligation_expiry_unsupported")
        if obligation.status not in {"open", "due", "retry"} or not reason_ref:
            return self._plan_failed("obligation_not_expirable")
        if fragment.owner_principal_ref != registration.owner_ref:
            return self._plan_failed("owner_fragment_mismatch")
        if not self._registration_stream_matches(registration, obligation):
            return self._plan_failed("obligation_registration_stream_mismatch")
        if obligation.visibility_scope != registration.visibility_scope:
            return self._plan_failed("obligation_registration_visibility_mismatch")
        if not self._fragment_matches_obligation(fragment, obligation):
            return self._plan_failed("obligation_fragment_revision_mismatch")
        if not self._fragment_event_types_allowed(registration, (fragment,)):
            return self._plan_failed("obligation_fragment_event_unregistered")
        if not self._fragment_visibility_allowed(registration, (fragment,)):
            return self._plan_failed("obligation_fragment_visibility_mismatch")
        if not any(
            event_type == registration.event_type_for("expire")
            for events in fragment.event_specs.values()
            for event_type, _payload in events
        ):
            return self._plan_failed("obligation_lifecycle_event_missing")
        expiry_key = f"{obligation.idempotency_key}:expire:{reason_ref}"
        try:
            batch = AppendDerivedSettlementRecipe.from_fragments(
                command_id=f"obligation:expire:{obligation.obligation_id}",
                idempotency_principal_ref=principal_ref,
                idempotency_key=expiry_key,
                causation_id=obligation.obligation_id,
                correlation_id=f"obligation:{obligation.obligation_id}:expire",
                fragments=(fragment,),
            ).batch
            batch = self._with_obligation_idempotency(
                self._with_outbox(batch, obligation, visibility_scope=registration.visibility_scope),
                operation="expire",
                obligation=obligation,
            )
        except ValueError as exc:
            return self._plan_failed(str(exc))
        existing = self.store.get_by_idempotency(principal_ref, expiry_key)
        if existing is not None and existing.committed:
            if not self._idempotency_payload_matches(principal_ref=principal_ref, key=expiry_key, batch=batch):
                return self._plan_failed("idempotency_key_reused")
            return self._planned_duplicate(result=existing, obligation=obligation, key=expiry_key)
        if any(self.store.get_stream_head(stream) != revision for stream, revision in obligation.expected_revisions.items()):
            return self._plan_failed("revision_conflict")
        if not self._has_cancellable_source_event(obligation, registration):
            return self._plan_failed("obligation_lifecycle_not_open")
        return ObligationSettlementPlan(
            ready=True,
            idempotency_status="new_commit",
            owner_commit_batch=batch,
        )

    def expire(
        self,
        *,
        obligation: ScheduledObligation,
        fragment: OwnerAuthorizedFragment,
        principal_ref: str,
        reason_ref: str,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None = None,
    ) -> ObligationSettlementResult:
        """Record a due owner obligation as expired through its registered fragment."""
        plan = self.plan_expire(
            obligation=obligation,
            fragment=fragment,
            principal_ref=principal_ref,
            reason_ref=reason_ref,
        )
        return self._compatibility_plan_result(plan, obligation=obligation, owner_commit=owner_commit)

    def replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-time-obligation", projector_version="1")
        events = self.store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def project_receipt(self, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        receipts = list(self._receipts.values())
        if not receipts:
            return {"committed_event_ids": (), "audit_refs": ()}
        receipt = receipts[-1]
        return {
            "committed_event_ids": receipt.committed_event_ids,
            "stream_revisions": receipt.stream_revisions,
            "audit_refs": receipt.audit_refs if scope == "authority" else (),
        }

    def registration_for(self, obligation: ScheduledObligation) -> ObligationLifecycleRegistration | None:
        """Expose the admitted closed contract without exposing a writer."""
        return self._registration_for(obligation)

    @staticmethod
    def _failed(code: str) -> ObligationSettlementResult:
        return ObligationSettlementResult(committed=False, error_code=code)

    @staticmethod
    def _plan_failed(code: str) -> ObligationSettlementPlan:
        return ObligationSettlementPlan(ready=False, error_code=code)

    def _planned_duplicate(
        self,
        *,
        result: AppendBatchResult,
        obligation: ScheduledObligation,
        key: str,
    ) -> ObligationSettlementPlan:
        return ObligationSettlementPlan(
            ready=False,
            idempotency_status="duplicate_replayed",
            duplicate_result=result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
            receipt=self._receipts.get(key) or self._receipt(result, obligation),
        )

    def _compatibility_plan_result(
        self,
        plan: ObligationSettlementPlan,
        *,
        obligation: ScheduledObligation,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None,
    ) -> ObligationSettlementResult:
        """Reject legacy coordinator execution without ever invoking an owner callback."""
        if not plan.ready:
            return self._failed(plan.error_code or "obligation_plan_rejected")
        owner_error = self._owner_commit_error(owner_commit=owner_commit, obligation=obligation)
        if owner_error is not None:
            return self._failed(owner_error)
        return self._failed("coordinator_direct_write_disallowed")

    @staticmethod
    def _owner_commit_error(
        *,
        owner_commit: Callable[[AtomicEventBatch], AppendBatchResult] | None,
        obligation: ScheduledObligation,
    ) -> str | None:
        if owner_commit is None:
            return "coordinator_owner_commit_required"
        owner = getattr(owner_commit, "__self__", None)
        if (
            owner is None
            or getattr(owner, "_PRINCIPAL", None) != obligation.owner_ref
            or getattr(owner_commit, "__name__", None) != "commit_obligation_batch"
        ):
            return "owner_commit_authority_mismatch"
        return None

    def _registration_for(self, obligation: ScheduledObligation) -> ObligationLifecycleRegistration | None:
        policy_ref = next((ref for ref in obligation.source_refs if ref.startswith("policy:")), None)
        if policy_ref is None:
            return None
        return self._registrations.get((policy_ref, obligation.policy_revision))

    @staticmethod
    def _registration_with_required_admission(
        registration: ObligationLifecycleRegistration,
    ) -> ObligationLifecycleRegistration:
        canonical = ObligationLifecycleContractRegistry.require(
            policy_ref=registration.policy_ref,
            policy_revision=registration.policy_revision,
        )
        return registration.model_copy(
            update={
                "requires_committed_open": canonical.requires_committed_open,
                "requires_expired_event_on_settle": canonical.requires_expired_event_on_settle,
            },
            deep=True,
        )

    @staticmethod
    def _registration_stream_matches(
        registration: ObligationLifecycleRegistration, obligation: ScheduledObligation
    ) -> bool:
        if len(obligation.expected_revisions) != 1:
            return False
        return ObligationSettlementCoordinator._stream_matches(
            registration.stream_pattern, next(iter(obligation.expected_revisions))
        )

    @staticmethod
    def _stream_matches(stream_pattern: str, stream_id: str) -> bool:
        pattern = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", r".+", stream_pattern)
        return re.fullmatch(pattern, stream_id) is not None

    @staticmethod
    def _fragment_matches_obligation(
        fragment: OwnerAuthorizedFragment, obligation: ScheduledObligation
    ) -> bool:
        return (
            fragment.expected_revisions == obligation.expected_revisions
            and set(fragment.event_specs) == set(obligation.expected_revisions)
        )

    @staticmethod
    def _fragment_event_types_allowed(
        registration: ObligationLifecycleRegistration,
        fragments: tuple[OwnerAuthorizedFragment, ...],
    ) -> bool:
        canonical = ObligationLifecycleContractRegistry.require(
            policy_ref=registration.policy_ref,
            policy_revision=registration.policy_revision,
        )
        allowed = set(registration.allowed_event_types or canonical.allowed_event_types)
        if not allowed:
            return False
        return all(
            event_type in allowed
            for fragment in fragments
            for events in fragment.event_specs.values()
            for event_type, _payload in events
        )

    @staticmethod
    def _fragment_visibility_allowed(
        registration: ObligationLifecycleRegistration,
        fragments: tuple[OwnerAuthorizedFragment, ...],
    ) -> bool:
        return all(
            all(
                policy == registration.visibility_scope
                for policy in (
                    fragment.event_visibility_policies.get(stream_id)
                    or tuple("project" for _ in events)
                )
            )
            for fragment in fragments
            for stream_id, events in fragment.event_specs.items()
        )

    def _idempotency_payload_matches(self, *, principal_ref: str, key: str, batch) -> bool:
        record = self.store.get_idempotency_record(principal_ref, key)
        return record is not None and record.payload_digest == batch.idempotency_record.payload_digest

    @staticmethod
    def _with_obligation_idempotency(
        batch,
        *,
        operation: str,
        obligation: ScheduledObligation,
        idempotency_context: Mapping[str, Any] | None = None,
    ):
        """Bind the append idempotency digest to the complete owner obligation input."""
        digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "batch_digest": batch.idempotency_record.payload_digest,
                    "operation": operation,
                    "obligation": obligation.model_dump(mode="json"),
                    "idempotency_context": dict(idempotency_context or {}),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return batch.model_copy(
            update={"idempotency_record": batch.idempotency_record.model_copy(update={"payload_digest": digest})},
            deep=True,
        )

    def _has_cancellable_source_event(
        self,
        obligation: ScheduledObligation,
        registration: ObligationLifecycleRegistration,
    ) -> bool:
        stream_id = next(iter(obligation.expected_revisions), "")
        if not stream_id:
            return False
        events = [event for event in self.store.read_events() if event.stream_id == stream_id]
        state_event_refs = {
            source_ref.removeprefix("state_event:")
            for source_ref in obligation.source_refs
            if source_ref.startswith("state_event:")
        }
        started = any(
            event.event_type == registration.opened_event_type
            and (
                event.payload.get("obligation_id") == obligation.obligation_id
                or event.payload.get("due_obligation_id") == obligation.obligation_id
            )
            and (
                event.payload.get("policy_ref") in obligation.source_refs
                or event.payload.get("due_policy_ref") in obligation.source_refs
            )
            and (
                event.payload.get("policy_revision") == obligation.policy_revision
                or event.payload.get("due_policy_revision") == obligation.policy_revision
            )
            and (
                not state_event_refs
                or event.payload.get("state_event_id") in state_event_refs
            )
            for event in events
        )
        due_matches = any(
            event.event_type == registration.opened_event_type
            and event.payload.get("obligation_id", event.payload.get("due_obligation_id")) == obligation.obligation_id
            and event.payload.get("due_tick", event.payload.get("finish_tick")) == obligation.due_tick
            for event in events
        )
        if obligation.status == "retry":
            due_matches = any(
                event.event_type == registration.event_type_for("retry")
                and event.payload.get("obligation_id") == obligation.obligation_id
                and event.payload.get("next_due_tick") == obligation.due_tick
                for event in events
            )
        terminal = any(
            event.event_type in {
                registration.event_type_for("settle"),
                registration.event_type_for("cancel"),
                registration.event_type_for("expire"),
                registration.event_type_for("compensate"),
                *registration.additional_compensated_event_types,
            }
            and event.payload.get("obligation_id") == obligation.obligation_id
            for event in events
        )
        return started and due_matches and not terminal

    @staticmethod
    def _with_outbox(batch, obligation: ScheduledObligation, *, visibility_scope: str):
        return batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.obligation.scoped_projection",
                            audience=visibility_scope,
                        payload_projection={"obligation_id": obligation.obligation_id, "owner_ref": obligation.owner_ref},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )

    @staticmethod
    def _receipt(result: AppendBatchResult, obligation: ScheduledObligation) -> SettlementReceipt:
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"obligation:{obligation.obligation_id}",),
            pinned_revisions={"policy": 1},
        )


__all__ = [
    "ObligationLifecycleContractRegistry",
    "ObligationLifecycleProjection",
    "ObligationLifecycleRecord",
    "ObligationLifecycleRegistration",
    "ObligationLifecycleView",
    "ObligationSettlementCoordinator",
    "ObligationSettlementPlan",
    "ObligationSettlementResult",
]
