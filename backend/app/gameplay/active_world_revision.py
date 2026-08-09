"""Explicit, append-only active world revision lifecycle primitives."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import json
from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.shared_contracts import ActiveWorldRevision


class WorldProfile(StrEnum):
    DISABLED = "disabled"
    NARRATIVE = "narrative"
    LIGHTWEIGHT = "lightweight"
    SIMULATION = "simulation"


class RevisionCandidate(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    revision_ref: str = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    core_compatibility_version: str = "gameplay-core:v1"


class ActiveWorldRevisionAuthority:
    """Tracks candidate/active revisions without becoming a second event store."""

    def __init__(self) -> None:
        self._staged: dict[str, RevisionCandidate] = {}
        self._known: set[str] = set()
        self._lock_ref: str | None = None
        self._sessions: dict[str, str] = {}
        self.active_revision: ActiveWorldRevision | None = None

    @staticmethod
    def profile_effects(profile: WorldProfile | str) -> tuple[str, ...]:
        value = WorldProfile(profile)
        return {
            WorldProfile.DISABLED: (),
            WorldProfile.NARRATIVE: ("narrative",),
            WorldProfile.LIGHTWEIGHT: ("narrative", "lightweight"),
            WorldProfile.SIMULATION: ("narrative", "lightweight", "simulation"),
        }[value]

    def stage(self, candidate: RevisionCandidate, *, lock_ref: str | None = None) -> RevisionCandidate:
        if self._lock_ref is not None and lock_ref != self._lock_ref:
            raise ValueError("active_revision_lock_conflict")
        for dependency in candidate.dependencies:
            if dependency not in self._known and dependency != candidate.revision_ref:
                raise ValueError("package_dependency_conflict")
        if set(candidate.conflicts) & (self._known | set(self._staged)):
            raise ValueError("package_dependency_conflict")
        if self._lock_ref is None:
            self._lock_ref = lock_ref
        self._staged[candidate.revision_ref] = candidate
        self._known.add(candidate.revision_ref)
        return candidate

    def activate(self, revision_ref: str, *, tick: int) -> ActiveWorldRevision:
        try:
            candidate = self._staged[revision_ref]
        except KeyError as exc:
            raise ValueError("policy_revision_unavailable") from exc
        digest = "sha256:" + sha256(
            json.dumps(
                {
                    "revision_ref": revision_ref,
                    "dependencies": candidate.dependencies,
                    "tick": tick,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.active_revision = ActiveWorldRevision(
            world_ref="world:active",
            content_package_revisions=(revision_ref,),
            semantic_set_ref=f"semantic-set:{revision_ref}",
            schema_registry_revision=f"schema:{revision_ref}",
            policy_revision_refs=(f"policy:{revision_ref}",),
            core_compatibility_version=candidate.core_compatibility_version,
            digest=digest,
        )
        self._staged.pop(revision_ref, None)
        self._lock_ref = None
        return self.active_revision

    def pin_session(self, session_ref: str, digest: str) -> str:
        if not session_ref or not digest:
            raise ValueError("session_revision_pin_invalid")
        existing = self._sessions.get(session_ref)
        if existing is not None and existing != digest:
            raise ValueError("session_revision_pinned")
        if self.active_revision is None or self.active_revision.digest != digest:
            raise ValueError("policy_revision_unavailable")
        self._sessions[session_ref] = digest
        return digest


__all__ = ["ActiveWorldRevisionAuthority", "RevisionCandidate", "WorldProfile"]
