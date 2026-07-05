# 当前项目感知输入对齐层母计划

- 状态：`proposed-parent-plan`
- 日期：`2026-07-05`

上位设计：

- [2026-07-05-current-project-perception-input-alignment-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-perception-input-alignment-design.md)

## 1. 目标

这是一份母计划，不负责单独实现所有代码改动。

它的职责是：

- 定义感知 identity 收口的总目标
- 约束子计划之间的依赖顺序
- 明确哪些问题必须拆成独立计划处理
- 防止实施阶段重新把问题压回单一 `capture_id` 接线任务

在不强行合并 fact 链和 provider 链的前提下，最终目标仍然是引入统一输入时空 envelope，使两条链在输入阶段对齐，并为多角色私有视角分发建立共同基准。

完成后应能回答：

- 这一条 `CharacterPerceivedEvent` 和这一份 `CanonicalPerceptBundle` 是否属于同一拍输入？
- `char_a` 与 `char_b` 是否在同一 capture window 下各自拥有独立视角？
- `VLAProviderResult` 是否来自某次明确的输入 capture？

## 2. 非目标

- 不在本计划中重写 authority event bus
- 不在本计划中完成 full `L4 -> CharacterActor` 收敛
- 不在本计划中引入新的 live model provider
- 不在本计划中合并或删除全部 provider
- 不把“完整 identity 设计”继续压缩回单一 schema 接线计划

## 3. 子计划边界

本母计划不直接作为代码实施清单使用。

当前完整实现已经拆成以下子计划：

1. `2026-07-05-current-project-perception-capture-clock-contract-implementation-plan.md`
2. `2026-07-05-current-project-cross-modal-object-anchor-and-reference-implementation-plan.md`
3. `2026-07-05-current-project-multi-actor-private-perspective-reconciliation-implementation-plan.md`
4. `2026-07-05-current-project-perception-identity-verification-matrix-implementation-plan.md`

它们分别承担：

- 绝对时间与 capture 身份
- 对象锚点与指代统一
- 多角色私有视角分发
- 行为级验证矩阵

本母计划只保留总控和门禁。

## 4. 总控依赖顺序

必须按下面顺序推进：

1. `perception-capture-clock-contract`
   - 先固定 `capture_root_id / capture_id / monotonic_tick / clock_domain`
2. `cross-modal-object-anchor-and-reference`
   - 再固定 `world_anchor_id / target_ref / source_ref_lineage`
3. `multi-actor-private-perspective-reconciliation`
   - 再升级 bridge 和多 actor 视角投影
4. `perception-identity-verification-matrix`
   - 最后补 focused verifier、矩阵验收和 harness profile

禁止顺序：

- 在没有 clock contract 前先做多 actor bridge 升级
- 在没有 object anchor 前先做跨模态对象 merge
- 在没有行为矩阵前宣称 identity 收口完成

## 5. 总体验收

完整实现完成时，必须同时满足：

- fact 链和 provider 链可证明同拍 identity
- 同一对象跨链统一到同一 world anchor
- 多 actor 私有视角下可对同物产生不同属性，但不混淆对象
- `VLA` late advisory 不伪装原拍
- `Siming` 汇总不读取 actor-private context，且不丢 object/time identity

## 6. 禁止事项

实施时禁止：

- 新增第三条并行“总融合器”
- 让 `capture_id` 直接进入 authority event bus 作为公共事实主身份
- 在 object anchor 未定义前，用近邻/命名近似做对象硬合并
- 在 verifier 未补齐前，只凭字段存在宣称完成

## 7. 风险

1. 若子计划脱离总控顺序推进，会出现重复身份体系
2. 若继续把母计划当成直接代码计划，会和子计划重复
3. 若不加门禁，后续实现仍可能回到“字段接线完成即完工”的伪完成状态

## 8. 推荐执行方式

执行时应：

1. 先把本母计划视为 closure / gating 文档
2. 每次只执行一个子计划
3. 每完成一项子计划，就回写 README 顺序和验收状态
4. 只有四个子计划都过行为矩阵验证，才能宣称“完整实现”
