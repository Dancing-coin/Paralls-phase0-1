from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from app.character_agent.models.simulation_seed import CharacterMemoryCandidate, CharacterSimulationSeedCandidate

from .siming_contracts import PopulationProjection, PopulationReadSet


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _projection_actor(projection: PopulationProjection) -> str:
    payload = projection.payload
    actor = payload.get("actor_ref") or payload.get("profile_ref") or payload.get("character_ref")
    return str(actor or projection.ref)


class CharacterSeedPlanner:
    """Derives pending actor inputs from an immutable population read set."""

    ADMITTED_BEHAVIORS = frozenset(
        {
            "routine_work",
            "schedule_gated_supply",
            "relationship_negotiation",
            "high_value_event",
            "b3_event",
        }
    )

    def derive(
        self,
        read_set: PopulationReadSet,
        accepted_owner_receipts: Sequence[str],
        *,
        owner_receipt_associations: Mapping[str, str] | None = None,
    ) -> tuple[CharacterSimulationSeedCandidate, ...]:
        cadence = read_set.cadence
        accepted = frozenset(str(item) for item in accepted_owner_receipts)
        seeds: list[CharacterSimulationSeedCandidate] = []
        for projection in sorted(read_set.projections, key=lambda item: (_projection_actor(item), item.ref)):
            payload = projection.payload
            actor_ref = _projection_actor(projection)
            kind = str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "")
            if kind not in self.ADMITTED_BEHAVIORS or not actor_ref.startswith("character:"):
                continue
            source_refs = self._source_refs(payload)
            owner_refs = self._owner_receipt_refs(payload)
            if owner_receipt_associations and projection.ref in owner_receipt_associations:
                owner_refs = owner_refs | frozenset({str(owner_receipt_associations[projection.ref])})
            objective = kind == "schedule_gated_supply" or bool(payload.get("objective_effect")) or bool(payload.get("world_effect"))
            if kind == "routine_work":
                objective = False
            state_deltas = payload.get("state_deltas")
            if kind == "routine_work":
                state_deltas = {}
            elif not isinstance(state_deltas, dict):
                state_deltas = {"task": str(payload.get("task") or "supply") } if objective else {}
            exposure_basis = str(payload.get("exposure_basis") or payload.get("exposure") or "")
            memory_candidates: tuple[CharacterMemoryCandidate, ...] = ()
            if kind != "relationship_negotiation" and exposure_basis in {"affected_directly", "public_propagation"}:
                event_ref = source_refs[0] if source_refs else f"projection:{projection.ref}"
                memory_candidates = (
                    CharacterMemoryCandidate(
                        candidate_id=f"memory:{actor_ref}:{projection.ref}",
                        actor_ref=actor_ref,
                        candidate_kind="event_experience",
                        source_event_refs=(event_ref,),
                        event_valid_at=cadence.window_end,
                        event_recorded_at=cadence.window_end,
                        knowledge_available_at=cadence.window_end,
                        exposure_basis=exposure_basis,
                        summary=str(payload.get("summary") or kind),
                        confidence=float(payload.get("confidence", 0.5)),
                        salience=float(payload.get("salience", 0.5)),
                        visibility_scope="actor:self",
                        privacy_disposition="actor_private",
                        materialization_policy="pending",
                        dedup_key=f"{actor_ref}:{event_ref}",
                        source_revision_vector=dict(projection.revision_vector),
                    ),
                )
            deterministic_seed = _digest({"base": cadence.deterministic_seed, "projection": projection.ref, "actor": actor_ref})
            seed_id = f"seed:{actor_ref}:{projection.ref}"
            owner_status = "not_required"
            if objective:
                owner_status = "settled" if owner_refs.intersection(accepted) else "owner_settlement_required"
            settled_refs = tuple(sorted(owner_refs.intersection(accepted)))
            presentation = dict(payload.get("presentation_seed") or {})
            presentation.setdefault("behavior_kind", kind)
            presentation.setdefault("report_scope", cadence.report_scope)
            presentation["actor_scope"] = "actor:self"
            presentation.setdefault("exposure_basis", exposure_basis)
            seeds.append(
                CharacterSimulationSeedCandidate(
                    seed_id=seed_id,
                    actor_ref=actor_ref,
                    world_ref=cadence.world_ref,
                    from_tick=cadence.window_start,
                    to_tick=cadence.window_end,
                    source_event_refs=source_refs,
                    source_owner_receipt_refs=settled_refs if owner_status == "settled" else (),
                    state_deltas=state_deltas,
                    memory_candidates=memory_candidates,
                    drift_candidates=tuple(payload.get("drift_candidates") or ()),
                    activation_hints=tuple(str(item) for item in (payload.get("activation_hints") or ())),
                    presentation_seed=presentation,
                    visibility_scope="actor:self",
                    privacy_disposition=str(payload.get("privacy_disposition") or "scoped"),
                    source_revision_vector=dict(projection.revision_vector),
                    ruleset_revision=cadence.ruleset_revision,
                    selector_revision=cadence.selector_revision,
                    deterministic_seed=deterministic_seed,
                    owner_effect_status=owner_status,
                    idempotency_key=seed_id,
                )
            )
        return tuple(seeds)

    @staticmethod
    def _source_refs(payload: dict[str, Any]) -> tuple[str, ...]:
        values = payload.get("source_event_refs") or payload.get("event_refs") or payload.get("event_ref") or ()
        if isinstance(values, str):
            values = (values,)
        return tuple(str(item) for item in values if str(item))

    @staticmethod
    def _owner_receipt_refs(payload: dict[str, Any]) -> frozenset[str]:
        values = payload.get("source_owner_receipt_refs") or payload.get("owner_receipt_refs") or payload.get("owner_receipt_ref") or ()
        if isinstance(values, str):
            values = (values,)
        return frozenset(str(item) for item in values if str(item))
