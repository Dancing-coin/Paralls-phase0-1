from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService


class HandoffSettlementResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    transaction_id: str = ""
    error_code: str = ""
    idempotent: bool = False
    append_result: AppendBatchResult | None = None


class _PossessionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ref: str
    custody_holder_ref: str
    owner_ref: str
    authority_transaction_id: str = ""
    source: str = "backend_authority"


class EmbodiedHandoffAuthorityService:
    """Minimal Phase 7 handoff authority slice over the Gameplay event spine."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        dispatcher: GameplayOutboxDispatcher,
        evidence_ledger: EmbodiedEvidenceLedger,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._evidence_ledger = evidence_ledger
        self._session_service = EmbodiedInteractionSessionService(
            store=store,
            dispatcher=dispatcher,
            evidence_ledger=evidence_ledger,
        )
        self._projection_by_asset: dict[str, _PossessionProjection] = {}
        self._receipts_by_idempotency_key: dict[str, tuple[str, HandoffSettlementResult]] = {}

    def seed_asset_possession(self, *, asset_ref: str, custody_holder_ref: str, owner_ref: str) -> None:
        self._projection_by_asset[asset_ref] = _PossessionProjection(
            asset_ref=asset_ref,
            custody_holder_ref=custody_holder_ref,
            owner_ref=owner_ref,
        )

    def possession_projection(self, asset_ref: str) -> dict[str, object]:
        projection = self._projection_by_asset[asset_ref]
        return projection.model_dump()

    def apply_local_attachment_hint(self, *, asset_ref: str, attached_to_ref: str, source_ref: str) -> dict[str, object]:
        _ = (asset_ref, attached_to_ref, source_ref)
        return {
            "accepted": True,
            "authority_mutation": False,
            "reason": "presentation_hint_only",
        }

    def start_handoff(
        self,
        *,
        session_id: str,
        asset_ref: str,
        from_actor_ref: str,
        to_actor_ref: str,
        causation_id: str,
        correlation_id: str,
    ) -> HandoffSettlementResult:
        projection = self._projection_by_asset.get(asset_ref)
        if projection is None:
            return HandoffSettlementResult(accepted=False, error_code="asset_unknown")
        if projection.custody_holder_ref != from_actor_ref:
            return HandoffSettlementResult(accepted=False, error_code="custody_holder_mismatch")
        proposed = self._session_service.propose(
            session_id=session_id,
            semantic_action="handoff",
            initiator_ref=from_actor_ref,
            participant_refs=[from_actor_ref, to_actor_ref],
            target_refs=[asset_ref],
            authority_preflight_ref=f"preflight:{session_id}",
            policy_revision=3,
            scene_revision=11,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        if not proposed.accepted:
            return HandoffSettlementResult(accepted=False, error_code=proposed.error_code)
        accepted = self._session_service.accept(
            session_id=session_id,
            participant_ref=to_actor_ref,
            causation_id=f"{causation_id}:accept:{to_actor_ref}",
            payload_digest=self._digest({"session_id": session_id, "participant_ref": to_actor_ref}),
        )
        if not accepted.accepted:
            return HandoffSettlementResult(accepted=False, error_code=accepted.error_code)
        realizing = self._session_service.start_realizing(
            session_id=session_id,
            causation_id=f"{causation_id}:realize",
        )
        return HandoffSettlementResult(
            accepted=realizing.accepted,
            transaction_id=realizing.append_result.transaction_id if realizing.append_result is not None else "",
            error_code=realizing.error_code,
            append_result=realizing.append_result,
        )

    def settle_handoff(
        self,
        *,
        session_id: str,
        asset_ref: str,
        from_actor_ref: str,
        to_actor_ref: str,
        participant_observations: dict[str, str],
        idempotency_key: str,
        payload_digest: str,
        expected_stream_revisions: dict[str, int] | None = None,
    ) -> HandoffSettlementResult:
        existing = self._receipts_by_idempotency_key.get(idempotency_key)
        if existing is not None:
            existing_digest, existing_receipt = existing
            if existing_digest == payload_digest:
                return existing_receipt.model_copy(update={"idempotent": True}, deep=True)
            return HandoffSettlementResult(accepted=False, error_code="idempotency_key_reused")

        projection = self._projection_by_asset.get(asset_ref)
        if projection is None:
            return HandoffSettlementResult(accepted=False, error_code="asset_unknown")
        if projection.custody_holder_ref != from_actor_ref or projection.owner_ref != from_actor_ref:
            return HandoffSettlementResult(accepted=False, error_code="handoff_source_not_authorized")
        if self._session_service.session_state(session_id) != "realizing":
            return HandoffSettlementResult(accepted=False, error_code="session_not_realizing")
        if set(participant_observations) != {from_actor_ref, to_actor_ref}:
            return HandoffSettlementResult(accepted=False, error_code="participant_observations_incomplete")

        session_stream = f"session:{session_id}"
        possession_stream = f"inventory:possession:{asset_ref}"
        ownership_stream = f"ownership:right:{asset_ref}"
        handoff_stream = f"embodied:handoff:{session_id}"
        expected = {
            session_stream: self._store.get_stream_head(session_stream),
            possession_stream: self._store.get_stream_head(possession_stream),
            ownership_stream: self._store.get_stream_head(ownership_stream),
            handoff_stream: self._store.get_stream_head(handoff_stream),
        }
        if expected_stream_revisions:
            expected.update(expected_stream_revisions)

        transaction_id = f"tx:{session_id}:handoff:{self._store.get_stream_head(handoff_stream) + 1}"
        command_id = f"cmd:{session_id}:handoff:settle"
        event_payloads = [
            (
                "embodied.interaction_session.participant_observed",
                session_stream,
                {
                    "session_id": session_id,
                    "participant_ref": from_actor_ref,
                    "attempt_ref": f"attempt:{session_id}:{from_actor_ref}",
                    "terminal_status": "completed",
                    "payload_digest": participant_observations[from_actor_ref],
                },
            ),
            (
                "embodied.interaction_session.participant_observed",
                session_stream,
                {
                    "session_id": session_id,
                    "participant_ref": to_actor_ref,
                    "attempt_ref": f"attempt:{session_id}:{to_actor_ref}",
                    "terminal_status": "completed",
                    "payload_digest": participant_observations[to_actor_ref],
                },
            ),
            (
                "inventory.custody_changed",
                possession_stream,
                {
                    "asset_ref": asset_ref,
                    "from_holder_ref": from_actor_ref,
                    "to_holder_ref": to_actor_ref,
                    "custody_holder_ref": to_actor_ref,
                    "source_session_id": session_id,
                },
            ),
            (
                "ownership.right_transferred",
                ownership_stream,
                {
                    "asset_ref": asset_ref,
                    "from_owner_ref": from_actor_ref,
                    "to_owner_ref": to_actor_ref,
                    "owner_ref": to_actor_ref,
                    "right_kind": "full_title",
                    "source_session_id": session_id,
                },
            ),
            (
                "embodied.handoff.settled",
                handoff_stream,
                {
                    "session_id": session_id,
                    "asset_ref": asset_ref,
                    "from_actor_ref": from_actor_ref,
                    "to_actor_ref": to_actor_ref,
                    "custody_holder_ref": to_actor_ref,
                    "owner_ref": to_actor_ref,
                    "settlement_ref": f"settlement:{session_id}",
                    "attachment_directive": {
                        "mode": "attach_for_presentation",
                        "asset_ref": asset_ref,
                        "attach_to_ref": to_actor_ref,
                        "authority_only": True,
                    },
                },
            ),
            (
                "embodied.interaction_session.committed",
                session_stream,
                {
                    "session_id": session_id,
                    "state": "committed",
                    "settlement_ref": f"settlement:{session_id}",
                    "attempt_refs": [
                        f"attempt:{session_id}:{from_actor_ref}",
                        f"attempt:{session_id}:{to_actor_ref}",
                    ],
                },
            ),
        ]
        events = []
        outbox_entries = []
        for index, (event_type, stream_id, payload) in enumerate(event_payloads, start=1):
            event_id = f"evt:{session_id}:handoff:{index}"
            events.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "schema_version": 1,
                    "stream_id": stream_id,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": transaction_id,
                    "command_id": command_id,
                    "causation_id": command_id,
                    "correlation_id": f"corr:{session_id}",
                    "visibility_policy": "session_public_safe",
                    "payload": dict(payload),
                }
            )
            outbox_entries.append(
                {
                    "outbox_id": f"outbox:{event_id}",
                    "transaction_id": transaction_id,
                    "event_id": event_id,
                    "global_sequence": 0,
                    "topic": event_type,
                    "audience": "godot_room",
                    "payload_projection": {
                        "room_id": "room_demo",
                        "scene_id": "scene_demo",
                        "zone_id": "zone_focus",
                        "source": {"layer": "embodied", "system": "handoff_authority"},
                        "routing": {
                            "audience_mode": "room",
                            "routing_mode": "event_type",
                            "target_ids": ["godot_mirror", "observatory"],
                        },
                        "priority": "p1",
                        "durability": "replayable",
                        "payload": dict(payload),
                    },
                    "delivery_state": "pending",
                    "attempt_count": 0,
                    "last_error": None,
                }
            )

        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": expected,
                "pinned_revisions": {"policy": 3, "scene": 11},
                "events": events,
                "idempotency_record": {
                    "principal_ref": "embodied_handoff_authority",
                    "idempotency_key": idempotency_key,
                    "payload_digest": payload_digest,
                },
                "outbox_entries": outbox_entries,
                "result_digest": self._digest({"session_id": session_id, "asset_ref": asset_ref, "to": to_actor_ref}),
                "projection_refresh_hints": [
                    {"projection_id": "embodied_handoff", "stream_id": handoff_stream, "reason": "handoff_settled"},
                    {"projection_id": "inventory_possession", "stream_id": possession_stream, "reason": "handoff_settled"},
                    {"projection_id": "ownership_right", "stream_id": ownership_stream, "reason": "handoff_settled"},
                ],
            }
        )
        if not append_result.committed:
            return HandoffSettlementResult(
                accepted=False,
                transaction_id=append_result.transaction_id,
                error_code=append_result.failure.error_code if append_result.failure is not None else "append_batch_failed",
                append_result=append_result,
            )

        self._projection_by_asset[asset_ref] = _PossessionProjection(
            asset_ref=asset_ref,
            custody_holder_ref=to_actor_ref,
            owner_ref=to_actor_ref,
            authority_transaction_id=transaction_id,
        )
        self._session_service.apply_external_committed_projection(
            session_id=session_id,
            attempt_refs=[f"attempt:{session_id}:{from_actor_ref}", f"attempt:{session_id}:{to_actor_ref}"],
            settlement_ref=f"settlement:{session_id}",
            causation_id=command_id,
        )
        self._dispatcher.dispatch_pending()
        receipt = HandoffSettlementResult(
            accepted=True,
            transaction_id=transaction_id,
            append_result=append_result,
        )
        self._receipts_by_idempotency_key[idempotency_key] = (payload_digest, receipt)
        return receipt

    @staticmethod
    def _digest(payload: dict[str, object]) -> str:
        return "sha256:" + sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()
