# 当前项目多角色私有视角分发与协调实施计划

- 状态：`proposed`
- 日期：`2026-07-05`

上位设计：

- [2026-07-05-current-project-multi-actor-private-perspective-reconciliation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-multi-actor-private-perspective-reconciliation-design.md)

## 1. 目标

把当前 bridge 从单 actor assembler 升级成共享 world capture 下的多 actor 私有视角分发器。

## 2. 实施范围

- `backend/app/world_runtime/l1_runtime_perception_bridge.py`
- `backend/app/world_runtime/l1_perception_frame.py`
- `backend/app/character_agent/reasoning/l1_perception.py`
- `backend/app/services/siming_global_situation.py`
- 验证脚本与 tests

## 3. 实施步骤

1. 定义 shared world capture 到 per-actor projection 的结构
2. 让 bridge 接收 capture root + actor projection 输入
3. 为每个 actor 组装独立 frame/bundle
4. 为 Siming 组装独立 multi-actor public patch 输入
5. 补多 actor focused verifier

## 4. 验收

- [ ] actor A/B 同拍私有 bundle 可同时构造
- [ ] actor A/B 拥有不同视角 ref
- [ ] actor A/B 可对同物产生不同感知属性但不混淆对象
- [ ] Siming 不读取 actor-private context
