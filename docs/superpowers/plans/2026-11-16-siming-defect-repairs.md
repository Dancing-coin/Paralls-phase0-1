# 司命非 Owner 缺陷补齐实施计划

**日期**：2026-11-16  
**依据**：`.harness/SIMING-ARCHITECTURE.md`、`.harness/defect-registry-q1-q2-q3.md`  
**约束**：不改 Owner 设计，只改司命代码；Q1/Q2/Q3 长期项已推迟到 Phase 2

---

## 一、范围与优先级

### 🔴 P0：核心架构缺陷（必须修复）

1. **三套状态副本无对账机制**
   - 文件：`backend/app/services/siming_runtime.py`、新建 `siming_consistency.py`
   - 问题：`InMemorySimingStateTree`、`GlobalSituationLayer`、`NarrativeCore` 独立更新，无一致性验证
   - 后果：版本漂移、恢复失败、调试困难
   - 工作量：中

2. **siming_data_layer 定位模糊**
   - 文件：`backend/app/services/siming_data_layer.py`
   - 问题：建了 6 个表但与三套副本关系不清
   - 后果：不知道哪些数据必须持久化、如何恢复
   - 工作量：低（主要是文档）

### 🟡 P1：文档与接口债务

3. **输入/输出契约文档缺失**
   - 文件：新建 `docs/reference/phase1-siming/` 下四份文档
   - 缺失：INPUT_CONTRACT.md、STATE_MODEL.md、OUTPUT_CONTRACT.md、PROJECTION_CONTRACT.md
   - 后果：新人无法理解司命数据流
   - 工作量：低

4. **fair_focus 模块归属不清**
   - 文件：`backend/app/population_continuity/fair_focus.py`
   - 问题：司命模块依赖群体模拟内部数据（HOT_FIELDS）
   - 后果：边界模糊、难以独立测试
   - 工作量：低（接口隔离）

### 🟢 P2：验证与澄清

5. **ESM 订阅验证（S7）**
   - 验证：ESM 确实订阅了 `siming.environment_request`
   - 工作量：极低

---

## 二、详细实施方案

### P0.1：三套状态副本对账机制

#### 目标

实现 `validate_state_consistency()` 函数，在每次 tick 后验证三套副本一致性。

#### 实施步骤

1. **新建 `backend/app/services/siming_consistency.py`**

```python
from dataclasses import dataclass
from app.services.siming_state_tree import InMemorySimingStateTree
from app.services.siming_global_situation import GlobalSituationLayer
from app.services.siming_narrative_core import NarrativeCore


@dataclass
class StateInconsistency:
    """状态不一致记录"""
    category: str  # "actor_state" | "tick_mismatch" | "event_missing" | "revision_drift"
    entity_id: str
    detail: str


class SimingConsistencyValidator:
    """司命三套状态副本一致性验证器
    
    验证 InMemorySimingStateTree、GlobalSituationLayer、NarrativeCore 三套副本的一致性。
    
    检查项：
    1. 同一 actor_id 在三套中的存在性一致
    2. tick/timestamp 对齐
    3. 关键事件是否都被记录
    4. revision 是否漂移
    """
    
    def validate(
        self,
        tree: InMemorySimingStateTree,
        global_situation: GlobalSituationLayer,
        narrative: NarrativeCore,
        *,
        current_tick: int
    ) -> list[StateInconsistency]:
        """验证三套副本一致性，返回不一致项列表"""
        inconsistencies: list[StateInconsistency] = []
        
        # 检查 actor 存在性一致
        tree_actors = set(tree.get_all_actor_ids())
        global_actors = set(global_situation.get_all_actor_ids())
        narrative_actors = set(narrative.get_all_actor_ids())
        
        missing_in_global = tree_actors - global_actors
        missing_in_narrative = tree_actors - narrative_actors
        
        for actor_id in missing_in_global:
            inconsistencies.append(StateInconsistency(
                category="actor_state",
                entity_id=actor_id,
                detail=f"Actor exists in StateTree but missing in GlobalSituation"
            ))
        
        for actor_id in missing_in_narrative:
            inconsistencies.append(StateInconsistency(
                category="actor_state",
                entity_id=actor_id,
                detail=f"Actor exists in StateTree but missing in NarrativeCore"
            ))
        
        # 检查 tick 对齐
        tree_tick = tree.current_tick
        global_tick = global_situation.current_tick
        narrative_tick = narrative.current_tick
        
        if tree_tick != current_tick:
            inconsistencies.append(StateInconsistency(
                category="tick_mismatch",
                entity_id="state_tree",
                detail=f"StateTree tick {tree_tick} != expected {current_tick}"
            ))
        
        if global_tick != current_tick:
            inconsistencies.append(StateInconsistency(
                category="tick_mismatch",
                entity_id="global_situation",
                detail=f"GlobalSituation tick {global_tick} != expected {current_tick}"
            ))
        
        if narrative_tick != current_tick:
            inconsistencies.append(StateInconsistency(
                category="tick_mismatch",
                entity_id="narrative_core",
                detail=f"NarrativeCore tick {narrative_tick} != expected {current_tick}"
            ))
        
        # 检查关键事件记录一致性
        # TODO: Phase 2 添加事件溯源验证
        
        return inconsistencies
    
    def is_consistent(
        self,
        tree: InMemorySimingStateTree,
        global_situation: GlobalSituationLayer,
        narrative: NarrativeCore,
        *,
        current_tick: int
    ) -> bool:
        """快速检查是否一致"""
        return len(self.validate(tree, global_situation, narrative, current_tick=current_tick)) == 0
```

2. **在 `siming_runtime.py` 中集成**

```python
# 在 SimingRuntime.__init__() 添加
self._consistency_validator = SimingConsistencyValidator()

# 在每次 tick 后验证
def _post_tick_validation(self, current_tick: int) -> None:
    """Tick 后验证三套副本一致性"""
    inconsistencies = self._consistency_validator.validate(
        self._state_tree,
        self._global_situation,
        self._narrative_core,
        current_tick=current_tick
    )
    
    if inconsistencies:
        # 记录到审计日志
        for inc in inconsistencies:
            self._audit_writer.log_consistency_warning(
                category=inc.category,
                entity_id=inc.entity_id,
                detail=inc.detail,
                tick=current_tick
            )
        
        # 严重不一致时拒绝继续
        if any(inc.category in {"actor_state", "tick_mismatch"} for inc in inconsistencies):
            raise SimingConsistencyError(
                f"Critical state inconsistency detected: {inconsistencies}"
            )
```

3. **添加测试**

```python
# backend/tests/test_siming_consistency.py
def test_actor_missing_in_global_situation():
    """测试 actor 在 GlobalSituation 中缺失"""
    tree = InMemorySimingStateTree()
    tree.add_actor("char_a")
    
    global_situation = GlobalSituationLayer()
    # 故意不添加 char_a
    
    narrative = NarrativeCore()
    narrative.add_actor("char_a")
    
    validator = SimingConsistencyValidator()
    inconsistencies = validator.validate(tree, global_situation, narrative, current_tick=100)
    
    assert len(inconsistencies) == 1
    assert inconsistencies[0].category == "actor_state"
    assert inconsistencies[0].entity_id == "char_a"


def test_tick_mismatch():
    """测试 tick 不对齐"""
    tree = InMemorySimingStateTree()
    tree.current_tick = 100
    
    global_situation = GlobalSituationLayer()
    global_situation.current_tick = 99  # 故意不对齐
    
    narrative = NarrativeCore()
    narrative.current_tick = 100
    
    validator = SimingConsistencyValidator()
    inconsistencies = validator.validate(tree, global_situation, narrative, current_tick=100)
    
    assert len(inconsistencies) == 1
    assert inconsistencies[0].category == "tick_mismatch"
    assert inconsistencies[0].entity_id == "global_situation"


def test_all_consistent():
    """测试三套副本一致"""
    tree = InMemorySimingStateTree()
    tree.add_actor("char_a")
    tree.current_tick = 100
    
    global_situation = GlobalSituationLayer()
    global_situation.add_actor("char_a")
    global_situation.current_tick = 100
    
    narrative = NarrativeCore()
    narrative.add_actor("char_a")
    narrative.current_tick = 100
    
    validator = SimingConsistencyValidator()
    assert validator.is_consistent(tree, global_situation, narrative, current_tick=100)
```

#### 验收条件

- [ ] `siming_consistency.py` 存在并实现 `SimingConsistencyValidator`
- [ ] `siming_runtime.py` 每次 tick 后调用 `_post_tick_validation()`
- [ ] 三个测试通过：actor 缺失、tick 不对齐、完全一致
- [ ] 后端回归通过（10074+ passed）

---

### P0.2：siming_data_layer 定位明确

#### 目标

明确 `siming_data_layer` 是"事实层"而非"热缓存"，三套副本从它读取而非直接读原始事件。

#### 实施步骤

1. **添加架构文档 `docs/reference/phase1-siming/siming-data-layer-role.md`**

```markdown
# Siming Data Layer 角色定位

## 定位

**siming_data_layer 是司命的"事实层"**，而非热缓存。

## 职责

1. **持久化司命事实**：
   - `FairnessStateSnapshot`：公平性快照
   - `InterventionCandidate`：干预候选
   - `SimingOutput`：输出记录
   - `WorldFactMemoryEntry`：世界事实记忆
   - `CausalTimelineMemoryEntry`：因果时间线
   - `ActorCognitionMemoryEntry`：角色认知

2. **提供恢复能力**：
   - 司命重启后从 siming_data_layer 恢复状态
   - 而非重新读取全部原始事件

3. **隔离司命与 Owner**：
   - 司命不直接访问 Owner 内部表
   - 通过 siming_data_layer 读取投影后的事实

## 数据流向

```
Owner Events → HeavenlyGraph → siming_data_layer → 三套副本
                                      ↓
                              持久化到 SQLite
```

## 三套副本从 siming_data_layer 读取

- `InMemorySimingStateTree` 启动时从 `siming_data_layer.load_state_tree()` 恢复
- `GlobalSituationLayer` 启动时从 `siming_data_layer.load_global_situation()` 恢复
- `NarrativeCore` 启动时从 `siming_data_layer.load_narrative()` 恢复

## Phase 2 改进

- 当前：三套副本仍直接读 HeavenlyGraph（过渡期）
- 目标：三套副本只从 siming_data_layer 读取
- 前置条件：OwnerFactQuery 接口落地
```

2. **在 `siming_data_layer.py` 添加恢复接口**

```python
# backend/app/services/siming_data_layer.py

class SimingDataLayer:
    """司命事实层：持久化司命状态并提供恢复能力
    
    职责：
    1. 持久化 FairnessStateSnapshot、InterventionCandidate、SimingOutput 等
    2. 提供恢复接口供三套副本启动时读取
    3. 隔离司命与 Owner 内部表
    
    Phase 2: 三套副本改为只从 siming_data_layer 读取，不再直接读 HeavenlyGraph
    """
    
    def load_state_tree_snapshot(self, room_id: str, up_to_tick: int) -> dict:
        """加载 StateTree 快照供恢复使用"""
        # TODO: Phase 2 实现
        return {}
    
    def load_global_situation_snapshot(self, room_id: str, up_to_tick: int) -> dict:
        """加载 GlobalSituation 快照供恢复使用"""
        # TODO: Phase 2 实现
        return {}
    
    def load_narrative_snapshot(self, room_id: str, up_to_tick: int) -> dict:
        """加载 NarrativeCore 快照供恢复使用"""
        # TODO: Phase 2 实现
        return {}
```

3. **添加测试**

```python
# backend/tests/test_siming_data_layer_role.py
def test_data_layer_persist_and_load():
    """测试 siming_data_layer 持久化和加载"""
    data_layer = SimingDataLayer(room_id="room_test")
    
    # 持久化快照
    snapshot = FairnessStateSnapshot(
        room_id="room_test",
        tick=100,
        eligible_actor_ids=["char_a", "char_b"],
        blocked_actor_ids=[],
        dimensions={},
        known_fact_ids=set(),
        eligible_environment_ids=[],
        eligible_object_ids=[]
    )
    data_layer.save_fairness_snapshot(snapshot)
    
    # 加载验证
    loaded = data_layer.load_latest_fairness_snapshot()
    assert loaded.tick == 100
    assert loaded.eligible_actor_ids == ["char_a", "char_b"]
```

#### 验收条件

- [ ] `docs/reference/phase1-siming/siming-data-layer-role.md` 存在
- [ ] `siming_data_layer.py` 添加三个恢复接口（带 TODO: Phase 2）
- [ ] 测试通过：持久化和加载
- [ ] 后端回归通过

---

### P1.1：输入/输出契约文档

#### 目标

补齐四份契约文档，让新人能理解司命数据流。

#### 实施步骤

**四份文档内容见下节详细方案**

#### 验收条件

- [ ] `docs/reference/phase1-siming/INPUT_CONTRACT.md` 存在
- [ ] `docs/reference/phase1-siming/STATE_MODEL.md` 存在
- [ ] `docs/reference/phase1-siming/OUTPUT_CONTRACT.md` 存在
- [ ] `docs/reference/phase1-siming/PROJECTION_CONTRACT.md` 存在

---

### P1.2：fair_focus 归属澄清

#### 目标

明确 `fair_focus` 是"司命公平性调度器"，通过接口读取 `starvation_credit` 而非直接访问 HOT_FIELDS。

#### 实施步骤

1. **在 `hot_state.py` 添加接口**

```python
# backend/app/population_continuity/hot_state.py

def get_starvation_credit_for_siming(actor_id: str, b0_row: dict) -> float:
    """司命调度接口：读取角色饥饿积分
    
    接口隔离：fair_focus 通过此接口读取，而非直接访问 HOT_FIELDS。
    """
    return b0_row.get("starvation_credit", 0.0)
```

2. **在 `fair_focus.py` 改为调用接口**

```python
# backend/app/population_continuity/fair_focus.py

from app.population_continuity.hot_state import get_starvation_credit_for_siming

class FairFocusScheduler:
    """司命公平性调度器
    
    职责：根据 starvation_credit 调度角色，确保长期未出现的角色有机会。
    
    数据来源：通过 get_starvation_credit_for_siming() 接口读取群体模拟数据。
    """
    
    def calculate_priority(self, actor_id: str, b0_row: dict) -> float:
        """计算角色优先级"""
        starvation = get_starvation_credit_for_siming(actor_id, b0_row)
        # 其他计算逻辑...
        return starvation * 10.0
```

3. **添加测试**

```python
# backend/tests/test_fair_focus_isolation.py
def test_fair_focus_uses_interface():
    """测试 fair_focus 通过接口读取 starvation_credit"""
    b0_row = {"starvation_credit": 0.5, "fatigue": 0.3}
    
    credit = get_starvation_credit_for_siming("char_a", b0_row)
    assert credit == 0.5
    
    scheduler = FairFocusScheduler()
    priority = scheduler.calculate_priority("char_a", b0_row)
    assert priority == 5.0  # 0.5 * 10.0
```

#### 验收条件

- [ ] `hot_state.py` 添加 `get_starvation_credit_for_siming()` 接口
- [ ] `fair_focus.py` 改为调用接口而非直接访问 HOT_FIELDS
- [ ] 测试通过：接口隔离
- [ ] 后端回归通过

---

### P2.1：ESM 订阅验证

#### 目标

验证 ESM 确实订阅了 `siming.environment_request`。

#### 实施步骤

1. **grep 查找订阅**

```bash
grep -rn "siming.environment_request" backend/app/
```

2. **添加测试**

```python
# backend/tests/test_esm_siming_subscription.py
def test_esm_subscribes_to_siming_environment_request():
    """验证 ESM 订阅了 siming.environment_request"""
    from app.main import authority_event_bus
    
    subscribers = authority_event_bus.get_subscribers("siming.environment_request")
    assert len(subscribers) > 0
    assert any("esm" in str(sub).lower() for sub in subscribers)
```

#### 验收条件

- [ ] 确认 ESM 订阅了 `siming.environment_request`
- [ ] 测试通过：订阅验证

---

## 三、详细文档内容

### INPUT_CONTRACT.md

```markdown
# 司命输入契约

## FactType → 司命事件类型映射

### world_fact_event

- **FactType**: `FactType.WORLD_FACT`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "fact_id": str,
      "world_anchor_id": str,
      "state_key": str,
      "state_value": JsonValue,
      "authority_result_ref": str
  }
  ```
- **Impact**: 
  - `InMemorySimingStateTree` 更新世界状态
  - `SimingGlobalSituationLayer` 更新环境快照

### visual_fact_event

- **FactType**: `FactType.VISUAL_FACT`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "fact_id": str,
      "observer_actor_id": str,
      "observed_entity_id": str,
      "visibility_level": str
  }
  ```
- **Impact**:
  - `SimingNarrativeCore` 更新可见性图谱

### esm_result_event

- **FactType**: `FactType.ESM_RESULT`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "resolution_id": str,
      "result_type": str,
      "affected_entities": list[str]
  }
  ```
- **Impact**:
  - `InMemorySimingStateTree` 更新环境状态

### character_behavior_event

- **FactType**: `FactType.CHARACTER_BEHAVIOR`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "actor_id": str,
      "behavior_type": str,
      "target_entity_id": str | None
  }
  ```
- **Impact**:
  - `SimingNarrativeCore` 记录行为事件

### conversation_resolution_event

- **FactType**: `FactType.CONVERSATION_RESOLUTION`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "conversation_id": str,
      "participants": list[str],
      "outcome": str
  }
  ```
- **Impact**:
  - `SimingNarrativeCore` 更新对话链

### constraint_state_event

- **FactType**: `FactType.CONSTRAINT_STATE`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "constraint_id": str,
      "state": str,
      "affected_actors": list[str]
  }
  ```
- **Impact**:
  - `InMemorySimingStateTree` 更新约束状态

### population_cadence_event

- **FactType**: `FactType.POPULATION_CADENCE`
- **Subscriber**: `siming_observe.SimingObservePipeline`
- **Schema**:
  ```python
  {
      "tick": int,
      "updated_actors": list[str]
  }
  ```
- **Impact**:
  - 所有三套副本更新 tick

## 订阅机制

```python
# backend/app/main.py
for fact_type in [
    FactType.WORLD_FACT,
    FactType.VISUAL_FACT,
    FactType.ESM_RESULT,
    FactType.CHARACTER_BEHAVIOR,
    FactType.CONVERSATION_RESOLUTION,
    FactType.CONSTRAINT_STATE,
    FactType.POPULATION_CADENCE,
]:
    authority_event_bus.subscribe(
        fact_type.value,
        _project_to_heavenly_graph
    )
```
```

### STATE_MODEL.md

```markdown
# 司命状态模型

## 三套副本角色定义

### InMemorySimingStateTree

- **Role**: 计划/决策的 staging 区域
- **Authority**: `siming_orchestrator`
- **数据来源**: HeavenlyGraph 投影 + siming_data_layer 恢复
- **更新时机**: 每次观测到新事件
- **持久化**: 通过 siming_data_layer
- **Consistency Check**: 与 NarrativeCore 对账

**关键字段**：
- `actor_states: dict[str, ActorState]`
- `environment_states: dict[str, EnvironmentState]`
- `current_tick: int`

### SimingGlobalSituationLayer

- **Role**: 环境快照和上下文
- **Authority**: `siming_runtime`
- **数据来源**: HeavenlyGraph 投影 + siming_data_layer 恢复
- **更新时机**: 每次 tick
- **持久化**: 通过 siming_data_layer
- **Consistency Check**: tick 与 StateTree 对齐

**关键字段**：
- `current_situation: Situation`
- `recent_events: list[Event]`
- `current_tick: int`

### SimingNarrativeCore

- **Role**: 叙事事件追踪
- **Authority**: `siming_orchestrator`
- **数据来源**: HeavenlyGraph 投影 + siming_data_layer 恢复
- **更新时机**: 每次观测到角色行为/对话事件
- **持久化**: 通过 siming_data_layer
- **Consistency Check**: actor_ids 与 StateTree 一致

**关键字段**：
- `causal_chains: list[CausalChain]`
- `actor_timelines: dict[str, Timeline]`
- `current_tick: int`

## 一致性验证机制

```python
def validate_consistency(
    tree: InMemorySimingStateTree,
    global_situation: SimingGlobalSituationLayer,
    narrative: NarrativeCore
) -> list[StateInconsistency]:
    """验证三套副本一致性
    
    检查项：
    1. 同一 actor_id 在三套中的存在性一致
    2. tick 对齐
    3. 关键事件是否都被记录
    4. revision 是否漂移
    """
```

## 恢复流程

```
1. siming_runtime 启动
2. 从 siming_data_layer 读取最新快照
3. 恢复三套副本状态
4. 验证一致性
5. 继续运行
```
```

### OUTPUT_CONTRACT.md

```markdown
# 司命输出契约

## SimingOutput → AuthorityEvent 映射

### impulse

- **event_type**: `siming.impulse`
- **target_ids**: `[character_actor_id, frontend_projector]`
- **Subscriber**: CharacterAgentService, FrontendProjector
- **Schema**:
  ```python
  {
      "impulse_id": str,
      "target_actor_id": str,
      "impulse_type": str,  # "urgency" | "curiosity" | "social_pressure"
      "strength": float,
      "reason_tags": list[str]
  }
  ```

### opportunity

- **event_type**: `siming.opportunity`
- **target_ids**: `[character_actor_id, frontend_projector]`
- **Subscriber**: CharacterAgentService, FrontendProjector
- **Schema**:
  ```python
  {
      "opportunity_id": str,
      "target_actor_id": str,
      "opportunity_type": str,  # "confrontation" | "secret_reveal" | "solo"
      "window_start_tick": int,
      "window_end_tick": int,
      "reason_tags": list[str]
  }
  ```

### fact_reveal

- **event_type**: `siming.fact_reveal`
- **target_ids**: `[character_actor_id, frontend_projector]`
- **Subscriber**: CharacterAgentService, FrontendProjector
- **Schema**:
  ```python
  {
      "reveal_id": str,
      "target_actor_id": str,
      "fact_id": str,
      "reveal_method": str,  # "observation" | "conversation" | "inference"
      "reason_tags": list[str]
  }
  ```

### environment_change

- **event_type**: `siming.environment_request`
- **target_ids**: `[esm]`
- **Subscriber**: ESMService
- **Schema**:
  ```python
  {
      "request_id": str,
      "target_environment_id": str,
      "requested_change_type": str,  # "light_level_drop" | "temperature_change"
      "requested_strength": str,  # "weak" | "medium" | "strong"
      "reason_tags": list[str]
  }
  ```

### visual_observability_request

- **event_type**: `siming.visual_observability_request`
- **target_ids**: `[frontend_projector]`
- **Subscriber**: FrontendProjector
- **Schema**:
  ```python
  {
      "request_id": str,
      "observer_actor_id": str,
      "target_entity_id": str,
      "visibility_level": str,  # "fully_visible" | "partially_visible" | "hidden"
      "reason_tags": list[str]
  }
  ```

## 事件生命周期

```
1. SimingRuntime 产生 SimingOutput
2. SimingEventProducer 转换为 AuthorityEvent
3. authority_event_bus.publish()
4. 订阅者接收并处理
5. 订阅者产生 receipt
6. SimingRuntime 收到 receipt 确认
```
```

### PROJECTION_CONTRACT.md

```markdown
# 司命投影契约

## Owner Event → HeavenlyGraph Node 映射

### gameplay.inventory.*

- **Domain**: `inventory`
- **Subscription**: explicit (FactType.INVENTORY_*)
- **Revision**: `Owner.revision`（不混用 producer_ts）
- **Node Type**: `causal_event`

**示例**：
```python
{
    "node_id": "authority-projection:evt_12345",
    "node_type": "causal_event",
    "attributes": {
        "domain": "inventory",
        "event_type": "gameplay.inventory.item_acquired",
        "owner_ref": "inventory",
        "source_revision_vector": {"inventory": 42}
    }
}
```

### gameplay.survival.*

- **Domain**: `survival_body`
- **Subscription**: explicit (FactType.SURVIVAL_*)
- **Revision**: `Owner.revision`
- **Node Type**: `causal_event`

### esm_result_event

- **Domain**: `esm_world`
- **Subscription**: explicit (FactType.ESM_RESULT)
- **Revision**: `Owner.revision`
- **Node Type**: `causal_event`

### constraint_state_event

- **Domain**: `esm_world`
- **Subscription**: explicit (FactType.CONSTRAINT_STATE)
- **Revision**: `Owner.revision`
- **Node Type**: `causal_event`

## Revision 处理规则

**❌ 错误做法**（Phase 0 遗留）：
```python
source_revision = max(
    event.payload.get("global_sequence", event.producer_ts),
    event.producer_ts
)
```

**✅ 正确做法**（Q2 已修复）：
```python
source_vector = event.payload.get("source_revision_vector", {})
source_revision = max([
    event.payload.get("global_sequence", event.producer_ts),
    *[int(v) for v in source_vector.values() if isinstance(v, int)]
])
```

## 订阅机制

**Phase 0 遗留**：
```python
authority_event_bus.subscribe("*", _project_to_heavenly_graph)
```

**Phase 1 改进**（Q2 已修复）：
```python
for fact_type in FACT_TYPE_REGISTRY.get_all_types():
    authority_event_bus.subscribe(
        fact_type.value,
        _project_to_heavenly_graph
    )
```

## Phase 2 改进计划

- 图只存边（关系）
- 事实走 OwnerFactQuery
- 前置条件：OwnerFactQuery 接口落地
```

---

## 四、执行顺序

1. **P1.1：输入/输出契约文档**（最快，无代码改动）
   - 写四份文档
   - 验收：文档存在

2. **P0.1：三套状态副本对账机制**（核心）
   - 新建 `siming_consistency.py`
   - 集成到 `siming_runtime.py`
   - 写三个测试
   - 验收：全后端回归通过

3. **P0.2：siming_data_layer 定位明确**（文档 + 接口）
   - 写架构文档
   - 添加恢复接口（带 TODO）
   - 写测试
   - 验收：全后端回归通过

4. **P1.2：fair_focus 归属澄清**（接口隔离）
   - 添加 `get_starvation_credit_for_siming()` 接口
   - 改 `fair_focus.py` 调用接口
   - 写测试
   - 验收：全后端回归通过

5. **P2.1：ESM 订阅验证**（验证）
   - grep 查找
   - 写测试
   - 验收：订阅验证通过

---

## 五、验收标准

### 全部完成后

- [ ] 四份契约文档存在（INPUT_CONTRACT.md、STATE_MODEL.md、OUTPUT_CONTRACT.md、PROJECTION_CONTRACT.md）
- [ ] `siming_consistency.py` 存在并实现验证逻辑
- [ ] `siming_runtime.py` 每次 tick 后调用对账验证
- [ ] `siming_data_layer.py` 明确定位为"事实层"
- [ ] `fair_focus.py` 通过接口读取 `starvation_credit`
- [ ] ESM 确实订阅了 `siming.environment_request`
- [ ] 全后端回归通过：10074+ passed, 6 skipped, 2 xfailed
- [ ] 工作区干净，所有改动已提交

### 提交信息格式

```
fix(siming): P0.1 - 三套状态副本对账机制

新增 SimingConsistencyValidator，每次 tick 后验证 StateTree、GlobalSituation、
NarrativeCore 三套副本一致性。检查 actor 存在性、tick 对齐、事件记录一致性。

Co-Authored-By: Claude 5.5 <noreply@anthropic.com>
```

---

## 六、风险与限制

### 已知限制

1. **Godot 缺失**：广泛运行时验收无法完成，只能验证后端测试
2. **Phase 2 标记保留**：对账机制的事件溯源验证、siming_data_layer 恢复接口实现均推迟到 Phase 2
3. **Owner 依赖项推迟**：Q1/Q2/Q3 长期项不在本次范围

### 不改动项

- ❌ 不创建或修改 Owner
- ❌ 不改 B0 六个字段归属
- ❌ 不实现 OwnerFactQuery 接口
- ❌ 不改 revision 混推历史数据

---

**状态**：待实施  
**估计工作量**：1-2 天（4 份文档 + 3 个代码改动 + 测试）
