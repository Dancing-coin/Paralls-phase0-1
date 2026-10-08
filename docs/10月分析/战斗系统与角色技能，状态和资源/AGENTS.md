# 战斗与角色设计文档指导

本目录继承根 AGENTS.md；所有设计保持 analysis/planned/non-authorizing。仅在用户明确授权后进入正式 spec、plan 或代码实现。

## 标签与元标签

- 00 是导航和审查矩阵；08 是对象标签、元标签、编辑与版本治理的唯一 owner。01–07 定义领域消费合同并链接 08，避免复制相互矛盾的标签模型。
- 定义/实例/派生/运行时是生命周期轴；INF category、命名空间、descriptive/effectful、主动/被动/反应式触发是其他轴。命名空间不能创建未经接纳的类别、资源或权限。
- 复用 TagDefinition、TagAssignment、SemanticSnapshot、受限 SemanticSelector 和 MetaRuleDefinition。元标签治理字段尚未实现的部分必须标为 [planned]；元标签不等于元规则或 INF 的 evidence/provenance 元数据。
- 标签可作为对象、组件、关系、状态和事件的语义编辑载体，亦可与资源、效果、技能并列引用；组件账本和 lifecycle 保留正式数据 owner。
- 创作者编辑修改注册草稿/内容 revision；角色改变与司命改变提交 owner-bound 意图/催化。只有已注册的 domain authority 原子提交世界事实，司命模型不能直接写入。
- 标签参数合并、效果叠加、命中/控制/资源结算必须分开；同一 binding 的多个入口去重，并声明卸下、过期、资格撤销和生成状态的生命周期。
- 稳定标签/绑定/治理版本改变 stable prefill；高频状态和派生条件进入 hot/delta。可见性过滤先于缓存写入，外部事实经 L1 授权投影，预算不能突破角色能力和隐私边界。

## 图表与验证

每个实质更新文档包含或明确链接架构图、主流程时序图、数据流图。图中区分 [current]、[planned]、[deferred]，并画出 proposal 与 authority commit 边界。禁止越权不应写成以后可开放的 deferred 能力。

更新时核对 00–09 的标签接点、相对链接、状态标记、当前代码映射与验收案例。文档静态检查不代表通用 Gameplay Foundation、战斗内容包、编辑器或 Godot 运行时已验证；保留工作区已有修改。

## 通用玩法时序与命名

时间语义及 profile 由 `../16-通用玩法时序模型与编辑器设计.md` 唯一负责，不以 Runtime 命名；本目录只定义战斗动作、状态、资源和证据如何消费它。通用能力在现有 Gameplay Foundation 与世界时钟/调度上增量升级；通用基础不按战斗建立独立中心，也不要把 Street Combat 验证 slice 当作架构模板。
