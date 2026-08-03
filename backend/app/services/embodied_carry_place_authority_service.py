from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService


class CarryPlaceSettlementResult(BaseModel):
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


class _DropTargetProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ref: str
    occupied_by_ref: str = ""
    scene_revision: int
    authority_transaction_id: str = ""
    source: str = "backend_authority"


class EmbodiedCarryPlaceAuthorityService:
    """Minimal Phase 7 grab-carry-place authority slice over Gameplay append_batch."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        dispatcher: GameplayOutboxDispatcher,
        evidence_ledger: EmbodiedEvidenceLedger,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._session_service = EmbodiedInteractionSessionService(
            store=store,
            dispatcher=dispatcher,
            evidence_ledger=evidence_ledger,
        )
        self._projection_by_asset: dict[str, _PossessionProjection] = {}
        self._drop_target_by_ref: dict[str, _DropTargetProjection] = {}
        self._receipts_by_idempotency_key: dict[str, tuple[str, CarryPlaceSettlementResult]] = {}

    def seed_asset_possession(self, *, asset_ref: str, custody_holder_ref: str, owner_ref: str) -> None:
        self._projection_by_asset[asset_ref] = _PossessionProjection(
            asset_ref=asset_ref,
            custody_holder_ref=custody_holder_ref,
            owner_ref=owner_ref,
        )

    def seed_drop_target(self, *, target_ref: str, occupied_by_ref: str, scene_revision: int) -> None:
        self._drop_target_by_ref[target_ref] = _DropTargetProjection(
            target_ref=target_ref,
            occupied_by_ref=occupied_by_ref,
            scene_revision=scene_revision,
        )

    def possession_projection(self, asset_ref: str) -> dict[str, object]:
        return self._projection_by_asset[asset_ref].model_dump()

    def drop_target_projection(self, target_ref: str) -> dict[str, object]:
        return self._drop_target_by_ref[target_ref].model_dump()

    def tracked_drop_target_projection(self, target_ref: str) -> dict[str, object] | None:
        projection = self._drop_target_by_ref.get(target_ref)
        return projection.model_dump() if projection is not None else None

    def apply_committed_custody_transfer(
        self,
        *,
        asset_ref: str,
        expected_holder_ref: str,
        custody_holder_ref: str,
        authority_transaction_id: str,
        released_drop_target_ref: str = "",
        occupied_drop_target_ref: str = "",
    ) -> bool:
        """Refresh the in-memory custody read model after an external atomic batch."""

        projection = self._projection_by_asset.get(asset_ref)
        released_target = self._drop_target_by_ref.get(released_drop_target_ref)
        occupied_target = self._drop_target_by_ref.get(occupied_drop_target_ref)
        if projection is None or projection.custody_holder_ref != expected_holder_ref:
            return False
        if released_drop_target_ref and (
            released_target is None or released_target.occupied_by_ref != asset_ref
        ):
            return False
        if occupied_drop_target_ref and (
            occupied_target is None or occupied_target.occupied_by_ref
        ):
            return False
        self._projection_by_asset[asset_ref] = _PossessionProjection(
            asset_ref=asset_ref,
            custody_holder_ref=custody_holder_ref,
            owner_ref=projection.owner_ref,
            authority_transaction_id=authority_transaction_id,
        )
        if released_target is not None:
            self._drop_target_by_ref[released_drop_target_ref] = _DropTargetProjection(
                target_ref=released_drop_target_ref,
                occupied_by_ref="",
                scene_revision=released_target.scene_revision + 1,
                authority_transaction_id=authority_transaction_id,
            )
        if occupied_target is not None:
            self._drop_target_by_ref[occupied_drop_target_ref] = _DropTargetProjection(
                target_ref=occupied_drop_target_ref,
                occupied_by_ref=asset_ref,
                scene_revision=occupied_target.scene_revision + 1,
                authority_transaction_id=authority_transaction_id,
            )
        return True

    def apply_local_carry_hint(
        self,
        *,
        asset_ref: str,
        carried_by_ref: str,
        intended_drop_target_ref: str,
        source_ref: str,
    ) -> dict[str, object]:
        _ = (asset_ref, carried_by_ref, intended_drop_target_ref, source_ref)
        return {
            "accepted": True,
            "authority_mutation": False,
            "reason": "presentation_hint_only",
        }

    def start_carry_place(
        self,
        *,
        session_id: str,
        asset_ref: str,
        actor_ref: str,
        source_holder_ref: str,
        drop_target_ref: str,
        causation_id: str,
        correlation_id: str,
    ) -> CarryPlaceSettlementResult:
        projection = self._projection_by_asset.get(asset_ref)
        if projection is None:
            return CarryPlaceSettlementResult(accepted=False, error_code="asset_unknown")
        drop_target = self._drop_target_by_ref.get(drop_target_ref)
        if drop_target is None:
            return CarryPlaceSettlementResult(accepted=False, error_code="drop_target_unknown")
        if drop_target.occupied_by_ref:
            return CarryPlaceSettlementResult(accepted=False, error_code="drop_target_occupied")
        if projection.custody_holder_ref != source_holder_ref:
            return CarryPlaceSettlementResult(accepted=False, error_code="source_custody_mismatch")

        proposed = self._session_service.propose(
            session_id=session_id,
            semantic_action="grab-carry-place",
            initiator_ref=actor_ref,
            participant_refs=[actor_ref, drop_target_ref],
            target_refs=[asset_ref, source_holder_ref, drop_target_ref],
            authority_preflight_ref=f"preflight:{session_id}",
            policy_revision=3,
            scene_revision=drop_target.scene_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        if not proposed.accepted:
            return CarryPlaceSettlementResult(accepted=False, error_code=proposed.error_code)
        accepted = self._session_service.accept(
            session_id=session_id,
            participant_ref=drop_target_ref,
            causation_id=f"{causation_id}:accept:{drop_target_ref}",
            payload_digest=self._digest({"session_id": session_id, "participant_ref": drop_target_ref}),
        )
        if not accepted.accepted:
            return CarryPlaceSettlementResult(accepted=False, error_code=accepted.error_code)
        realizing = self._session_service.start_realizing(
            session_id=session_id,
            causation_id=f"{causation_id}:realize",
        )
        return CarryPlaceSettlementResult(
            accepted=realizing.accepted,
            transaction_id=realizing.append_result.transaction_id if realizing.append_result is not None else "",
            error_code=realizing.error_code,
            append_result=realizing.append_result,
        )

    def settle_carry_place(
        self,
        *,
        session_id: str,
        asset_ref: str,
        actor_ref: str,
        source_holder_ref: str,
        drop_target_ref: str,
        participant_observations: dict[str, str],
        idempotency_key: str,
        payload_digest: str,
        expected_stream_revisions: dict[str, int] | None = None,
    ) -> CarryPlaceSettlementResult:
        existing = self._receipts_by_idempotency_key.get(idempotency_key)
        if existing is not None:
            existing_digest, existing_receipt = existing
            if existing_digest == payload_digest:
                return existing_receipt.model_copy(update={"idempotent": True}, deep=True)
            return CarryPlaceSettlementResult(accepted=False, error_code="idempotency_key_reused")

        projection = self._projection_by_asset.get(asset_ref)
        if projection is None:
            return CarryPlaceSettlementResult(accepted=False, error_code="asset_unknown")
        drop_target = self._drop_target_by_ref.get(drop_target_ref)
        if drop_target is None:
            return CarryPlaceSettlementResult(accepted=False, error_code="drop_target_unknown")
        if projection.custody_holder_ref != source_holder_ref:
            return CarryPlaceSettlementResult(accepted=False, error_code="source_custody_mismatch")
        if drop_target.occupied_by_ref:
            return CarryPlaceSettlementResult(accepted=False, error_code="drop_target_occupied")
        if self._session_service.session_state(session_id) != "realizing":
            return CarryPlaceSettlementResult(accepted=False, error_code="session_not_realizing")
        if set(participant_observations) != {actor_ref, drop_target_ref}:
            return CarryPlaceSettlementResult(accepted=False, error_code="participant_observations_incomplete")

        session_stream = f"session:{session_id}"
        possession_stream = f"inventory:possession:{asset_ref}"
        carry_stream = f"embodied:carry:{session_id}"
        occupancy_stream = f"scene:occupancy:{drop_target_ref}"
        place_stream = f"embodied:place:{session_id}"
        expected = {
            session_stream: self._store.get_stream_head(session_stream),
            possession_stream: self._store.get_stream_head(possession_stream),
            carry_stream: self._store.get_stream_head(carry_stream),
            occupancy_stream: self._store.get_stream_head(occupancy_stream),
            place_stream: self._store.get_stream_head(place_stream),
        }
        if expected_stream_revisions:
            expected.update(expected_stream_revisions)

        transaction_id = f"tx:{session_id}:carry-place:{self._store.get_stream_head(place_stream) + 1}"
        command_id = f"cmd:{session_id}:carry-place:settle"
        next_scene_revision = drop_target.scene_revision + 1
        event_payloads = [
            (
                "embodied.interaction_session.participant_observed",
                session_stream,
                {
                    "session_id": session_id,
                    "participant_ref": actor_ref,
                    "attempt_ref": f"attempt:{session_id}:{actor_ref}",
                    "terminal_status": "completed",
                    "payload_digest": participant_observations[actor_ref],
                },
            ),
            (
                "embodied.interaction_session.participant_observed",
                session_stream,
                {
                    "session_id": session_id,
                    "participant_ref": drop_target_ref,
                    "attempt_ref": f"attempt:{session_id}:{drop_target_ref}",
                    "terminal_status": "completed",
                    "payload_digest": participant_observations[drop_target_ref],
                },
            ),
            (
                "inventory.custody_changed",
                possession_stream,
                {
                    "asset_ref": asset_ref,
                    "from_holder_ref": source_holder_ref,
                    "to_holder_ref": drop_target_ref,
                    "custody_holder_ref": drop_target_ref,
                    "owner_ref": projection.owner_ref,
                    "source_session_id": session_id,
                },
            ),
            (
                "embodied.carry.started",
                carry_stream,
                {
                    "session_id": session_id,
                    "asset_ref": asset_ref,
                    "actor_ref": actor_ref,
                    "source_holder_ref": source_holder_ref,
                    "drop_target_ref": drop_target_ref,
                    "presentation_hint_only": True,
                },
            ),
            (
                "scene.occupancy.changed",
                occupancy_stream,
                {
                    "target_ref": drop_target_ref,
                    "previous_occupied_by_ref": "",
                    "occupied_by_ref": asset_ref,
                    "scene_revision": next_scene_revision,
                    "source_session_id": session_id,
                },
            ),
            (
                "embodied.place.settled",
                place_stream,
                {
                    "session_id": session_id,
                    "asset_ref": asset_ref,
                    "actor_ref": actor_ref,
                    "source_holder_ref": source_holder_ref,
                    "drop_target_ref": drop_target_ref,
                    "custody_holder_ref": drop_target_ref,
                    "owner_ref": projection.owner_ref,
                    "settlement_ref": f"settlement:{session_id}",
                    "placement_directive": {
                        "mode": "place_for_presentation",
                        "asset_ref": asset_ref,
                        "place_at_ref": drop_target_ref,
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
                        f"attempt:{session_id}:{actor_ref}",
                        f"attempt:{session_id}:{drop_target_ref}",
                    ],
                },
            ),
        ]
        events = []
        outbox_entries = []
        for index, (event_type, stream_id, payload) in enumerate(event_payloads, start=1):
            event_id = f"evt:{session_id}:carry-place:{index}"
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
                        "source": {"layer": "embodied", "system": "carry_place_authority"},
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
                "pinned_revisions": {"policy": 3, "scene": drop_target.scene_revision},
                "events": events,
                "idempotency_record": {
                    "principal_ref": "embodied_carry_place_authority",
                    "idempotency_key": idempotency_key,
                    "payload_digest": payload_digest,
                },
                "outbox_entries": outbox_entries,
                "result_digest": self._digest(
                    {
                        "session_id": session_id,
                        "asset_ref": asset_ref,
                        "drop_target_ref": drop_target_ref,
                    }
                ),
                "projection_refresh_hints": [
                    {"projection_id": "embodied_place", "stream_id": place_stream, "reason": "place_settled"},
                    {"projection_id": "inventory_possession", "stream_id": possession_stream, "reason": "place_settled"},
                    {"projection_id": "scene_occupancy", "stream_id": occupancy_stream, "reason": "place_settled"},
                ],
            }
        )
        if not append_result.committed:
            return CarryPlaceSettlementResult(
                accepted=False,
                transaction_id=append_result.transaction_id,
                error_code=append_result.failure.error_code if append_result.failure is not None else "append_batch_failed",
                append_result=append_result,
            )

        self._projection_by_asset[asset_ref] = _PossessionProjection(
            asset_ref=asset_ref,
            custody_holder_ref=drop_target_ref,
            owner_ref=projection.owner_ref,
            authority_transaction_id=transaction_id,
        )
        self._drop_target_by_ref[drop_target_ref] = _DropTargetProjection(
            target_ref=drop_target_ref,
            occupied_by_ref=asset_ref,
            scene_revision=next_scene_revision,
            authority_transaction_id=transaction_id,
        )
        self._session_service.apply_external_committed_projection(
            session_id=session_id,
            attempt_refs=[f"attempt:{session_id}:{actor_ref}", f"attempt:{session_id}:{drop_target_ref}"],
            settlement_ref=f"settlement:{session_id}",
            causation_id=command_id,
        )
        self._dispatcher.dispatch_pending()
        receipt = CarryPlaceSettlementResult(
            accepted=True,
            transaction_id=transaction_id,
            append_result=append_result,
        )
        self._receipts_by_idempotency_key[idempotency_key] = (payload_digest, receipt)
        return receipt

    @staticmethod
    def _digest(payload: dict[str, object]) -> str:
        return "sha256:" + sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()
