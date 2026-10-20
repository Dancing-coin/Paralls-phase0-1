from __future__ import annotations

from pathlib import Path
from typing import Self
import hashlib
import json

from app.character_agent.profile.loader import CharacterProfileLoader
from app.character_agent.profile.models import CharacterProfile
from app.gameplay.resource_template_admission import ResourceTemplateEntry, ResourceTemplateSource


class CharacterProfileRegistry:
    def __init__(self, profiles_by_actor_id: dict[str, CharacterProfile]) -> None:
        self._profiles_by_actor_id = dict(profiles_by_actor_id)

    @classmethod
    def from_directory(cls, directory: str | Path) -> Self:
        directory = Path(directory)
        active_loader = CharacterProfileLoader(directory)
        profiles_by_actor_id: dict[str, CharacterProfile] = {}

        for path in sorted(directory.glob("*.yaml")):
            profile = active_loader.load(path.stem)
            profiles_by_actor_id[profile.identity_core.character_id] = profile

        return cls(profiles_by_actor_id)

    def actor_ids(self) -> list[str]:
        return sorted(self._profiles_by_actor_id)

    def get(self, actor_id: str) -> CharacterProfile:
        return self._profiles_by_actor_id[actor_id]

    def contains(self, actor_id: str) -> bool:
        return actor_id in self._profiles_by_actor_id

    def profile_ref(self, actor_ref: str) -> CharacterProfile:
        actor_id = actor_ref.removeprefix("character:") if actor_ref.startswith("character:") else actor_ref
        if not actor_id or actor_id.startswith("npc:"):
            raise KeyError(actor_ref)
        return self.get(actor_id)

    def revision(self) -> str:
        payload = {
            actor_id: profile.identity_core.model_dump(mode="json")
            for actor_id, profile in sorted(self._profiles_by_actor_id.items())
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def authored_identity_digest(self, actor_ref: str) -> str:
        profile = self.profile_ref(actor_ref)
        encoded = json.dumps(
            profile.identity_core.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def resource_template_source(
        self,
        actor_ref: str,
        *,
        world_ref: str,
        timeline_ref: str,
    ) -> ResourceTemplateSource:
        """Expose the authored, versioned resource policy as an admitted source.

        The profile remains the content owner; this adapter only binds its
        published policy to the existing read-only admission contract.
        """
        profile = self.profile_ref(actor_ref)
        template = profile.resource_template
        if template is None:
            raise KeyError(f"resource_template:{actor_ref}")
        if world_ref not in template.world_scope or timeline_ref not in template.timeline_scope:
            raise ValueError("resource_template_scope_not_published")
        encoded = json.dumps(template.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return ResourceTemplateSource(
            template_ref=template.template_ref,
            template_revision=template.template_revision,
            issuer_ref=template.issuer_ref,
            fact_owner_ref=template.fact_owner_ref,
            actor_scope=(profile.identity_core.character_id,),
            world_scope=template.world_scope,
            timeline_scope=template.timeline_scope,
            valid_from_world_tick=template.valid_from_world_tick,
            valid_until_world_tick=template.valid_until_world_tick,
            source_digest="sha256:" + hashlib.sha256(encoded).hexdigest(),
            binding_revision=template.binding_revision,
            read_principals=template.read_principals,
            receipt_kind=template.receipt_kind,
            receipt_key=template.receipt_key,
            revocation_owner_ref=template.revocation_owner_ref,
            relation_policy_ref=template.relation_policy_ref,
            relation_kind=template.relation_kind,
            resources=tuple(
                ResourceTemplateEntry(**entry.model_dump(mode="json")) for entry in template.resources
            ),
        )

    def build_gameplay_scope_view(
        self,
        actor_id: str,
        *,
        profile_registry_revision: str,
        allowed_intent_kinds: tuple[str, ...] = (
            "respond_shift", "start_work", "finish_work", "report_absence", "request_break"
        ),
    ):
        from app.character_agent.profile.views import ActorGameplayScopeView

        profile = self.get(actor_id.removeprefix("character:"))
        return ActorGameplayScopeView(
            actor_ref=profile.identity_core.character_id,
            canonical_name=profile.identity_core.canonical_name,
            occupation_role=profile.identity_core.occupation_role,
            profile_registry_revision=profile_registry_revision,
            permitted_role_refs=(profile.identity_core.occupation_role,),
            allowed_intent_kinds=allowed_intent_kinds,
        )
