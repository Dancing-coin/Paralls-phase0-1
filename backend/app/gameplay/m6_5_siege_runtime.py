"""Production dispatch wiring for M6-5 siege commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Callable

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.facility_gate_layered_runtime import FacilityGateLayeredAuthority
from app.gameplay.impact_gate_obligation import rebuild_impact_gate_obligations
from app.gameplay.information_runtime import (
    INFORMATION_REPORT_EVENT,
    INFORMATION_REPORT_FACT_TYPE,
    INFORMATION_REPORT_PRINCIPAL,
    InformationAuthority,
    InformationReportPublicationResult,
    SiegeReportPublicationReceipt,
)
from app.gameplay.l5_dispatch_runtime import (
    L5ReactionDispatcher,
    TriggeredGameplayCommand,
    TrustedGameplayCommandGateway,
)
from app.gameplay.models import AppendBatchResult, AtomicEventBatch, GameplayEvent
from app.gameplay.morale_refold_runtime import MoraleRefoldAuthority
from app.gameplay.place_passability_runtime import (
    PlacePassabilityAssessment,
    PlacePassabilityAuthority,
)
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.config import FacilityGateProfileSettings
from app.gameplay.siege_physical_input_runtime import (
    GATE_IMPACT_INPUT_EVENT,
    GATE_IMPACT_INPUT_EVENT_V2,
    PRESENCE_ASSESSMENT_INPUT_EVENT,
    PRESENCE_ASSESSMENT_INPUT_EVENT_V2,
    GateImpactReceipt,
    GateImpactReceiptV2,
    PresenceAssessmentReceipt,
    PresenceAssessmentReceiptV2,
    SiegePhysicalInputAuthority,
)
from app.gameplay.rule_pack_validator import load_pack
from app.gameplay.package_migration_runtime import PackageArchive, PackageRef


M6_5_PACK = Path(__file__).resolve().parents[3] / "packs" / "county_siege_morale_presence"
INFORMATION_PACK = Path(__file__).resolve().parents[3] / "packs" / "county_siege_information"
MORALE_OWNER_DOMAINS = {
    "Morale": "morale",
    "Presence": "presence",
}
INFORMATION_KNOWLEDGE_FACT_TYPE = "fact:information:siege:report_knowledge"
INFORMATION_DELIVERY_EVENT_TYPE = "gameplay.social.delivery_recorded@2"
DEFAULT_MORALE_DEFINITIONS = MappingProxyType({
    ("organization:garrison:east@1", "role:garrison-defender@1"): PoolDefinition(
        fact_type="fact:unit:garrison-east:morale",
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        aggregation_mode="distribution",
        refold_model_ref="morale_refold@1",
    ),
})
PlaceResolver = Callable[
    [str, GameplayEvent], PlacePassabilityAssessment | None
]


def build_facility_integrity_authority(
    *,
    store: GameplayEventStore,
    profiles: tuple[FacilityGateProfileSettings, ...],
) -> FacilityIntegrityAuthority | None:
    if not profiles:
        return None
    return FacilityIntegrityAuthority(
        store=store,
        definitions={
            profile.gate_ref: PoolDefinition(
                fact_type=FacilityIntegrityAuthority.fact_type_for(profile.gate_ref),
                lower=profile.integrity_lower,
                upper=profile.integrity_upper,
                initial=profile.integrity_initial,
                thresholds=(PoolThreshold(
                    "breach",
                    profile.breach_threshold,
                    profile.breach_reset_threshold,
                ),),
            )
            for profile in profiles
        },
        impact_profiles={
            profile.gate_ref: profile.impact_deltas
            for profile in profiles
        },
    )


def build_facility_gate_layered_authority(
    *,
    store: GameplayEventStore,
    profiles: tuple[FacilityGateProfileSettings, ...],
) -> FacilityGateLayeredAuthority | None:
    layered_profiles = tuple(
        profile for profile in profiles if profile.durability_lower is not None
    )
    if not layered_profiles:
        return None
    definitions: dict[str, dict[str, PoolDefinition]] = {}
    impact_magnitudes: dict[str, dict[str, Decimal]] = {}
    for profile in layered_profiles:
        definitions[profile.gate_ref] = {
            FacilityGateLayeredAuthority.fact_type_for(profile.gate_ref, "durability"):
                PoolDefinition(
                    fact_type=FacilityGateLayeredAuthority.fact_type_for(profile.gate_ref, "durability"),
                    lower=profile.durability_lower,
                    upper=profile.durability_upper,
                    initial=profile.durability_initial,
                ),
            FacilityGateLayeredAuthority.fact_type_for(profile.gate_ref, "latch-durability"):
                PoolDefinition(
                    fact_type=FacilityGateLayeredAuthority.fact_type_for(profile.gate_ref, "latch-durability"),
                    lower=profile.latch_durability_lower,
                    upper=profile.latch_durability_upper,
                    initial=profile.latch_durability_initial,
                ),
            FacilityGateLayeredAuthority.fact_type_for(profile.gate_ref, "integrity"):
                PoolDefinition(
                    fact_type=FacilityGateLayeredAuthority.fact_type_for(profile.gate_ref, "integrity"),
                    lower=profile.integrity_lower,
                    upper=profile.integrity_upper,
                    initial=profile.integrity_initial,
                    thresholds=(PoolThreshold(
                        "breach",
                        profile.breach_threshold,
                        profile.breach_reset_threshold,
                    ),),
                ),
        }
        impact_magnitudes[profile.gate_ref] = {
            impact_kind_ref: -delta
            for impact_kind_ref, delta in profile.impact_deltas.items()
        }
    return FacilityGateLayeredAuthority(
        store=store,
        definitions=definitions,
        impact_magnitudes=impact_magnitudes,
    )


@dataclass(frozen=True)
class M6_5SiegeRuntime:
    morale: MoraleRefoldAuthority
    presence: PlacePassabilityAuthority
    dispatcher: L5ReactionDispatcher
    physical_inputs: SiegePhysicalInputAuthority
    facility: FacilityIntegrityAuthority | None
    layered_facility: FacilityGateLayeredAuthority | None
    information: InformationAuthority
    world_tick_provider: Callable[[], int | None] | None = None

    def impact_gate_obligations(self):
        return rebuild_impact_gate_obligations(self.physical_inputs.store())

    def after_transaction_dispatched(
        self, transaction: AtomicEventBatch
    ) -> tuple[object, ...]:
        return self.dispatcher.after_transaction_dispatched(transaction)

    def publish_siege_report(
        self, receipt: SiegeReportPublicationReceipt,
    ) -> InformationReportPublicationResult:
        world_now = self.world_tick_provider() if self.world_tick_provider is not None else None
        return self.information.publish_siege_report(receipt=receipt, world_now=world_now)

    def record_gate_impact(self, receipt: GateImpactReceipt):
        evidence = self.physical_inputs.record_gate_impact(receipt)
        if not evidence.committed or self.facility is None:
            return evidence, None
        result = self.facility.apply_signed_impact(
            input_authority=self.physical_inputs,
            authority_ref=receipt.authority_ref,
            receipt_id=receipt.receipt_id,
        )
        return evidence, result

    def record_gate_impact_v2(self, receipt: GateImpactReceiptV2):
        evidence = self.physical_inputs.record_gate_impact_v2(receipt)
        if not evidence.committed or self.layered_facility is None:
            return evidence, None, ()
        result = self.layered_facility.apply_signed_impact(
            input_authority=self.physical_inputs,
            authority_ref=receipt.authority_ref,
            receipt_id=receipt.receipt_id,
        )
        transaction = self.physical_inputs.store().get_transaction(result.transaction_id)
        dispatch_results = (
            self.dispatcher.after_transaction_dispatched(transaction)
            if result.committed and transaction is not None
            else ()
        )
        return evidence, result, dispatch_results

    def record_presence_assessment(self, receipt: PresenceAssessmentReceipt | PresenceAssessmentReceiptV2):
        evidence = self.physical_inputs.record_presence_assessment(receipt)
        if not evidence.committed:
            return evidence, None
        committed = self.presence.commit_signed_assessment(
            input_authority=self.physical_inputs,
            authority_ref=receipt.authority_ref,
            receipt_id=receipt.receipt_id,
        )
        return evidence, committed

    def recover_physical_input_obligations(
        self,
    ) -> tuple[tuple[str, AppendBatchResult], ...]:
        """Reconcile domain commits from durable signed inputs and owner receipts."""
        results: list[tuple[str, AppendBatchResult]] = []
        if self.facility is not None:
            for event in self.physical_inputs.store().read_events(
                event_type=GATE_IMPACT_INPUT_EVENT,
            ):
                receipt = GateImpactReceipt.model_validate(event.payload["receipt"])
                result = self.facility.apply_signed_impact(
                    input_authority=self.physical_inputs,
                    authority_ref=receipt.authority_ref,
                    receipt_id=receipt.receipt_id,
                )
                results.append((event.event_id, result))

        if self.layered_facility is not None:
            for event in self.physical_inputs.store().read_events(
                event_type=GATE_IMPACT_INPUT_EVENT_V2,
            ):
                receipt = GateImpactReceiptV2.model_validate(event.payload["receipt"])
                result = self.layered_facility.apply_signed_impact(
                    input_authority=self.physical_inputs,
                    authority_ref=receipt.authority_ref,
                    receipt_id=receipt.receipt_id,
                )
                transaction = self.physical_inputs.store().get_transaction(result.transaction_id)
                if result.committed and transaction is not None:
                    self.dispatcher.after_transaction_dispatched(transaction)
                results.append((event.event_id, result))

        assessment_events = {
            PRESENCE_ASSESSMENT_INPUT_EVENT: PresenceAssessmentReceipt,
            PRESENCE_ASSESSMENT_INPUT_EVENT_V2: PresenceAssessmentReceiptV2,
        }
        for event in self.physical_inputs.store().read_events():
            receipt_model = assessment_events.get(event.event_type)
            if receipt_model is None:
                continue
            receipt = receipt_model.model_validate(event.payload["receipt"])
            result = self.presence.commit_signed_assessment(
                input_authority=self.physical_inputs,
                authority_ref=receipt.authority_ref,
                receipt_id=receipt.receipt_id,
            )
            results.append((event.event_id, result))
        return tuple(results)


def build_m6_5_siege_runtime(
    *,
    store: GameplayEventStore,
    morale_definitions: Mapping[tuple[str, str], PoolDefinition],
    presence_resolver: PlaceResolver | None = None,
    evidence_event_principals: Mapping[str, str] | None = None,
    physical_authority_secrets: Mapping[str, str] | None = None,
    facility: FacilityIntegrityAuthority | None = None,
    layered_facility: FacilityGateLayeredAuthority | None = None,
    information_report_authority_secrets: Mapping[str, str] | None = None,
    world_tick_provider: Callable[[], int | None] | None = None,
    package_archive: PackageArchive | None = None,
    package_refs: Mapping[str, PackageRef] | None = None,
) -> M6_5SiegeRuntime:
    if (facility is not None and facility.store is not store) or (
        layered_facility is not None and layered_facility.store is not store
    ):
        raise ValueError("m6_5_siege_facility_store_mismatch")
    physical_inputs = SiegePhysicalInputAuthority(
        store=store,
        authority_secrets=physical_authority_secrets or {},
        evidence_event_principals={
            **(evidence_event_principals or {}),
            "gameplay.facility.gate_impact_input_received":
                "authority:siege:physical-input",
            GATE_IMPACT_INPUT_EVENT_V2: "authority:siege:physical-input",
        },
    )
    morale = MoraleRefoldAuthority(store=store, definitions=morale_definitions)
    presence = PlacePassabilityAuthority(
        store=store,
        resolver=presence_resolver,
        evidence_event_principals=evidence_event_principals,
    )
    information = InformationAuthority(
        store=store, report_authority_secrets=information_report_authority_secrets,
    )
    command_outputs = {
        "morale.refold": {definition.fact_type for definition in morale_definitions.values()},
        "presence.reevaluate": {presence.stream_id("gate-03")},
    }
    if (package_archive is None) != (package_refs is None):
        raise ValueError("m6_5_package_consumer_configuration_incomplete")
    if package_archive is None:
        pack = load_pack(
            M6_5_PACK,
            handlers={},
            owner_domains=MORALE_OWNER_DOMAINS,
            command_fact_outputs=command_outputs,
        )
    else:
        assert package_refs is not None
        morale_ref = package_refs.get("morale_presence")
        information_ref = package_refs.get("information")
        if not isinstance(morale_ref, PackageRef) or not isinstance(information_ref, PackageRef):
            raise ValueError("m6_5_package_consumer_package_refs_missing")
        pack = package_archive.resolve(morale_ref)
    information_outputs = {
        "information.update_knowledge": {INFORMATION_KNOWLEDGE_FACT_TYPE},
    }
    if package_archive is None:
        information_pack = load_pack(
            INFORMATION_PACK,
            handlers={},
            owner_domains={"Information": "information"},
            command_fact_outputs=information_outputs,
        )
    else:
        information_pack = package_archive.resolve(information_ref)
    all_command_outputs = {**command_outputs, **information_outputs}
    gateway = TrustedGameplayCommandGateway(
        handlers={
            "morale.refold": lambda command: morale.refold_after_casualty(
                death_event_id=command.trigger_event.event_id,
            ),
            "presence.reevaluate": lambda command: presence.commit_assessment(
                gate_ref=str(command.target["scope"]),
                breach_event_id=command.trigger_event.event_id,
                expected_revision=store.get_stream_head(
                    presence.stream_id(str(command.target["scope"]))
                ),
            ),
            "information.update_knowledge": lambda command: information.update_from_delivery(
                delivery=command.trigger_event,
                world_now=_required_world_tick(world_tick_provider),
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            ),
        },
        command_fact_outputs=all_command_outputs,
    )
    dispatcher = L5ReactionDispatcher(
        reactions=tuple(pack.reactions.values()) + tuple(information_pack.reactions.values()),
        gateway=gateway,
        fact_type_for=lambda event: _fact_type_for(event, store=store),
        conditions={"facility_breach@1": _is_breach_entry},
    )
    return M6_5SiegeRuntime(
        morale=morale,
        presence=presence,
        dispatcher=dispatcher,
        physical_inputs=physical_inputs,
        facility=facility,
        layered_facility=layered_facility,
        information=information,
        world_tick_provider=world_tick_provider,
    )


def _fact_type_for(
    event: GameplayEvent,
    *,
    store: GameplayEventStore,
) -> str | None:
    if event.event_type == INFORMATION_DELIVERY_EVENT_TYPE:
        payload = event.payload
        source_event_id = payload.get("source_event_id")
        source_stream_id = payload.get("source_stream_id")
        source_revision = payload.get("source_revision")
        recipient_ref = payload.get("recipient_ref")
        try:
            source = store.get_event(source_event_id) if isinstance(source_event_id, str) else None
        except KeyError:
            source = None
        if (
            source is not None
            and source.event_type == INFORMATION_REPORT_EVENT
            and source.schema_version == 1
            and source.stream_id == source_stream_id
            and source.stream_revision == source_revision
            and source.payload.get("fact_type") == INFORMATION_REPORT_FACT_TYPE
            and isinstance(recipient_ref, str)
            and source.payload.get("recipient_ref") == recipient_ref
            and source.visibility_policy == f"actor:{recipient_ref}"
            and store.transaction_owns_event(
                transaction_id=source.transaction_id,
                event_id=source.event_id,
                principal_ref=INFORMATION_REPORT_PRINCIPAL,
            )
        ):
            return INFORMATION_REPORT_FACT_TYPE
        return None
    fact_type = event.payload.get("fact_type")
    if isinstance(fact_type, str):
        return fact_type
    actor_ref = event.payload.get("actor_ref")
    if event.event_type == "gameplay.character.life_state_changed" and isinstance(actor_ref, str):
        return f"fact:character:{actor_ref}:lifestate"
    return None


def _required_world_tick(provider: Callable[[], int | None] | None) -> int:
    world_tick = provider() if provider is not None else None
    if type(world_tick) is not int or world_tick < 0:
        raise ValueError("information_world_clock_unavailable")
    return world_tick


def _is_breach_entry(event: GameplayEvent) -> bool:
    return (
        event.payload.get("threshold_ref") == "breach"
        and event.payload.get("direction") == "enter"
    )
