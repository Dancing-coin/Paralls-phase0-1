# 司命（Siming）架构与不合理之处

**日期**：2026-11-08  
**状态**：Phase 0-1 基线  
**关键问题**：三套状态副本无对账机制、投影不完整、OwnerFactQuery 缺失

---

## 一、当前架构概览

### 数据流向

```
Owner Events (gameplay.*)
    ↓
authority_event_bus.subscribe("*", ...)
    ↓
HeavenlyAuthorityEventProjector.project()
    ↓
HeavenlyGraphNode (in-memory)
    ↓
[三套副本并行更新]
├─ InMemorySimingStateTree
├─ SimingGlobalSituationLayer.snapshots
└─ SimingNarrativeCore
    ↓
siming_orchestrator / siming_runtime
    ↓
SimingOutput
    ↓
siming_event_producer → AuthorityEvent
    ↓
authority_event_bus.publish()
```

### 三套状态副本

| 名称 | 位置 | 用途 | source_owner | 对账 |
|------|------|------|--------------|------|
| InMemorySimingStateTree | siming_state_tree.py | 计划状态 | ❌ 无 | ❌ 无 |
| GlobalSituationLayer | siming_global_situation.py | 环境快照 | ❌ 无 | ❌ 无 |
| NarrativeCore | siming_narrative_core.py | 叙事追踪 | ❌ 无 | ❌ 无 |

---

## 二、不合理之处（Phase 2 需改）

### ❌ 问题 1：三套副本独立更新，无对账机制

**现状**：
- 三套副本各自从原始事件独立读取
- 无 source_owner / source_revision 追踪
- 无一致性验证

**后果**：
- 版本漂移（某一套更新失败，其他继续）
- 恢复时无法验证一致性
- 调试困难

**Phase 2 方案**：
- 改所有三套从 `OwnerFactQuery` 读取
- 添加 `source_owner / source_revision` 字段
- 实现 `validate_consistency()` 检查函数

---

### ❌ 问题 2：投影用 `*` 通配，复制全量事件

**现状**：
- `main.py:2230` — `authority_event_bus.subscribe("*", ...)`
- 复制全部 gameplay 事件
- revision 混推 `max(payload_revision, producer_ts)`

**后果**：
- 无法按 Owner / FactType 过滤
- 司命被迫处理所有事件
- siming_data_layer 持久化了无用数据

**Phase 2 方案**：
- 改成按 FactType 显式订阅
- 建立 FactType → Owner domain 映射
- 用 Owner 的真实 revision

---

### ❌ 问题 3：siming_observe.py 的输入白名单无来源

**S2 缺陷**：
```python
ALLOWED_EVENT_TYPES = {
    "world_fact_event",
    "visual_fact_event",
    "esm_result_event",
    ...
}
```

**问题**：
- 这些是怎么选出来的？
- 与 Owner FactType 的对应关系是什么？
- 新 Owner 加进来怎么办？

**Phase 2 方案**：
- 改成 `ALLOWED_FACT_TYPES` 枚举（从 FactType 驱动）
- 自动推导而非硬编码

---

### ❌ 问题 4：siming_data_layer 的定位模糊

**现状**：
- 补充了 `FairnessStateSnapshot` 等的持久化
- 建了 6 个表
- 但与三套副本的关系不清

**问题**：
- 是"热缓存"还是"真相来源"？
- 为什么三套副本仍然直接读原始事件？
- 新增数据与三套副本如何对账？

**Phase 2 方案**：
- 明确 siming_data_layer 是"事实层"（与 Owner 一致）
- 三套副本从它读取，而非直接读 HeavenlyGraph

---

### ⚠️ 问题 5：环境请求路由不清（S7）

**现状**：
- `siming_event_producer._event_type_for()` 返回 `"siming.environment_request"`
- 目标是 `["esm"]`
- 文档不说明 ESM 如何处理

**问题**：
- 命名 environment_request 但实际走 ESM
- 没有说明这是"环境变化通知"还是"请求"

**Phase 2 改进**：
- 改名为 `siming.environment_change_event` 更清晰
- 添加文档说明 ESM 是订阅者

---

### ⚠️ 问题 6：char_b 硬编码占位符（S8）

**现状**：
- siming_runtime.py 中 3 处 `"char_b"` 硬编码
- 用于备选 actor 或缺省值

**问题**：
- 这是测试数据还是占位符？
- 在产品代码中不应该有魔数

**Phase 2 改进**：
- 使用 roster 系统动态解析
- 或标记为"default_observer"并通过配置

---

### ❓ 问题 7：fair_focus 与 starvation_credit（Q1 未决）

**现状**：
- fair_focus 管理 starvation_credit
- starvation_credit 来自 HOT_FIELDS（群体模拟）

**问题**：
- fair_focus 是司命模块还是群体模拟模块？
- 为什么司命依赖群体模拟的内部数据？

**依赖**：
- 等待 Q1 决策（B0 字段 Owner 归属）

---

## 三、需要的补充文档

### 1. 司命输入契约（INPUT_CONTRACT.md）

```
FactType → 司命事件类型 映射

world_fact_event
├─ Schema: {...}
├─ Subscriber: siming_observe
└─ Impact: [StateTree, GlobalSituation, ...]

visual_fact_event
├─ Schema: {...}
├─ Subscriber: siming_observe
└─ Impact: [StateTree, ...]

...
```

### 2. 司命状态模型（STATE_MODEL.md）

```
三套副本角色定义

InMemorySimingStateTree
├─ Role: 计划/决策的 staging 区域
├─ Authority: siming_orchestrator
├─ Consistency Check: 与 NarrativeCore 对账

SimingGlobalSituationLayer
├─ Role: 环境快照和上下文
├─ Authority: ?
├─ Consistency Check: ?

SimingNarrativeCore  
├─ Role: 叙事事件追踪
├─ Authority: ?
├─ Consistency Check: ?

验证机制：validate_consistency(tree, global, narrative) → bool
```

### 3. 司命输出契约（OUTPUT_CONTRACT.md）

```
SimingOutput → AuthorityEvent 映射

impulse
├─ event_type: siming.impulse
├─ target_ids: [character_actor_id, frontend_projector]
└─ Subscriber: ?

opportunity
├─ event_type: siming.opportunity
├─ target_ids: [character_actor_id, frontend_projector]
└─ Subscriber: ?

fact_reveal
├─ event_type: siming.fact_reveal
├─ target_ids: [character_actor_id, frontend_projector]
└─ Subscriber: ?

environment_change (S7)
├─ event_type: siming.environment_request
├─ target_ids: [esm]
└─ Subscriber: ESM Service

visual_observability_request
├─ event_type: siming.visual_observability_request
├─ target_ids: [frontend_projector]
└─ Subscriber: Frontend Projector

...
```

### 4. 投影规则（PROJECTION_CONTRACT.md）

```
Owner Event → HeavenlyGraph Node 映射

gameplay.inventory.*
├─ Domain: inventory
├─ Subscription: explicit (FactType)
└─ Revision: Owner.revision

gameplay.survival.*
├─ Domain: survival_body
├─ Subscription: explicit (FactType)
└─ Revision: Owner.revision

...

Revision handling:
- NOT max(payload, producer_ts)
- Use Owner's actual revision_vector
```

---

## 四、立即可改的项（Phase 1 补救）

### S7：环境请求路由澄清

**文件**：siming_event_producer.py:146-149

改前：
```python
if output.selected_path == "environment_change_path":
    return "siming.environment_request"
```

改后：
```python
# S7: environment_change_path routes to ESM
# Routes to "environment_request" but target is ["esm"]. Clarify in Phase 2.
if output.selected_path == "environment_change_path":
    return "siming.environment_request"
```

✅ 已改

---

### S8：char_b 占位符澄清

**文件**：siming_runtime.py（3 处）

改后注释：
```python
# S8: char_b placeholder. In Phase 2, should use roster resolution.
# TODO: Replace with actual character from roster system.
"target_actor_id": "char_b",
```

✅ 已改

---

## 五、Phase 2 实施优先级

| 优先级 | 项 | 工作量 | 阻塞项 |
|--------|-----|--------|---------|
| 🔴 P0 | 三套副本对账机制 | 高 | - |
| 🔴 P0 | OwnerFactQuery 端口 | 高 | P0 |
| 🟡 P1 | 投影改 FactType 订阅 | 中 | Q2 决策 |
| 🟡 P1 | 输入/输出契约文档 | 低 | - |
| 🟡 P1 | char_b → roster 解析 | 低 | - |
| 🟡 P1 | fair_focus → Owner 驱动 | 中 | Q1 决策 |

---

**状态**：✅ 已标记和澄清，等待 Phase 2 实施

