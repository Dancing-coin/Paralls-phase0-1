# 当前项目感知 capture 时钟契约设计

- 状态：`proposed`
- 日期：`2026-07-05`

## 1. 目标

为双感知链建立“绝对同拍”判定基础，避免只靠近似 `started_at/ended_at` 窗口判断输入是否属于同一感知时刻。

本设计要求：

- 明确 `capture_id` 与 `capture_root_id`
- 明确时钟来源
- 明确单调序列与墙钟的职责分离
- 明确 active perception、VLA slow path、recheck 的 capture 派生规则

## 2. 核心问题

当前代码只有：

- `TimeWindow.started_at`
- `TimeWindow.ended_at`
- `RawFactEvent.producer_ts`

这足以表达顺序，不足以表达：

- 是否是同一拍
- 是否来自同一世界 capture
- provider slow path 回填是否属于原拍还是新拍

## 3. 统一身份模型

建议引入三层身份：

1. `capture_root_id`
   - 一次共享世界采样窗口的根身份
   - 代表“同一世界状态采样时刻”

2. `capture_id`
   - 面向某一 consumer scope / actor projection 的输入身份
   - 可由 `capture_root_id + consumer_scope + subject_id` 派生

3. `sample_ref_id`
   - 单个 fact / provider sample 的局部身份

## 4. 时钟字段

建议统一字段：

```text
capture_root_id
capture_id
clock_domain
wall_clock_ts
monotonic_tick
source_frame_index
capture_started_at
capture_ended_at
```

### 4.1 字段职责

- `wall_clock_ts`
  - 用于证据、日志、外部对照
  - 不用于同拍判定

- `monotonic_tick`
  - 用于同拍与顺序判定
  - 必须来自同一单调时钟域

- `source_frame_index`
  - 用于 Godot 本地帧级对齐
  - 不能单独代替后端单调时钟

- `capture_started_at / capture_ended_at`
  - 用于时间窗边界
  - 但最终同拍判定必须依赖 `capture_root_id + monotonic_tick`

## 5. 同拍判定

必须同时满足：

1. 同一 `capture_root_id`
2. 同一 `clock_domain`
3. `monotonic_tick` 相等或处于同一允许窗口
4. 若为 actor 投影，则 `capture_id` 必须能回溯到同一 `capture_root_id`

禁止：

- 仅凭 `started_at/ended_at` 重叠就判定同拍
- 仅凭 wall clock 秒级时间相等就判定同拍

## 6. 派生规则

### 6.1 fact emitter

- 直接从当前 `capture_root_id` 派生自身 `sample_ref_id`
- fact payload 至少保留 `capture_root_id`

### 6.2 provider sample

- 从同一 `capture_root_id` 产出 `SampleInputRef`
- provider 自身不能擅自创建新的 root capture

### 6.3 active perception / recheck

- 若只是对原拍补充材料，必须保留 `capture_root_id`
- 若主体移动、视角改变、或窗口重开，则必须派生新的 `capture_root_id`

### 6.4 VLA slow path

- `VLAProviderRequest` 必须引用原 `capture_root_id`
- 若结果超时跨拍返回，只能作为“后补 advisory”，不得伪装成原拍主结果

## 7. 验证要求

至少要能证明：

- 两条链同拍时 `capture_root_id` 一致
- 不同拍 slow path advisory 不会伪装成原拍
- actor A/B 在同一 root capture 下有不同 `capture_id`
- 日志可回溯 `capture_root_id -> capture_id -> sample_ref_id`

## 8. 与后续专题的关系

本设计只定义“时间身份和时钟契约”。

它不替代：

- 对象锚点与指代统一
- 多角色私有视角 reconciliation
- bridge 接线与验证矩阵
