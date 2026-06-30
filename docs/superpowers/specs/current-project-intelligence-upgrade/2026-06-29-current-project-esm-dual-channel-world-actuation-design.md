# 当前项目 `ESM` 双通道世界作用层设计

- 日期：`2026-06-29`
- 状态：`awaiting-user-review`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

让当前 `ESM` 从“语义结算主导”升级为“双通道世界作用层”。

## 2. 当前现状

当前 `ESM` 主体上仍是：

- 交互请求
- 规则和约束检查
- 返回结算结果

适合：

- 调查
- 对话相关交互
- 轻环境变化

但不适合：

- 连续接触
- 真实抓取
- 物理推拉
- 连续身体对抗

## 3. 双通道定义

### A. `Semantic Interaction Channel`

继续保留。

适合：

- 对话
- 调查
- 轻交互
- 剧情触发
- 规则主导环境请求

### B. `Physical Interaction Channel`

新增。

适合：

- 推
- 拉
- 搬
- 抓
- 真实阻挡
- 连续接触
- 武器与身体对抗

## 4. 统一点

两条通道必须共享：

- 世界状态底座
- 结果协议
- 认知回流接口

也就是说，它们不是两个世界，只是两种作用世界的方式。

## 5. 结果协议

无论结果来自哪条通道，都必须最终能回流为统一结果对象族，例如：

- `world_result`
- `object_state_result`
- `environment_state_result`
- `body_state_result`
- `constraint_state_result`

## 6. 与交互编排层关系

`ESM` 不自己决定全部交互走哪条通道。

这件事由上层 `Interaction Orchestration Layer` 选择。

`ESM` 负责：

- 按被选中的作用通道执行世界作用
- 回流统一结果

## 7. 一句话收束

这份规格的目标，是保留当前 `ESM` 的稳定语义结算能力，同时为未来需要更真实具身交互的玩法打开物理作用通道。
