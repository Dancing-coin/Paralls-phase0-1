from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayOutboxEntry
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority
from app.gameplay.settlement_plan import build_atomic_event_batch


_DELIVERY_EVENT = "gameplay.social.delivery_recorded@2"
_INFORMATION_EVENT = "gameplay.information.knowledge_updated@1"
_DELIVERY_PRINCIPAL = "authority:p5:social-delivery"
_INFORMATION_PRINCIPAL = "authority:information"


@dataclass(frozen=True)
class InformationUpdateResult:
    committed: bool
    error_code: str | None = None
    append_result: AppendBatchResult | None = None


class InformationAuthority:
    """Record recipient knowledge only after a committed Social delivery."""

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._delivery = SocialDeliveryAuthority(store=store)

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
            if (prior is not None and prior.event_type == _INFORMATION_EVENT
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
            event_specs=((_INFORMATION_EVENT, event_payload),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        batch = batch.model_copy(update={
            "events": [batch.events[0].model_copy(update={
                "visibility_policy": f"actor:{recipient_ref}",
            }, deep=True)],
            "outbox_entries": [GameplayOutboxEntry(
                outbox_id=f"outbox:{batch.events[0].event_id}:information",
                transaction_id=batch.transaction_id,
                event_id=batch.events[0].event_id,
                global_sequence=0,
                topic=_INFORMATION_EVENT,
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
