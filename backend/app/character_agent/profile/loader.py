from __future__ import annotations

from pathlib import Path

import yaml

from app.character_agent.profile.models import CharacterProfile


class CharacterProfileLoader:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parents[4] / "assets" / "characters" / "profiles"

        self._root = Path(root)

    def load(self, actor_id: str) -> CharacterProfile:
        path = self._root / f"{actor_id}.yaml"

        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)

        profile = CharacterProfile.model_validate(payload)
        profile_actor_id = profile.identity_core.character_id

        if profile_actor_id != actor_id:
            raise ValueError(
                f"Profile actor_id mismatch for '{actor_id}': payload declares '{profile_actor_id}'"
            )

        return profile
