# 司命长期改造方案（Q1/Q2 Long-Term Implementation Plan）

**生成时间**：2026-11-08  
**依据文档**：`docs/reference/phase1-siming/Q1-Q2-decisions.md`、`C:\Users\38101\Desktop\05-Owner重构影响评估.md`  
**目标**：按照 Q1/Q2 长期方案实施断点修复，而非短期注释改进

---

## 一、改造范围概览

本方案解决以下断点：

| 断点 | 当前问题 | 长期方案 | 优先级 |
|------|---------|---------|--------|
| **Q1** | B0 HOT_FIELDS 无 Owner 归属 | 创建 daily_rhythm_runtime Owner | P0 |
| **Q2-C** | Heavenly Graph 存事实副本（第二真相） | 图只存边，事实走 OwnerFactQuery | P1 |
| **S2** | siming_observe 字符串白名单 | 改为 FactType 枚举订阅 | P1 |
| **S3** | authority_graph_projector 前缀推断 | 改为 FactType → domain 契约声明 | P1 |
| **S4** | heavenly_graph_semantics 硬编码规则 | 改为 FactType → GraphNodeType 映射 | P2 |
| **S5** | WorldFactMemoryEntry 缺 fact_type_ref | 增加字段，映射到 Owner FactType | P2 |
| **S6** | siming_policy 只认 actor_id | 扩展到统一 entity eligibility registry | P2 |

---

## 二、前置条件与依赖

### 2.1 Owner 重构前置条件

以下能力需要 Owner 重构提供，**不在本方案实施范围**：

1. **FactType 基础设施**：
   - `app.models.fact_type.FactType` enum 或声明式注册表
   - FactType → domain / visibility / graph规则 的映射
   - FactType 验证器

2. **OwnerFactQuery 接口**：
   - 司命查询 Owner 事实的统一端口
   - 支持 `fact_type_ref` / `entity_id` / `revision` 查询
   - 返回 Owner 事实的当前值 + revision vector

3. **Owner 事件总线集成**：
   - 按 FactType 枚举订阅（替代当前的 `"*"` 通配）
   - 事件 payload 携带 `fact_type_ref` 字段

### 2.2 可独立实施的部分

以下改造**不依赖 Owner 重构**，可以立即开始：

1. **Q1**：创建 daily_rhythm_runtime Owner
2. **S1/S7/S8**：司命内部硬编码改进（不涉及 Owner 接口）

---

## 三、Q1 长期方案：创建 daily_rhythm_runtime Owner

### 3.1 目标

解决 B0 六个字段的归属问题：

```python
# backend/app/population_continuity/hot_state.py:44
HOT_FIELDS = frozenset({
    "last_update_tick",      # 上次更新 tick
    "activity_phase",        # 活动阶段（早/午/晚/深夜）
    "fatigue",               # 疲劳度（0.0-1.0）
    "need_pressure",         # 需求压力
    "next_due_tick",         # 下次到期 tick
    "starvation_credit",     # 饥饿积分（公平性覆盖指标）
})
```

### 3.2 实施步骤

#### Step 1：创建 daily_rhythm_runtime.py

**路径**：`backend/app/gameplay/daily_rhythm_runtime.py`

**参考模板**：`backend/app/gameplay/survival_runtime.py`（同样管理角色状态）

**需要声明的 FactType**：

```python
from app.gameplay.event_schema_registry import register_event_schema
from app.gameplay.semantic_registry import register_fact_type

# FactType 声明（假设 FactType 基础设施存在）
FATIGUE_STATE = register_fact_type(
    fact_type="daily_rhythm.fatigue_state",
    domain="daily_rhythm",
    schema={
        "type": "object",
        "properties": {
            "actor_id": {"type": "string"},
            "fatigue": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "tick": {"type": "integer"},
        },
        "required": ["actor_id", "fatigue", "tick"],
    },
    visibility="actor_private",
)

NEED_PRESSURE_STATE = register_fact_type(
    fact_type="daily_rhythm.need_pressure_state",
    domain="daily_rhythm",
    schema={
        "type": "object",
        "properties": {
            "actor_id": {"type": "string"},
            "need_pressure": {"type": "number", "minimum": 0.0},
            "tick": {"type": "integer"},
        },
        "required": ["actor_id", "need_pressure", "tick"],
    },
    visibility="actor_private",
)

STARVATION_CREDIT_STATE = register_fact_type(
    fact_type="daily_rhythm.starvation_credit_state",
    domain="daily_rhythm",
    schema={
        "type": "object",
        "properties": {
            "actor_id": {"type": "string"},
            "starvation_credit": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "tick": {"type": "integer"},
        },
        "required": ["actor_id", "starvation_credit", "tick"],
    },
    visibility="siming_internal",  # 司命调度公平性指标
)

ACTIVITY_PHASE_STATE = register_fact_type(
    fact_type="daily_rhythm.activity_phase_state",
    domain="daily_rhythm",
    schema={
        "type": "object",
        "properties": {
            "actor_id": {"type": "string"},
            "activity_phase": {
                "type": "string",
                "enum": ["morning", "afternoon", "evening", "night"]
            },
            "tick": {"type": "integer"},
        },
        "required": ["actor_id", "activity_phase", "tick"],
    },
    visibility="public",
)

# 对应的事件 schema
register_event_schema(
    event_type="daily_rhythm.fatigue_updated",
    schema={...}
)
register_event_schema(
    event_type="daily_rhythm.need_pressure_updated",
    schema={...}
)
register_event_schema(
    event_type="daily_rhythm.starvation_credit_updated",
    schema={...}
)
register_event_schema(
    event_type="daily_rhythm.activity_phase_changed",
    schema={...}
)
```

#### Step 2：迁移 continuous.py 的计算逻辑

**当前位置**：`backend/app/population_continuity/continuous.py`

**改造内容**：

```python
# 当前：直接写 HOT_FIELDS
def advance_b0_row(row: dict, tick: int, delta_seconds: float) -> dict:
    row["fatigue"] = min(1.0, row.get("fatigue", 0.0) + 0.001 * delta_seconds)
    row["need_pressure"] = min(1.0, row.get("need_pressure", 0.0) + 0.01 / 3600)
    # ...
    return row

# 改为：发送 daily_rhythm 事件
def advance_b0_row(row: dict, tick: int, delta_seconds: float) -> dict:
    actor_id = row["actor_id"]
    
    # 计算新状态（保持原逻辑）
    new_fatigue = min(1.0, row.get("fatigue", 0.0) + 0.001 * delta_seconds)
    new_need_pressure = min(1.0, row.get("need_pressure", 0.0) + 0.01 / 3600)
    # ...
    
    # 发送 Owner 事件（替代直接写 row）
    events = []
    if new_fatigue != row.get("fatigue"):
        events.append(AuthorityEvent(
            event_type="daily_rhythm.fatigue_updated",
            payload={
                "actor_id": actor_id,
                "fatigue": new_fatigue,
                "tick": tick,
            },
            # ...
        ))
    if new_need_pressure != row.get("need_pressure"):
        events.append(AuthorityEvent(
            event_type="daily_rhythm.need_pressure_updated",
            payload={
                "actor_id": actor_id,
                "need_pressure": new_need_pressure,
                "tick": tick,
            },
            # ...
        ))
    
    # 发送到 Authority 总线
    for event in events:
        authority_event_bus.publish(event)
    
    # 返回更新后的 row（从 Owner 读回，或等待 receipt）
    return row
```

#### Step 3：迁移 hot_state.py 的读写逻辑

**当前位置**：`backend/app/population_continuity/hot_state.py:44`

**改造内容**：

```python
# 当前：HOT_FIELDS 直接写 dict
HOT_FIELDS = frozenset({
    "last_update_tick", "activity_phase", "fatigue",
    "need_pressure", "next_due_tick", "starvation_credit",
})

# 改为：从 Owner 读取
def get_hot_fields(actor_id: str) -> dict:
    """从 daily_rhythm Owner 读取热表字段"""
    fatigue = owner_fact_query.query(
        fact_type="daily_rhythm.fatigue_state",
        entity_id=actor_id,
    )
    need_pressure = owner_fact_query.query(
        fact_type="daily_rhythm.need_pressure_state",
        entity_id=actor_id,
    )
    # ...
    return {
        "fatigue": fatigue.value if fatigue else 0.0,
        "need_pressure": need_pressure.value if need_pressure else 0.0,
        # ...
    }
```

#### Step 4：迁移 world.py 的初始化逻辑

**当前位置**：`backend/app/population_continuity/world.py:780`

**改造内容**：

```python
# 当前：初始化 HOT_FIELDS 为 dict
def _initialize_actor_hot_state(actor_id: str) -> dict:
    return {
        "actor_id": actor_id,
        "last_update_tick": 0,
        "activity_phase": "morning",
        "fatigue": 0.0,
        "need_pressure": 0.0,
        "next_due_tick": 0,
        "starvation_credit": 0.0,
    }

# 改为：发送初始化事件
def _initialize_actor_hot_state(actor_id: str) -> None:
    """初始化角色的 daily_rhythm 状态"""
    authority_event_bus.publish(AuthorityEvent(
        event_type="daily_rhythm.initialized",
        payload={
            "actor_id": actor_id,
            "initial_fatigue": 0.0,
            "initial_need_pressure": 0.0,
            "initial_starvation_credit": 0.0,
            "initial_activity_phase": "morning",
            "tick": 0,
        },
        # ...
    ))
```

#### Step 5：更新 fair_focus.py

**当前位置**：`backend/app/population_continuity/fair_focus.py:13-17`

**改造内容**：

```python
# 当前：直接读写 starvation_credit
def rank_by_starvation(actors: list[dict]) -> list[dict]:
    return sorted(actors, key=lambda a: a.get("starvation_credit", 0.0), reverse=True)

# 改为：从 daily_rhythm Owner 查询
def rank_by_starvation(actor_ids: list[str]) -> list[str]:
    """从 daily_rhythm Owner 查询 starvation_credit 并排序"""
    credits = {}
    for actor_id in actor_ids:
        fact = owner_fact_query.query(
            fact_type="daily_rhythm.starvation_credit_state",
            entity_id=actor_id,
        )
        credits[actor_id] = fact.value if fact else 0.0
    return sorted(actor_ids, key=lambda aid: credits[aid], reverse=True)
```

### 3.3 Q1.2：activity_phase 升级为状态机

**文档位置**：`docs/reference/phase1-siming/Q1-Q2-decisions.md` Q1.2

**当前问题**：`continuous.py:24-30` 硬编码枚举

**改造方案**：

1. 声明状态机 `machine_id: "daily_rhythm.activity_phase"`
2. 四个状态：`morning` / `afternoon` / `evening` / `night`
3. 触发器：按 tick 计算（每 6 小时一次）
4. 替换硬编码函数为状态机查询

**实施细节**：参考 `backend/app/gameplay/life_state_runtime.py` 的状态机实现

### 3.4 验收条件

- [ ] `backend/app/gameplay/daily_rhythm_runtime.py` 存在
- [ ] 六个字段全部有对应 FactType 声明
- [ ] `hot_state.py` 的 `HOT_FIELDS` 常量标记为"已废弃，现从 daily_rhythm Owner 读取"
- [ ] `continuous.py` 的计算逻辑改为发送 daily_rhythm 事件
- [ ] `fair_focus.py` 改为从 Owner 查询 starvation_credit
- [ ] 状态机 `daily_rhythm.activity_phase` 可查询
- [ ] 全量回归测试通过（2552+ passed）

---

## 四、Q2-C 长期方案：图只存边 + OwnerFactQuery

### 4.1 目标

**当前问题**：Heavenly Graph 存储事实副本，导致"第二真相"

**长期方案**：
1. 图只存边（关系）：角色 A 在房间 R、物品 I 被角色 A 持有、事件 E1 导致 E2
2. 事实走 OwnerFactQuery：不存事实副本，单一真相原则

### 4.2 前置条件（Owner 重构必须提供）

- [ ] **OwnerFactQuery 接口**：`owner_fact_query.query(fact_type, entity_id, revision?)`
- [ ] **FactType registry**：所有 Owner domain 的 FactType 枚举
- [ ] **Revision vector 对账**：司命查询的 revision 必须与 Owner 一致

### 4.3 实施步骤（Phase 2+）

#### Step 1：重设计 Heavenly Graph schema

**当前**：`HeavenlyGraphNode` 存储完整 payload

```python
class HeavenlyGraphNode:
    node_id: str
    node_type: str
    attributes: dict  # 存事实副本！
```

**改为**：只存 identity + revision

```python
class HeavenlyGraphNode:
    node_id: str
    node_type: str
    fact_type_ref: str  # 指向 Owner FactType
    entity_id: str      # Owner 实体 ID
    revision: int       # Owner revision
    # attributes 字段删除
```

#### Step 2：改造 authority_graph_projector

**当前**：`authority_graph_projector.py:61-121` 复制整个 payload 到图节点

```python
node = HeavenlyGraphNode(
    node_id=f"authority-projection:{event.event_id}",
    attributes={
        "domain": domain,
        "committed_payload": payload,  # 事实副本！
    },
)
```

**改为**：只存引用

```python
node = HeavenlyGraphNode(
    node_id=f"authority-projection:{event.event_id}",
    fact_type_ref=event.fact_type,  # 从 Owner 事件读取
    entity_id=event.payload["entity_id"],
    revision=event.payload["revision"],
    # attributes 删除
)
```

#### Step 3：改造 SimingFactCore

**当前**：从图节点的 `attributes` 读事实

```python
def get_world_fact(self, fact_id: str) -> dict:
    node = self.graph.get_node(fact_id)
    return node.attributes["committed_payload"]
```

**改为**：通过 OwnerFactQuery 读取

```python
def get_world_fact(self, fact_id: str) -> dict:
    node = self.graph.get_node(fact_id)
    return owner_fact_query.query(
        fact_type=node.fact_type_ref,
        entity_id=node.entity_id,
        revision=node.revision,
    )
```

#### Step 4：改造 WorldFactMemoryEntry

**当前**：`siming_heavenly_memory.py:45-58` 缺 fact_type_ref

```python
class WorldFactMemoryEntry(StrictMemoryModel):
    state_key: str
    state_value: JsonValue  # 存事实副本！
```

**改为**：增加 fact_type_ref

```python
class WorldFactMemoryEntry(StrictMemoryModel):
    fact_type_ref: str      # 新增：指向 Owner FactType
    entity_id: str          # 新增：Owner 实体 ID
    revision: int           # 新增：Owner revision
    state_key: str          # 保留：快速访问键
    state_value: JsonValue  # 保留：缓存值（可选）
```

### 4.4 验收条件

- [ ] `HeavenlyGraphNode.attributes` 字段删除
- [ ] `authority_graph_projector` 改为存引用
- [ ] `SimingFactCore` 改为通过 OwnerFactQuery 读取
- [ ] `WorldFactMemoryEntry` 增加 `fact_type_ref` 字段
- [ ] revision 对账测试通过
- [ ] 全量回归测试通过

---

## 五、S2/S3 长期方案：FactType 枚举订阅

### 5.1 S3：authority_graph_projector 改造

**当前位置**：`backend/app/services/authority_graph_projector.py:40-50`

**当前问题**：字符串前缀推断 domain

```python
DOMAIN_BY_EVENT_PREFIX = {
    "esm_result_event": "esm_world",
    "gameplay.inventory.": "inventory",
    # ...
}
```

**改造方案**：改为 FactType → domain 契约声明

```python
# 假设 FactType 基础设施提供
from app.models.fact_type import FactType, get_domain_for_fact_type

def _domain_for(cls, event_type: str) -> str | None:
    # 不再用前缀推断，直接查 FactType registry
    fact_type = FactType.from_event_type(event_type)
    if fact_type is None:
        return None
    return get_domain_for_fact_type(fact_type)
```

### 5.2 S2：siming_observe 改造

**当前位置**：`backend/app/services/siming_observe.py:9-17`

**当前问题**：字符串白名单

```python
ALLOWED_EVENT_TYPES = {
    "world_fact_event",
    "visual_fact_event",
    # ...
}
```

**改造方案**：改为 FactType 枚举白名单

```python
from app.models.fact_type import FactType

ALLOWED_FACT_TYPES = frozenset({
    FactType.WORLD_FACT,
    FactType.VISUAL_FACT,
    FactType.ESM_RESULT,
    FactType.CHARACTER_BEHAVIOR,
    FactType.CONVERSATION_RESOLUTION,
    FactType.CONSTRAINT_STATE,
    FactType.POPULATION_CADENCE,
})

def observe(self, events: list[AuthorityEvent]) -> list[ObservedSimingEvent]:
    observed = []
    for event in events:
        fact_type = FactType.from_event_type(event.event_type)
        if fact_type not in self.ALLOWED_FACT_TYPES:
            continue
        # ...
```

### 5.3 main.py 订阅改造

**当前位置**：`backend/app/main.py:2233`

**当前问题**：`"*"` 通配订阅

```python
authority_event_bus.subscribe("*", _handle_heavenly_graph_projection)
```

**改造方案**：改为 FactType 枚举订阅

```python
from app.models.fact_type import FactType

# 司命关心的 FactType 列表
SIMING_SUBSCRIBED_FACT_TYPES = [
    FactType.WORLD_FACT,
    FactType.VISUAL_FACT,
    FactType.ESM_RESULT,
    FactType.CHARACTER_BEHAVIOR,
    FactType.CONVERSATION_RESOLUTION,
    FactType.CONSTRAINT_STATE,
    FactType.POPULATION_CADENCE,
    # 以及所有 gameplay.* domain 的 FactType
    *FactType.get_by_domain("inventory"),
    *FactType.get_by_domain("organization"),
    *FactType.get_by_domain("ownership"),
    *FactType.get_by_domain("economy"),
    *FactType.get_by_domain("survival_body"),
    *FactType.get_by_domain("resource_scene"),
]

for fact_type in SIMING_SUBSCRIBED_FACT_TYPES:
    event_type = fact_type.to_event_type()
    authority_event_bus.subscribe(event_type, _handle_heavenly_graph_projection)
```

### 5.4 验收条件

- [ ] `main.py:2233` 的 `"*"` 改为 FactType 枚举订阅
- [ ] `authority_graph_projector.DOMAIN_BY_EVENT_PREFIX` 删除，改为 FactType registry
- [ ] `siming_observe.ALLOWED_EVENT_TYPES` 改为 FactType 枚举
- [ ] 242 个 gameplay 事件全部有对应 FactType 声明
- [ ] 启动验证：所有订阅的 FactType 都在 registry 中
- [ ] 全量回归测试通过

---

## 六、S4/S5/S6 长期方案

### 6.1 S4：heavenly_graph_semantics 改造

**当前位置**：`backend/app/services/heavenly_graph_semantics.py:51-60`

**当前问题**：硬编码 node_type → 规则映射

**改造方案**：改为 FactType → GraphNodeType 映射

```python
class HeavenlyNodeTypeRegistry:
    @staticmethod
    def rule_for(fact_type: FactType) -> _NodeRule:
        """从 FactType metadata 派生图规则"""
        return _NodeRule(
            allowed_namespaces=fact_type.graph_namespaces,
            allowed_record_kinds=fact_type.graph_record_kinds,
            allowed_visibility_scopes=fact_type.visibility_scopes,
        )
```

### 6.2 S5：WorldFactMemoryEntry 改造

**见 4.4 Q2-C 改造**（增加 fact_type_ref 字段）

### 6.3 S6：siming_policy 改造

**当前位置**：`backend/app/services/siming_policy.py:39-47`

**当前问题**：只检查 `target_actor_id`

**改造方案**：扩展到统一 entity eligibility registry

```python
def evaluate(self, candidate: InterventionCandidate, *, snapshot: FairnessStateSnapshot) -> SimingPolicyResult:
    # 当前只检查 actor
    if candidate.target_actor_id:
        if candidate.target_actor_id in snapshot.blocked_actor_ids:
            reasons.append("actor_not_eligible")
    
    # 扩展：检查 environment_id
    if candidate.target_environment_id:
        if not self._entity_registry.is_eligible(
            entity_type="environment",
            entity_id=candidate.target_environment_id,
        ):
            reasons.append("environment_not_eligible")
    
    # 扩展：检查 object_id
    if candidate.target_object_id:
        if not self._entity_registry.is_eligible(
            entity_type="object",
            entity_id=candidate.target_object_id,
        ):
            reasons.append("object_not_eligible")
```

---

## 七、实施优先级

### Phase 0（立即可做，不依赖 Owner 重构）

1. **Q1**：创建 daily_rhythm_runtime Owner（P0）
2. **S1**：siming_state_tree 硬编码 payload 键改为类型化字段
3. **S7**：siming_event_producer environment_change_path 注释改进
4. **S8**：siming_runtime "char_b" 硬编码改为 roster 解析

### Phase 1（需要 FactType 基础设施）

1. **S2/S3**：FactType 枚举订阅（P1）
2. **S4**：FactType → GraphNodeType 映射（P2）

### Phase 2（需要 OwnerFactQuery 接口）

1. **Q2-C**：图只存边 + OwnerFactQuery（P1）
2. **S5**：WorldFactMemoryEntry 增加 fact_type_ref（P2）
3. **S6**：统一 entity eligibility registry（P2）

---

## 八、技术债务与风险

### 8.1 FactType 基础设施缺失

**问题**：当前仓库没有 FactType enum/registry

**解决方案**：
1. **临时方案**：司命自己搭建 FactType stub（仅用于 Phase 0）
2. **正式方案**：等 Owner 重构提供统一 FactType registry

### 8.2 OwnerFactQuery 接口缺失

**问题**：Q2-C 依赖 OwnerFactQuery，但接口尚未实现

**解决方案**：
1. Q2-C 必须等到 Owner 重构完成后才能开始
2. 在此之前，图仍存事实副本（但标记为"待迁移"）

### 8.3 Revision 对账复杂度

**问题**：司命查询的 revision 必须与 Owner 一致，否则会出现时序错误

**解决方案**：
1. 在 Q2-C 实施前，先实施 revision 对账测试（Q3 pinned_revisions 验证）
2. 每次图查询都验证 revision 是否匹配

### 8.4 242 个 gameplay 事件迁移

**问题**：S2/S3 需要为 242 个 gameplay 事件声明 FactType

**解决方案**：
1. 按 domain 分批迁移（inventory → organization → ownership → ...）
2. 每个 domain 迁移后立即测试，不要积压到最后

---

## 九、交接清单

### 9.1 已完成工作

- [x] S1/S3/S5/S6/S7/S8 断点标记（3304ebdd）
- [x] Q1/Q2/Q3 决策记录（fb1f0972）
- [x] Protocol 09 ESM 桥接（8ea1bc44）
- [x] T2 recovery.py 语义指纹修复（7d0155e0）
- [x] 全量回归降到 15 failed → 0 failed

### 9.2 待实施工作

1. **Q1 daily_rhythm_runtime**（本文第三章）
2. **S2/S3 FactType 订阅改造**（本文第五章）
3. **Q2-C 图只存边**（本文第四章，需 OwnerFactQuery）

### 9.3 关键文档

- `docs/reference/phase1-siming/Q1-Q2-decisions.md`：决策依据
- `C:\Users\38101\Desktop\05-Owner重构影响评估.md`：断点清单
- `.harness/SIMING-ARCHITECTURE.md`：司命架构现状

### 9.4 验证命令

```bash
# 全量回归
python -m pytest backend/tests/ -q --tb=no

# 司命专项测试
python -m pytest backend/tests/ -k siming -xvs

# daily_rhythm 测试（Q1 实施后）
python -m pytest backend/tests/test_daily_rhythm_runtime.py -xvs
```

---

## 十、补充说明

### 10.1 为什么不能立即做 Q2-C？

Q2-C（图只存边 + OwnerFactQuery）需要：
1. Owner 重构提供 OwnerFactQuery 接口
2. 所有 Owner domain 的 FactType 声明完成
3. Revision vector 对账机制落地

这些都是 **Owner 重构的输出**，不在司命范围内。

### 10.2 为什么可以立即做 Q1？

Q1（daily_rhythm_runtime）是**新建一个 Owner domain**，不依赖现有 Owner 重构：
1. 它只管理 6 个 HOT_FIELDS
2. 事件总线已存在（Authority EventBus）
3. 参考模板充足（survival_runtime.py）

### 10.3 短期 vs 长期的区别

- **短期方案（Q2-A）**：FactType 订阅，但图仍存事实副本
- **长期方案（Q2-C）**：图只存边，事实走 OwnerFactQuery

用户要求"按长期方案"，即**直接做 Q2-C**，跳过 Q2-A。但 Q2-C 的前置条件不满足，所以：
1. **Phase 0 先做 Q1**（不依赖 Owner 重构）
2. **Phase 1 再做 S2/S3**（需要 FactType 基础设施）
3. **Phase 2 最后做 Q2-C**（需要 OwnerFactQuery）

---

**方案生成完毕。交接给另一台电脑的 AI 继续实施。**
