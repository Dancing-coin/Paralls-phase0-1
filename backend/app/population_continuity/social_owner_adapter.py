from __future__ import annotations

from typing import Any

from app.gameplay.organization_government_social_platform_runtime import PopulationSignalMaterializationProposalIntent
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import PopulationOwnerReceipt, PopulationReadSet


class SocialPopulationSignalOwnerExecutor:
    """Route one public signal through the existing SocialFactAuthority only."""

    OWNER_REF = "authority:p5:social"
    EVENT_FAMILY = "gameplay.social.population_signal_recorded@1"
    CAPABILITY_ID = "population:social-population-signal:v1"
    BINDING_REF = "binding:population-materialization@1"

    def __init__(self, *, authority: Any) -> None:
        self._authority = authority

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        rejected = lambda: PopulationOwnerReceipt(
            receipt_ref=f"rejected:{intent.intent_ref}",
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=False,
            revision_vector={},
            zero_write=True,
        )
        if (
            intent.intent_kind != "social_population_signal"
            or intent.package_revision != self.CAPABILITY_ID
            or intent.privacy_scope != "public"
        ):
            return rejected()
        projection = next((item for item in read_set.projections if item.ref == intent.source_ref), None)
        if projection is None or projection.scope != "public" or dict(projection.revision_vector) != dict(intent.expected_revisions):
            return rejected()
        payload = projection.payload
        if set(payload).intersection({"stream_ref", "event_family", "owner_ref", "participant_refs", "relationship_ref"}):
            return rejected()
        try:
            signal_ref = str(payload["signal_ref"])
            provenance_ref = str(payload["provenance_ref"])
            source_revision = int(payload["source_revision_pin"])
            source_stream_ref = str(payload["source_stream_ref"])
            canonical_key = f"social:population-signal:{signal_ref}:{source_revision}:v1"
            if (
                intent.expected_revisions.get(source_stream_ref) != source_revision
                or payload.get("idempotency_key") != canonical_key
                or payload.get("visibility_scope") != "public"
                or payload.get("materialization_state") != "proposed"
                or payload.get("source_domain") != "social"
            ):
                return rejected()
            stream_ref = f"gameplay:social:population:{signal_ref}"
            store = getattr(self._authority, "_store", None)
            if store is not None and store.get_stream_head(stream_ref) > 0:
                existing = next(
                    (
                        event
                        for event in store.read_stream(stream_ref)
                        if event.event_type == self.EVENT_FAMILY
                        and event.payload.get("signal_ref") == signal_ref
                        and event.payload.get("source_revision_pin") == source_revision
                    ),
                    None,
                )
                if existing is not None:
                    if existing.payload.get("provenance_ref") != provenance_ref:
                        return rejected()
                    return PopulationOwnerReceipt(
                        receipt_ref=existing.event_id,
                        owner_ref=self.OWNER_REF,
                        event_family=self.EVENT_FAMILY,
                        committed=True,
                        revision_vector={stream_ref: existing.stream_revision},
                        zero_write=True,
                        idempotency_status="duplicate_replayed",
                    )
            authored = PopulationSignalMaterializationProposalIntent(
                signal_ref=signal_ref,
                provenance_ref=provenance_ref,
                source_revision_pin=source_revision,
                materialization_state="proposed",
                visibility_scope="public",
            )
            result = self._authority.record_admitted_population_signal_materialization_proposal(
                intent=authored,
                binding_ref=self.BINDING_REF,
                command_id=intent.intent_ref,
                idempotency_key=canonical_key,
                causation_id=intent.source_ref,
                correlation_id=intent.correlation_id,
                expected_revision=0,
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return rejected()
        receipt = getattr(result, "receipt", None)
        committed = receipt is not None and bool(getattr(result.resolution, "result_kind", "") == "committed_success")
        status = str(getattr(receipt, "idempotency_status", "rejected")) if receipt is not None else "rejected"
        revisions = dict(getattr(receipt, "stream_revisions", {}) or {}) if receipt is not None else {}
        event_ids = tuple(str(item) for item in (getattr(receipt, "committed_event_ids", ()) or ())) if receipt is not None else ()
        return PopulationOwnerReceipt(
            receipt_ref=event_ids[0] if event_ids else f"receipt:{intent.intent_ref}",
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=committed,
            revision_vector=revisions,
            zero_write=not committed or status == "duplicate_replayed",
            idempotency_status=status,
        )


__all__ = ["SocialPopulationSignalOwnerExecutor"]
