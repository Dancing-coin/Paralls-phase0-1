# 十月分析规格与计划审查索引

状态：`analysis/planned/non-authorizing`；审查日期：2026-10-11。

本目录审查 [规格](../规格/README.md) 与 [计划](../计划/README.md) 对现有代码和十月分析原文的符合性，不增加领域对象、协议或实现权限。

| 文档 | 用途 |
|---|---|
| [01-设计来源与规格计划覆盖矩阵](01-设计来源与规格计划覆盖矩阵.md) | 逐一登记 47 个内容文件的原文章节、收敛规格、实施任务和未闭合条件 |
| [02-规格与计划完整性审查报告](02-规格与计划完整性审查报告.md) | 记录 17 份规格、8 份计划的审查结论、已修问题、顺序、阻断和实际检查结果 |
| [03-实施待决收敛与验证闸门](03-实施待决收敛与验证闸门.md) | 登记D01–D18、官方Laya协议来源、剩余证据、A/B/C回验次序，以及编辑器/AD暂不启动的当前范围 |
| [04-第二项实施准入包与静态映射](04-第二项实施准入包与静态映射.md) | 在计划启动前固定候选来源、U/P离线边界、评估fixture合同、两轨归因和实施/验收证据分界；不授权runtime实现 |
| [05-第三项阿博评估档案与四角色夹具](05-第三项阿博评估档案与四角色夹具.md) | 将角色13的阿博定义逐字段映射到现有 profile/dossier，固定隔离 authored `char_d`、四角色夹具和 Actor/roster admission 边界；不授权runtime实现 |
| [06-第四项通用资源集中迁移与兼容边界](06-第四项通用资源集中迁移与兼容边界.md) | 将 D06 的集中资源迁移映射到现有 ResourceBody runtime、reservation、receipt/replay 和各领域 owner；固定迁移前排空预留及新 consumer pin 的证据门槛；不授权runtime实现 |
| [07-第五项Life-Presence-Soul真实owner与角色投影边界](07-第五项Life-Presence-Soul真实owner与角色投影边界.md) | 核对 Life/Presence/Soul 的现有 owner、代码和证据；固定缺 owner 时的 unavailable/diagnostic 投影与角色基础解锁边界；不授权runtime实现 |
| [08-第六项B-C隔离Godot场景与真实边界证据](08-第六项B-C隔离Godot场景与真实边界证据.md) | 核对 `StreetCombatActorDemo` 动作底座、`StreetCombatDemo` 语义边界、B/C actor admission、真实模型/authority/mirror/visible evidence；固定缺证据只阻断 B/C；不授权runtime实现 |

当前阅读顺序：总规格00 → 角色规格01–08 → 对应计划01–03 → 通用领域09–12/计划04 → 覆盖矩阵和报告。按D15，编辑器14/计划05和AD16/计划07暂不启动，保留供恢复时参考；已有合格动作仍供角色/B/C使用。自走棋15仅作deferred单局运行时归档。

矩阵中的“覆盖”表示设计和任务可追踪。Laya/provider、完整生命/灵魂 owner、AD 完整 Blender/GLB 资格链及通用编辑器控制面实现验收必须另外取得真实证据；AD WebApp 基线测试已运行并记入报告。自走棋 owner 不属于本批 active gate。计划中的其余命令是未来门禁；本轮实际执行项只以报告的验证记录为准。

审查还必须区分“来源被引用”和“收敛发生了回写”。所有相对原始设计改变路线、缩小范围或延期的项目，见 [设计回写登记](../回写/README.md) 及各原始设计文档末尾的回写小节；未回写项目不得进入运行时实施。


## 2026-10-13 calibration 前置阶段

新增[审查12](12-calibration前置收口与独立题集门禁.md)，统一 reviewer independent approval、lead audit approval 与 formal truth usability，纠正审查11历史批准表述。独立v2新输入24条/6 trajectories/三轨；22条fixture选择已获独立reviewer与lead分别批准，calibration本轮不运行且仍blocked。历史全量pytest exit1保持not clean，新鲜验证另追加；A-Cognition、A-Embodied、Godot与Harness all分别记录。原reviewer污染不可恢复，final/holdout继续封存。


### RW-29 v2独立审查与前置证据更新

新v2全新独立reviewer先冻结标签并亲自批准，实际verifier确认 reviewer_independent_approval=true、lead_audit_approval=true、formal_truth_usable=true，严格仅22条fixture选择（autonomous8、explicit6、role-sensitive8）；runtime动作/legality/owner/话语/receipt均0。角色敏感仅各参与者authored当前/过时可见证据，不是人格验证；char_d缺口unknown。24题实际token max46 <48，v4 48条digest精确重建；CPU health通过但live checkpoint revision未证明、阈值未预登记，calibration仍blocked、provider新调用0。docs/backend-contract/change-lifecycle Harness各exit0/cleanup passed。全量最终结果统一见审查12最终工程区块，历史full exit1保留。
