"""Shared plumbing for owner runtime modules.

本模块是 docs/architecture-v2/08-迁移/02-共享Owner基类.md 中"第一批：纯工具归一"
的落地。它只提供被多个 runtime 逐字重复的工具函数，不改变任何领域语义。

设计边界（见迁移文档 §二）：
  - 只做命令摘要与幂等重放，不含任何领域校验
  - 不提供投影重建（各域投影类型不同，签名无法统一）
  - 不统一 result_digest 算法：各域的恢复校验依赖自己的算法，统一会
    破坏历史数据的一致性检查
  - 不统一 pinned_revisions 命名与幂等键形态：两者都有实际语义

这些刻意的不做，与做掉的部分同样重要。
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

from app.gameplay.models import AppendBatchResult


class OwnerRuntimeError(ValueError):
    """所有 owner runtime 错误类的共同基类。

    保留每域自己的子类，只是为了错误码前缀与调用方 except 的可读性。
    """


def digest(value: object) -> str:
    """稳定摘要。

    归一自 17 处逐字重复的实现。两种原有写法功能等价，唯一差别是
    不可序列化对象抛出的异常类型：

      写法 A（ownership / equipment）：显式 raise TypeError
      写法 B（credential / debt / gift / contract / land_right）：算术式 lambda

    这里采用写法 A。对可序列化输入两者逐字节相同；对不可序列化输入，
    差异在异常类型上呈现（TypeError vs AttributeError）。这不是业务差异——
    两者都是在配置写错时抛出——采用 A 是因为它的报错更明确。
    """

    def default(item: object) -> object:
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        raise TypeError(type(item).__name__)

    return sha256(
        json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class IdempotencyOutcome:
    """幂等预检结果。

    duplicate 非空表示应直接返回该回执，调用方不必继续执行。
    """

    duplicate: AppendBatchResult | None

    @property
    def should_return(self) -> bool:
        return self.duplicate is not None


def replay_duplicate(
    store: object,
    *,
    principal: str,
    idempotency_key: str,
    payload_digest: str,
    error_factory: type[Exception],
    missing_result_code: str,
) -> IdempotencyOutcome:
    """标准的幂等重放预检。

    归一自 7 个域逐字重复的 `_duplicate()` 实现：

        record = store.get_idempotency_record(principal, key)
        if record is None:              return None
        if record.payload_digest != digest: raise ...("idempotency_key_reused")
        result = store.get_by_idempotency(principal, key)
        if result is None:              raise ...(missing_result_code)
        return result

    两处调用方差异保留为参数：
      - error_factory：各域自己的异常类
      - missing_result_code：各域自己的错误码前缀
     """

    record = store.get_idempotency_record(principal, idempotency_key)
    if record is None:
        return IdempotencyOutcome(duplicate=None)

    if record.payload_digest != payload_digest:
        raise error_factory("idempotency_key_reused")

    result = store.get_by_idempotency(principal, idempotency_key)
    if result is None:
        raise error_factory(missing_result_code)

    return IdempotencyOutcome(
        duplicate=result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
    )


def rejected_result(*, command_id: str, error_code: str, stage: str) -> AppendBatchResult:
    """统一的拒绝回执。

    各域原有 `_rejected_append` 的唯一差异是 failed_stage 字面量，
    因此 stage 作为参数保留。
    """
    from app.gameplay.models import GameplayFailure

    return AppendBatchResult(
        committed=False,
        transaction_id=f"transaction:{command_id}",
        command_id=command_id,
        idempotency_status="rejected",
        failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage=stage),
    )
