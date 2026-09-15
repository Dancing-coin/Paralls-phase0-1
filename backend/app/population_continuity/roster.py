from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROSTER_PATH = _PROJECT_ROOT / "backend/assets/population/default_roster.json"


class PopulationRoster(BaseModel):
    """启动时固定的居民名单；人数取决于名单内容。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    actor_ids: tuple[
        Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.@-]*$")], ...
    ] = Field(min_length=1)

    @field_validator("actor_ids")
    @classmethod
    def require_unique_actors(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("population_roster_duplicate_actor_id")
        # 这些 ID 拼入投影引用后会触发既有隐私/分支权限边界，须在加载时拒绝。
        if any("actor_private" in actor or actor.endswith(("private", "branch")) for actor in value):
            raise ValueError("population_roster_reserved_scope_marker")
        return value


def load_population_roster(path: str | Path | None = None) -> PopulationRoster:
    """相对路径按仓库根解析；配置错误不回退到默认样例。"""
    source = DEFAULT_ROSTER_PATH if path is None else Path(path)
    if not source.is_absolute():
        source = _PROJECT_ROOT / source
    return PopulationRoster.model_validate_json(source.read_text(encoding="utf-8-sig"))
