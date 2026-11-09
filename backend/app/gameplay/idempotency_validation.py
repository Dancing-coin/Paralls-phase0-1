"""Idempotency replay validation.

独立于 owner_runtime_base 的缺陷修复模块。背景见
docs/architecture-v2/09-验收/05-基线缺陷-幂等回放未校验.md。

问题：幂等回放路径直接信任存储的回执，未校验其引用的
`committed_event_ids` 是否真实存在。当回执被篡改或存储部分损坏时，
系统返回 `committed=True` 而实际没有任何事件写入——调用方据此认为
世界状态已改变。

本模块只提供校验，不改变任何回放路径的默认行为。调用方显式选用。
"""

from __future__ import annotations

from typing import Protocol, Sequence

from app.gameplay.models import AppendBatchResult


class ReplayValidationError(Exception):
    """回执未通过完整性校验。"""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class _EventStoreLike(Protocol):
    def get_event(self, event_id: str) -> object: ...
    def get_transaction(self, transaction_id: str) -> object | None: ...


def validate_replay_result(
    store: _EventStoreLike,
    result: AppendBatchResult,
    *,
    require_transaction_match: bool = True,
    require_event_count: bool = True,
) -> None:
    """校验一条幂等回执是否自洽。

    三个校验点，缺一不可：

      1. 事件可解析      防：引用不存在的事件
      2. 批次存在且一致  防：回执来自另一次事务
      3. 事件数匹配      防：部分提交伪装成完整

    任一项失败抛 ReplayValidationError。调用方应将其转换为
    自己的拒绝回执，而不是继续返回该结果。

    require_transaction_match / require_event_count 允许特定域关闭某项
    校验——有些域的多事件批次不保证与事务批次逐项对齐。默认全开。
    """

    if not result.committed:
        # 未提交的结果没有可校验的事件，交由调用方处理
        return

    event_ids: Sequence[str] = tuple(result.committed_event_ids)

    # 1. 事件必须全部可解析
    resolved = []
    for event_id in event_ids:
        try:
            resolved.append(store.get_event(event_id))
        except KeyError:
            raise ReplayValidationError(
                "idempotency_result_event_missing", event_id
            ) from None

    # 2. 事务批次必须存在，且与回执引用的事件一致
    if require_transaction_match:
        batch = store.get_transaction(result.transaction_id)
        if batch is None:
            raise ReplayValidationError(
                "idempotency_result_transaction_missing", result.transaction_id
            )
        batch_event_ids = tuple(event.event_id for event in batch.events)
        if batch_event_ids != event_ids:
            raise ReplayValidationError(
                "idempotency_result_transaction_mismatch",
                f"receipt={len(event_ids)} transaction={len(batch_event_ids)}",
            )

    # 3. 事件数必须匹配；事件 ID 不得重复
    if require_event_count:
        if len(set(event_ids)) != len(event_ids):
            raise ReplayValidationError(
                "idempotency_result_event_duplicated", str(len(event_ids))
            )
        for event, event_id in zip(resolved, event_ids):
            if getattr(event, "transaction_id", None) != result.transaction_id:
                raise ReplayValidationError(
                    "idempotency_result_event_transaction_mismatch", event_id
                )
