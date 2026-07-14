from __future__ import annotations

from pathlib import Path

import yaml

from app.character_agent.profile.dossier_models import CharacterDossier
from app.character_agent.profile.models import CharacterProfile


class CharacterDossierLoader:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parents[4] / "assets" / "characters" / "dossiers"

        self._root = Path(root)

    def load(self, actor_id: str) -> CharacterDossier:
        path = self._root / f"{actor_id}.yaml"

        with path.open("r", encoding="utf-8") as handle:
            raw_payload = yaml.safe_load(handle)

        if not isinstance(raw_payload, dict):
            raise ValueError(f"Dossier payload for '{actor_id}' must be a mapping")

        payload = self._resolve_payload(raw_payload)
        resolved_actor_id = str(payload.get("actor_id", "") or "")
        if resolved_actor_id and resolved_actor_id != actor_id:
            raise ValueError(
                f"Dossier actor_id mismatch for '{actor_id}': payload declares "
                f"'{resolved_actor_id}'"
            )

        dossier = CharacterDossier.model_validate(payload)
        if dossier.actor_id != actor_id:
            raise ValueError(
                f"Dossier actor_id mismatch for '{actor_id}': payload declares "
                f"'{dossier.actor_id}'"
            )
        return dossier

    def _resolve_payload(self, payload: dict[str, object]) -> dict[str, object]:
        wrapped = payload.get("character_dossier")
        if isinstance(wrapped, dict):
            return dict(wrapped)

        if payload.get("schema_version") == "character_dossier.v1":
            return dict(payload)

        return self._legacy_profile_payload(payload)

    @staticmethod
    def _legacy_profile_payload(payload: dict[str, object]) -> dict[str, object]:
        profile = CharacterProfile.model_validate(payload)
        identity = profile.identity_core
        return {
            "dossier_id": f"dossier:{identity.character_id}",
            "actor_id": identity.character_id,
            "schema_version": "character_dossier.v1",
            "identity_profile": {
                "actor_id": identity.character_id,
                "canonical_name": identity.canonical_name,
                "aliases": list(identity.aliases),
                "role_identities": {
                    "occupational_role": identity.occupation_role,
                },
            },
            "character_profile": payload,
        }


__all__ = ["CharacterDossierLoader"]
