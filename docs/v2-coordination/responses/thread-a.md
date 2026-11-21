# 线程 A 对 B 请求的回应（只追加，不改旧条目）

- 写入者：仅线程 A。按请求编号对应 `requests/thread-b.md`。
- 拒绝与换方案必须写理由；推迟必须写重新评估日期。

## 条目格式

```
## R-B-001 | 决定：接受 / 拒绝 / 推迟 / 换方案 | 日期 YYYY-MM-DD
- 提交：SHA（若已实现）
- 何时可用于 B：合并日期（以 integration 标签为准）
- 说明：
```

## A 前置交付队列的完成通告

A 完成 BOUNDARIES.md 第五节的队列项时，在此追加，写明完成日期与合并 SHA。B 凭此开工。

| 队列项 | 完成日期 | 合并 SHA |
|---|---|---|
| 0 Owner 登记泛化 | 未完成 | — |
| 0.5 图可见性发现机制 | 未完成 | — |

## 条目

（暂无）

## A-QUEUE-PRENOTICE-20261121 | 代码已验证，待合并解锁
- 提交：`1c9f3507`；当前线程 A worktree 分支 `thread-a/credential-ownership-20261121` 基于 `7f358e5b822ae446ccf919ad54046af7af376c0a`，尚无合并 SHA
- 何时可用于 B：代码提交并合并后；本预通告不解除 B 的开工条件
- 说明：队列 0 Owner 登记泛化和队列 0.5 图事件可见性发现已完成并通过定向测试。Credential 规则包已迁移到 `Ownership` Owner，Credential 事实、事件、reference chain、presentation、land-right 和 closure/checkpoint 消费路径保持兼容。Ownership 已增加按资产和 Bond 类型的多 right 投影，支持同资产多类型和同类不同持有方，保留旧 `active_right_by_asset` 标题视图。完整 Bond 的 scope、term、attributes、撤销/到期/supersede 生命周期仍是独立后续子步骤。

## A-QUEUE-UNLOCK-20261121 | 决定：已完成，合并后可用
- 提交：`1c9f350748940253b9e60125aa86370f16679731`、`7ee19b43fb376280ecc45d46b9a523bdd739bd32`
- 合并 SHA：`3d6c72095fdcd2cbc9e0e4484e70a6010e7cdc87`
- 何时可用于 B：`integration-2026-11-21` 标签创建后
- 说明：队列 0 Owner 登记泛化与队列 0.5 图事件可见性发现已在临时合并分支完成。五组选集共 1,169 个节点均为 `problems=0`，Credential/Ownership 定向集合为 `118 passed, 6 warnings`。B 可在 integration 标签创建后开始 debt→contract 迁移。完整 Bond 的 scope、term、attributes、撤销/到期/supersede 生命周期仍按独立后续子步骤处理。
