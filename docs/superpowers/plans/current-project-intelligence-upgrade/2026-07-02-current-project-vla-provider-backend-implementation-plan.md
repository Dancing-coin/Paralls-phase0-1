# 当前项目 VLA Provider Backend 实施计划

> 对应规格：
> [2026-07-02-current-project-vla-provider-backend-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-vla-provider-backend-design.md)

**状态：** `planned`

**目标：** 在不新增 `VLA Runtime`、不重定义 `L1`、不改写 ESM authority 的前提下，把开源多模态/VLA 能力接为现有多模态慢通路的 provider backend，并让结果以 advisory 形式进入统一感知协议。

## 0. 边界

本计划允许：

- 新增 VLA provider request/result 协议
- 新增 provider adapter / scheduler / cache / trace 的 backend 模块
- 使用 mock provider 建立第一版可验证链路
- 后续替换为本地或服务化开源 VLM / spatial model backend
- 把结果转换为 `ModalityInterpretationResult`、`CrossModalUnderstandingResult` 和 percept bundle

本计划禁止：

- 新增产品级 `VLA Runtime`
- 新增产品级 `L1 Runtime`
- 让 VLA 写 world truth
- 让 VLA 接管角色动作控制
- 让 VLA 接管司命主循环
- 让 Godot 跑大模型推理
- 让角色和司命共享私有 cache、hidden state 或推理历史
- 直接接入 robotics VLA action head 控制世界

## 1. 前置事实

- `L1` 已按 runtime-facing world fact subsystem 标准补全并验证。
- Godot runtime 已能产出 `PerceptionQueryFrame` 所需的 provider refs。
- `L1RuntimePerceptionBridge` 已把 projected facts/provider refs 组装为角色和司命可消费的 percept bundle。
- 旧 VLA plan 只完成 contract/design/focused proof，未接入真实 VLA provider。

## 2. 阶段 A：协议补强

目标文件建议：

- `backend/app/world_runtime/intelligence_upgrade.py`
- `backend/tests/test_vla_provider_backend_contract.py`

任务：

- [ ] 定义 `VLAProviderRequest`
- [ ] 定义 `VLAProviderResult`
- [ ] 定义 `VLAProviderStatus`
- [ ] 定义 advisory、TTL、conflict、missing input、trace ref 字段
- [ ] 建立 request 从 `PerceptionQueryFrame` 继承 context/cache namespace 的规则
- [ ] 建立 result 不可表达 authority decision 的校验

验收：

- schema 禁止 shared context/cache
- schema 要求 `advisory = true`
- schema 能表达 timeout、artifact missing、low confidence、conflict with L1

## 3. 阶段 B：Provider Adapter 骨架

目标文件建议：

- `backend/app/world_runtime/vla_provider.py`
- `backend/tests/test_vla_provider_backend_adapter.py`

任务：

- [ ] 定义 provider protocol
- [ ] 实现 deterministic/mock provider
- [ ] 实现 request artifact refs 读取边界，不直接读取 Godot scene
- [ ] 实现 result schema validation
- [ ] 记录 provider id、model id、model version、schema version

验收：

- mock provider 能返回结构化 spatial findings
- provider result 可稳定转换为 `ModalityInterpretationResult(visual_spatial)`
- provider 不持久化跨主体 hidden state

## 4. 阶段 C：开源模型后端选择门

目标文件建议：

- `docs/superpowers/plans/current-project-intelligence-upgrade/vla-provider-model-selection.md`
- `backend/app/world_runtime/vla_model_registry.py`

任务：

- [ ] 建立候选 backend 清单
- [ ] 记录 license、部署方式、硬件预算、结构化输出能力
- [ ] 第一阶段优先评估 VLM / grounding model
- [ ] depth model 只作为辅助，不替代 L1 occupancy
- [ ] robotics VLA action head 标记为 forbidden for runtime control

候选方向：

- open-source VLM / grounding model
- depth estimation model
- visual-spatial structured output model
- OpenVLA 类 robotics VLA 仅作研究或后续 adapter 候选

验收：

- 每个候选 backend 都有 license 和 runtime boundary 结论
- 没有任何候选被允许直接写 authority 或控制 actor

## 5. 阶段 D：Slow Path Scheduler

目标文件建议：

- `backend/app/world_runtime/vla_slow_path_scheduler.py`
- `backend/tests/test_vla_slow_path_scheduler.py`

任务：

- [ ] 建立 per-owner queue
- [ ] 分离 character queue 与 siming queue
- [ ] 支持 priority、timeout、max queue size
- [ ] 支持 artifact fingerprint 去重
- [ ] 支持 stale request discard
- [ ] 支持 fallback to structured facts
- [ ] 保证 result 只影响 next tick 或后续 bundle

触发条件：

- high ambiguity
- cross modal conflict
- low confidence global situation
- expected target missing
- expected reachable but failed
- LOS conflict
- active perception request

验收：

- timeout 不阻塞当前 runtime tick
- queue 满时可记录 drop/degrade trace
- 同一 owner 的重复请求可去重
- character/siming queue 不共享上下文

## 6. 阶段 E：Cache 与隔离

目标文件建议：

- `backend/app/world_runtime/vla_cache.py`
- `backend/tests/test_vla_provider_cache_isolation.py`

任务：

- [ ] 建立 cache key
- [ ] cache key 包含 context id、query window、artifact refs hash、fact refs hash、model version
- [ ] 禁止 shared namespace
- [ ] 禁止跨角色命中私有 patch cache
- [ ] cache 命中结果仍需 freshness 检查

验收：

- character 与 siming 相同 artifact 也不能共享私有 cache result
- stale cache result 不覆盖新 L1 fact
- cache hit/miss 进入 trace

## 7. 阶段 F：协议落点与 Fusion

目标文件建议：

- `backend/app/world_runtime/vla_percept_bridge.py`
- `backend/tests/test_vla_percept_bridge.py`

任务：

- [ ] `VLAProviderResult` -> `ModalityInterpretationResult`
- [ ] `ModalityInterpretationResult` -> `CrossModalUnderstandingResult`
- [ ] 把 advisory findings 合入 character `CanonicalPerceptBundle`
- [ ] 把 advisory findings 合入 siming percept/global situation input
- [ ] 保留 uncertainty、conflicts、missing modalities、expires_at

验收：

- 角色结果可进入 Actor Scene Knowledge update 或 active perception request
- 司命结果可增强 global situation/fairness explanation
- VLA conflict 不覆盖 L1/world truth

## 8. 阶段 G：Runtime 消费接线

目标文件建议：

- `backend/app/world_runtime/l1_runtime_perception_bridge.py`
- `backend/app/character_agent/reasoning/l1_perception.py`
- `backend/app/services/siming_runtime.py`
- `backend/tests/test_vla_runtime_consumption.py`

任务：

- [ ] 在现有 bridge 周围接入可选 VLA slow path result
- [ ] 保持 VLA disabled 时现有 L1 structured facts path 不变
- [ ] 角色只消费 `character_mm:*` 结果
- [ ] 司命只消费 `siming_mm:*` 结果
- [ ] 结果标记为 advisory

验收：

- VLA disabled 回归通过
- VLA enabled 只增加 advisory fields
- 不改变 ESM settlement result

## 9. 阶段 H：Trace 与 Harness

目标文件建议：

- `scripts/verification/verify_vla_provider_backend.py`
- `.harness/profiles/vla-provider-backend.json`
- `docs/harness.md`

任务：

- [ ] 记录 request/result trace
- [ ] 记录 cache hit/miss
- [ ] 记录 timeout/degrade/drop
- [ ] 记录 consumed bundle id
- [ ] 写入 `.harness/verification/vla-provider-backend-report.json`
- [ ] 接入 harness profile

验收：

- 证明 provider 被调用
- 证明 result 是 advisory
- 证明 timeout 不阻塞 runtime
- 证明上下文/cache 隔离
- 证明 VLA 不写 authority
- 证明 result 进入 unified percept protocol

## 10. 验证命令

计划完成后至少运行：

```bash
python -m pytest -q backend/tests/test_vla_provider_backend_contract.py backend/tests/test_vla_provider_backend_adapter.py backend/tests/test_vla_slow_path_scheduler.py backend/tests/test_vla_provider_cache_isolation.py backend/tests/test_vla_percept_bridge.py backend/tests/test_vla_runtime_consumption.py
python scripts/verification/verify_vla_provider_backend.py
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile l1-world-fact-runtime
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile docs
```

如果 Godot runtime 或真实模型环境不可用，报告必须拆分：

- `backend-contract-verified`
- `mock-provider-verified`
- `real-provider-unverified`
- `godot-runtime-artifact-unverified`

不能把 mock provider proof 写成真实 VLA provider 完整接入。

## 11. 不接受的完成口径

- 只新增 schema，没有 scheduler/cache/trace proof
- 只调用模型，没有落到统一感知协议
- 只在单元测试手工构造 result，没有从 PQF 转 request
- provider result 覆盖 L1/world truth
- VLA timeout 导致角色/司命主循环等待
- character 和 siming 共享 private cache
- 使用 robotics VLA action output 控制世界

## 12. 完成定义

完成后应能说：

> 当前项目已把开源多模态/VLA 能力作为 VLA provider backend 接入慢通路。provider 消费现有 PQF 和 artifact refs，输出 advisory 空间视觉理解结果，经 scheduler/cache/trace 管控后进入统一感知协议，并由角色/司命各自私有多模态栈消费；VLA 不新增 runtime、不写 authority、不阻塞主循环。

未达到真实模型接入时只能说：

> VLA provider backend 契约、mock provider、调度、缓存、trace 和协议落点已验证；真实开源模型 backend 尚未接入或尚未完成 runtime artifact 验证。
