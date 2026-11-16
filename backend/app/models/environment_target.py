from pydantic import BaseModel, ConfigDict, Field


class EnvironmentTargetConstraints(BaseModel):
    """ESM 自有的局部环境约束；不从司命提案接收权威配置。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    compatible_change_types: list[str]
    cooldown_ms: int = Field(default=0, ge=0)
    cooldown_until_ts: int = Field(default=0, ge=0)
    resource_available: float = Field(default=0, ge=0, allow_inf_nan=False)
    resource_cost: float = Field(default=0, ge=0, allow_inf_nan=False)
    spatial_allowed: bool = True
