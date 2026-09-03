"""Owner-local Economy v3 primitives.

These explicit methods cover the first platform slice only; each event remains
Economy-owned and is committed through the existing append spine.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment
from app.gameplay.settlement_plan import build_atomic_event_batch


class EconomyPlatformRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class EconomyPlatformProjection:
    currency_issuance_minor: Mapping[str, int]
    population_signals: Mapping[str, Mapping[str, object]]
    ledger_postings: Mapping[str, Mapping[str, object]]
    holds: Mapping[str, Mapping[str, object]]
    obligations: Mapping[str, Mapping[str, object]]
    fx_fixings: Mapping[str, Mapping[str, object]]
    recipe_acceptances: Mapping[str, Mapping[str, object]]
    source_revision_vector: Mapping[str, int]


class EconomyPlatformProjector:
    def rebuild(self, events: Sequence[object], *, checkpoint: EconomyPlatformProjection | None = None) -> EconomyPlatformProjection:
        issuance = dict(checkpoint.currency_issuance_minor) if checkpoint else {}
        signals = dict(checkpoint.population_signals) if checkpoint else {}
        postings = dict(checkpoint.ledger_postings) if checkpoint else {}
        holds = dict(checkpoint.holds) if checkpoint else {}
        obligations = dict(checkpoint.obligations) if checkpoint else {}
        fixings = dict(checkpoint.fx_fixings) if checkpoint else {}
        recipe_acceptances = dict(checkpoint.recipe_acceptances) if checkpoint else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint else {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if not event.stream_id.startswith("gameplay:economy:"):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            payload = event.payload
            if event.event_type == "gameplay.economy.currency_issuance_recorded@1":
                currency_ref = payload.get("currency_ref")
                amount = payload.get("amount_minor")
                if not isinstance(currency_ref, str) or not currency_ref.startswith("currency:") or not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                    raise EconomyPlatformRuntimeError("economy_currency_issuance_replay_invalid")
                issuance[currency_ref] = issuance.get(currency_ref, 0) + amount
            elif event.event_type == "gameplay.economy.population_market_signal_recorded@1":
                signal_ref = payload.get("signal_ref")
                if not isinstance(signal_ref, str) or not signal_ref or signal_ref in signals:
                    raise EconomyPlatformRuntimeError("economy_population_signal_duplicate")
                signals[signal_ref] = dict(payload)
            elif event.event_type == "gameplay.economy.ledger_posted@1":
                posting_ref = payload.get("posting_ref")
                if not isinstance(posting_ref, str) or not posting_ref or posting_ref in postings:
                    raise EconomyPlatformRuntimeError("economy_ledger_posting_duplicate")
                postings[posting_ref] = dict(payload)
            elif event.event_type == "gameplay.economy.hold_recorded@1":
                hold_ref = payload.get("hold_ref")
                if not isinstance(hold_ref, str) or not hold_ref or hold_ref in holds:
                    raise EconomyPlatformRuntimeError("economy_hold_duplicate")
                holds[hold_ref] = dict(payload)
            elif event.event_type == "gameplay.economy.obligation_recorded@1":
                obligation_ref = payload.get("obligation_ref")
                if not isinstance(obligation_ref, str) or not obligation_ref or obligation_ref in obligations:
                    raise EconomyPlatformRuntimeError("economy_obligation_duplicate")
                obligations[obligation_ref] = dict(payload)
            elif event.event_type == "gameplay.economy.fx_fixing_recorded@1":
                fixing_ref = payload.get("fixing_ref")
                if not isinstance(fixing_ref, str) or not fixing_ref or fixing_ref in fixings:
                    raise EconomyPlatformRuntimeError("economy_fx_fixing_duplicate")
                fixings[fixing_ref] = dict(payload)
            elif event.event_type in {
                "gameplay.economy.organization_recipe_accepted@1",
                "gameplay.economy.government_recipe_accepted@1",
            }:
                acceptance_ref = payload.get("acceptance_ref")
                if not isinstance(acceptance_ref, str) or not acceptance_ref or acceptance_ref in recipe_acceptances:
                    raise EconomyPlatformRuntimeError("economy_recipe_acceptance_duplicate")
                recipe_acceptances[acceptance_ref] = dict(payload)
        return EconomyPlatformProjection(
            currency_issuance_minor=MappingProxyType(dict(sorted(issuance.items()))),
            population_signals=MappingProxyType(dict(sorted(signals.items()))),
            ledger_postings=MappingProxyType(dict(sorted(postings.items()))),
            holds=MappingProxyType(dict(sorted(holds.items()))),
            obligations=MappingProxyType(dict(sorted(obligations.items()))),
            fx_fixings=MappingProxyType(dict(sorted(fixings.items()))),
            recipe_acceptances=MappingProxyType(dict(sorted(recipe_acceptances.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class EconomyPlatformAuthority:
    _PRINCIPAL = "actor_gameplay.economy_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def _commit(self, *, command_id: str, idempotency_key: str, event_type: str, payload: Mapping[str, object], subject_ref: str, expected_revision: int, causation_id: str, correlation_id: str, pinned_revisions: Mapping[str, int] | None = None) -> AppendBatchResult:
        if not all(isinstance(value, str) and value for value in (command_id, idempotency_key, event_type, subject_ref, causation_id, correlation_id)):
            raise EconomyPlatformRuntimeError("economy_platform_input_invalid")
        stream_id = f"gameplay:economy:{subject_ref}"
        if self._store.get_stream_head(stream_id) != expected_revision:
            raise EconomyPlatformRuntimeError("economy_platform_revision_conflict")
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_specs=((event_type, dict(payload)),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions={stream_id: expected_revision},
            pinned_revisions=dict(pinned_revisions or {}),
        )
        batch = batch.model_copy(update={
            "owner_fragments": [OwnerAuthorizedFragment(
                fragment_id=f"fragment:economy-platform:{command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref="economy-platform:explicit-owner-operation@1",
                expected_revisions={stream_id: expected_revision},
                read_set_revisions={stream_id: expected_revision},
                pinned_revisions=dict(pinned_revisions or {}),
                event_specs={stream_id: ((event_type, dict(payload)),)},
                event_visibility_policies={stream_id: ("authority_only",)},
            )]
        }, deep=True)
        return self._store.append_batch(batch)

    def record_currency_issuance(self, *, command_id: str, idempotency_key: str, currency_ref: str, amount_minor: int, issuer_ref: str, policy_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not currency_ref.startswith("currency:") or amount_minor <= 0 or not issuer_ref or not policy_revision:
            raise EconomyPlatformRuntimeError("economy_currency_issuance_invalid")
        return self._commit(
            command_id=command_id, idempotency_key=idempotency_key,
            event_type="gameplay.economy.currency_issuance_recorded@1",
            payload={"currency_ref": currency_ref, "amount_minor": amount_minor, "issuer_ref": issuer_ref, "policy_revision": policy_revision},
            subject_ref=currency_ref, expected_revision=expected_revision,
            causation_id=causation_id, correlation_id=correlation_id,
        )

    def record_population_market_signal(self, *, command_id: str, idempotency_key: str, signal_ref: str, region_ref: str, period_ref: str, item_ref: str, side: str, quantity: int, source_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if side not in {"demand", "supply"} or quantity < 0 or not signal_ref or not region_ref or not period_ref or not item_ref or not source_revision:
            raise EconomyPlatformRuntimeError("economy_population_signal_invalid")
        return self._commit(
            command_id=command_id, idempotency_key=idempotency_key,
            event_type="gameplay.economy.population_market_signal_recorded@1",
            payload={"signal_ref": signal_ref, "region_ref": region_ref, "period_ref": period_ref, "item_ref": item_ref, "side": side, "quantity": quantity, "source_revision": source_revision},
            subject_ref=region_ref, expected_revision=expected_revision,
            causation_id=causation_id, correlation_id=correlation_id,
            pinned_revisions={"population": expected_revision},
        )

    def record_fx_fixing(self, *, command_id: str, idempotency_key: str, fixing_ref: str, base_currency_ref: str, quote_currency_ref: str, numerator: int, denominator: int, policy_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not fixing_ref or not base_currency_ref.startswith("currency:") or not quote_currency_ref.startswith("currency:") or base_currency_ref == quote_currency_ref or numerator <= 0 or denominator <= 0 or not policy_revision:
            raise EconomyPlatformRuntimeError("economy_fx_fixing_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.fx_fixing_recorded@1", payload={"fixing_ref": fixing_ref, "base_currency_ref": base_currency_ref, "quote_currency_ref": quote_currency_ref, "numerator": numerator, "denominator": denominator, "policy_revision": policy_revision}, subject_ref=f"fx:{fixing_ref}", expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)

    def record_ledger_posting(self, *, command_id: str, idempotency_key: str, posting_ref: str, account_ref: str, direction: str, amount_minor: int, transaction_ref: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not posting_ref or not account_ref.startswith("account:") or direction not in {"debit", "credit"} or amount_minor <= 0 or not transaction_ref:
            raise EconomyPlatformRuntimeError("economy_ledger_posting_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.ledger_posted@1", payload={"posting_ref": posting_ref, "account_ref": account_ref, "direction": direction, "amount_minor": amount_minor, "transaction_ref": transaction_ref}, subject_ref=account_ref, expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)

    def record_hold(self, *, command_id: str, idempotency_key: str, hold_ref: str, account_ref: str, amount_minor: int, purpose_ref: str, expires_at_tick: int, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not hold_ref or not account_ref.startswith("account:") or amount_minor <= 0 or not purpose_ref or expires_at_tick < 0:
            raise EconomyPlatformRuntimeError("economy_hold_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.hold_recorded@1", payload={"hold_ref": hold_ref, "account_ref": account_ref, "amount_minor": amount_minor, "purpose_ref": purpose_ref, "expires_at_tick": expires_at_tick}, subject_ref=account_ref, expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)

    def record_obligation(self, *, command_id: str, idempotency_key: str, obligation_ref: str, debtor_ref: str, creditor_ref: str, amount_minor: int, due_tick: int, policy_revision: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not obligation_ref or not debtor_ref or not creditor_ref or debtor_ref == creditor_ref or amount_minor <= 0 or due_tick < 0 or not policy_revision:
            raise EconomyPlatformRuntimeError("economy_obligation_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.obligation_recorded@1", payload={"obligation_ref": obligation_ref, "debtor_ref": debtor_ref, "creditor_ref": creditor_ref, "amount_minor": amount_minor, "due_tick": due_tick, "policy_revision": policy_revision}, subject_ref=obligation_ref, expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id)

    def accept_ogs_organization_commitment(self, *, source_event: object, expected_source_revision: int, command_id: str, idempotency_key: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        from app.gameplay.organization_government_social_recipes import validate_ogs_recipe_source
        if getattr(source_event, "event_type", None) != "gameplay.organization.commitment_budget_proposed@1" or getattr(source_event, "visibility_policy", None) != "project":
            raise EconomyPlatformRuntimeError("ogs_organization_recipe_source_invalid")
        source_stream = str(getattr(source_event, "stream_id", ""))
        source_revision = int(getattr(source_event, "stream_revision", 0))
        if source_revision != expected_source_revision or self._store.get_stream_head(source_stream) != expected_source_revision:
            raise EconomyPlatformRuntimeError("ogs_organization_recipe_source_stale")
        recipe = validate_ogs_recipe_source(recipe_ref="recipe:organization-operating-commitment@1", source_owner_ref="actor_gameplay.organization_domain", source_event_type=source_event.event_type, source_privacy_scope="project", source_revision=source_revision, expected_source_revision=expected_source_revision)
        acceptance_ref = f"acceptance:{recipe.recipe_ref}:{source_event.event_id}"
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.organization_recipe_accepted@1", payload={"acceptance_ref": acceptance_ref, "recipe_ref": recipe.recipe_ref, "source_event_id": source_event.event_id, "source_stream_id": source_stream, "source_stream_revision": source_revision, "source_owner_ref": recipe.source_owner_ref, "source_privacy_scope": recipe.privacy_scope, "target_owner_ref": recipe.target_owner_ref}, subject_ref=f"recipe:{recipe.recipe_ref}", expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id, pinned_revisions={source_stream: expected_source_revision})

    def accept_ogs_government_enforcement(self, *, source_event: object, expected_source_revision: int, command_id: str, idempotency_key: str, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        from app.gameplay.organization_government_social_recipes import validate_ogs_recipe_source
        if getattr(source_event, "event_type", None) != "gameplay.government.permit_inspection_case_recorded@1" or getattr(source_event, "visibility_policy", None) != "project":
            raise EconomyPlatformRuntimeError("ogs_government_recipe_source_invalid")
        source_stream = str(getattr(source_event, "stream_id", ""))
        source_revision = int(getattr(source_event, "stream_revision", 0))
        if source_revision != expected_source_revision or self._store.get_stream_head(source_stream) != expected_source_revision:
            raise EconomyPlatformRuntimeError("ogs_government_recipe_source_stale")
        recipe = validate_ogs_recipe_source(recipe_ref="recipe:government-enforcement-obligation@1", source_owner_ref="actor_gameplay.government_domain", source_event_type=source_event.event_type, source_privacy_scope="project", source_revision=source_revision, expected_source_revision=expected_source_revision)
        acceptance_ref = f"acceptance:{recipe.recipe_ref}:{source_event.event_id}"
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, event_type="gameplay.economy.government_recipe_accepted@1", payload={"acceptance_ref": acceptance_ref, "recipe_ref": recipe.recipe_ref, "source_event_id": source_event.event_id, "source_stream_id": source_stream, "source_stream_revision": source_revision, "source_owner_ref": recipe.source_owner_ref, "source_privacy_scope": recipe.privacy_scope, "target_owner_ref": recipe.target_owner_ref}, subject_ref=f"recipe:{recipe.recipe_ref}", expected_revision=expected_revision, causation_id=causation_id, correlation_id=correlation_id, pinned_revisions={source_stream: expected_source_revision})


__all__ = ["EconomyPlatformAuthority", "EconomyPlatformProjector", "EconomyPlatformProjection", "EconomyPlatformRuntimeError"]
