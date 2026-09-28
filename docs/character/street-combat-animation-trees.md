# StreetCombatDemo 角色动画树盘点

## 当前场景

`scenes/phase0/StreetCombatDemo.tscn` 有三个真实导入角色。每个 `StreetCharacterSkin` 在运行时挂载 `RoleAnimationController`。两个建模都严格使用同一组六个状态：`idle`、`walk`、`run`、`jump`、`boxing`、`sword_attack`，对齐 `Street Character External AnimationTree Demo` 的建模2状态机；源 GLB 中的其他动作不加入运行时状态树。

| 角色节点 | actor_id | 资源包 | 主控 | running 来源 | 动画树状态 |
| --- | --- | --- | --- | --- | --- |
| `PlayerCharacter` | `street_bandage` | `female_jk_external`（建模3 金色卷发 JK 女） | 是 | 建模2 `running`，按骨骼名映射 | idle / walk / run / jump / boxing / sword_attack |
| `AgentCharacterJK` | `char_a` | `female_jk_external`（建模3 金色卷发 JK 女） | 否 | 同上 | idle / walk / run / jump / boxing / sword_attack |
| `AgentCharacterT` | `char_b` | `female_t_external`（建模2 纹身腿黑卷发女） | 否 | 建模2原生 `running` | idle / walk / run / jump / boxing / sword_attack |

## 资产来源

- 建模2：`E:/下载/建模2 纹身腿黑卷发女T字版本  基础动作版.blend`
- 建模3：`E:/下载/建模3  金色卷发jk女 T字版  多动作版.blend`
- 建模3 的运行时 GLB 已重新生成；其 `running` 动画来自建模2，并按目标骨骼名称重定向。两份 `.blend` 均保持不修改。

## 状态切换

- 无移动：`idle`
- 普通移动：`walk`
- 按住奔跑：`run`
- 跳跃：`jump`
- 拳击：`boxing`，一次性动作结束后恢复 locomotion
- 剑击：`sword_attack`，一次性动作结束后恢复 locomotion
- 建模2和建模3的运行时状态树都只暴露六个状态；源文件中的 `left turn`、`right turn`、`drinking`、`walking2`、`waveing` 等动作不进入 StreetCombatDemo 状态机。

身体位移仍由 `CharacterMotor` 负责，动画树只负责可视动作；额外动作通过 `play_source_state()` 按源动作名播放。

## 运行时核验（2026-09-28）

Godot 4.6.3 运行 `StreetCombatDemo` 时，三个角色的 AnimationTree 均为 active，AnimationPlayer 绑定均有效。三棵运行时状态树各有 6 个状态和 6 个纳入状态机的 clip。`walking` 和 `running` 分别映射到 `walk` 和 `run`，不会额外生成同名状态。

两套角色的 `idle`、`walk`、`run`、`jump`、`boxing`、`sword_attack` 均已逐项确认；未纳入六状态树的源动作会被 `play_source_state()` 拒绝。
