# 司命数据层定位

`SimingDataLayer`（司命数据层）是**司命产出记录的持久事实层**；领域世界事实的权威仍归 Owner（权威归属域）。它与 `SimingHotCache`（司命热缓存）在同一文件中定义，职责和恢复保证不同。共同的架构、时序与数据流图见 [STATE_MODEL.md](STATE_MODEL.md)。

## 当前已实现

实现文件：`backend/app/services/siming_data_layer.py`。SQLite（嵌入式数据库）使用 WAL（预写日志）与完整同步；记录按 `room_id/id` 幂等更新，并携带 `sim_tick_ts/world_ts`。

| 表 | 实际 API（调用接口）与用途 |
|---|---|
| siming_fairness_snapshots | save_snapshot / latest_snapshot，公平状态可重新打开数据库加载 |
| siming_intervention_candidates | save_candidate，干预候选 |
| siming_intervention_decisions | save_decision / decisions_for_room，干预裁决 |
| siming_intervention_audits | 已建表，当前未提供独立保存/加载接口 |
| siming_checkpoints | 已建表，当前未提供统一三模型恢复接口 |
| siming_narrative_read_models | 已建表，当前未提供独立保存/加载接口 |

六张表不是六域记忆表。`WorldFactMemoryEntry`（世界事实记忆）、因果时间线和角色认知记忆由天道图协议存储，不能声称存在于本模块的这些表中。

热缓存只提供带过期时间的进程内键值读取，当前没有接入 Redis（远程键值存储），**不能用作重启恢复或历史重放来源**。

## 三套派生状态与恢复

主链仍基于经校验的事件规划状态树、叙事和公开全局态势，并在状态安装前核验共同作用域、来源事件、世界时间、角色目标和叙事本地修订。不同计数器不强制相等。

现有持久续跑路径由图中的 admission（准入记录）、阶段计划和房间 after-state（确定性提交后状态）负责；这不是 `SimingDataLayer` 已经实现统一恢复的证据。全局态势是公开证据的派生视图，不新增事实所有者。

本轮保留 `load_state_tree_snapshot(room_id, up_to_tick)`、`load_global_situation_snapshot(...)`、`load_narrative_snapshot(...)` 三个接口。它们显式抛出 `NotImplementedError`（功能未实现异常），不能把空结果解释为有效恢复。

Phase 2: 定义三模型一致检查点及恢复时点、分支/作用域和版本校验后，再实现这三个接口；事件历史溯源、OwnerFactQuery（权威事实查询）和统一读取路径均延期。B0 六字段不迁移，不改 Owner，不重写历史版本。
