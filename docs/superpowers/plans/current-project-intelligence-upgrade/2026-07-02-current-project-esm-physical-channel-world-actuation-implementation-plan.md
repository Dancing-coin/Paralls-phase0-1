# 当前项目 ESM Physical Channel World Actuation 实施计划

> 对应规格：
> [2026-07-02-current-project-esm-physical-channel-world-actuation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-design.md)

**状态：** `planned`

**目标：** 在现有 ESM 语义结算和统一结果协议之上，补齐 physical interaction channel、连续接触、推拉/携带和 mixed result 回流。

## 阶段 A：Physical Channel 协议

目标文件建议：

- `backend/app/services/physical_interaction_channel.py`
- `backend/tests/test_esm_physical_channel_runtime.py`

任务：

- [ ] 定义 physical request/result
- [ ] 定义 contact/push/pull/carry/blocking effect kinds
- [ ] 定义 constraint gate
- [ ] 映射统一 result family

## 阶段 B：Godot Adapter

目标文件建议：

- `scripts/interaction/PhysicalInteractionProbe.gd`
- `scripts/interaction/PhysicalInteractionAdapter.gd`

任务：

- [ ] 采样 contact/body/object refs
- [ ] 输出结构化 physical effect refs
- [ ] 禁止 raw physics stream 直入业务层

## 阶段 C：Mixed Merge

任务：

- [ ] 接入 Interaction Orchestration Service
- [ ] semantic approves goal/constraint
- [ ] physical reports effect
- [ ] merge 为统一 result
- [ ] failed constraint prevents effect application

## 阶段 D：Verification

目标文件建议：

- `scripts/verification/verify_esm_physical_channel_runtime.py`
- `.harness/profiles/esm-physical-channel-world-actuation.json`

验证命令：

```bash
python -m pytest -q backend/tests/test_esm_physical_channel_runtime.py
python scripts/verification/verify_esm_physical_channel_runtime.py
python scripts/verification/harness.py --profile esm-physical-channel-world-actuation
```

## 完成定义

完成后应能说：

> ESM 双通道已具备 physical world-actuation path，连续物理作用通过受控 adapter 和统一结果协议回流，不绕过 semantic authority。
