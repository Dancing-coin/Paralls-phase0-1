from __future__ import annotations

from collections.abc import Mapping
import math
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, PlainSerializer, model_validator


CodebookLevel = Literal["L0", "L1", "L2"]
ContentDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


def _plain_json(value):
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain_json(item) for item in value]
    return value


def _freeze_json(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("codebook_summary_value_invalid")
    return value


class CodebookContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False, revalidate_instances="always")


class CodebookEntry(CodebookContract):
    """获权来源的索引；正文仍由原Owner保存。"""

    code_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    content_digest: ContentDigest
    scope: str = Field(min_length=1)
    visibility: str = Field(min_length=1)
    reader_roles: tuple[str, ...]
    purpose_policy_ref: str = Field(min_length=1)
    codec_version: Literal["codebook:v1"]
    encryption_key_ref: str | None = None
    safe_summary: Annotated[Mapping[str, JsonValue], BeforeValidator(_plain_json),
        AfterValidator(_freeze_json), PlainSerializer(_plain_json)]
    expansion_levels: tuple[CodebookLevel, ...]
    expiry: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_declared_access(self):
        for values in (self.reader_roles, self.expansion_levels):
            if not values or any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError("codebook_access_declaration_invalid")
        return self


class CodebookReadRequest(CodebookContract):
    reader_ref: str = Field(min_length=1)
    code_ref: str = Field(min_length=1)
    requested_level: CodebookLevel
    purpose: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    expected_revision: str = Field(min_length=1)
    expected_digest: ContentDigest
    at_tick: int = Field(ge=0)


class CodebookReadPolicy(CodebookContract):
    """原Owner在当前读边界提供的封闭授权，不接受客户端自签。"""

    policy_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    code_ref: str = Field(min_length=1)
    reader_ref: str = Field(min_length=1)
    reader_roles: tuple[str, ...]
    purposes: tuple[str, ...]
    scopes: tuple[str, ...]
    level_fields: Annotated[Mapping[CodebookLevel, tuple[str, ...]],
        AfterValidator(lambda value: MappingProxyType(dict(value))), PlainSerializer(dict)]
    issued_at: int = Field(ge=0)
    expiry: int = Field(ge=0)
    historical: bool
    source_ref: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    source_digest: ContentDigest
    summary_digest: ContentDigest

    @model_validator(mode="after")
    def validate_grant(self):
        if self.issued_at >= self.expiry:
            raise ValueError("codebook_policy_interval_invalid")
        for values in (*self.level_fields.values(), self.reader_roles, self.purposes, self.scopes):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError("codebook_policy_fields_invalid")
        return self


class CodebookReadReceipt(CodebookContract):
    reader_ref: str
    code_ref: str
    source_revision: str
    requested_level: CodebookLevel
    purpose: str
    granted_fields: tuple[str, ...] = ()
    policy_revision: str
    issued_at: int = Field(ge=0)
    expiry: int = Field(ge=0)
    status: Literal["granted", "permission_denied", "expired", "stale_input", "digest_mismatch",
        "source_unavailable", "replay_input_unavailable"]
