# 任务：司命非 Owner 缺陷补齐

## 背景

**仓库**：`D:\Paralls-phase0-1`  
**分支**：`main`  
**参考文档**：`docs/superpowers/plans/2026-11-16-siming-defect-repairs.md`  
**约束**：**不改 Owner 设计，只改司命代码；Q1/Q2/Q3 长期项已推迟到 Phase 2**

## 当前状态

- S2-S8 断点已全部修复（commit 0fbc1493）
- Q2 短期改进已完成（FactType 显式订阅）
- 全后端：10074 passed, 6 skipped, 2 xfailed
- 工作区干净，已提交，未推送

## 待处理缺陷（按优先级）

### 🔴 P0：核心架构缺陷

#### P0.1：三套状态副本无对账机制

**问题**：`InMemorySimingStateTree`、`GlobalSituationLayer`、`NarrativeCore` 三套副本独立更新，无一致性验证。

**后果**：版本漂移、恢复失败、调试困难。

**实施**：
1. 新建 `backend/app/services/siming_consistency.py`
2. 实现 `SimingConsistencyValidator` 类
3. 在 `siming_runtime.py` 集成 `_post_tick_validation()`
4. 添加三个测试：actor 缺失、tick 不对齐、完全一致

**验收**：
- [ ] `siming_consistency.py` 存在
- [ ] `siming_runtime.py` 每次 tick 后调用验证
- [ ] 测试通过
- [ ] 全后端回归通过

#### P0.2：siming_data_layer 定位模糊

**问题**：建了 6 个表但与三套副本关系不清。

**实施**：
1. 新建 `docs/reference/phase1-siming/siming-data-layer-role.md`
2. 在 `siming_data_layer.py` 添加三个恢复接口（带 TODO: Phase 2）
3. 添加测试：持久化和加载

**验收**：
- [ ] 架构文档存在
- [ ] 恢复接口添加
- [ ] 测试通过

---

### 🟡 P1：文档与接口债务

#### P1.1：输入/输出契约文档缺失

**实施**：在 `docs/reference/phase1-siming/` 下创建四份文档：
- `INPUT_CONTRACT.md`：FactType → 司命事件类型映射
- `STATE_MODEL.md`：三套副本角色定义
- `OUTPUT_CONTRACT.md`：SimingOutput → AuthorityEvent 映射
- `PROJECTION_CONTRACT.md`：Owner Event → HeavenlyGraph Node 映射

**内容模板见实施文档第三节**。

**验收**：
- [ ] 四份文档存在
- [ ] 内容完整，包含 schema 和订阅者

#### P1.2：fair_focus 归属澄清

**问题**：司命模块依赖群体模拟内部数据（HOT_FIELDS）。

**实施**：
1. 在 `hot_state.py` 添加 `get_starvation_credit_for_siming()` 接口
2. 改 `fair_focus.py` 调用接口而非直接访问 HOT_FIELDS
3. 添加测试：接口隔离

**验收**：
- [ ] 接口添加
- [ ] `fair_focus.py` 改为调用接口
- [ ] 测试通过

---

### 🟢 P2：验证与澄清

#### P2.1：ESM 订阅验证

**实施**：
1. `grep -rn "siming.environment_request" backend/app/`
2. 添加测试验证 ESM 订阅

**验收**：
- [ ] 确认 ESM 订阅了 `siming.environment_request`
- [ ] 测试通过

---

## 实施顺序

**按优先级依次处理**：

1. **P1.1：输入/输出契约文档**（最快，无代码改动）
2. **P0.1：三套状态副本对账机制**（核心）
3. **P0.2：siming_data_layer 定位明确**（文档 + 接口）
4. **P1.2：fair_focus 归属澄清**（接口隔离）
5. **P2.1：ESM 订阅验证**（验证）

---

## 详细实施方案

### P0.1 代码模板（三套副本对账）

```python
# backend/app/services/siming_consistency.py
from dataclasses import dataclass

@dataclass
class StateInconsistency:
    category: str  # "actor_state" | "tick_mismatch" | "event_missing"
    entity_id: str
    detail: str

class SimingConsistencyValidator:
    """司命三套状态副本一致性验证器"""
    
    def validate(
        self,
        tree: InMemorySimingStateTree,
        global_situation: GlobalSituationLayer,
        narrative: NarrativeCore,
        *,
        current_tick: int
    ) -> list[StateInconsistency]:
        """验证三套副本一致性，返回不一致项列表"""
        inconsistencies = []
        
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
        
        return inconsistencies
    
    def is_consistent(
        self,
        tree: InMemorySimingStateTree,
        global_situation: GlobalSituationLayer,
        narrative: NarrativeCore,
        *,
        current_tick: int
    ) -> bool:
        return len(self.validate(tree, global_situation, narrative, current_tick=current_tick)) == 0
```

**集成到 siming_runtime.py**：
```python
# 在 SimingRuntime.__init__() 添加
self._consistency_validator = SimingConsistencyValidator()

# 在每次 tick 后验证
def _post_tick_validation(self, current_tick: int) -> None:
    inconsistencies = self._consistency_validator.validate(
        self._state_tree,
        self._global_situation,
        self._narrative_core,
        current_tick=current_tick
    )
    
    if inconsistencies:
        for inc in inconsistencies:
            self._audit_writer.log_consistency_warning(
                category=inc.category,
                entity_id=inc.entity_id,
                detail=inc.detail,
                tick=current_tick
            )
        
        if any(inc.category in {"actor_state", "tick_mismatch"} for inc in inconsistencies):
            raise SimingConsistencyError(f"Critical state inconsistency: {inconsistencies}")
```

**测试**：
```python
# backend/tests/test_siming_consistency.py
def test_actor_missing_in_global_situation():
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

def test_tick_mismatch():
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

def test_all_consistent():
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

---

### P1.2 代码模板（fair_focus 接口隔离）

```python
# backend/app/population_continuity/hot_state.py
def get_starvation_credit_for_siming(actor_id: str, b0_row: dict) -> float:
    """司命调度接口：读取角色饥饿积分
    
    接口隔离：fair_focus 通过此接口读取，而非直接访问 HOT_FIELDS。
    """
    return b0_row.get("starvation_credit", 0.0)
```

```python
# backend/app/population_continuity/fair_focus.py
from app.population_continuity.hot_state import get_starvation_credit_for_siming

class FairFocusScheduler:
    """司命公平性调度器
    
    职责：根据 starvation_credit 调度角色。
    数据来源：通过 get_starvation_credit_for_siming() 接口读取。
    """
    
    def calculate_priority(self, actor_id: str, b0_row: dict) -> float:
        starvation = get_starvation_credit_for_siming(actor_id, b0_row)
        return starvation * 10.0
```

**测试**：
```python
# backend/tests/test_fair_focus_isolation.py
def test_fair_focus_uses_interface():
    b0_row = {"starvation_credit": 0.5, "fatigue": 0.3}
    
    credit = get_starvation_credit_for_siming("char_a", b0_row)
    assert credit == 0.5
    
    scheduler = FairFocusScheduler()
    priority = scheduler.calculate_priority("char_a", b0_row)
    assert priority == 5.0  # 0.5 * 10.0
```

---

## 四份契约文档内容

详见实施文档 `docs/superpowers/plans/2026-11-16-siming-defect-repairs.md` 第三节，包含：
- INPUT_CONTRACT.md：FactType → 司命事件类型映射
- STATE_MODEL.md：三套副本角色定义
- OUTPUT_CONTRACT.md：SimingOutput → AuthorityEvent 映射
- PROJECTION_CONTRACT.md：Owner Event → HeavenlyGraph Node 映射

每份文档包含完整 schema、订阅者、数据流向说明。

---

## 验收标准

### 全部完成后

- [ ] 四份契约文档存在
- [ ] `siming_consistency.py` 存在并实现验证逻辑
- [ ] `siming_runtime.py` 每次 tick 后调用对账验证
- [ ] `siming_data_layer.py` 明确定位为"事实层"
- [ ] `fair_focus.py` 通过接口读取 `starvation_credit`
- [ ] ESM 确实订阅了 `siming.environment_request`
- [ ] 全后端回归通过：10074+ passed, 6 skipped, 2 xfailed
- [ ] 工作区干净，所有改动已提交

### 每项提交信息格式

```
fix(siming): P0.1 - 三套状态副本对账机制

新增 SimingConsistencyValidator，每次 tick 后验证 StateTree、GlobalSituation、
NarrativeCore 三套副本一致性。检查 actor 存在性、tick 对齐、事件记录一致性。

Co-Authored-By: Claude 5.5 <noreply@anthropic.com>
```

---

## 重要约束

### 不改动项

- ❌ **不创建或修改 Owner**
- ❌ **不改 B0 六个字段归属**
- ❌ **不实现 OwnerFactQuery 接口**
- ❌ **不改 revision 混推历史数据**

### Phase 2 标记

对账机制的事件溯源验证、siming_data_layer 恢复接口实现均保留 `TODO: Phase 2` 标记。

---

## 参考命令

```bash
# 确认当前分支
git branch --show-current  # 应为 main

# 搜索现有实现
grep -rn "InMemorySimingStateTree\|GlobalSituationLayer\|NarrativeCore" backend/app/services/

# 运行全后端测试
python -m pytest backend/tests/ -q --tb=no -p no:cacheprovider

# 运行聚焦测试
python -m pytest backend/tests/test_siming_consistency.py -v

# 提交格式
git add .
git commit -m "fix(siming): P0.1 - 三套状态副本对账机制

新增 SimingConsistencyValidator，每次 tick 后验证三套副本一致性。

Co-Authored-By: Claude 5.5 <noreply@anthropic.com>"
```

---

## 已知风险

1. **Godot 路径已确认**：`D:\godot\Godot_v4.6.3-stable_win64_console.exe`，需显式传入验证命令。本轮实际广泛验收限制见实施计划末尾记录。
2. **三套副本实际类名可能不同**：需先 grep 确认真实类名
3. **集成点可能需要调整**：如果 `siming_runtime.py` 没有明确的 tick 后钩子，需要找到合适的集成点

---

## 执行建议

1. **先做 P1.1（文档）**：最快，无代码改动，建立全局理解
2. **再做 P0.1（对账）**：核心架构改进，需要仔细阅读现有代码
3. **然后 P0.2/P1.2/P2.1**：逐项完成，每项提交后回归

预计工作量：1-2 天（4 份文档 + 3 个代码改动 + 测试）

---

**准备就绪，可以开始实施。**
