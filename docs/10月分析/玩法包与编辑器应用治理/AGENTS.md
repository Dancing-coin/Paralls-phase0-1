# 玩法包与编辑器应用治理文档指导

本目录继承仓库根 `AGENTS.md`；文档属于 `analysis/planned/non-authorizing`，不授权玩法包、编辑器、角色模型或司命直接写入运行时世界事实。

## 唯一 owner

- 本目录负责玩法包的分层、组合、底座复用、编辑器发现/配置/预览/应用、包版本生命周期和跨领域接入矩阵。
- `../编辑器与能力权限治理/` 负责编辑器控制面对象：`CapabilityDefinition`、`CapabilityProfile`、`AuthorityGrant`、`MutationContract`、Draft、Preview、Publish 和 Activation。
- `../战斗系统与角色技能，状态和资源/` 负责战斗、技能、状态、资源、效果、空间和 settlement 的领域合同。
- `../战斗系统与角色技能，状态和资源/08-对象标签、编辑与版本治理设计.md` 是标签和元标签唯一 owner。
- `../16-通用玩法时序模型与编辑器设计.md` 是时间坐标、时间 profile、调度和 settlement window 唯一 owner。
- 领域 authority 是运行时事实唯一提交 owner；玩法包只能提供定义、政策、适配声明和 owner-bound proposal。

## 玩法包边界

- 玩法包是基于通用 Gameplay Foundation 的不可变内容与适配 revision。
- “调整”只能覆盖已注册 schema 允许的政策字段；“补充”只能增加已接纳扩展点中的定义和绑定。
- 玩法包不能携带任意脚本，不能创建第二套 event store、clock、scheduler、tag registry 或 authority owner。
- 编辑器 `apply` 只提交 candidate install/activation 请求；最终由 authority 重新校验并提交事实。

## 图表和状态标记

每个实质文档必须标记 `[current]`、`[planned]`、`[deferred]`，并包含或链接架构图、主流程时序图和数据流图。`00-README.md` 提供目录级三张主图，其余文档提供领域细化图。
