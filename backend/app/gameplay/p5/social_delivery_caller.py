"""Production caller for Government public milling notice delivery.

The Government notice is the sole admitted source for this delivery path.  The
caller re-reads its durable stream and the cadence grant immediately before
delegating to the recipient-scoped Social delivery owner.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryResult, SocialDeliveryWindow
from app.world_runtime.temporal_contracts import verify_temporal_authorization


@dataclass(frozen=True)
class SocialDeliveryCallerResult:
    result: SocialDeliveryResult
    source_event_id: str | None = None
    source_revision: int | None = None


class GovernmentPublicMillingSocialDeliveryCaller:
    """Admitted Government -> Social caller for one recipient stream."""

    PARTICIPANT = "authority:p5:social-delivery"
    NOTICE_TYPE = "gameplay.government.public_milling_notice_recorded"

    def __init__(self, *, store: GameplayEventStore, authority: SocialDeliveryAuthority | None = None) -> None:
        self.store = store
        self.authority = authority or SocialDeliveryAuthority(store=store)

    def _deliver_notice(
        self,
        *,
        notice_event_id: str,
        recipient_ref: str,
        world_now: int,
        operational_now: int | None,
        effective_from: int,
        effective_to: int,
        operational_cutoff: int | None,
        temporal_pins: dict[str, object],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> SocialDeliveryCallerResult:
        source = self.store.get_event(notice_event_id) if self._has_event(notice_event_id) else None
        if source is None or source.event_type != self.NOTICE_TYPE or source.visibility_policy != "project":
            return self._reject("social_delivery_notice_source_invalid")
        # A committed request may be retried after the source stream advances
        # or its world window closes.  Let the owner recover the receipt by
        # exact idempotency identity; new requests still require a fresh head.
        has_receipt = self.store.get_idempotency_record(
            self.PARTICIPANT,
            idempotency_key,
        ) is not None
        if (not has_receipt) and source.stream_revision != self.store.get_stream_head(source.stream_id):
            return self._reject("social_delivery_notice_source_stale", source)
        payload = source.payload
        if (
            payload.get("notice_kind") != "public_milling_session_completed"
            or payload.get("status") != "completed"
            or payload.get("policy_revision") != "policy:government-public-milling-notice@1"
            or payload.get("descriptor_ref") != "descriptor:government-public-milling-notice@1"
            or payload.get("descriptor_revision") != "descriptor:government-public-milling-notice@1"
            or payload.get("catalog_ref") != "inf:government-public-milling-notice@1"
        ):
            return self._reject("social_delivery_notice_contract_invalid", source)
        try:
            confirmed_world_tick = int(temporal_pins["sampled_at"])
            confirmed_boundary = int(temporal_pins["confirmation_boundary"])
        except (KeyError, TypeError, ValueError):
            return self._reject("social_delivery_temporal_source_missing", source)
        if (world_now != confirmed_world_tick or confirmed_world_tick != confirmed_boundary
                or not verify_temporal_authorization(
            pins=temporal_pins,
            expected_participant=self.PARTICIPANT,
            expected_cutoff=confirmed_boundary,
            expected_timeline=str(temporal_pins.get("timeline_id", "")),
            grant_key="social",
        )):
            return self._reject("social_delivery_temporal_authorization_rejected", source)
        if operational_cutoff is not None:
            return self._reject("social_delivery_operational_cutoff_untrusted", source)
        result = self.authority.record_delivery(
            delivery_ref=f"social-delivery:{notice_event_id}:{recipient_ref}",
            source_stream_id=source.stream_id,
            source_revision=source.stream_revision,
            source_event_id=source.event_id,
            recipient_ref=recipient_ref,
            window=SocialDeliveryWindow(effective_from, effective_to, operational_cutoff),
            world_now=world_now,
            operational_now=operational_now,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return SocialDeliveryCallerResult(result, source.event_id, source.stream_revision)

    def deliver_bound_receiver_notice(
        self,
        *,
        notice_event_id: str,
        operational_now: int | None = None,
        temporal_pins: dict[str, object],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> SocialDeliveryCallerResult:
        """Deliver only to the receiver bound by the Government source facts.

        This is the production recipient-selection rule for this bounded slice:
        the contract/acquisition receiver is the sole admitted recipient.  A
        caller cannot substitute an arbitrary character or organization scope.
        """
        source = self.store.get_event(notice_event_id) if self._has_event(notice_event_id) else None
        recipient = self._bound_receiver(source) if source is not None else None
        if recipient is None:
            return self._reject("social_delivery_recipient_binding_invalid", source)
        try:
            world_now = temporal_pins["sampled_at"]
            boundary = temporal_pins["confirmation_boundary"]
            if (type(world_now) is not int or type(boundary) is not int
                    or world_now < 0 or world_now != boundary):
                raise ValueError("confirmed_boundary_mismatch")
        except (KeyError, TypeError, ValueError):
            return self._reject("social_delivery_temporal_source_invalid", source)
        if not verify_temporal_authorization(
            pins=temporal_pins, expected_participant=self.PARTICIPANT,
            expected_cutoff=world_now,
            expected_timeline=str(temporal_pins.get("timeline_id", "")), grant_key="social",
        ):
            return self._reject("social_delivery_temporal_source_missing", source)
        if (self.store.get_idempotency_record(self.PARTICIPANT, idempotency_key) is None
                and source.stream_revision != self.store.get_stream_head(source.stream_id)):
            return self._reject("social_delivery_notice_source_stale", source)
        payload = source.payload
        effective_from = payload.get("effective_from")
        effective_to = payload.get("effective_to")
        if (
            type(effective_from) is not int
            or type(effective_to) is not int
            or effective_from < 0
            or effective_to <= effective_from
            or payload.get("validity_policy_revision") != "policy:government-public-milling-validity@1"
        ):
            return self._reject("social_delivery_temporal_policy_missing", source)
        return self._deliver_notice(
            notice_event_id=notice_event_id,
            recipient_ref=recipient,
            world_now=world_now,
            operational_now=operational_now,
            effective_from=effective_from,
            effective_to=effective_to,
            operational_cutoff=None,
            temporal_pins=temporal_pins,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def expire_bound_receiver_notice(
        self,
        *,
        notice_event_id: str,
        operational_now: int | None = None,
        temporal_pins: dict[str, object],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> SocialDeliveryCallerResult:
        """Expire the delivery bound to the Government notice.

        Expiry is a second application ingress over the same admitted source,
        Population cadence grant and recipient binding as delivery.  It never
        accepts a caller-selected recipient or operational cutoff.
        """
        source = self.store.get_event(notice_event_id) if self._has_event(notice_event_id) else None
        recipient = self._bound_receiver(source) if source is not None else None
        if recipient is None:
            return self._reject("social_delivery_recipient_binding_invalid", source)
        try:
            world_now = temporal_pins["sampled_at"]
            boundary = temporal_pins["confirmation_boundary"]
            if (type(world_now) is not int or type(boundary) is not int
                    or world_now < 0 or world_now != boundary):
                raise ValueError("confirmed_boundary_mismatch")
        except (KeyError, TypeError, ValueError):
            return self._reject("social_delivery_temporal_source_invalid", source)
        if not verify_temporal_authorization(
            pins=temporal_pins, expected_participant=self.PARTICIPANT,
            expected_cutoff=world_now,
            expected_timeline=str(temporal_pins.get("timeline_id", "")), grant_key="social",
        ):
            return self._reject("social_delivery_temporal_source_missing", source)
        payload = source.payload
        effective_from = payload.get("effective_from")
        effective_to = payload.get("effective_to")
        if (
            type(effective_from) is not int
            or type(effective_to) is not int
            or effective_from < 0
            or effective_to <= effective_from
            or payload.get("validity_policy_revision") != "policy:government-public-milling-validity@1"
        ):
            return self._reject("social_delivery_temporal_policy_missing", source)
        result = self.authority.expire_delivery(
            delivery_ref=f"social-delivery:{notice_event_id}:{recipient}",
            recipient_ref=recipient,
            world_now=world_now,
            operational_now=operational_now,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return SocialDeliveryCallerResult(result, source.event_id, source.stream_revision)

    def _bound_receiver(self, source: object | None) -> str | None:
        if (
            source is None
            or getattr(source, "event_type", None) != self.NOTICE_TYPE
            or getattr(source, "visibility_policy", None) != "project"
        ):
            return None
        payload = getattr(source, "payload", {})
        created_id = payload.get("source_contract_created_event_id")
        if not isinstance(created_id, str):
            return None
        try:
            created = self.store.get_event(created_id)
            acquisition_id = created.payload.get("acquisition_event_id")
            acquisition = self.store.get_event(str(acquisition_id))
        except (KeyError, TypeError):
            return None
        party_refs = created.payload.get("party_refs")
        receiver = acquisition.payload.get("owner_ref")
        if (
            created.event_type != "gameplay.contract.record_created"
            or created.visibility_policy != "authority_only"
            or created.payload.get("facility_ref") != payload.get("facility_ref")
            or created.payload.get("project_ref") != payload.get("project_ref")
            or acquisition.event_type != "gameplay.construction_production.facility_acquired"
            or acquisition.visibility_policy != "project"
            or acquisition.payload.get("facility_ref") != payload.get("facility_ref")
            or acquisition.payload.get("plot_ref") != payload.get("project_ref")
            or acquisition.payload.get("jurisdiction_ref") != payload.get("jurisdiction_ref")
            or not isinstance(receiver, str)
            or not receiver.startswith(("organization:", "org:"))
            or receiver == payload.get("organization_ref")
            or not isinstance(party_refs, list)
            or len(party_refs) != 2
            or party_refs[0] != payload.get("organization_ref")
            or party_refs[1] != receiver
        ):
            return None
        return receiver

    def _has_event(self, event_id: str) -> bool:
        try:
            self.store.get_event(event_id)
        except KeyError:
            return False
        return True

    @staticmethod
    def _reject(code: str, source: object | None = None) -> SocialDeliveryCallerResult:
        return SocialDeliveryCallerResult(SocialDeliveryResult(False, code), getattr(source, "event_id", None), getattr(source, "stream_revision", None))


__all__ = ["GovernmentPublicMillingSocialDeliveryCaller", "SocialDeliveryCallerResult"]
