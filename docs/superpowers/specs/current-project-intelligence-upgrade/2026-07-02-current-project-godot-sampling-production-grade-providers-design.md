# 当前项目 Godot Sampling Production-Grade Providers 子规格

- 日期：`2026-07-02`
- 状态：`implemented-and-runtime-verified`
- 上位规格：[2026-06-29-current-project-godot-sampling-frontend-and-providers-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-godot-sampling-frontend-and-providers-design.md)

## 1. 目标

把已有 Godot sampling provider contract 和 L1 runtime capture refs 补全为 production-grade provider 体系。

## 2. Provider 范围

production-grade provider 至少包括：

- visual patch provider
- spatial patch provider
- auditory context provider
- embodied state provider
- skeletal state provider refs
- environment field refs

## 3. 生产级要求

每个 provider 必须具备：

- throttle policy
- artifact retention policy
- source ref stability
- failure status
- sample freshness
- redaction/privacy rule
- debug artifact option
- harness evidence output

## 4. Godot 边界

Godot 仍然只负责取样和本地表现。

禁止：

- 大模型推理
- 重体素化
- full-scene runtime rescan
- raw input 噪声直入 backend 业务层

## 5. PQF 接线

所有 provider 输出必须进入或可被组装进 `PerceptionQueryFrame`。

不能有 provider 直接写角色/司命 runtime。

## 6. Verification 要求

必须证明：

- 每类 provider 有真实 runtime sample 或可验证 stub artifact
- artifact refs 可被 backend PQF 消费
- 采样受 throttle 限制
- provider failure 可结构化表达
- 不执行 heavy inference/heavy voxelization/full rescan

## 7. 一句话收束

Godot production-grade sampling provider 体系把视觉、空间、听觉、身体和环境取样稳定化为可验证 refs，同时保持 Godot 不成为认知宿主。
