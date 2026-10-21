# 编辑器与能力权限治理文档指导

本目录继承仓库根 `AGENTS.md`；文档保持 `analysis/planned/non-authorizing`，不授权编辑器、任何 Gameplay domain、司命或角色模型直接写入运行时世界事实。

## 唯一 owner

- 本目录唯一负责编辑器控制面：`CapabilityDefinition`、`CapabilityProfile`、`RulePolicy`、`AuthorityGrant`、`MutationContract`、草稿、预览、发布、激活、回滚和缓存失效合同。
- 战斗系统与角色技能、状态和资源目录负责 `Method`、`Technique`、资源、状态、效果、动作、空间和结算的领域消费合同。
- `08-对象标签、编辑与版本治理设计.md` 是标签和元标签唯一 owner。本目录不得重新定义 `TagDefinition`、`TagAssignment`、`SemanticSnapshot` 或标签生命周期。
- 领域 authority 是运行时事实的唯一提交 owner。编辑器预览、角色 typed intent、司命 catalyst 和 `direct` grant 都必须经过 authority 校验。
- `../角色/16-通用玩法时序模型与编辑器设计.md` 唯一负责时间语义、TemporalProfile 及专项校验；本目录提供它复用的草稿、权限、发布和激活治理，不另建时间模型。
- `04-十月分析领域接入与编辑器同步矩阵.md` 负责登记十月分析各领域如何接入编辑器控制面；它只保存引用、owner、revision、权限和同步边界，不复制领域真值模型。

## 编辑规则

- 能力开关、角色资格、权力授予、最终结算是四条独立轴；不能用一个 `enabled` 字段代替它们。
- 下层 profile 不能启用上层未注册的能力，不能扩大数值、目标、频率或 authority 范围。
- `direct` 只表示调用已注册的限定命令，不表示任意字段写入。
- 草稿、预览、回放和沙盒不得产生正式 authority event；运行时变更必须带 owner、scope、revision、迁移和幂等信息。
- 权限撤销必须使 affordance、待处理意图、活动绑定和相关 actor cache 按合同失效；不得向角色泄露被撤销的秘密值。

## 图表与状态标记

每个实质文档必须有架构图、主流程时序图和数据流图，并标记 `[current]`、`[planned]`、`[deferred]`。禁止把模型直接写事实、任意脚本规则或绕过 authority 写入描述成可延期开放的能力。
