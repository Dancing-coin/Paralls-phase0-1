from __future__ import annotations

from pathlib import Path
from typing import Self

from app.character_agent.profile.loader import CharacterProfileLoader
from app.character_agent.profile.models import CharacterProfile


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
