"""Economy-owned evidence markers for commerce, labor periods and tax policy."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment
from app.gameplay.settlement_plan import build_atomic_event_batch


class EconomyCommerceRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class EconomyCommerceProjection:
    delivery_settlements: Mapping[str, Mapping[str, object]]
    labor_periods: Mapping[str, Mapping[str, object]]
    tax_regulations: Mapping[str, Mapping[str, object]]
    source_revision_vector: Mapping[str, int]


class EconomyCommerceProjector:
    def rebuild(self, events: Sequence[object], *, checkpoint: EconomyCommerceProjection | None = None) -> EconomyCommerceProjection:
        deliveries = dict(checkpoint.delivery_settlements) if checkpoint else {}
        labor = dict(checkpoint.labor_periods) if checkpoint else {}
        taxes = dict(checkpoint.tax_regulations) if checkpoint else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint else {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if not event.stream_id.startswith("gameplay:economy:"):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            payload = dict(event.payload)
            if event.event_type == "gameplay.economy.delivery_settlement_recorded@1":
                key = payload.get("settlement_ref")
                if not isinstance(key, str) or not key or key in deliveries:
                    raise EconomyCommerceRuntimeError("economy_delivery_settlement_duplicate")
                deliveries[key] = payload
            elif event.event_type == "gameplay.economy.organization_period_recorded@1":
                key = payload.get("period_ref")
                if not isinstance(key, str) or not key or key in labor:
                    raise EconomyCommerceRuntimeError("economy_labor_period_duplicate")
                labor[key] = payload
            elif event.event_type == "gameplay.economy.tax_obligation_recorded@1":
                key = payload.get("assessment_ref")
                if not isinstance(key, str) or not key or key in taxes:
                    raise EconomyCommerceRuntimeError("economy_tax_regulation_duplicate")
                taxes[key] = payload
        return EconomyCommerceProjection(
            delivery_settlements=MappingProxyType(dict(sorted(deliveries.items()))),
            labor_periods=MappingProxyType(dict(sorted(labor.items()))),
            tax_regulations=MappingProxyType(dict(sorted(taxes.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class EconomyCommerceAuthority:
    _PRINCIPAL = "actor_gameplay.economy_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def _commit(self, *, command_id: str, idempotency_key: str, event_type: str, payload: Mapping[str, object], subject_ref: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not all(isinstance(value, str) and value for value in (command_id, idempotency_key, event_type, subject_ref, causation_id, correlation_id)):
            raise EconomyCommerceRuntimeError("economy_commerce_input_invalid")
        stream = f"gameplay:economy:{subject_ref}"
        if self._store.get_stream_head(stream) != expected_revision:
            raise EconomyCommerceRuntimeError("economy_commerce_revision_conflict")
        batch = build_atomic_event_batch(command_id=command_id, principal_ref=self._PRINCIPAL, stream_id=stream, expected_revision=expected_revision, event_specs=((event_type, dict(payload)),), idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, read_stream_revisions={stream: expected_revision})
        fragment = OwnerAuthorizedFragment(fragment_id=f"fragment:economy-commerce:{command_id}", owner_principal_ref=self._PRINCIPAL, source_rule_ref="economy-commerce:owner-evidence@1", expected_revisions={stream: expected_revision}, read_set_revisions={stream: expected_revision}, pinned_revisions={"economy": expected_revision}, event_specs={stream: ((event_type, dict(payload)),)}, event_visibility_policies={stream: ("authority_only",)})
        return self._store.append_batch(batch.model_copy(update={"owner_fragments": [fragment]}, deep=True))

    def record_delivery_settlement(self, *, command_id: str, idempotency_key: str, settlement_ref: str, commitment_ref: str, policy_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not settlement_ref or not commitment_ref or not policy_revision:
            raise EconomyCommerceRuntimeError("economy_delivery_settlement_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.delivery_settlement_recorded@1", payload={"settlement_ref": settlement_ref, "commitment_ref": commitment_ref, "policy_revision": policy_revision}, subject_ref=settlement_ref, expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)

    def record_labor_period(self, *, command_id: str, idempotency_key: str, period_ref: str, organization_ref: str, payroll_amount_minor: int, policy_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not period_ref or not organization_ref or payroll_amount_minor < 0 or not policy_revision:
            raise EconomyCommerceRuntimeError("economy_labor_period_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.organization_period_recorded@1", payload={"period_ref": period_ref, "organization_ref": organization_ref, "payroll_amount_minor": payroll_amount_minor, "policy_revision": policy_revision}, subject_ref=period_ref, expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)

    def record_tax_regulation(self, *, command_id: str, idempotency_key: str, assessment_ref: str, organization_ref: str, amount_minor: int, policy_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not assessment_ref or not organization_ref or amount_minor < 0 or not policy_revision:
            raise EconomyCommerceRuntimeError("economy_tax_regulation_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.tax_obligation_recorded@1", payload={"assessment_ref": assessment_ref, "organization_ref": organization_ref, "amount_minor": amount_minor, "policy_revision": policy_revision}, subject_ref=assessment_ref, expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)


__all__ = ["EconomyCommerceAuthority", "EconomyCommerceProjector", "EconomyCommerceProjection", "EconomyCommerceRuntimeError"]
