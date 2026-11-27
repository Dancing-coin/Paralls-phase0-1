from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayOutboxEntry
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryWindow
from app.gameplay.settlement_plan import build_atomic_event_batch


_DELIVERY_EVENT = "gameplay.social.delivery_recorded@2"
_DELIVERY_PRINCIPAL = "authority:p5:social-delivery"
_INFORMATION_PRINCIPAL = "authority:information"
INFORMATION_KNOWLEDGE_EVENT_TYPE = "gameplay.information.knowledge_updated@1"
INFORMATION_REPORT_EVENT = "gameplay.information.siege_report_published@1"
INFORMATION_REPORT_FACT_TYPE = "fact:information:siege:report"
INFORMATION_REPORT_PRINCIPAL = "authority:information:report-publisher"


class SiegeReportPublicationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    authority_ref: str = Field(min_length=1, max_length=160)
    receipt_id: str = Field(min_length=1, max_length=160)
    report_ref: str = Field(min_length=1, max_length=160)
    recipient_ref: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=512)
    source_event_id: str = Field(min_length=1, max_length=200)
    source_stream_id: str = Field(min_length=1, max_length=200)
    source_revision: int = Field(ge=1, strict=True)
    effective_from: int = Field(ge=0, strict=True)
    effective_to: int = Field(ge=1, strict=True)
    signature: str = Field(min_length=64, max_length=64)

    @field_validator("report_ref")
    @classmethod
    def validate_report_ref(cls, value: str) -> str:
        if not value.startswith("report:"):
            raise ValueError("information_report_ref_invalid")
        return value

    @field_validator("recipient_ref")
    @classmethod
    def validate_recipient_ref(cls, value: str) -> str:
        if not value.startswith("character:"):
            raise ValueError("information_report_recipient_invalid")
        return value

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("information_report_summary_invalid")
        return value

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError("information_report_signature_invalid") from exc
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "SiegeReportPublicationReceipt":
        if self.effective_to <= self.effective_from:
            raise ValueError("information_report_window_invalid")
        return self

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json", exclude={"signature"}),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")


@dataclass(frozen=True)
class InformationReportPublicationResult:
    committed: bool
    error_code: str | None = None
    report_append_result: AppendBatchResult | None = None
    delivery_append_result: AppendBatchResult | None = None


@dataclass(frozen=True)
class InformationUpdateResult:
    committed: bool
    error_code: str | None = None
    append_result: AppendBatchResult | None = None


class InformationAuthority:
    """Publish signed siege reports and record knowledge from committed Social delivery."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        report_authority_secrets: Mapping[str, str] | None = None,
    ) -> None:
        self._store = store
        self._delivery = SocialDeliveryAuthority(store=store)
        self._report_authority_secrets = dict(report_authority_secrets or {})

    @staticmethod
    def report_stream_id(*, recipient_ref: str, report_ref: str) -> str:
        return f"gameplay:information:report:{recipient_ref}:{report_ref}"

    def publish_siege_report(
        self,
        *,
        receipt: SiegeReportPublicationReceipt,
        world_now: int | None,
    ) -> InformationReportPublicationResult:
        secret = self._report_authority_secrets.get(receipt.authority_ref)
        if secret is None or not hmac.compare_digest(
            hmac.new(secret.encode("utf-8"), receipt.canonical_bytes(), hashlib.sha256).hexdigest(),
            receipt.signature,
        ):
            return InformationReportPublicationResult(
                False, error_code="information_report_signature_invalid"
            )

        report_stream = self.report_stream_id(
            recipient_ref=receipt.recipient_ref,
            report_ref=receipt.report_ref,
        )
        identity_digest = hashlib.sha256(
            json.dumps((receipt.authority_ref, receipt.receipt_id)).encode("utf-8")
        ).hexdigest()
        report_idempotency_key = f"information-report:{identity_digest}"
        command_id = f"information-report:{identity_digest}"
        event_payload = {
            "fact_type": INFORMATION_REPORT_FACT_TYPE,
            "report_ref": receipt.report_ref,
            "recipient_ref": receipt.recipient_ref,
            "summary": receipt.summary,
            "source_event_id": receipt.source_event_id,
            "source_stream_id": receipt.source_stream_id,
            "source_revision": receipt.source_revision,
            "effective_from": receipt.effective_from,
            "effective_to": receipt.effective_to,
        }

        report_append_result = self._store.get_by_idempotency(
            INFORMATION_REPORT_PRINCIPAL, report_idempotency_key
        )
        if report_append_result is not None:
            prior_event = self._prior_event(report_append_result)
            if (prior_event is None or prior_event.event_type != INFORMATION_REPORT_EVENT
                    or prior_event.schema_version != 1
                    or prior_event.stream_id != report_stream
                    or any(prior_event.payload.get(key) != value for key, value in event_payload.items())
                    or prior_event.visibility_policy != f"actor:{receipt.recipient_ref}"):
                return InformationReportPublicationResult(
                    False, error_code="information_report_idempotency_key_reused"
                )
            report_append_result = report_append_result.model_copy(update={
                "idempotency_status": "duplicate_replayed",
            }, deep=True)
            report_event = prior_event
        else:
            if type(world_now) is not int or world_now < 0:
                return InformationReportPublicationResult(
                    False, error_code="information_world_clock_unavailable"
                )
            if not receipt.effective_from <= world_now < receipt.effective_to:
                return InformationReportPublicationResult(
                    False, error_code="information_report_window_invalid"
                )
            source = self._event(receipt.source_event_id)
            if source is None or source.stream_id != receipt.source_stream_id:
                return InformationReportPublicationResult(
                    False, error_code="information_report_source_invalid"
                )
            if (source.stream_revision != receipt.source_revision
                    or self._store.get_stream_head(receipt.source_stream_id) != receipt.source_revision):
                return InformationReportPublicationResult(
                    False, error_code="information_report_source_stale"
                )

            batch = build_atomic_event_batch(
                command_id=command_id,
                principal_ref=INFORMATION_REPORT_PRINCIPAL,
                stream_id=report_stream,
                expected_revision=0,
                read_stream_revisions={receipt.source_stream_id: receipt.source_revision},
                event_specs=((INFORMATION_REPORT_EVENT, {
                    **event_payload, "published_at_world_tick": world_now,
                }),),
                idempotency_key=report_idempotency_key,
                causation_id=receipt.source_event_id,
                correlation_id=f"siege-report:{receipt.report_ref}",
            )
            batch = batch.model_copy(update={
                "events": [batch.events[0].model_copy(update={
                    "visibility_policy": f"actor:{receipt.recipient_ref}",
                    "event_time": world_now,
                }, deep=True)],
                "outbox_entries": [GameplayOutboxEntry(
                    outbox_id=f"outbox:{batch.events[0].event_id}:siege-report",
                    transaction_id=batch.transaction_id,
                    event_id=batch.events[0].event_id,
                    global_sequence=0,
                    topic=INFORMATION_REPORT_EVENT,
                    audience=f"actor:{receipt.recipient_ref}",
                    payload_projection={
                        "report_ref": receipt.report_ref,
                        "recipient_ref": receipt.recipient_ref,
                        "status": "published",
                        "routing": {"target_ids": [receipt.recipient_ref]},
                    },
                )],
            }, deep=True)
            report_append_result = self._store.append_batch(batch)
            if not report_append_result.committed:
                return InformationReportPublicationResult(
                    False,
                    error_code=(report_append_result.failure.error_code
                                if report_append_result.failure else "information_report_append_failed"),
                    report_append_result=report_append_result,
                )
            report_event = self._prior_event(report_append_result)
            if report_event is None:
                return InformationReportPublicationResult(
                    False, error_code="information_report_append_receipt_invalid",
                    report_append_result=report_append_result,
                )

        delivery_result = self._delivery.record_delivery(
            delivery_ref=f"delivery:{receipt.report_ref}:{receipt.recipient_ref}",
            source_stream_id=report_event.stream_id,
            source_revision=report_event.stream_revision,
            source_event_id=report_event.event_id,
            recipient_ref=receipt.recipient_ref,
            window=SocialDeliveryWindow(
                receipt.effective_from,
                receipt.effective_to,
                None,
            ),
            world_now=report_event.payload["published_at_world_tick"],
            command_id=f"social-delivery:{identity_digest}",
            idempotency_key=f"information-report-delivery:{identity_digest}",
            causation_id=report_event.event_id,
            correlation_id=report_event.correlation_id,
        )
        if not delivery_result.committed or delivery_result.append_result is None:
            return InformationReportPublicationResult(
                False,
                error_code=delivery_result.error_code or "information_report_delivery_failed",
                report_append_result=report_append_result,
                delivery_append_result=delivery_result.append_result,
            )
        return InformationReportPublicationResult(
            True,
            error_code=delivery_result.error_code,
            report_append_result=report_append_result,
            delivery_append_result=delivery_result.append_result,
        )

    @staticmethod
    def stream_id(*, recipient_ref: str, report_ref: str) -> str:
        return f"gameplay:information:knowledge:{recipient_ref}:{report_ref}"

    def update_from_delivery(
        self,
        *,
        delivery: GameplayEvent,
        world_now: int,
        command_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> InformationUpdateResult:
        """Handle a Gateway reaction using the committed delivery as its target."""
        recipient_ref = delivery.payload.get("recipient_ref")
        report_ref = delivery.payload.get("source_event_id")
        if (
            delivery.event_type != _DELIVERY_EVENT
            or not isinstance(recipient_ref, str)
            or not isinstance(report_ref, str)
        ):
            return self._reject("information_delivery_source_invalid")
        stream = self.stream_id(recipient_ref=recipient_ref, report_ref=report_ref)
        return self.update_knowledge(
            delivery_event_id=delivery.event_id,
            recipient_ref=recipient_ref,
            world_now=world_now,
            expected_revision=self._store.get_stream_head(stream),
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=delivery.event_id,
            correlation_id=correlation_id,
        )

    def update_knowledge(
        self,
        *,
        delivery_event_id: str,
        recipient_ref: str,
        world_now: int,
        expected_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> InformationUpdateResult:
        if (not isinstance(delivery_event_id, str) or not delivery_event_id
                or not isinstance(recipient_ref, str) or not recipient_ref.startswith("character:")
                or type(world_now) is not int or world_now < 0
                or type(expected_revision) is not int or expected_revision < 0
                or not all((command_id, idempotency_key, causation_id, correlation_id))):
            return self._reject("information_update_input_invalid")

        delivery = self._event(delivery_event_id)
        if delivery is None:
            return self._reject("information_delivery_source_invalid")
        payload = delivery.payload
        if payload.get("recipient_ref") != recipient_ref:
            return self._reject("information_delivery_recipient_mismatch")
        report_ref = payload.get("source_event_id")
        report_stream = payload.get("source_stream_id")
        report_revision = payload.get("source_revision")
        delivery_ref = payload.get("delivery_ref")
        delivery_stream = delivery.stream_id
        if (delivery.event_type != _DELIVERY_EVENT or delivery.schema_version != 2
                or delivery.visibility_policy != f"actor:{recipient_ref}"
                or not isinstance(report_ref, str) or not report_ref
                or not isinstance(report_stream, str) or not report_stream
                or type(report_revision) is not int or report_revision < 1
                or not isinstance(delivery_ref, str) or not delivery_ref
                or delivery_stream != f"gameplay:social:delivery:{recipient_ref}:{delivery_ref}"
                or not self._has_committed_delivery(delivery)):
            return self._reject("information_delivery_source_invalid")

        stream_id = self.stream_id(recipient_ref=recipient_ref, report_ref=report_ref)
        event_payload = {
            "recipient_ref": recipient_ref,
            "report_ref": report_ref,
            "delivery_event_id": delivery.event_id,
            "delivery_ref": delivery_ref,
            "known_at_world_tick": payload.get("known_at_world_tick"),
            "source_stream_id": report_stream,
            "source_revision": report_revision,
        }
        existing = self._store.get_idempotency_record(_INFORMATION_PRINCIPAL, idempotency_key)
        if existing is not None:
            result = self._store.get_by_idempotency(_INFORMATION_PRINCIPAL, idempotency_key)
            prior = self._prior_event(result)
            if (prior is not None and prior.event_type == INFORMATION_KNOWLEDGE_EVENT_TYPE
                    and prior.stream_id == stream_id and prior.payload == event_payload
                    and prior.command_id == command_id
                    and prior.causation_id == causation_id and prior.correlation_id == correlation_id):
                return InformationUpdateResult(
                    True, append_result=result.model_copy(
                        update={"idempotency_status": "duplicate_replayed"}, deep=True
                    ),
                )
            return self._reject("information_idempotency_key_reused")

        visible = self._delivery.view_for(recipient_ref=recipient_ref, world_now=world_now)
        if not any(
            row.get("delivery_ref") == delivery_ref
            and row.get("source_event_id") == report_ref
            and row.get("known_at_world_tick") == event_payload["known_at_world_tick"]
            for row in visible.deliveries
        ):
            return self._reject("information_delivery_not_visible")
        if type(event_payload["known_at_world_tick"]) is not int:
            return self._reject("information_delivery_time_invalid")

        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._reject("information_revision_conflict")
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=_INFORMATION_PRINCIPAL,
            stream_id=stream_id,
            expected_revision=expected_revision,
            read_stream_revisions={
                delivery_stream: delivery.stream_revision,
                report_stream: report_revision,
            },
            event_specs=((INFORMATION_KNOWLEDGE_EVENT_TYPE, event_payload),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        batch = batch.model_copy(update={
            "events": [batch.events[0].model_copy(update={
                "visibility_policy": f"actor:{recipient_ref}",
                "event_time": world_now,
            }, deep=True)],
            "outbox_entries": [GameplayOutboxEntry(
                outbox_id=f"outbox:{batch.events[0].event_id}:information",
                transaction_id=batch.transaction_id,
                event_id=batch.events[0].event_id,
                global_sequence=0,
                topic=INFORMATION_KNOWLEDGE_EVENT_TYPE,
                audience=f"actor:{recipient_ref}",
                payload_projection={
                    "recipient_ref": recipient_ref,
                    "report_ref": report_ref,
                    "delivery_event_id": delivery.event_id,
                },
            )],
        }, deep=True)
        result = self._store.append_batch(batch)
        if not result.committed:
            return self._reject(
                result.failure.error_code if result.failure is not None
                else "information_append_rejected"
            )
        return InformationUpdateResult(True, append_result=result)

    def _has_committed_delivery(self, event: GameplayEvent) -> bool:
        batch = self._store.get_transaction(event.transaction_id)
        if (batch is None or len(batch.events) != 1
                or batch.events[0].event_id != event.event_id
                or batch.idempotency_record.principal_ref != _DELIVERY_PRINCIPAL):
            return False
        receipt = self._store.get_by_idempotency(
            batch.idempotency_record.principal_ref,
            batch.idempotency_record.idempotency_key,
        )
        return bool(
            receipt is not None and receipt.committed
            and receipt.transaction_id == batch.transaction_id
            and receipt.committed_event_ids == [event.event_id]
        )

    def _event(self, event_id: str) -> GameplayEvent | None:
        try:
            return self._store.get_event(event_id)
        except KeyError:
            return None

    def _prior_event(self, result: AppendBatchResult | None) -> GameplayEvent | None:
        if result is None or not result.committed or len(result.committed_event_ids) != 1:
            return None
        return self._event(result.committed_event_ids[0])

    @staticmethod
    def _reject(error_code: str) -> InformationUpdateResult:
        return InformationUpdateResult(False, error_code=error_code)


__all__ = [
    "InformationAuthority",
    "InformationUpdateResult",
]
