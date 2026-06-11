# 13-FACS-SACS Planner 规范

## 1. 定义

`FACS-SACS Planner` 是角色内部状态到具身语义表达单元的统一编排层。它决定角色“如何露出来”，而不是直接决定角色“如何动起来”。

## 2. 上下游边界

### 上游输入

- `Intent Packet`
- `Affect State`
- `Belief / Social Appraisal Summary`
- `Character Runtime State`
- `Character Profile Bias`
- `Contextual Constraint Hints`

### 下游输出

- `Expression Core State`
- `FACS Activation Set`
- `SACS Activation Set`
- `Coupling Policy`
- `Expression Meta Flags`

## 3. 核心内部模块

1. `Expression State Builder`
2. `Face Unit Selector`
3. `Body Unit Selector`
4. `Coupling Resolver`
5. `Leakage & Suppression Resolver`
6. `Output Packager`

## 4. 主动表达与自动泄露

Planner 必须同时处理：

- 主动表达
- 自动表达 / 泄露

并显式区分哪些单元来自角色主动表演，哪些来自角色无法完全压制的身体泄露。

## 5. 统一表达核

面部和身体必须共享同一个 `expression_core_state`，不能各自随机跑。

## 6. 玩家与 AI 共用

玩家角色与 AI 角色共用同一 Planner。差异只在上游 `intent_packet` 来源不同； affect、pressure、suppression 和 leakage 仍来自角色系统本身。

## 7. 与 Binder 的边界

Planner 负责选哪些 `FACS/SACS` 单元、给什么权重、采用什么耦合和泄露策略；Binder 负责把这些单元映射到 canonical 控制图并处理低层约束。

## 8. Phase 1 范围

Phase 1 最小支持：

- 输入统一表达核
- `FACS` 选择
- `SACS` 选择
- 耦合模式
- 压抑/泄露/失控判定
- 玩家与 AI 共用同一 Planner

## 9. 一句话收束

`FACS-SACS Planner` 是角色内部状态到具身语义表达单元的统一编排层，它决定角色如何露出来，而不是直接决定角色如何动起来。
