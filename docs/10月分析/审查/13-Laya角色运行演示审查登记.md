# Laya 角色运行演示审查登记

状态：`analysis/planned/non-authorizing`。

| 项目 | 当前结论 |
|---|---|
| Godot 入口 | 新建独立 `LayaCharacterRuntimeDemo`，不替换 root 场景 |
| backend 接线 | 复用既有 fact ingress、cognition、L3/L4、gateway/Laya、公开消息投影 |
| 私密性 | UI 只显示 backend 已投影字段；不发送 profile/private archive |
| 执行语义 | 第一版允许选择/高亮/阶段反馈；无 owner receipt 时显示诊断/阻断 |
| 证据 | 需要真实 provider、真实 L4、Godot 边界消息及第二回合；静态测试不能替代运行证据 |
| 关闭范围 | char_d、战斗、B/C、AD/Blender、完整 calibration 继续关闭 |



## 2026-10-15 用户收口：仅验证 Laya choice 输出类型

按用户明确要求，本轮到此收口，不再验证 Godot。验证范围仅记录为 Laya 的 `choice` 输出类型；不扩展到 `score`、`noul` 或其他输出类型。合同/回归测试与历史 provider 证据按原轮次保留，不作为本轮真实运行证据。

Godot editor/runtime、按钮交互、截图/录屏、第二事件回合及完整 `raw_fact_event → backend → Laya → L4 → Godot` live 链路均未验证，本轮不再安排。暂停本轮这些验证要求不等于它们已通过，也不表示领域 owner 执行或角色选择质量已验收。L4/owner receipt 与 A-Cognition 的既有未验收状态保留。本条覆盖前文要求本轮继续取得 Godot 运行证据的安排；实现范围和原始验收设计保留供后续另行推进。

## 2026-10-15 backend 收口与局部阶段三续行

本轮用户授权顺序：真实 backend choice 回合 → 计划02/03角色剩余基础 → 阶段三局部准入。阶段三专指规格09–12／计划04通用领域接入，与计划03和A/B/C不同。先复用当前实现与新鲜证据，仅核对实际依赖；不重做整批静态审计。

真实回合须由事实解析、privacy/visibility投影、cognition admission及原coordinator/driver进入MindFrame、CandidateCompiler U/P与冻结映射、gateway、固定官方离线multilingual CPU Laya、choice、accept/freeze/resume和实际L4。显式启用共享完整预算门，保留同turn/request的实际usage与阶段receipt；模型接纳、L4合同接纳、owner提交分列。第二不同事件及取消/迟到、provider不可用复用现有负例路径。此条恢复backend-only验证，不恢复Godot安排。

计划04 Task1–2按局部API/owner依赖实施，阶段准备、开始实施、合同通过、最终验收分别记录。缺某consumer API仅阻断该consumer；没有soul owner的结果等待计划04，不能反向阻断所有通用工作。Godot、领域执行和模型质量均未验收。Policy A保持autonomous 0/8、explicit diagnostic 0/6、role-sensitive 1/8；真实backend回合不能补算质量。禁止final/holdout、训练、Godot启动或交互/截图/录屏及非choice类型验证；B/C、玩法包、编辑器、自走棋、AD/Blender继续关闭。

验证：focused、完整pytest、适用backend Harness、git diff --check；不运行Godot profile或Harness all，历史all未通过状态保留。证据导出仓库外，仅回收本轮自有进程与临时数据。实现结果另附本批回写，不把此准备登记写为验收通过。


## 本批规格与计划回写：RW-34 backend choice与基础合同局部实施（2026-10-15）

本轮实际结果见[RW-34批次报告](../回写/backend-choice-foundations-stage3-20261015.md)：固定官方离线multilingual CPU服务经真实backend事实入口与原coordinator/driver完成choice接纳、冻结续行及L4结果。首回合L4为cognition_unavailable下的physiology_hint，第二不同事件新turn已完成但L4命令为空；不登记领域执行成功。取消后迟到结果zero_write，服务不可用有真实URLError。完整预算门在该backend进程显式启用，普通runtime仍opt-in。

角色新增调节投影、表达/观察episode、协同/短契约、SpeechLease的局部合同，任务证据及剩余项见计划02/03；阶段三严格为规格09–12／计划04，Task1–2已开始实施、局部合同与生产迁移/最终验收分列。原角色03/04/15、规格08、计划02/03及原角色16/规格09–12/计划04分别回写。模型质量仍0/8、0/6、1/8未验收，Godot未验证，领域最终执行未验收；本轮不恢复Godot、其他输出类型、final/holdout或训练。验证与清理以批次报告最终区块为准。

收尾审查：L4同键变更合同影响feedback/cancel/expire的P1已修复，6例RED→GREEN及独立复审通过。完整pytest为8010 passed、17 failed、2 skipped；其中事实序列化兼容回归已修复，随后相关72项通过，backend-contract Harness再次通过及清理成功。另16项因原角色13回写使两套历史fixture source pins失配，保持fail-closed，不刷新封存hash冒充通过；完整套件仍未通过。Task6局部纵向证据及原角色13/14、规格05/06、计划02已补写。详见RW-34最终证据区块。
