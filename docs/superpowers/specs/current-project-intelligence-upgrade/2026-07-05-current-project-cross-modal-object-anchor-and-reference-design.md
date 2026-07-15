# 当前项目跨感知对象锚点与指代统一设计

- 状态：`implemented-and-focused-verified`
- 日期：`2026-07-05`

## 1. 目标

定义同一对象在 fact 链、provider patch、VLA advisory、ASK、Siming global situation 中的稳定 identity，避免：

- 同一物体被不同 patch 记成多个对象
- 不同物体因为近邻/同名而被误合并
- advisory 与 world truth 的指代关系混淆

## 2. 核心对象身份

建议引入统一锚点：

```text
world_anchor_id
subject_ref
target_ref
source_ref lineage
```

### 2.1 约束

- `world_anchor_id`
  - 指向仓库中的 canonical object/world entity identity

- `subject_ref`
  - 面向某条感知记录的观察主体对象

- `target_ref`
  - 当前 capture 下聚焦对象

- `source_ref lineage`
  - 记录从 fact / provider / advisory 到 object anchor 的映射链

## 3. 统一规则

1. 同一 `world_anchor_id` 可对应多个 patch/artifact/source ref
2. patch 命中对象时，必须先回锚到 `world_anchor_id`
3. `subject_ref` 不能替代 `world_anchor_id`
4. `VLA advisory` 若无法回锚对象，不得写 world truth marker

## 4. 冲突模型

当不同链路对同一 `world_anchor_id` 给出不同属性时：

- 记录为“同对象冲突”
- 不允许拆成“双对象”

当不同 patch 指向不同对象但外观相似时：

- 必须保留为不同 `world_anchor_id`
- 不允许仅凭空间近邻合并

## 5. world truth anchor 写入资格

只有：

- `L1 projected fact`
- authority/publicly accepted result family

可以写 world truth anchor。

`VLA advisory`、角色私有推断、Siming 推断只能写：

- `subjective_not_world_truth`
- advisory marker

## 6. 需要落地的对象

- `CandidatePerceptEvent`
- `CharacterPerceivedEvent`
- `CanonicalPerceptBundle.target_state`
- `ActorSceneKnowledgeEntry`
- `VLAProviderResult.findings`
- `SimingGlobalSituationSnapshot.evidence_chain`

## 7. 验证要求

必须覆盖：

- 同拍同物跨链统一到同一 `world_anchor_id`
- 同名/近邻对象不误合并
- 同对象跨模态差异记成冲突，不记成双对象
- advisory 无 anchor 时不能升级为 world truth
