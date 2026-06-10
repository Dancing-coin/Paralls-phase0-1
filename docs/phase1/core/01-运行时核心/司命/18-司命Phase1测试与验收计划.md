# 18-司命Phase1测试与验收计划

## 1. 文档目标

本文档定义 `Phase 1` 司命从文档进入实现时的最小测试和验收口径。

它回答：

- 哪些链路必须有 golden trace
- 哪些 schema 必须可验证
- 哪些失败态必须可 replay
- 工作台 read model 如何验收
- 哪些内容不应拖进 `Phase 1` 最小验收

## 2. 验收边界

`Phase 1` 必验：

1. 事件 ingest
2. 五个 auditor 输出
3. `FairnessStateSnapshot`
4. `InterventionCandidate`
5. `InterventionDecision`
6. dispatch 到角色 / `ESM` / 视觉表现边界
7. `Checkpoint`
8. `InterventionAuditRecord`
9. `NarrativeReadModel`
10. replay 链

`Phase 1` 不验：

- 完整 `NarrativeProjectionCore`
- 多步 `EventChainCandidate`
- `DramaticPriorityModel`
- 完整工作台 UI
- 离线世界持续后台运行

## 3. Golden traces

至少准备 6 条 golden trace：

| trace | 目标 | 预期主干结果 |
| --- | --- | --- |
| `information_starvation_basic` | 关键事实被单人垄断 | `fact_reveal` candidate |
| `participation_starvation_basic` | 某角色长期无行动窗口 | `opportunity` candidate |
| `private_channel_lock_basic` | 私密会话锁死关键流转 | `opportunity` 或低强度 `environment_request` |
| `suspicion_runaway_basic` | 怀疑单点过热 | 低强度 `fact_reveal` 或 `impulse` |
| `evidence_bottleneck_visual` | 证据已存在但不可见 | `visual_fact_path` |
| `balanced_no_action` | 局势无明显失衡 | `none` / `no_action` audit |

每条 trace 必须包含：

- 输入事件列表
- 预期五维分数
- 预期 `dominant_imbalance_type`
- 预期 candidate band
- 预期 selected path
- 预期 audit status
- 预期 read model 摘要字段

## 4. Schema tests

必须覆盖：

1. 所有 canonical 对象必填字段缺失会失败。
2. 可空字段缺失会失败，显式 `null` 可通过。
3. 分数字段 `<0`、`>1`、`NaN` 会失败。
4. 未知枚举会失败。
5. 新增可选字段不会破坏旧对象读取。
6. `world_ts` 出现在事件总线公共信封时会失败。

## 5. Determinism tests

同一输入 trace 重复运行 3 次，必须满足：

- `dominant_imbalance_type` 一致
- `recommended_intervention_band` 一致
- `selected_path` 一致
- `decision` 一致
- replay 链对象顺序一致

允许不同：

- 自动生成的 id
- `producer_ts`
- 非排序用途的 debug 文本

## 6. Idempotency tests

必须覆盖：

| 场景 | 期望 |
| --- | --- |
| 重复 dispatch key | 不重复下发，写 `duplicate_suppressed` |
| 重复 audit key | 不重复 final record，追加 duplicate ref |
| retry 后 ack 成功 | 原 timeout 不覆盖，追加 correction |
| stale candidate dispatch | suppress，写 `stale_snapshot` |
| no_action | 仍写 audit，`snapshot_after_ref=null` |

## 7. Late event tests

必须覆盖：

1. late input 到达后生成新 snapshot。
2. 新 snapshot 标记 `late_input=true`。
3. late result 不覆盖 final audit。
4. late result 追加 `correction_record`。
5. read model 标记存在 correction。

## 8. Feasibility tests

必须使用 `05` 中的确定性选路算法覆盖：

- hard veto
- band/path 不兼容
- approve 阈值
- downgrade 阈值
- reject 阈值
- tie-break
- fallback selection

每条 feasibility case 都要断言：

- 6 个 score
- `path_score`
- `decision`
- `selected_path`
- `fallback_path`
- `execution_notes`

## 9. Workbench read model tests

不要求完整 UI，但必须验证 read model 能表达：

- pending dispatch
- ack timeout
- partial target delivery
- ESM rejection
- duplicate suppression
- stale snapshot
- late correction
- before / after snapshot 对比

测试方式可以是 snapshot JSON，不要求前端页面。

## 10. Fake adapters

实现测试时建议提供 4 个 fake adapter：

1. `FakeEventBus`
2. `FakeCharacterService`
3. `FakeESM`
4. `FakeVisualFactBoundary`

fake adapter 必须能注入：

- 成功 ack
- 超时
- 部分成功
- 约束拒绝
- late result
- duplicate result

## 11. 推荐 harness profile

后续可以新增：

```powershell
python scripts/verification/harness.py --profile siming-phase1
```

最小检查项：

1. schema validation
2. golden trace replay
3. idempotency
4. late event correction
5. feasibility deterministic selection
6. read model snapshot

在 profile 未实现前，文档验收只能描述为“测试计划已写”，不能描述为“运行时已验证”。

## 12. 一句话收束

司命 `Phase 1` 的验收重点不是证明它会写戏，而是证明同一条公平裁判链在成功、失败、延迟、重复和降级情况下都能稳定产出结构化结果，并且能被 replay、audit 和工作台解释。
