"""Stormnight's fixed handoff to existing Quest and Social owners.

The handoff is deliberately row-specific. It carries case provenance into the
existing owner event families and never accepts caller-selected streams or
event vectors.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.p5.contracts import canonical_sha256_digest
from app.gameplay.settlement_plan import build_atomic_event_batch


@dataclass(frozen=True)
class StormnightOwnerHandoffService:
    store: GameplayEventStore
    social_authority: object | None = None
    quest_authority: object | None = None

    def record_social_statement(
        self,
        *,
        case_ref: str,
        statement_ref: str,
        speaker_ref: str,
        target_ref: str,
        mode: str,
        expected_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if self.social_authority is not None and hasattr(self.social_authority, "record_scripted_mystery_statement"):
            result = self.social_authority.record_scripted_mystery_statement(
                case_ref=case_ref,
                statement_ref=statement_ref,
                speaker_ref=speaker_ref,
                target_ref=target_ref,
                mode=mode,
                expected_revision=expected_revision,
                command_id=command_id,
                idempotency_key=idempotency_key,
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
            return result.receipt if hasattr(result, "receipt") and result.receipt is not None else result
        stream_id = "gameplay:knowledge:" + canonical_sha256_digest(
            {"case_ref": case_ref, "statement_ref": statement_ref, "speaker_ref": speaker_ref}
        ).split(":", 1)[1]
        payload = {
            "fact_ref": statement_ref,
            "knower_ref": speaker_ref,
            "subject_ref": target_ref,
            "observation_ref": case_ref,
            "knowledge_kind": f"statement:{mode}",
            "confidence": 1.0,
            "decay_rate_per_day": 0.0,
            "evidence_ref": statement_ref,
            "provenance_source_ref": case_ref,
            "observed_at": "2026-09-05T00:00:00Z",
            "visibility": "project",
            "case_ref": case_ref,
            "statement_ref": statement_ref,
        }
        return self._append(
            principal_ref="authority:p5:social",
            stream_id=stream_id,
            expected_revision=expected_revision,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.social.knowledge_observed",
            payload=payload,
        )

    def record_quest_evidence(
        self,
        *,
        case_ref: str,
        clue_ref: str,
        discoverer_ref: str,
        expected_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if self.quest_authority is not None and hasattr(self.quest_authority, "record_scripted_mystery_evidence"):
            result = self.quest_authority.record_scripted_mystery_evidence(
                case_ref=case_ref,
                clue_ref=clue_ref,
                discoverer_ref=discoverer_ref,
                expected_revision=expected_revision,
                command_id=command_id,
                idempotency_key=idempotency_key,
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
            return result.receipt if hasattr(result, "receipt") and result.receipt is not None else result
        stream_id = f"gameplay:evidence:{clue_ref}"
        payload = {
            "evidence_ref": clue_ref,
            "evidence_kind_ref": "evidence:stormnight:physical",
            "subject_ref": discoverer_ref,
            "provider_ref": "provider:stormnight:case",
            "provenance_source_ref": case_ref,
            "visibility": "project",
            "observed_at": "2026-09-05T00:00:00Z",
            "case_ref": case_ref,
            "clue_ref": clue_ref,
        }
        return self._append(
            principal_ref="authority:p5:quest-evidence",
            stream_id=stream_id,
            expected_revision=expected_revision,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.quest.evidence_registered",
            payload=payload,
        )

    def record_inventory_clue_custody(
        self,
        *,
        inventory_authority,
        case_ref: str,
        clue_ref: str,
        discoverer_ref: str,
        container_id: str,
        expected_inventory_setup: bool = True,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        """Use the existing Inventory owner for one fixed clue-custody handoff."""
        if not expected_inventory_setup or not container_id.startswith(f"container:stormnight:{discoverer_ref}:"):
            raise ValueError("stormnight_inventory_container_mapping_invalid")
        return inventory_authority.instantiate(
            command_id=command_id,
            actor_ref=discoverer_ref,
            item_id=f"item:{clue_ref}",
            definition_id="item:stormnight:clue@1",
            quantity=1,
            container_id=container_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def _append(
        self,
        *,
        principal_ref: str,
        stream_id: str,
        expected_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> AppendBatchResult:
        return self.store.append_batch(
            build_atomic_event_batch(
                command_id=command_id,
                principal_ref=principal_ref,
                stream_id=stream_id,
                expected_revision=expected_revision,
                read_stream_revisions={stream_id: expected_revision},
                event_specs=((event_type, payload),),
                idempotency_key=idempotency_key,
                causation_id=causation_id,
                correlation_id=correlation_id,
                pinned_revisions={"case": 1},
            )
        )


__all__ = ["StormnightOwnerHandoffService"]
