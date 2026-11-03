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


def rejected_result(
    *,
    command_id: str,
    error_code: str,
    stage: str,
    transaction_prefix: str = "transaction",
) -> AppendBatchResult:
    """统一的拒绝回执。

    各域原有 `_rejected_append` 的两处差异作为参数保留：

      - stage：failed_stage 字面量，各域不同
      - transaction_prefix：多数域用 "transaction"，inventory 用 "tx"

    transaction_prefix 不是风格差异：inventory 全文件的提交路径统一用
    f"tx:{command_id}"（12 处），拒绝回执必须与之一致，否则同一命令的
    拒绝回执与提交回执会在 transaction_id 上不一致。
    """
    from app.gameplay.models import GameplayFailure

    return AppendBatchResult(
        committed=False,
        transaction_id=f"{transaction_prefix}:{command_id}",
        command_id=command_id,
        idempotency_status="rejected",
        failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage=stage),
    )


# ---------------------------------------------------------------------------
# 提交批次骨架
# ---------------------------------------------------------------------------
#
# AST 核验（2026-11-03）：27 处 append_batch 调用全部包含下列 9 个顶层键：
#   transaction_id / command_id / expected_stream_revisions / pinned_revisions /
#   events / idempotency_record / outbox_entries / result_digest /
#   projection_refresh_hints
# 只在部分调用出现的可选键：
#   read_stream_revisions（7 处）、owner_fragments（3 处）


def build_event_batch(
    *,
    command_id: str,
    principal: str,
    idempotency_key: str,
    payload_digest: str,
    events: list[dict] | tuple[dict, ...],
    expected_stream_revisions: Mapping[str, int],
    result_digest: str,
    transaction_prefix: str = "tx",
    pinned_revisions: Mapping[str, int] | None = None,
    read_stream_revisions: Mapping[str, int] | None = None,
    owner_fragments: list | None = None,
    outbox_entries: list | None = None,
    projection_refresh_hints: list | None = None,
) -> dict:
    """组装可直接交给 `EventStore.append_batch` 的批次字典。

    **只组装，不判断。** 它不计算任何摘要、不校验任何不变量、不决定
    revision。所有语义仍由调用方提供。

    三个刻意保留为参数的差异（见迁移文档 §五）：

      transaction_prefix    "tx" 与 "transaction" 两套约定并存。
                            inventory 全文件用 "tx"（12 处），其余多用
                            "transaction"。统一会改变 transaction_id，
                            而它被恢复校验引用。
      result_digest         由调用方传入，**builder 不计算**。各域的
                            恢复校验依赖自己的算法（事件摘要 / 事件
                            列表摘要 / 命令摘要），统一会破坏历史数据
                            的一致性检查。
      pinned_revisions      默认与 expected_stream_revisions 相同，
                            但 equipment / land_right 用不同的键名与
                            来源，必须显式传入。

    read_stream_revisions / owner_fragments 只在部分调用出现，因此可选。
    """

    batch: dict = {
        "transaction_id": f"{transaction_prefix}:{command_id}",
        "command_id": command_id,
        "expected_stream_revisions": dict(expected_stream_revisions),
        "pinned_revisions": dict(
            expected_stream_revisions if pinned_revisions is None else pinned_revisions
        ),
        "events": list(events),
        "idempotency_record": {
            "principal_ref": principal,
            "idempotency_key": idempotency_key,
            "payload_digest": payload_digest,
        },
        "outbox_entries": list(outbox_entries or []),
        "result_digest": result_digest,
        "projection_refresh_hints": list(projection_refresh_hints or []),
    }

    if read_stream_revisions is not None:
        batch["read_stream_revisions"] = dict(read_stream_revisions)
    if owner_fragments is not None:
        batch["owner_fragments"] = list(owner_fragments)

    return batch


# ---------------------------------------------------------------------------
# 单条命令内的读快照
# ---------------------------------------------------------------------------


class StoreReadSnapshot:
    """把一条命令内的多次全量读合并成一次。

    **实测依据（2026-11-04，见迁移文档 §六）**

    原计划的 ProjectionCheckpointer 有两处前提经实测不成立：

      1. `rebuild(events, checkpoint_at=...)` 比全量重建**慢 1.68 倍**
         （N=100/300/600 稳定复现）：它做两次全量过滤 + 两次 reduce，
         而 `checkpoint_at` 阶段的过滤本身就是 O(事件总数)。
      2. 同一方法内的多次 rebuild 用的是**不同 projector**
         （credential.issue_credential 同时用 credential/ownership/inventory
         三个），投影 cache key 含 projector 身份，因此永不命中。

    真正重复的是 `read_events()` 的深拷贝：

        issue_credential   调 3 次
        verify_..._presentation 调 3 次
        supersede_credential 调 2 次

    400 事件时每次约 2.9 ms。合并后实测 9.48 → 5.18 ms/命令。

    **安全前提**（已核验）

      - `read_events()` 返回的列表无任何调用方就地修改（AST 全仓扫描，0 处）
      - 本类只以 tuple 返回，结构上禁止调用方修改
      - head 与事件元组取自同一次读，不存在读到一半被打断的窗口

    这不是跨命令缓存：提交会改变 head，下次调用自动重读。
    """

    __slots__ = ("_store", "_head", "_events")

    def __init__(self, store: object) -> None:
        self._store = store
        self._head: int | None = None
        self._events: tuple | None = None

    def all_events(self) -> tuple:
        """当前 head 对应的全部事件，缓存命中时复用。

        head 从事件本身取（最后一条的 global_sequence），而不是先调
        get_last_global_sequence 再读 —— 避免两次调用之间的并发写入
        让缓存键与内容对不上。
        """
        if self._events is not None and self._head == self._store.get_last_global_sequence():
            return self._events

        events = tuple(self._store.read_events())
        head = events[-1].global_sequence if events else 0
        self._events = events
        self._head = head
        return events
