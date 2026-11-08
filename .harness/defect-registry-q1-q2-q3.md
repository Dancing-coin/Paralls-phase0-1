# 05-待决问题与缺陷登记

**版本**：1.0  
**日期**：2026-11-08  
**状态**：进行中 — 记录文档指出的三个"必须你定"的问题  
**关联**：[05-Owner重构影响评估.md](../../05-Owner重构影响评估.md)（第九章）

---

## 一、三个必须你定的问题（Q1-Q3）

### Q1：B0 六个字段的 Owner 归属

**问题定义**（文档表 3.1）：
- 字段：`fatigue` / `need_pressure` / `starvation_credit` / `activity_phase` / `next_due_tick` / `last_update_tick`
- 位置：`backend/app/population_continuity/hot_state.py` 第 11-18 行（HOT_FIELDS）
- 现状：直接写入，无 Owner、无事件、无 receipt
- 风险：引入分层后会成为"双真相 + revision 冲突"

**依赖的代码**：
- `backend/app/population_continuity/fair_focus.py` — 在没有 Owner 的前提下管理 `starvation_credit`
- `backend/app/population_continuity/siming_contracts.py:159` — 校验新增字段时拒绝 HOT_FIELDS 之外的字段

**需要你的决策**：
```
这 6 个字段应该分配给哪个 Owner？
- 选项 A：创建新 Owner（如 b0_vitality）
- 选项 B：分配给现有 Owner（如 survival, behavior, mood 等）
- 选项 C：保持当前黑盒状态（延后到 Phase 2）
```

**决策日期**：_____  
**你的决策**：  

---

### Q2：Heavenly Graph 保留还是砍

**问题定义**（文档表 3.2）：
- 位置：`backend/app/main.py:2229` — `authority_event_bus.subscribe("*", ...)`
- 现状：用 `*` 通配订阅复制全部 gameplay 事件
- revision 混推：`max(payload_revision, producer_ts)`
- 风险：新的 siming 服务会继承"全量复制"模式，而不是按 FactType 订阅

**依赖的代码**：
- `backend/app/services/siming_orchestrator.py` — 依赖底层的全量订阅
- `backend/app/services/siming_data_layer.py` — 持久化的数据可能混入了未过滤的事件
- `backend/app/services/authority_graph_projector.py:22-32` — 用字符串前缀推 Owner domain

**需要你的决策**：
```
Heavenly Graph 应该保留还是砍？

- 选项 A：保留，但改成按 FactType 订阅（中等工作量）
  → 需要更新 DOMAIN_BY_EVENT_PREFIX，改成 FactType 声明
  → 新的 siming 服务继续在此基础上构建
  
- 选项 B：砍掉，司命直接访问 OwnerFactQuery 端口（高工作量）
  → Heavenly Graph 相关的 3 个模块需要重写
  → revision 混推问题自然消失
  
- 选项 C：暂时保留现状，标记为"Phase 2 代债"（低工作量）
  → 新模块继续依赖全量订阅
  → 但会固化缺陷
```

**决策日期**：_____  
**你的决策**：  

---

### Q3：pinned_revisions 补上校验是否算"行为改变"

**问题定义**（文档表 2.1）：
- 现状：333 处使用 `pinned_revisions`，但 event_store 里出现 0 次
- 意义：从不与实际 revision 校验
- 已做：`bf300868` 在 `population_driver.py:234` 补了一处校验
- 问题：这是"修缺陷"还是"行为改变"？

**现有的补救**：
- `backend/app/world_runtime/population_driver.py:234` — 新增 revision 校验
  ```python
  or self.mapping.revision != self.mapping.target_profile_revision
  ```

**需要你的决策**：
```
是否要全量推广 pinned_revisions 校验？

- 选项 A：是，这是"补缺陷"，应该在所有 333 处推广
  → 需要逐个 Owner runtime 补类似的校验
  → 可能会导致现有的某些流程被拒绝（行为改变）
  
- 选项 B：否，这个是"行为改变"，需要单独评审
  → 只保留 population_driver 的这一处
  → 其他 333 处保持现状（从不校验）
  
- 选项 C：延后到 Phase 2，作为 Owner 重构的一部分
  → 暂时保留现状
  → 在阶段 1 建立适配器时一并处理
```

**决策日期**：_____  
**你的决策**：  

---

## 二、现有代码中的缺陷标记

### 缺陷 1：B0 热表无 Owner 归属

**位置**：`backend/app/population_continuity/hot_state.py:11-18`  
**标记**：`# TODO: Q1 - B0 字段 Owner 归属待决`  
**影响范围**：
- `fair_focus.py` — 管理 starvation_credit  
- `siming_contracts.py:159` — 校验新字段

**状态**：⏳ 等待 Q1 决策

---

### 缺陷 2：Heavenly Graph 全量订阅

**位置**：`backend/app/main.py:2229`  
**标记**：`# TODO: Q2 - Heavenly Graph 全量订阅改 FactType 或砍`  
**影响范围**：
- `siming_orchestrator.py` — 依赖全量订阅  
- `authority_graph_projector.py:22-32` — 字符串前缀推断

**状态**：⏳ 等待 Q2 决策

---

### 缺陷 3：pinned_revisions 333 处不校验

**已补**：`population_driver.py:234` 补了 1/333  
**标记**：`# TODO: Q3 - 是否全量推广 pinned_revisions 校验`  
**状态**：⏳ 等待 Q3 决策 → 决策后推广或保持现状

---

## 三、缺陷补救的执行顺序

**阶段 1（已完成）**：
- ✅ T2 修复：`recovery.py` 改语义指纹（commit f1e18067）
- ✅ Q3 部分修复：population_driver 补校验（commit bf300868）

**阶段 2（等待你的决策）**：
- ⏳ Q1 决策 → 给 B0 字段定 Owner 或标记推迟
- ⏳ Q2 决策 → 改 Heavenly Graph 订阅或标记代债
- ⏳ Q3 决策 → 全量推广或保持单点修复

**阶段 3（条件执行）**：
- 如 Q1 = 创建新 Owner → 需要修改 world.py 和新增 Owner runtime
- 如 Q2 = 改 FactType 订阅 → 需要重写 authority_event_bus 订阅逻辑
- 如 Q3 = 全量推广 → 需要逐个 Owner runtime 补类似校验

---

## 四、新增模块与缺陷的关系

**新增的 9 个模块**（commit 6e328d29）：
- ❌ `fair_focus.py` — 依赖 Q1 未决
- ❌ `driver_arbitration.py` 等 — 依赖 HOT_FIELDS 黑盒
- ❌ `siming_orchestrator.py` 等 — 依赖 Q2 未决（全量订阅）
- ✅ `siming_data_layer.py` — 独立，只是补持久化

**建议**：
- 在 Q1/Q2/Q3 决策前，这 9 个模块的集成应该保持谨慎
- 至少应该在代码中标记依赖关系，方便后续快速适配

---

## 五、检查清单

- [ ] Q1：B0 字段 Owner 归属已决策
- [ ] Q2：Heavenly Graph 保留/砍/改 FactType 已决策  
- [ ] Q3：pinned_revisions 全量推广/保持/延后 已决策
- [ ] T2：recovery.py 改语义指纹 ✅ 已完成
- [ ] 新增 9 个模块根据决策重新评审
- [ ] 依赖标记添加到代码中（TODO 注释）

---

**更新历史**：

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-11-08 | 1.0 | 初始版本：记录三个待决问题和现有缺陷标记 |

