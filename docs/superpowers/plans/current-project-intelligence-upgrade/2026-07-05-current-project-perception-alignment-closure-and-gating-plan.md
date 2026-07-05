# 当前项目感知 identity 收口总控计划

- 状态：`implemented-and-focused-verified`
- 日期：`2026-07-05`

上位母计划：

- [2026-07-05-current-project-perception-input-alignment-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-input-alignment-implementation-plan.md)

## 1. 目标

这是一份总控 / 门禁计划。

它不直接承担单模块代码实施，而是负责：

- 固定 2026-07-05 五个子计划的依赖顺序
- 规定每个子计划的进入门槛与完成门槛
- 把 relationship spec 中的链路定位落实成执行约束
- 防止实现退化成“字段接线完成即完工”

## 2. 纳管子计划

1. `perception-capture-clock-contract`
2. `cross-modal-object-anchor-and-reference`
3. `multi-actor-private-perspective-reconciliation`
4. `capture-aware-bridge-and-downstream-propagation`
   - [2026-07-05-current-project-capture-aware-bridge-and-downstream-propagation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-capture-aware-bridge-and-downstream-propagation-implementation-plan.md)
5. `perception-identity-verification-matrix`
   - [2026-07-05-current-project-perception-identity-verification-matrix-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-identity-verification-matrix-implementation-plan.md)

## 3. 执行顺序

强制顺序：

1. `perception-capture-clock-contract`
2. `cross-modal-object-anchor-and-reference`
3. `multi-actor-private-perspective-reconciliation`
4. `capture-aware-bridge-and-downstream-propagation`
5. `perception-identity-verification-matrix`

## 4. 进入门槛

### 4.1 进入对象锚点计划前

必须先有：

- `capture_root_id`
- `capture_id`
- `clock_domain`
- `monotonic_tick`

### 4.2 进入多 actor 视角计划前

必须先有：

- `world_anchor_id`
- `target_ref`
- `source_ref_lineage`
- 同拍判定规则

### 4.3 进入验证矩阵前

必须先有：

- actor-private projection 接线
- `VLA` 后补 advisory 标记
- `Siming` 的 object/time identity 保留

## 5. relationship 约束

来自 `fact-chain and multimodal-chain relationship` spec 的执行约束：

1. 事实上抛链路仍是主感知链
2. 多模态链路是增强感知链
3. 不新增第三条并行总融合器
4. provider 分级与保留策略必须在实现末期回写到文档与计划树

## 6. provider / fact 裁剪责任

这份总控计划额外承担一个当前缺失的主题：

- provider necessity grading
- fact-first / provider-enhanced ownership mapping

至少要形成一份落地结论，明确：

- 哪些 provider 是 runtime critical
- 哪些 provider 是 advisory / optional
- 哪些模态优先走 fact-first
- 哪些模态必须保留 provider-enhanced

### 6.1 当前落地结论

- runtime critical：结构化 L1 fact / projected fact、`RawFactEvent`、`CanonicalPerceptBundle`、`SampleInputRef` 的 ref identity。它们构成主感知链与同拍判定证据。
- provider-enhanced：`visual_patch`、`spatial_patch`、`auditory_context`、`embodied_state`、`skeletal_state`、`environment_field`。这些 provider 保留为输入证据和私有/全局 percept bundle 的增强材料，不直接拥有 world truth。
- advisory / optional：VLA slow path 与 VLA findings。它们必须保持 `advisory=True`，后补结果必须标记 `capture_relation="late_advisory"`，不得伪装原拍主事实。
- fact-first 模态：空间可达、对象状态、环境状态、约束结果、world result / ESM result。下游 authority 与 world truth 继续以结构化 fact/result 为主。
- provider-enhanced 模态：视觉 patch、空间 patch、听觉窗口、具身/骨架 ref、环境 field ref。它们可增强角色私有感知、Siming 全局情况与 VLA advisory，但不替代 fact anchor。

## 7. 完成定义

只有同时满足下面 5 条，才能宣称 2026-07-05 这一组“完整实现 ready”：

1. 时钟契约落地
2. 对象锚点契约落地
3. 多 actor 私有视角分发落地
4. bridge / downstream identity 接线落地
5. 行为矩阵 verifier 全绿

当前 focused 证据：

- `python scripts/verification/verify_perception_capture_clock_contract.py`
- `python scripts/verification/verify_perception_object_anchor_contract.py`
- `python scripts/verification/verify_perception_multi_actor_private_perspective.py`
- `python scripts/verification/verify_perception_downstream_identity_propagation.py`
- `python scripts/verification/verify_perception_input_alignment.py`
- `python scripts/verification/harness.py --profile perception-input-alignment`

## 8. 禁止事项

禁止：

- 跳过时钟契约直接做多 actor 分发
- 跳过对象锚点直接做跨模态 merge
- 不补 verifier 就宣称 identity 收口
- 在 provider / fact 主次关系未固定前继续扩两条链

## 9. 验证

最低要求：

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile l1-world-fact-runtime
python scripts/verification/verify_perception_input_alignment.py
```
