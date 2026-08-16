from __future__ import annotations

import hashlib
import json

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.p5.social_knowledge import SocialRecipientView


class FrozenSocialPlanningInput(StrictGameplayModel):
    """Read-only, recipient-scoped SocialFactAuthority view pinned for planning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipient_ref: str = Field(min_length=1)
    observed_at: str = Field(min_length=1)
    projection_digest: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    relationship_facts: tuple[dict[str, object], ...] = ()
    knowledge_facts: tuple[dict[str, object], ...] = ()
    reputation: dict[str, dict[str, float]] = Field(default_factory=dict)

    @property
    def input_digest(self) -> str:
        payload = {
            "recipient_ref": self.recipient_ref,
            "observed_at": self.observed_at,
            "projection_digest": self.projection_digest,
            "source_revision_vector": dict(sorted(self.source_revision_vector.items())),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    @classmethod
    def freeze(
        cls,
        *,
        recipient_ref: str,
        observed_at: str,
        view: SocialRecipientView,
    ) -> "FrozenSocialPlanningInput":
        return cls(
            recipient_ref=recipient_ref,
            observed_at=observed_at,
            projection_digest=view.projection_hash,
            source_revision_vector=dict(view.source_revision_vector),
            relationship_facts=view.relationship_facts,
            knowledge_facts=view.knowledge_facts,
            reputation=view.reputation,
        )

    def validate_against(self, *, store: GameplayEventStore) -> "SocialInputValidation":
        for stream_id, expected_revision in self.source_revision_vector.items():
            if store.get_stream_head(stream_id) != expected_revision:
                return SocialInputValidation(accepted=False, error_code="social_source_revision_stale")
        return SocialInputValidation(accepted=True)


class SocialInputValidation(StrictGameplayModel):
    accepted: bool
    error_code: str | None = None


__all__ = ["FrozenSocialPlanningInput", "SocialInputValidation"]
