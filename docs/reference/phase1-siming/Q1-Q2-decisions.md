# Q1/Q2 决策记录

**日期**：2026-11-08  
**状态**：已定  
**依据**：[05-Owner重构影响评估.md](../../11月份分析/Owner重构、司命与群体模拟底座适配/05-Owner重构影响评估.md)  
**上下文**：司命底座适配与 Owner 重构前置条件

---

## Q1.1：B0 六个字段的 Owner 归属

### 决策

**选 A：新建 `daily_rhythm_runtime` Owner**

### 六个字段

| 字段 | 当前语义 | 位置 |
|------|---------|------|
| `fatigue` | 疲劳度（0.0-1.0，每秒 +0.001） | `continuous.py:76` |
| `need_pressure` | 需求压力（每小时 +0.01） | `continuous.py:77-80` |
| `starvation_credit` | 饥饿积分（每天 +0.1） | `continuous.py:81-84` |
| `activity_phase` | 活动阶段枚举（早/午/晚/深夜） | `continuous.py:96` |
| `next_due_tick` | 下次到期 tick | `continuous.py:99` |
| `last_update_tick` | 上次更新 tick | `continuous.py:95` |

### 归属理由

1. **语义独立**：这六个字段是"日常节律"语义，不是"生存需求"（Survival 管饥饿/口渴/体温）
2. **避免大杂烩**：塞进 Survival 会让它变成"角色状态垃圾桶"
3. **可扩展**：未来昼夜循环、睡眠周期、生物钟都归这里

### 实施路径

1. 创建 `backend/app/gameplay/daily_rhythm_runtime.py`
2. 声明 FactType：
   - `fatigue_state`（pool 语义：0.0-1.0）
   - `need_pressure_state`（pool 语义）
   - `starvation_credit_state`（pool 语义）
   - `activity_phase_state`（状态机，见 Q1.2）
3. `hot_state.py:44` / `world.py:780` / `continuous.py` 改为读写 daily_rhythm 事件
4. B0 六个字段从私有槽位迁移到 Owner 事实

---

## Q1.2：`activity_phase` 升级为状态机

### 决策

**是** — 将 `activity_phase` 升级为正式状态机

### 当前问题

硬编码枚举（`continuous.py:24-30`）：
```python
def _phase_at(tick: int) -> str:
    hour = (tick // 3600) % 24
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"
```

无状态机基础设施，允许集合硬编码 4 处。

### 升级方案

1. 声明状态机 `machine_id: "daily_rhythm.activity_phase"`
2. 四个状态：`morning` / `afternoon` / `evening` / `night`
3. 迁移触发器：按 tick 计算（每 6 小时一次）
4. 替换 `continuous.py:24-30` 的硬编码函数为状态机查询

---

## Q2：Heavenly Graph 处置

### 决策

**A（短期）+ C（长期路线图）**

### 短期方案（Phase 0-1）

**改为 FactType 订阅**（最小改动）：

1. 把 `main.py:2233` 的 `"*"` 通配改为按 FactType 枚举订阅
2. `authority_graph_projector.py:22-32` 的字符串前缀表改为 FactType 声明表
3. revision 改读真 Owner revision，不再混推 `max(payload_revision, producer_ts)`

**保留现状**：
- 司命保留独立图索引
- 图能力不削弱（"谁影响了谁"查询）
- revision 对账留 TODO

### 长期路线图（Phase 2+）

**迁移到混合架构**：

1. **图只存边**（关系）：
   - "角色 A 在 房间 R"
   - "物品 I 被 角色 A 持有"
   - "事件 E1 导致 E2"（因果链）
   
2. **事实走 OwnerFactQuery**：
   - 不存事实副本（物品属性、角色状态）
   - 单一真相原则
   
3. **前置条件**：
   - OwnerFactQuery 接口已落地
   - 图 schema 重设计
   - 司命查询逻辑全部改写

### 不选方案 B（砍掉图）

理由：
- 司命"上帝视角"的核心是快速看清全局关系
- 单点 Query 做不到传递关系查询
- 图能力对司命战略价值高

---

## 影响评估

| 决策 | 解锁项 | 阻塞项 |
|------|--------|--------|
| Q1.1（新建 daily_rhythm） | 解锁 Owner 重构阶段 0 | 需先实现 daily_rhythm_runtime |
| Q1.2（状态机升级） | activity_phase 不再是硬编码特例 | 需声明状态机 |
| Q2（短期 A） | 收口第二真相（前缀表→契约） | Phase 2 仍需改混合架构 |

---

## 验收条件

### Q1 完成

1. `backend/app/gameplay/daily_rhythm_runtime.py` 存在
2. 六个字段全部有对应 FactType 声明
3. `hot_state.py` 的 `HOT_FIELDS` 常量标记为"过渡期兼容"
4. `continuous.py` 的计算逻辑迁移到 daily_rhythm 事件处理
5. 状态机 `daily_rhythm.activity_phase` 可查询

### Q2 短期完成

1. `main.py:2233` 的 `"*"` 订阅改为 FactType 枚举
2. `authority_graph_projector.py:22-32` 前缀表换成契约声明
3. revision 读取逻辑改为真 Owner revision
4. 测试通过：司命仍能查询全局关系

---

## 关联文档

- [05-Owner重构影响评估.md](../../11月份分析/Owner重构、司命与群体模拟底座适配/05-Owner重构影响评估.md)
- [08-司命与角色智能体协作协议.md](08-司命与角色智能体协作协议.md)
- [09-司命与ESM协作协议.md](09-司命与ESM协作协议.md)
- [11-司命与视觉事实系统协作协议.md](11-司命与视觉事实系统协作协议.md)
