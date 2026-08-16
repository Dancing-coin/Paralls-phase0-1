from __future__ import annotations

import hashlib
import json

from pydantic import ConfigDict, Field

from app.gameplay.civilization_capability_runtime import CivilizationCapabilityAuthority, CivilizationCapabilityView
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel


class CapabilityInputValidation(StrictGameplayModel):
    accepted: bool
    error_code: str | None = None


class FrozenCapabilityEligibilityInput(StrictGameplayModel):
    """Read-only authority view pinned for the one admitted INF-4Y supply edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    capability_revision: int = Field(ge=1)
    policy_revision: str = Field(min_length=1)
    effective_tick: int = Field(ge=0)
    status: str = Field(min_length=1)
    visibility: str = Field(min_length=1)
    reader_scope: str = Field(min_length=1)
    evaluated_tick: int = Field(ge=0)
    source_event_refs: tuple[str, ...] = ()
    projection_digest: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def freeze(
        cls,
        *,
        view: CivilizationCapabilityView,
        evaluated_tick: int,
        source_revision_vector: dict[str, int],
    ) -> "FrozenCapabilityEligibilityInput":
        return cls(
            capability_ref=view.capability_ref,
            jurisdiction_ref=view.jurisdiction_ref,
            capability_revision=view.capability_revision,
            policy_revision=view.policy_revision,
            effective_tick=view.effective_tick,
            status=view.status,
            visibility=view.visibility,
            reader_scope="authority",
            evaluated_tick=evaluated_tick,
            source_event_refs=view.source_event_refs,
            projection_digest=view.digest,
            source_revision_vector=dict(source_revision_vector),
        )

    @property
    def input_digest(self) -> str:
        payload = self.model_dump(mode="json", exclude={"projection_digest"})
        payload["projection_digest"] = self.projection_digest
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    def validate_against(self, *, store: GameplayEventStore) -> CapabilityInputValidation:
        if self.reader_scope != "authority" or self.visibility != "authority_only":
            return CapabilityInputValidation(accepted=False, error_code="capability_reader_scope_denied")
        if self.status != "active":
            return CapabilityInputValidation(accepted=False, error_code="capability_status_invalid")
        stream_id = CivilizationCapabilityAuthority.capability_stream_id(
            jurisdiction_ref=self.jurisdiction_ref
        )
        if set(self.source_revision_vector) != {stream_id}:
            return CapabilityInputValidation(accepted=False, error_code="capability_source_vector_invalid")
        if store.get_stream_head(stream_id) != self.source_revision_vector[stream_id]:
            return CapabilityInputValidation(accepted=False, error_code="capability_source_revision_stale")
        current = CivilizationCapabilityAuthority(store=store).view_for(
            capability_ref=self.capability_ref,
            jurisdiction_ref=self.jurisdiction_ref,
            reader_scope="authority",
            now_tick=self.evaluated_tick,
            expected_capability_revision=self.capability_revision,
        )
        if not current.accepted or current.view is None:
            return CapabilityInputValidation(
                accepted=False,
                error_code=current.error_code or "capability_source_unavailable",
            )
        view = current.view
        if view.visibility != "authority_only":
            return CapabilityInputValidation(accepted=False, error_code="capability_reader_scope_denied")
        if view.digest != self.projection_digest:
            return CapabilityInputValidation(accepted=False, error_code="capability_projection_digest_mismatch")
        if view.source_event_refs != self.source_event_refs:
            return CapabilityInputValidation(accepted=False, error_code="capability_source_event_mismatch")
        return CapabilityInputValidation(accepted=True)


__all__ = ["CapabilityInputValidation", "FrozenCapabilityEligibilityInput"]
