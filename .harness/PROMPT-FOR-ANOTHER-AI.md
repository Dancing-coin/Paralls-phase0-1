# AI 执行提示词：司命长期改造方案实施

## 一、任务概述

你需要按照 `.harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md` 文档实施司命（Siming）的长期架构改造。这是一个多阶段的重构任务，涉及 Owner 系统、FactType 基础设施和 Heavenly Graph 的架构升级。

**关键约束**：
- 必须保持全量回归测试通过（2552+ passed）
- 不得改变现有 Owner 设计的核心契约
- 每个阶段完成后提交，带 Co-Authored-By 署名
- 遵循 ponytail 原则：最小可行改动

---

## 二、执行步骤

### Phase 0：Q1 daily_rhythm_runtime（优先级 P0）

**目标**：创建 `daily_rhythm_runtime` Owner，解决 6 个 HOT_FIELDS 的归属问题。

**执行指令**：

```
我需要实施司命 Q1 长期方案：创建 daily_rhythm_runtime Owner。

请按照 .harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md 第三章的步骤：

1. 创建 backend/app/gameplay/daily_rhythm_runtime.py
   - 参考 backend/app/gameplay/survival_runtime.py 的结构
   - 声明 4 个 FactType：fatigue_state, need_pressure_state, starvation_credit_state, activity_phase_state
   - 注册对应的事件 schema

2. 迁移 backend/app/population_continuity/continuous.py 的计算逻辑
   - 将直接写 HOT_FIELDS dict 改为发送 daily_rhythm 事件
   - 保持原有计算逻辑不变
   - 通过 Authority EventBus 发送事件

3. 迁移 backend/app/population_continuity/hot_state.py 的读写逻辑
   - 从 Owner 读取字段（如果 OwnerFactQuery 接口存在）
   - 或标记为"待 OwnerFactQuery 接口落地后迁移"

4. 迁移 backend/app/population_continuity/world.py 的初始化逻辑
   - 发送 daily_rhythm.initialized 事件

5. 更新 backend/app/population_continuity/fair_focus.py
   - 从 daily_rhythm Owner 查询 starvation_credit

6. 实施 Q1.2：将 activity_phase 升级为状态机
   - 声明状态机 machine_id: "daily_rhythm.activity_phase"
   - 四个状态：morning/afternoon/evening/night
   - 替换 continuous.py:24-30 的硬编码函数

7. 验收：
   - python -m pytest backend/tests/ -q --tb=no（全量回归通过）
   - python -m pytest backend/tests/test_daily_rhythm_runtime.py -xvs（如果有专项测试）

注意：
- 如果当前仓库没有 FactType 基础设施，先搭建 stub（临时方案）
- 如果 OwnerFactQuery 接口不存在，保留事件发送逻辑，但读取仍走原路径
- 每个文件改完立即测试，不要积压
- 提交信息格式：feat(gameplay): create daily_rhythm_runtime Owner for Q1\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

执行完毕后告诉我：Phase 0 完成，HOT_FIELDS 已迁移到 daily_rhythm_runtime Owner。
```

---

### Phase 1：S2/S3 FactType 枚举订阅（优先级 P1）

**前置条件**：Phase 0 完成，且 FactType 基础设施已就绪

**执行指令**：

```
实施司命 S2/S3 长期方案：FactType 枚举订阅改造。

请按照 .harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md 第五章的步骤：

1. 改造 backend/app/main.py:2233
   - 将 authority_event_bus.subscribe("*", ...) 改为 FactType 枚举订阅
   - 列出司命关心的所有 FactType（包括 gameplay.* domain）

2. 改造 backend/app/services/authority_graph_projector.py
   - 删除 DOMAIN_BY_EVENT_PREFIX 字符串前缀表
   - 改为 FactType.from_event_type() + get_domain_for_fact_type()

3. 改造 backend/app/services/siming_observe.py
   - 将 ALLOWED_EVENT_TYPES 字符串白名单改为 FactType 枚举
   - 使用 FactType.from_event_type() 进行过滤

4. 添加启动验证
   - 检查所有订阅的 FactType 都在 registry 中
   - 检查 242 个 gameplay 事件都有对应 FactType 声明

5. 验收：
   - python -m pytest backend/tests/ -q --tb=no（全量回归通过）
   - python -m pytest backend/tests/test_siming_observe_state_tree.py -xvs
   - python -m pytest backend/tests/ -k "heavenly_graph" -xvs

注意：
- 如果 FactType 基础设施不完整，先按 domain 分批迁移（inventory → organization → ...）
- 每个 domain 迁移后立即测试
- 提交信息格式：refactor(siming): replace string subscriptions with FactType enum (S2/S3)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

执行完毕后告诉我：Phase 1 完成，S2/S3 已改为 FactType 枚举订阅。
```

---

### Phase 2：Q2-C 图只存边（优先级 P1，需 OwnerFactQuery）

**前置条件**：Phase 0/1 完成，且 OwnerFactQuery 接口已落地

**执行指令**：

```
实施司命 Q2-C 长期方案：图只存边 + OwnerFactQuery。

请按照 .harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md 第四章的步骤：

1. 重设计 Heavenly Graph schema
   - 修改 app/models/siming_heavenly_graph.py 的 HeavenlyGraphNode
   - 删除 attributes 字段
   - 增加 fact_type_ref, entity_id, revision 字段

2. 改造 backend/app/services/authority_graph_projector.py
   - 将存事实副本改为只存引用
   - node.attributes 改为 node.fact_type_ref / entity_id / revision

3. 改造 backend/app/services/siming_fact_core.py
   - 从图节点读 attributes 改为通过 OwnerFactQuery 读取
   - get_world_fact() 改为 owner_fact_query.query(fact_type, entity_id, revision)

4. 改造 backend/app/models/siming_heavenly_memory.py（S5）
   - WorldFactMemoryEntry 增加 fact_type_ref, entity_id, revision 字段
   - state_key/state_value 保留用于缓存

5. 添加 revision 对账测试
   - 每次图查询都验证 revision 是否匹配 Owner
   - 参考 backend/tests/test_pinned_revisions_validation_q3.py

6. 验收：
   - python -m pytest backend/tests/ -q --tb=no（全量回归通过）
   - python -m pytest backend/tests/ -k "heavenly" -xvs
   - python -m pytest backend/tests/test_siming_fact_core.py -xvs

注意：
- 这是 Phase 2+ 的大型改造，需要 OwnerFactQuery 接口完整可用
- 如果接口不存在，等 Owner 重构完成后再执行
- 提交信息格式：refactor(siming): graph stores edges only, facts via OwnerFactQuery (Q2-C)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

执行完毕后告诉我：Phase 2 完成，Q2-C 图只存边改造完成。
```

---

### Phase 3：S4/S5/S6 剩余断点（优先级 P2）

**执行指令**：

```
实施司命 S4/S6 长期方案。

请按照 .harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md 第六章的步骤：

1. S4：改造 backend/app/services/heavenly_graph_semantics.py
   - HeavenlyNodeTypeRegistry.DEFAULT_RULES 改为从 FactType metadata 派生
   - rule_for(fact_type: FactType) -> _NodeRule

2. S6：改造 backend/app/services/siming_policy.py
   - 扩展资格判定到 environment_id 和 object_id
   - 增加统一 entity eligibility registry

3. 验收：
   - python -m pytest backend/tests/ -q --tb=no（全量回归通过）
   - python -m pytest backend/tests/test_siming_activation_policy.py -xvs

注意：
- S5 已在 Phase 2 完成（WorldFactMemoryEntry 增加 fact_type_ref）
- 提交信息格式：refactor(siming): declarative node type rules and unified entity eligibility (S4/S6)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

执行完毕后告诉我：Phase 3 完成，S4/S6 改造完成。
```

---

## 三、关键注意事项

### 3.1 FactType 基础设施缺失的处理

如果当前仓库没有 `app/models/fact_type.py`，你需要先创建 stub：

```python
# backend/app/models/fact_type.py
from enum import Enum

class FactType(str, Enum):
    WORLD_FACT = "world_fact_event"
    VISUAL_FACT = "visual_fact_event"
    ESM_RESULT = "esm_result_event"
    CHARACTER_BEHAVIOR = "character_behavior_event"
    CONVERSATION_RESOLUTION = "conversation_resolution_event"
    CONSTRAINT_STATE = "constraint_state_event"
    POPULATION_CADENCE = "population_cadence_event"
    
    # gameplay domain（242 个事件需逐步补充）
    GAMEPLAY_INVENTORY_ITEM_ACQUIRED = "gameplay.inventory.item_acquired"
    # ...
    
    @classmethod
    def from_event_type(cls, event_type: str) -> "FactType | None":
        try:
            return cls(event_type)
        except ValueError:
            return None
    
    def to_event_type(self) -> str:
        return self.value

def get_domain_for_fact_type(fact_type: FactType) -> str:
    """FactType → domain 映射"""
    DOMAIN_MAPPING = {
        FactType.WORLD_FACT: "world",
        FactType.VISUAL_FACT: "visual",
        FactType.ESM_RESULT: "esm_world",
        # ...
    }
    return DOMAIN_MAPPING.get(fact_type, "unknown")
```

**标记为临时方案**，等 Owner 重构提供统一 FactType registry 后替换。

### 3.2 OwnerFactQuery 接口缺失的处理

如果当前仓库没有 OwnerFactQuery 接口，Phase 2 **必须等待**，不要强行实施。

在此之前：
1. Phase 0（Q1）可以先发送事件，但读取仍走原路径
2. Phase 1（S2/S3）可以用 FactType enum，但图仍存事实副本
3. Phase 2（Q2-C）等 Owner 重构完成后再执行

### 3.3 回归测试验证

**每个 Phase 完成后必须验证**：

```bash
# 全量回归
python -m pytest backend/tests/ -q --tb=no -p no:cacheprovider

# 司命专项测试
python -m pytest backend/tests/ -k siming -xvs

# 特定模块测试
python -m pytest backend/tests/test_daily_rhythm_runtime.py -xvs
python -m pytest backend/tests/test_siming_observe_state_tree.py -xvs
python -m pytest backend/tests/test_siming_fact_core.py -xvs
```

如果有测试失败，**必须修复后再继续下一个 Phase**。

### 3.4 Git 提交规范

**每个 Phase 提交一次**，格式：

```
<type>(scope): <subject>

<body>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

示例：

```
feat(gameplay): create daily_rhythm_runtime Owner for Q1

- 创建 daily_rhythm_runtime.py，声明 4 个 FactType
- 迁移 continuous.py 计算逻辑为事件发送
- 迁移 hot_state.py 读写逻辑
- 迁移 world.py 初始化逻辑
- 更新 fair_focus.py 为 Owner 查询
- activity_phase 升级为状态机

验收：全量回归 2552 passed

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

## 四、问题诊断与应对

### 4.1 如果测试失败

1. **先读错误信息**：`python -m pytest <失败测试> -xvs`
2. **检查是否是 import 错误**：新文件的 import 路径是否正确
3. **检查是否是 schema 不匹配**：FactType schema 与事件 payload 是否一致
4. **检查是否是 revision 冲突**：Owner revision 是否与图节点一致

### 4.2 如果遇到架构限制

**例如**：OwnerFactQuery 接口不存在，无法实施 Phase 2

**应对**：
1. 在文档中标记："Phase 2 blocked: OwnerFactQuery 接口缺失"
2. 先实施 Phase 0/1，提交后停止
3. 等 Owner 重构完成后再继续

### 4.3 如果需要修改方案

**例如**：发现原方案有逻辑漏洞

**应对**：
1. 在 `.harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md` 文档中补充"修正案"章节
2. 说明原方案的问题、修正方案、影响范围
3. 提交修正后的代码

---

## 五、执行完成后的交付物

完成所有 Phase 后，你需要提供：

1. **提交记录**：`git log --oneline -10`
2. **回归测试结果**：`python -m pytest backend/tests/ -q --tb=no` 的输出
3. **改造总结**：
   - Phase 0：Q1 daily_rhythm_runtime 创建完成，HOT_FIELDS 已迁移
   - Phase 1：S2/S3 FactType 枚举订阅完成，字符串白名单已废弃
   - Phase 2：Q2-C 图只存边完成，事实走 OwnerFactQuery
   - Phase 3：S4/S6 完成，剩余断点已修复
4. **未完成项**（如果有）：哪些 Phase 因前置条件不满足而跳过

---

## 六、快速开始（推荐执行顺序）

```bash
# 1. 克隆仓库（或确认工作目录）
cd D:/Paralls-phase0-1

# 2. 检查当前分支和提交
git log --oneline -5

# 3. 读取改造方案
Read .harness/SIMING-LONG-TERM-IMPLEMENTATION-PLAN.md

# 4. 开始 Phase 0（执行上述 Phase 0 的提示词）
# 然后逐步执行 Phase 1/2/3
```

---

**开始执行！按 Phase 顺序逐个实施，每个 Phase 完成后告诉我进度。**
