"""Fixed-offer Econ-1 economy owner; no market discovery or NPC state."""

from __future__ import annotations

from hashlib import sha256
import json

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayFailure, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.settlement_plan import SettlementPlan, build_atomic_event_batch, build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SettlementReceipt
from app.gameplay.economy_runtime import EconomyProjector, EconomyRuntimeError


class MarketQuote(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    quote_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    unit_price: float = Field(gt=0)
    quantity_limit: int = Field(gt=0)
    valid_until_tick: int = Field(ge=0)
    public_digest: str = Field(min_length=1)


class PurchasePosting(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    posting_ref: str = Field(min_length=1)
    quote_ref: str = Field(min_length=1)
    buyer_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    total_amount: float = Field(gt=0)
    tax_ref: str | None = None


class SalePosting(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    posting_ref: str = Field(min_length=1)
    seller_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    total_amount: float = Field(gt=0)
    demand_digest: str = Field(min_length=1)


class EconomicObligation(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    obligation_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    amount: float = Field(ge=0)
    due_tick: int = Field(ge=0)
    status: str = "due"


class OperatingWindow(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    window_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    opens_at_tick: int = Field(ge=0)
    closes_at_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    status: str = "planned"


class WageAccrual(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    accrual_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    payee_actor_ref: str = Field(pattern=r"^character:")
    work_evidence_refs: tuple[str, ...] = Field(min_length=1)
    wage_policy_revision: str = Field(min_length=1)
    amount: float = Field(gt=0)
    status: str = "accrued"


class BusinessPeriod(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    period_ref: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    policy_revision: str = Field(min_length=1)
    revenue: float = 0
    cost: float = 0
    tax: float = 0
    obligations: tuple[EconomicObligation, ...] = ()
    closed: bool = False

    @property
    def result_digest(self) -> str:
        payload = self.model_dump(mode="json")
        return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EconomyAuthority:
    _PRINCIPAL = "actor_gameplay.econ1_economy_domain"
    _P2DR_ORGANIZATION_REF = "org:bakery-authored"
    _P2DR_COUNTER_REF = "character:char_c"
    _P2DR_COUNTER_WORK_ORDER_REF = "work:flour"
    _P2DR_COUNTER_ROLE = "counter/procurement"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def commit_obligation_batch(self, batch: AtomicEventBatch) -> AppendBatchResult:
        """Commit only an Economy wage-owned lifecycle plan."""
        if not batch.owner_fragments or any(
            fragment.owner_principal_ref != self._PRINCIPAL
            or any(not event.stream_id.startswith("gameplay:economy:wage:") for event in batch.events)
            for fragment in batch.owner_fragments
        ):
            return self._rejected_append(batch.command_id, "economy_wage_owner_commit_scope_denied")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-wage-accrual-obligation@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=tuple(sorted({event.stream_id for event in batch.events})),
                event_types=tuple(event.event_type for event in batch.events),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(batch.command_id, str(error))
        return self._store.append_batch(batch)

    @staticmethod
    def _rejected_append(command_id: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="economy_wage_obligation_commit"),
        )

    @classmethod
    def wage_obligation_lifecycle_registration(cls):
        """Return the closed lifecycle contract owned by the wage authority."""
        from app.world_runtime.obligations import ObligationLifecycleRegistration

        return ObligationLifecycleRegistration(
            policy_ref="policy:economy_wage_accrual",
            policy_revision="1",
            owner_ref=cls._PRINCIPAL,
            stream_pattern="gameplay:economy:wage:{worker_ref}",
            opened_event_type="gameplay.economy.wage_obligation_opened",
            settled_event_type="gameplay.economy.wage_obligation_settled",
            cancelled_event_type="gameplay.economy.wage_obligation_cancelled",
            retry_event_type="gameplay.economy.wage_obligation_retry_scheduled",
            compensated_event_type="gameplay.economy.wage_obligation_compensated",
            expired_event_type="gameplay.economy.wage_obligation_expired",
            visibility_scope="project",
        )

    def open_wage_obligation(
        self,
        *,
        command: GameplayCommandEnvelope,
        accrual_ref: str,
        organization_ref: str,
        work_evidence_refs: tuple[str, ...],
        wage_amount_minor: int,
        due_tick: int,
        policy_revision: str,
    ) -> AppendBatchResult:
        """Open the one registered wage-accrual obligation on its owner stream."""
        worker_ref = command.actor_ref
        stream_id = f"gameplay:economy:wage:{worker_ref}" if worker_ref else ""
        if (
            command.principal_ref != self._PRINCIPAL
            or command.source_ref != self._PRINCIPAL
            or not worker_ref or not worker_ref.startswith("character:")
            or set(command.expected_revisions) != {stream_id}
        ):
            return self._rejected(command, "economy_wage_obligation_owner_required")
        if command.payload.get("visibility_scope") != "project":
            return self._rejected(command, "economy_wage_obligation_privacy_denied")
        semantic_effect_ref = command.payload.get("semantic_effect_ref")
        semantic_snapshot_digest = command.payload.get("semantic_snapshot_digest")
        if (semantic_effect_ref is None) != (semantic_snapshot_digest is None) or (
            semantic_effect_ref is not None
            and (
                semantic_effect_ref != "effect:wage_accrual_due"
                or not isinstance(semantic_snapshot_digest, str)
                or not semantic_snapshot_digest
            )
        ):
            return self._rejected(command, "economy_wage_obligation_semantic_metadata_invalid")
        if (
            not accrual_ref
            or not organization_ref
            or not work_evidence_refs
            or any(not ref for ref in work_evidence_refs)
            or wage_amount_minor <= 0
            or due_tick < 0
            or not policy_revision
        ):
            return self._rejected(command, "economy_wage_obligation_invalid")
        obligation_id = f"obligation:economy:wage:{worker_ref}:{accrual_ref}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
        if existing is None and command.expected_revisions != {stream_id: self._store.get_stream_head(stream_id)}:
            return self._rejected(command, "revision_conflict")
        if existing is None and any(
            event.event_type == "gameplay.economy.wage_obligation_opened"
            and event.payload.get("obligation_id") == obligation_id
            for event in self._store.read_stream(stream_id)
        ):
            return self._rejected(command, "economy_wage_obligation_already_open")
        event_payload = {
            "obligation_id": obligation_id,
            "accrual_ref": accrual_ref,
            "organization_ref": organization_ref,
            "payee_actor_ref": worker_ref,
            "work_evidence_refs": work_evidence_refs,
            "amount": wage_amount_minor,
            "due_tick": due_tick,
            "policy_ref": "policy:economy_wage_accrual",
            "policy_revision": policy_revision,
        }
        if semantic_effect_ref is not None:
            event_payload.update(
                {
                    "semantic_effect_ref": semantic_effect_ref,
                    "semantic_snapshot_digest": semantic_snapshot_digest,
                }
            )
        envelope = command.model_copy(
            update={
                "payload": {
                    "stream_ref": stream_id,
                    "event_type": "gameplay.economy.wage_obligation_opened",
                    "visibility_policy": "project",
                    **event_payload,
                }
            },
            deep=True,
        )
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-wage-accrual-obligation@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=("gameplay.economy.wage_obligation_opened",),
                projection_scope="project",
            )
            batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="economy.wage_obligation.scoped_projection",
                            audience="project",
                            payload_projection={"obligation_id": obligation_id, "payee_actor_ref": worker_ref},
                        )
                        for event in batch.events
                    ]
                },
                deep=True,
            )
            return self._store.append_batch(batch)
        except ValueError as exc:
            return self._rejected(command, str(exc))

    def build_wage_obligation_settlement_fragment(self, *, obligation) -> OwnerAuthorizedFragment:
        """Build the wage owner consequence; the coordinator remains the sole assembler."""
        stream_id = next(iter(obligation.expected_revisions), "")
        expected_revision = obligation.expected_revisions.get(stream_id)
        if (
            obligation.owner_ref != self._PRINCIPAL
            or not stream_id.startswith("gameplay:economy:wage:character:")
            or expected_revision is None
            or "policy:economy_wage_accrual" not in obligation.source_refs
        ):
            raise ValueError("economy_wage_obligation_invalid")
        opening = next(
            (
                event
                for event in self._store.read_stream(stream_id)
                if event.event_type == "gameplay.economy.wage_obligation_opened"
                and event.payload.get("obligation_id") == obligation.obligation_id
                and event.payload.get("policy_ref") == "policy:economy_wage_accrual"
                and event.payload.get("policy_revision") == obligation.policy_revision
            ),
            None,
        )
        if opening is None:
            raise ValueError("economy_wage_obligation_source_missing")
        payload = opening.payload
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:wage-settle:{obligation.obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:wage-obligation-settlement",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"economy_wage_policy": 1},
            event_specs={
                stream_id: (
                    (
                        "gameplay.economy.wage_accrued",
                        {
                            "obligation_id": obligation.obligation_id,
                            "accrual_ref": payload["accrual_ref"],
                            "organization_ref": payload["organization_ref"],
                            "payee_actor_ref": payload["payee_actor_ref"],
                            "work_evidence_refs": payload["work_evidence_refs"],
                            "wage_policy_revision": payload["policy_revision"],
                            "amount": payload["amount"],
                            "status": "accrued",
                        },
                    ),
                    ("gameplay.economy.wage_obligation_settled", {"obligation_id": obligation.obligation_id}),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    def build_wage_obligation_retry_fragment(
        self, *, obligation, next_due_tick: int
    ) -> OwnerAuthorizedFragment:
        """Economy owns the bounded retry cursor for its admitted wage row."""
        stream_id, opening = self._wage_obligation_source(obligation)
        policy = obligation.retry_policy
        attempt, maximum = policy.get("attempt"), policy.get("max_attempts")
        if (
            not isinstance(attempt, int)
            or isinstance(attempt, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or attempt < 1
            or attempt > maximum
            or next_due_tick < obligation.due_tick
        ):
            raise ValueError("economy_wage_obligation_retry_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:wage-retry:{obligation.obligation_id}:{attempt}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:wage-obligation-retry",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy_wage_policy": 1, "wage_opening": opening.stream_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.economy.wage_obligation_retry_scheduled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "policy_ref": "policy:economy_wage_accrual",
                            "policy_revision": obligation.policy_revision,
                            "attempt": attempt,
                            "max_attempts": maximum,
                            "next_due_tick": next_due_tick,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project",)},
        )

    def build_wage_obligation_cancel_fragment(
        self, *, obligation, reason_ref: str
    ) -> OwnerAuthorizedFragment:
        """Economy may cancel only its committed open wage obligation."""
        stream_id, opening = self._wage_obligation_source(obligation)
        if not reason_ref:
            raise ValueError("economy_wage_obligation_cancel_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:wage-cancel:{obligation.obligation_id}:{reason_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:wage-obligation-cancel",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy_wage_policy": 1, "wage_opening": opening.stream_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.economy.wage_obligation_cancelled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "cancelled",
                            "policy_ref": "policy:economy_wage_accrual",
                            "policy_revision": obligation.policy_revision,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project",)},
        )

    def build_wage_obligation_expiry_fragment(
        self, *, obligation, reason_ref: str
    ) -> OwnerAuthorizedFragment:
        """Economy may expire only its committed, unsettled wage obligation."""
        stream_id, opening = self._wage_obligation_source(obligation)
        if not reason_ref:
            raise ValueError("economy_wage_obligation_expiry_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:wage-expire:{obligation.obligation_id}:{reason_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:wage-obligation-expiry",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy_wage_policy": 1, "wage_opening": opening.stream_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.economy.wage_obligation_expired",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "expired",
                            "policy_ref": "policy:economy_wage_accrual",
                            "policy_revision": obligation.policy_revision,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project",)},
        )

    def build_wage_obligation_compensation_fragment(
        self, *, obligation, reason_ref: str
    ) -> OwnerAuthorizedFragment:
        """Reverse only the accrued wage fact; payment/account truth is excluded."""
        stream_id, opening = self._wage_obligation_source(obligation)
        if not reason_ref or obligation.status != "settled" or not obligation.compensation_policy:
            raise ValueError("economy_wage_obligation_compensation_invalid")
        settled = any(
            event.event_type == "gameplay.economy.wage_obligation_settled"
            and event.payload.get("obligation_id") == obligation.obligation_id
            for event in self._store.read_stream(stream_id)
        )
        if not settled:
            raise ValueError("economy_wage_obligation_settlement_missing")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:wage-compensate:{obligation.obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:wage-obligation-compensation",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy_wage_policy": 1, "wage_opening": opening.stream_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.economy.wage_accrual_compensated",
                        {
                            "obligation_id": obligation.obligation_id,
                            "accrual_ref": opening.payload["accrual_ref"],
                            "payee_actor_ref": opening.payload["payee_actor_ref"],
                            "reason_ref": reason_ref,
                        },
                    ),
                    (
                        "gameplay.economy.wage_obligation_compensated",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": "settled",
                            "current_state": "compensated",
                            "policy_ref": "policy:economy_wage_accrual",
                            "policy_revision": obligation.policy_revision,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    def _wage_obligation_source(self, obligation) -> tuple[str, object]:
        stream_id = next(iter(obligation.expected_revisions), "")
        expected_revision = obligation.expected_revisions.get(stream_id)
        if (
            obligation.owner_ref != self._PRINCIPAL
            or not stream_id.startswith("gameplay:economy:wage:character:")
            or expected_revision is None
            or "policy:economy_wage_accrual" not in obligation.source_refs
        ):
            raise ValueError("economy_wage_obligation_invalid")
        opening = next(
            (
                event
                for event in self._store.read_stream(stream_id)
                if event.event_type == "gameplay.economy.wage_obligation_opened"
                and event.payload.get("obligation_id") == obligation.obligation_id
                and event.payload.get("policy_ref") == "policy:economy_wage_accrual"
                and event.payload.get("policy_revision") == obligation.policy_revision
            ),
            None,
        )
        if opening is None:
            raise ValueError("economy_wage_obligation_source_missing")
        return stream_id, opening

    @staticmethod
    def _rejected(command: GameplayCommandEnvelope, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=command.transaction_id or f"transaction:{command.command_id}",
            command_id=command.command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="economy_wage_obligation"),
        )

    @classmethod
    def build_commerce_wage_accrual_fragment(
        cls,
        *,
        commitment_ref: str,
        organization_ref: str,
        worker_ref: str,
        wage_obligation_ref: str,
        work_evidence_refs: tuple[str, ...],
        wage_amount_minor: int,
        wage_policy_revision: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        """Economy-owned labor consequence; commerce only references the contract."""
        if not work_evidence_refs or wage_amount_minor <= 0 or not worker_ref.startswith("character:"):
            raise ValueError("commerce_wage_accrual_invalid")
        stream_id = f"gameplay:economy:wage:{worker_ref}"
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:wage:{commitment_ref}:{worker_ref}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="economy:commerce-labor-accrual",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={f"wage:{worker_ref}": expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.economy.wage_accrued",
                        {
                            "accrual_ref": wage_obligation_ref,
                            "commitment_ref": commitment_ref,
                            "organization_ref": organization_ref,
                            "payee_actor_ref": worker_ref,
                            "work_evidence_refs": work_evidence_refs,
                            "wage_policy_revision": wage_policy_revision,
                            "amount": wage_amount_minor,
                            "status": "accrued",
                        },
                    ),
                )
            },
        )

    def settle_production_evidence_wage_accrual(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        organization_ref: str,
        worker_ref: str,
        wage_obligation_ref: str,
        work_evidence_refs: tuple[str, ...],
        production_evidence_projection_digest: str,
        production_evidence_source_event_refs: tuple[str, ...],
        production_evidence_source_revision_vector: dict[str, int],
        production_wage_plan_digest: str,
        wage_amount_minor: int,
        wage_policy_revision: str,
        expected_wage_revision: int,
    ):
        """The lone Economy-owned consumer for frozen Production evidence."""
        if (
            not organization_ref
            or not worker_ref.startswith("character:")
            or not wage_obligation_ref
            or not work_evidence_refs
            or not production_evidence_projection_digest.startswith("sha256:")
            or not production_evidence_source_event_refs
            or not production_evidence_source_revision_vector
            or not production_wage_plan_digest.startswith("sha256:")
            or wage_amount_minor <= 0
            or not wage_policy_revision
        ):
            raise ValueError("production_wage_accrual_invalid")
        wage_stream = f"gameplay:economy:wage:{worker_ref}"
        if self._store.get_stream_head(wage_stream) != expected_wage_revision:
            raise ValueError("revision_conflict")
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.economy.accrue_production_wage",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=worker_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={wage_stream: expected_wage_revision},
            read_set_revisions=dict(production_evidence_source_revision_vector),
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=production_evidence_source_event_refs[0],
            submitted_at="production-evidence-wage",
            pinned_revisions={
                **{f"production:{stream_id}": revision for stream_id, revision in production_evidence_source_revision_vector.items()},
                f"wage_policy:{wage_policy_revision}": 1,
            },
            payload={
                "stream_ref": wage_stream,
                "event_type": "gameplay.economy.wage_accrued",
                "visibility_policy": f"actor:{worker_ref}",
                "accrual_ref": wage_obligation_ref,
                "organization_ref": organization_ref,
                "payee_actor_ref": worker_ref,
                "work_evidence_refs": work_evidence_refs,
                "wage_policy_revision": wage_policy_revision,
                "amount": wage_amount_minor,
                "status": "accrued",
                "production_evidence_projection_digest": production_evidence_projection_digest,
                "production_evidence_source_event_refs": production_evidence_source_event_refs,
                "production_evidence_source_revision_vector": dict(production_evidence_source_revision_vector),
                "production_wage_plan_digest": production_wage_plan_digest,
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:event:{command_id}:1",
                        transaction_id=batch.transaction_id,
                        event_id=batch.events[0].event_id,
                        global_sequence=0,
                        topic="economy.wage.scoped_projection",
                        audience=f"actor:{worker_ref}",
                        payload_projection={
                            "accrual_ref": wage_obligation_ref,
                            "evidence_ref": work_evidence_refs[0],
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    @staticmethod
    def validate_quote(quote: MarketQuote, *, tick: int, quantity: int) -> None:
        if tick > quote.valid_until_tick:
            raise ValueError("quote_expired")
        if quantity > quote.quantity_limit:
            raise ValueError("quote_quantity_exhausted")

    @staticmethod
    def _scheduled_procurement_rejected(
        *, command_id: str, error_code: str
    ) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=error_code,
                message=error_code,
                failed_stage="economy_scheduled_procurement",
            ),
        )

    def settle_scheduled_procurement(
        self,
        *,
        quote: MarketQuote,
        posting: PurchasePosting,
        organization_schedule: object,
        recipient_ref: str,
        work_order_ref: str,
        observed_at: str,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        """Commit the one admitted counter-work purchase after re-reading its schedule."""
        organization_ref = str(getattr(organization_schedule, "organization_ref", ""))
        if (
            not recipient_ref.startswith("character:")
            or not work_order_ref
            or not organization_ref.startswith("org:")
            or posting.buyer_ref != organization_ref
            or str(getattr(organization_schedule, "owner_principal_ref", ""))
            != OrganizationAuthority._PRINCIPAL
        ):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_procurement_invalid",
            )
        if (
            organization_ref != self._P2DR_ORGANIZATION_REF
            or recipient_ref != self._P2DR_COUNTER_REF
            or work_order_ref != self._P2DR_COUNTER_WORK_ORDER_REF
        ):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="scheduled_procurement_unsupported",
            )
        if str(getattr(organization_schedule, "recipient_ref", recipient_ref)) != recipient_ref:
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_recipient_denied",
            )
        source_rows = tuple(
            row
            for row in getattr(organization_schedule, "work_orders", ())
            if row.get("work_order_ref") == work_order_ref
            and row.get("recipient_ref") == recipient_ref
            and row.get("role") == self._P2DR_COUNTER_ROLE
        )
        if not source_rows:
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_recipient_denied",
            )
        if any(
            row.get("visibility_scope") != f"actor:{recipient_ref}"
            for row in source_rows
        ):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_privacy_denied",
            )
        validate_against = getattr(organization_schedule, "validate_against", None)
        if not callable(validate_against) or not validate_against(store=self._store):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_revision_conflict",
            )
        canonical_schedule = OrganizationAuthority(store=self._store).schedule_view_for(
            organization_ref=organization_ref,
            recipient_ref=recipient_ref,
            observed_at=observed_at,
        )
        if (
            canonical_schedule.projection_hash
            != getattr(organization_schedule, "projection_hash", "")
            or canonical_schedule.source_revision_vector
            != getattr(organization_schedule, "source_revision_vector", {})
        ):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_forged",
            )
        canonical_rows = tuple(
            row
            for row in canonical_schedule.work_orders
            if row.get("work_order_ref") == work_order_ref
            and row.get("recipient_ref") == recipient_ref
            and row.get("role") == self._P2DR_COUNTER_ROLE
        )
        if not canonical_rows:
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_work_order_missing",
            )
        if any(
            row.get("visibility_scope") != f"actor:{recipient_ref}"
            for row in canonical_rows
        ):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="organization_schedule_privacy_denied",
            )
        try:
            self.validate_quote(quote, tick=tick, quantity=posting.quantity)
        except ValueError as exc:
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code=str(exc),
            )
        if (
            posting.quote_ref != quote.quote_ref
            or posting.total_amount != quote.unit_price * posting.quantity
        ):
            return self._scheduled_procurement_rejected(
                command_id=command_id,
                error_code="purchase_posting_invalid",
            )
        stream_id = f"gameplay:economy:{posting.buyer_ref}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        expected_revision = (
            existing.resulting_stream_revisions.get(stream_id, 0) - 1
            if existing is not None
            else self._store.get_stream_head(stream_id)
        )
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.economy.settle_scheduled_procurement",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=recipient_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            read_set_revisions=dict(canonical_schedule.source_revision_vector),
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=OrganizationAuthority._PRINCIPAL,
            submitted_at=observed_at,
            pinned_revisions={
                f"organization_schedule:{stream}": revision
                for stream, revision in canonical_schedule.source_revision_vector.items()
            },
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.economy.purchase_posted",
                "visibility_policy": f"actor:{recipient_ref}",
                **posting.model_dump(mode="json"),
                "item_ref": quote.item_ref,
                "tick": tick,
                "organization_ref": organization_ref,
                "recipient_ref": recipient_ref,
                "work_order_ref": work_order_ref,
                "organization_schedule_projection_digest": canonical_schedule.projection_hash,
                "organization_schedule_source_revisions": dict(
                    canonical_schedule.source_revision_vector
                ),
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.procurement_work.scoped_projection",
                        audience=f"actor:{recipient_ref}",
                        payload_projection={
                            "posting_ref": posting.posting_ref,
                            "work_order_ref": work_order_ref,
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def open_window(
        self,
        window: OperatingWindow,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        visibility_scope: str = "project",
    ):
        result = OrganizationAuthority(store=self._store).open_operating_window(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            window=window,
            visibility_scope=visibility_scope,
        )
        self._raise_window_compat_error(result)
        return result

    def close_window(
        self,
        window: OperatingWindow,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        visibility_scope: str = "project",
        expected_stream_revision: int | None = None,
    ):
        if expected_stream_revision is None:
            expected_stream_revision = self._store.get_stream_head(
                f"gameplay:organization:window:{window.window_ref}"
            )
        result = OrganizationAuthority(store=self._store).close_operating_window(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            organization_ref=window.organization_ref,
            window_ref=window.window_ref,
            expected_stream_revision=expected_stream_revision,
            visibility_scope=visibility_scope,
        )
        self._raise_window_compat_error(result)
        return result

    def evaluate_due(
        self,
        window: OperatingWindow,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        visibility_scope: str = "project",
        expected_stream_revision: int | None = None,
    ):
        if expected_stream_revision is None:
            expected_stream_revision = self._store.get_stream_head(
                f"gameplay:organization:window:{window.window_ref}"
            )
        result = OrganizationAuthority(store=self._store).record_operating_window_due(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            organization_ref=window.organization_ref,
            window_ref=window.window_ref,
            expected_stream_revision=expected_stream_revision,
            visibility_scope=visibility_scope,
        )
        self._raise_window_compat_error(result)
        return result

    def accrue_wage(self, accrual: WageAccrual, *, completed_evidence_refs: set[str], command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        if not set(accrual.work_evidence_refs).issubset(completed_evidence_refs):
            raise ValueError("work_evidence_invalid")
        return self._settle(stream_id=f"gameplay:economy:wage:{accrual.payee_actor_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.economy.wage_accrued", payload=accrual.model_dump(mode="json"), pinned_revisions={"wage": 1})

    def mark_overdue(self, accrual: WageAccrual, *, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        overdue = accrual.model_copy(update={"status": "overdue"})
        return self._settle(stream_id=f"gameplay:economy:wage:{accrual.payee_actor_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.economy.wage_overdue", payload=overdue.model_dump(mode="json"), pinned_revisions={"wage": 1})

    def pay_wage(
        self,
        accrual: WageAccrual,
        *,
        payer_account_id: str,
        payee_account_id: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        """Commit wage payment and account transfer as one multi-stream batch."""
        if accrual.status not in {"accrued", "due"}:
            raise ValueError("wage_payment_invalid_status")
        amount = int(accrual.amount)
        if amount != accrual.amount or amount <= 0:
            raise ValueError("wage_amount_not_integral")
        projection = EconomyProjector().rebuild(self._store.read_events())
        payer = projection.accounts.get(payer_account_id)
        payee = projection.accounts.get(payee_account_id)
        if payer is None or payee is None or payer.currency_ref != payee.currency_ref:
            raise EconomyRuntimeError("economy_account_invalid")
        if payer.balance < amount:
            raise EconomyRuntimeError("economy_insufficient_funds")
        wage_stream = f"gameplay:economy:wage:{accrual.payee_actor_ref}"
        account_stream = "gameplay:economy"
        expected_revisions = {
            wage_stream: self._store.get_stream_head(wage_stream),
            account_stream: projection.source_revision_vector.get(account_stream, 0),
        }
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-wage-payment@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(wage_stream, account_stream),
                event_types=(
                    "gameplay.economy.wage_paid",
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                ),
                projection_scope="mixed",
            )
        except GovernedAuthorityContractError as error:
            raise EconomyRuntimeError(str(error)) from error
        wage_payload = {
            **accrual.model_dump(mode="json"),
            "status": "paid",
            "payer_account_id": payer_account_id,
            "payee_account_id": payee_account_id,
        }
        command = GameplayCommandEnvelope(
            command_id=command_id, command_type="gameplay.economy.pay_wage", command_version=1,
            principal_ref=self._PRINCIPAL, actor_ref=accrual.payee_actor_ref, project_ref=None,
            transaction_id=f"transaction:{command_id}", idempotency_key=idempotency_key,
            expected_revisions=expected_revisions, causation_id=causation_id,
            correlation_id=correlation_id, source_ref=self._PRINCIPAL, submitted_at="economy",
            pinned_revisions={"wage": 1, "economy": expected_revisions[account_stream]},
            payload={
                "stream_ref": wage_stream,
                "event_type": "gameplay.economy.wage_paid",
                "visibility_policy": f"actor:{accrual.payee_actor_ref}",
                **wage_payload,
            },
        )
        wage_event = SettlementPlan.from_command_envelope(command).to_atomic_event_batch().events[0]
        fragments = (
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:economy:wage-payment:accounts:{accrual.accrual_ref}",
                owner_principal_ref=self._PRINCIPAL, source_rule_ref="economy:wage-payment",
                expected_revisions={account_stream: expected_revisions[account_stream]},
                pinned_revisions=dict(command.pinned_revisions),
                event_specs={account_stream: (("gameplay.economy.account_debited", {"account_id": payer_account_id, "amount": amount}), ("gameplay.economy.account_credited", {"account_id": payee_account_id, "amount": amount}))},
                event_visibility_policies={account_stream: ("authority_only", "authority_only")},
            ),
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:economy:wage-payment:wage:{accrual.accrual_ref}",
                owner_principal_ref=self._PRINCIPAL, source_rule_ref="economy:wage-payment",
                expected_revisions={wage_stream: expected_revisions[wage_stream]},
                pinned_revisions=dict(command.pinned_revisions),
                event_specs={wage_stream: ((wage_event.event_type, wage_event.payload),)},
                event_visibility_policies={wage_stream: (wage_event.visibility_policy,)},
            ),
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command.command_id, idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key, causation_id=command.causation_id,
            correlation_id=command.correlation_id, fragments=fragments,
        )
        batch = batch.model_copy(update={"outbox_entries": [
            GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="economy.wage.scoped_projection" if event.stream_id == wage_stream else "economy.account.authority_projection", audience=f"actor:{accrual.payee_actor_ref}" if event.stream_id == wage_stream else "authority:economy", payload_projection={"accrual_ref": accrual.accrual_ref, "status": "paid"} if event.stream_id == wage_stream else {"event_type": event.event_type}) for event in batch.events
        ]}, deep=True)
        return self._store.append_batch(batch)

    @staticmethod
    def payroll_settlement_receipt_for(
        *, result: AppendBatchResult | None, privacy_scope: str
    ) -> SettlementReceipt:
        if privacy_scope != "authority":
            raise EconomyRuntimeError("economy_payroll_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("economy_payroll_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"payroll_transaction:{result.transaction_id}",),
        )

    def _window_status(self, window_ref: str) -> str | None:
        stream_id = f"gameplay:organization:window:{window_ref}"
        status: str | None = None
        for event in self._store.read_stream(stream_id):
            if event.event_type.endswith("operating_window_opened"):
                status = "open"
            elif event.event_type.endswith("operating_window_closed"):
                status = "closed"
        return status

    @staticmethod
    def _raise_window_compat_error(result: AppendBatchResult) -> None:
        if result.committed or result.failure is None:
            return
        mapping = {
            "organization_operating_window_already_opened": "operating_window_already_opened",
            "organization_operating_window_invalid": "operating_window_invalid",
            "organization_operating_window_not_open": "operating_window_closed",
            "organization_operating_window_not_closed": "operating_window_open",
            "organization_window_visibility_invalid": "operating_window_invalid",
        }
        error_code = mapping.get(result.failure.error_code)
        if error_code is not None:
            raise ValueError(error_code)

    @staticmethod
    def close_period(period: BusinessPeriod) -> BusinessPeriod:
        if period.closed:
            raise ValueError("period_already_closed")
        if any(obligation.status == "overdue" for obligation in period.obligations):
            raise ValueError("overdue_obligation")
        return period.model_copy(update={"closed": True}, deep=True)

    def settle_purchase(
        self,
        quote: MarketQuote,
        posting: PurchasePosting,
        *,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        self.validate_quote(quote, tick=tick, quantity=posting.quantity)
        if posting.quote_ref != quote.quote_ref or posting.total_amount != quote.unit_price * posting.quantity:
            raise ValueError("purchase_posting_invalid")
        return self._settle(
            stream_id=f"gameplay:economy:{posting.buyer_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.economy.purchase_posted",
            payload={**posting.model_dump(mode="json"), "item_ref": quote.item_ref, "tick": tick},
            pinned_revisions={"quote": quote.valid_until_tick},
        )

    def settle_sale(
        self,
        posting: SalePosting,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        return self._settle(
            stream_id=f"gameplay:economy:{posting.seller_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.economy.sale_posted",
            payload=posting.model_dump(mode="json"),
            pinned_revisions={},
        )

    def settle_period_close(
        self,
        period: BusinessPeriod,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        closed = self.close_period(period)
        return self._settle(
            stream_id=f"gameplay:economy:period:{period.period_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.economy.business_period_closed",
            payload=closed.model_dump(mode="json"),
            pinned_revisions={"period": period.sequence},
        )

    def _settle(
        self,
        *,
        stream_id: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        event_type: str,
        payload: dict[str, object],
        pinned_revisions: dict[str, int],
    ):
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        expected_revision = (
            existing.resulting_stream_revisions.get(stream_id, 0) - 1
            if existing is not None
            else self._store.get_stream_head(stream_id)
        )
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type=event_type,
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=payload.get("payee_actor_ref") if isinstance(payload.get("payee_actor_ref"), str) else None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=self._PRINCIPAL,
            submitted_at="economy",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions=pinned_revisions,
            payload={"stream_ref": stream_id, "event_type": event_type, "visibility_policy": "project", **payload},
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        payee = payload.get("payee_actor_ref")
        if event_type.startswith("gameplay.economy.wage_") and isinstance(payee, str):
            batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(
                outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id,
                event_id=event.event_id, global_sequence=0, topic="economy.wage.scoped_projection",
                audience=f"actor:{payee}", payload_projection={"accrual_ref": payload.get("accrual_ref"), "status": payload.get("status")},
            ) for event in batch.events]}, deep=True)
        return self._store.append_batch(batch)

    @staticmethod
    def post_purchase(
        *,
        store: GameplayEventStore,
        buyer_ref: str,
        seller_ref: str,
        item_ref: str,
        quantity: int,
        total_amount: float,
        quote_ref: str,
        tick: int,
    ):
        if quantity <= 0 or total_amount <= 0:
            raise ValueError("purchase_invalid")
        command_id = f"purchase:{buyer_ref}:{quote_ref}:{tick}"
        authority = EconomyAuthority(store=store)
        quote = MarketQuote(
            quote_ref=quote_ref,
            item_ref=item_ref,
            unit_price=total_amount / quantity,
            quantity_limit=quantity,
            valid_until_tick=tick,
            public_digest=f"legacy:{quote_ref}",
        )
        posting = PurchasePosting(
            posting_ref=command_id,
            quote_ref=quote_ref,
            buyer_ref=buyer_ref,
            quantity=quantity,
            total_amount=total_amount,
        )
        return authority.settle_purchase(
            quote,
            posting,
            tick=tick,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{buyer_ref}:{tick}",
        )

    @staticmethod
    def post_sale(
        *,
        store: GameplayEventStore,
        seller_ref: str,
        buyer_ref: str,
        item_ref: str,
        quantity: int,
        total_amount: float,
        tick: int,
    ):
        if quantity <= 0 or total_amount <= 0:
            raise ValueError("sale_invalid")
        command_id = f"sale:{seller_ref}:{item_ref}:{tick}"
        posting = SalePosting(
            posting_ref=command_id,
            seller_ref=seller_ref,
            item_ref=item_ref,
            quantity=quantity,
            total_amount=total_amount,
            demand_digest=f"legacy:{buyer_ref}",
        )
        return EconomyAuthority(store=store).settle_sale(
            posting,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{seller_ref}:{tick}",
        )

    @staticmethod
    def close_period_and_settle(*, store: GameplayEventStore, period: BusinessPeriod, organization_ref: str):
        command_id = f"period-close:{period.period_ref}"
        return EconomyAuthority(store=store).settle_period_close(
            period,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{organization_ref}:{period.sequence}",
        )


__all__ = ["BusinessPeriod", "EconomicObligation", "EconomyAuthority", "MarketQuote", "OperatingWindow", "PurchasePosting", "SalePosting", "WageAccrual"]
