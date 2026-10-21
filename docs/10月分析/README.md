# 十月分析：模型驱动的角色心智、快慢循环与语音协同

状态：`architecture analysis; proposed and non-authorizing`

整理日期：2026-10-05

执行范围更新（2026-10-10）：按 [D15](审查/03-实施待决收敛与验证闸门.md)，通用编辑器控制面和AD工作流暂不处理，规格14/16与计划05/07标记为 `paused-by-user`、暂不启动。当前讨论待决项1–6，已有合格动作底座可继续用于角色/B/C；自走棋仍按D14关闭并延期。以下保留全批次来源索引，不表示暂停任务可自动执行。

本目录整理 2026 年 10 月围绕角色智能体、Laya、快慢思考、协同作战和语音交互的设计讨论。它是后续正式 spec、plan 和实现工作的输入，不替代正式批准的架构 spec，也不表示 Laya 已经接入运行时。

本批次的收敛文档已经物理分离：

- [规格索引](规格/README.md)：四域总规格和 01–16 子规格，角色智能体心智模型优先；15 为单局自走棋的延期归档。
- [计划索引](计划/README.md)：总实施计划和角色、通用领域、玩法包/编辑器分计划；05/07由用户要求暂不启动，06自走棋计划已关闭并延期。
- [审查索引](审查/README.md)：47 个内容来源的逐文件覆盖矩阵、规格/计划完整性结论、实现阻断和本轮静态证据。
- [设计回写登记](回写/README.md)：记录收敛规格/计划相对原始分析设计的路线变化、范围收缩、延期和实施准入状态，并链接原文末尾的回写记录。
- [实施决策登记](审查/03-实施待决收敛与验证闸门.md)：十四项已收敛脑暴选择、Laya基线/候选规模实验、资源集中迁移、缺owner策略、A/B/C必验次序、`char_d` 评估档案边界和开放世界范围。
- 2026-10-12 第二阶段门禁复核：Laya 五种 live 负例因固定 revision 服务无法建立真实 admission，全部登记 `blocked/unverified`；`unarmed_punch`/`sword_slash` 缺完整 owner/target/contact 链，当前无可执行动作；`short_punch` 保持兼容语义且不自动 alias。全量 pytest 新鲜结果为 `7821 passed、2 skipped、4 failed`，失败归因和外部证据见审查03 §4.11。
- 2026-10-12 第二阶段候选准入实现：现有 CandidateCompiler 已接入 L3 prepared request，完成 U/P 分离、完整动作＋目标冻结、真实 Laya 字符串 label 到 candidate 映射及 envelope/policy/revision pins；L3/L4 对 target、affordance、grant、revision 和 label 异常 fail-closed。L4 保留 semantic action 与 target refs，但 owner ingress 仍 blocked，不生成 ActionAttempt 或 live 动作证据。实现边界和 `178 passed` focused evidence 见审查03 §4.12、审查09 §13；不解除 B/C、玩法包、编辑器、自走棋、AD/Blender/GLB 或三项动作执行门禁。
- 2026-10-12 第二阶段学习/承诺/评估准备：复用既有 evidence、learning、settlement 和 execution owner，补齐十二阶段学习进度、八维 mastery、七因子 difficulty、source/privacy/expiry/duplicate fail-closed，以及 stale/expired/revoked/interrupted/rejected/missing/late recovery。无 owner admission 时 L4 只返回 blocked diagnostic，不生成 ActionAttempt；char_d 继续为隔离 fixture。固定 Laya 端口当前不可达，focused mapping 不能升级为真实 positive mapping；精确 focused 集合为 `59 passed`，全量 pytest 新鲜结果为 `7831 passed、2 skipped、7 failed`，7 项单独复跑均为稳定的既有静态/资产输入或旧 runtime/action receipt 合同差异。详见审查03 §4.13、审查05 §7.1、审查09 §14；B/C、玩法包、编辑器、自走棋、AD/Blender/GLB 继续关闭。
- 2026-10-12 第二阶段最终复核：固定 Laya artifact 已恢复并完成 Windows backend → WSL forwarding → `/health=200`、真实 `/v1/systemone=200`、CandidateCompiler positive mapping 和五项 live negative；证据保存在 `D:\HarnessEvidence\phase2-live-positive-20261012\live-positive-mapping.json` 与 `D:\HarnessEvidence\phase2-live-negative-20261012-recovered\`。Candidate digest 为 `sha256:8544699fee1956eab5d15d3e20c2e9cec40e39b4a9f9d8493e7bf17870bbf93c`，真实选择为 `ask_probe`，unknown/reordered/stale mapping 均拒绝。四角色仍是 evaluation-fixture-only，checkpoint/policy 未冻结、calibration/final 为空；无 target-enabled executable Laya action、owner receipt/replay/Godot boundary。七项 pytest 合同差异已按当前设计最小修订；此前一次全量曾为 `7838 passed、2 skipped`，本轮新鲜全量为 `7837 passed、2 skipped、1 failed`，失败的 dialogue streaming 测试单项复跑及连续五次复跑均通过，故 full gate 仍未 clean。四个相关 Harness 本轮新鲜通过并 cleanup passed，但 readiness 中仍有 provider 未验证/缺凭据。A 最终验收保持 `blocked/unverified`，B/C、玩法包、编辑器、自走棋、AD/Blender/GLB 继续关闭。

固定执行顺序：角色心智基础 → 角色能力/学习/动作 → 协同表达与精神边界 → 通用时间/权限/领域服务 → 玩法包与编辑器。

本批只服务开放世界运行时。自走棋及其单局回合、棋盘、羁绊和奖励适配关闭并延期到未来独立的单局运行时批次，不阻塞当前主线。

角色基础先完成A单角色跨情境闭环并在完整能力包络后复验；通用合同和资源集中迁移完成后，依次取得B单角色连续Boss战、C双角色连续协同的真实证据。协同结构/拒绝测试可先行，不能替代C；Life/Presence/Soul缺owner时明确不可用，真实owner准入后回验角色私有消费。详细门禁见总规格 §4.1与总计划Task6A。

## 设计主张

1. 角色智能体是完整运行 harness；心智模型也是 harness，承担角色智能体的大脑职责；模型是心智模型的智能来源。
2. L1 是角色获得外部信息的唯一入口。模型可以提出信息需求，但不能直接读取玩法 authority 的隐藏事实。
3. Laya 作为快思考和小脑，负责在当前心智状态、感知和能力边界内选择 typed intent；L4 和 CharacterActor 负责执行连续动作。
4. 普通模型承担慢思考，Deep Model 按需处理复杂重规划；快循环应能够独立完成常规长时间战斗。
5. 多个思考模式是同一个心智模型的输入输出适配视角，不是多个独立角色。模式管理由心智模型和运行时调度共同完成，Laya 负责当前 intent 选择。
6. 语音是角色行为的一种表达通道：预设语音负责低延迟通信，动态语音负责复杂表达，多模态语音模型负责受控的自然表达，不负责越权的战术决策。

## 文档索引

| 主题 | 设计文档 | 实现说明 | 重点 |
|---|---|---|---|
| 角色心智与模型 | [01-设计](角色/01-角色心智模型与模型驱动运行时设计.md) | [01-说明](角色/01-角色心智模型与模型驱动运行时说明.md) | L1-L4、模型路由、harness 边界 |
| Laya 快慢循环战斗 | [02-设计](角色/02-Laya快循环与快慢思考战斗设计.md) | [02-说明](角色/02-Laya快循环与快慢思考战斗说明.md) | 魂游 Boss、阶段、降级、升级 |
| 协同作战与通信 | [03-设计](角色/03-协同作战与信息通信设计.md) | [03-说明](角色/03-协同作战与信息通信说明.md) | 局部感知、协同契约、队友通信 |
| 语音与多模态表达 | [04-设计](角色/04-角色语音与多模态表达设计.md) | [04-说明](角色/04-角色语音与多模态表达说明.md) | 音色、口癖、动态语音、流式 TTS |
| 玩法思考模式适配 | [05-设计](角色/05-玩法思考模式适配与L1信息获取设计.md) | [05-说明](角色/05-玩法思考模式适配与L1信息获取说明.md) | 战斗/经济/社交模式、模式触发、输入输出适配 |
| 自身状态与具身反馈 | [06-设计](角色/06-自身状态感知与具身反馈设计.md) | — | 自身数值、动作阶段、方位、身体体感 |
| 传统游戏 AI 感知参考 | [07-设计](角色/07-传统游戏AI感知与Boss战思考模式设计.md) | — | 传感器、Blackboard、有限/全知感知差异 |
| 游戏 AI 启发的架构增强 | [08-设计](角色/08-游戏AI启发下L1-L4架构增强设计.md) | — | L1 工作区、L2/L3/Laya/L4 改造边界 |
| L1 多源感知与信息入口 | [09-设计](角色/09-L1多源感知与信息入口设计.md) | — | 事实链、provider/PQF、VLA advisory、私有过滤 |
| 主动感知与记忆边界 | [10-设计](角色/10-主动感知与记忆边界设计.md) | — | 过期、冲突、回想、重观察、试探与询问 |
| 跨玩法动作承诺协议 | [11-设计](角色/11-跨玩法动作承诺协议设计.md) | — | typed intent、阶段、取消、回退、authority 结果 |
| 传统游戏 AI 与 ThoughtMode | [12-设计](角色/12-传统游戏AI与ThoughtMode设计.md) | — | Blackboard 映射、Boss 阶段、模式适配 |
| 角色能力图谱、认知包络与动态算力 | [13-设计](角色/13-角色能力图谱、认知包络与动态算力设计.md) | — | 人格、认知上限、动态推理预算及其言行映射 |
| 学习、模仿与技能进化 | [14-设计](角色/14-角色学习系统、模仿与技能进化设计计划.md) | — | 学习对象、模仿 episode、动作学习、难度、人格勾稽、技能演化 |
| 设定、言行、理智与灵魂边界 | [15-设计](角色/15-角色设定、言行表达、理智调节与灵魂规则边界设计.md) | — | 长期设定、五通道表达、理智调节、精神资源、灵魂规则与短暂失控 |
| 通用玩法时序模型 | [16-设计](角色/16-通用玩法时序模型与编辑器设计.md) | — | 跨玩法时间坐标、调度、结算窗口、编辑器 profile、确定性与有限回放/回滚 |
| 战斗系统、角色技能、状态和资源 | [子目录入口](战斗系统与角色技能，状态和资源/00-README.md) | — | 战斗内容包、跨通道效果、环境场、职业/身份标签、外物、通用装备核心、资源、状态、authority 与 CombatPrefill；自走棋玩法包仅保留为未来单局运行时来源，不属于本批 active scope；复用通用 Gameplay Foundation |
| 编辑器与能力权限治理 | [子目录入口](编辑器与能力权限治理/00-README.md) | — | 能力开关、世界规则配置、角色/司命权限授予、预览、发布与运行时同步 |
| 玩法包与编辑器应用治理 | [子目录入口](玩法包与编辑器应用治理/00-README.md) | — | 玩法包分层、通用底座复用、编辑器发现/配置/预览/应用、发布激活、领域接入和差距矩阵 |
| 角色动作工作流 | [子目录入口](角色动作工作流/00-README.md) | — | AD 骨架注册、动作库、通用映射、四视角参考和 Blender 正式烘焙边界 |

## 议题唯一 owner

每个议题只在一个文档中定义，其他文档只引用。`08` 是跨层变更清单，不重新定义下列协议。

```text
L1 多源链路与信息入口                         -> 09
主动感知、记忆新鲜度与信息获取               -> 10
自身数值、位置、姿态与身体反馈               -> 06
战斗快慢循环与升级条件                       -> 02
跨玩法动作承诺、阶段和结果                   -> 11
传统游戏 AI 感知机制                         -> 07
Boss 阶段与 ThoughtMode 适配                 -> 12
战斗/经济/社交玩法模式注册                   -> 05
跨层架构差距与落地顺序                       -> 08
角色能力图谱、认知包络与动态算力             -> 13
角色学习、模仿和技能进化                     -> 14
角色设定、言行表达、理智调节与灵魂规则边界   -> 15
通用玩法时序模型、调度与时间 profile            -> 16
战斗系统、角色技能、状态和资源               -> 战斗系统与角色技能，状态和资源/
编辑器能力开关、权限授予、预览与发布           -> 编辑器与能力权限治理/
玩法包分层、组合、编辑器应用与生命周期           -> 玩法包与编辑器应用治理/
战斗效果通道、环境场、生命/精神/灵魂规则     -> 战斗系统与角色技能，状态和资源/05
装备、药品、弹药、媒介、阵法组件与使用限制   -> 战斗系统与角色技能，状态和资源/06
职业/身份标签与跨维度战斗影响源              -> 战斗系统与角色技能，状态和资源/07
对象标签、元标签治理、编辑与版本边界          -> 战斗系统与角色技能，状态和资源/08
战斗空间/物理证据适配与语义结算协作          -> 战斗系统与角色技能，状态和资源/03
战斗动态原语、仇恨/恐惧/战意/士气             -> 战斗系统与角色技能，状态和资源/09
通用装备定义、栏位、触发器和变体                 -> 战斗系统与角色技能，状态和资源/11
自走棋装备、棋盘栏位、羁绊和随机奖励案例         -> 战斗系统与角色技能，状态和资源/12（未来单局运行时来源）
装备/玩法包编辑器草稿、预览、发布和同步          -> 编辑器与能力权限治理/05
生命状态、伤势、死亡连续性与灵魂关系         -> 战斗系统与角色技能，状态和资源/10
```

## 与已有文档的关系

- 角色档案、心智状态与 `CharacterMindFrame`：见 [8 月角色档案与状态核心架构](../8月分析/02-角色档案与状态核心架构.md)。
- 快慢链路、模型路由和性能分级：见 [运行时服务拆分、模型路由与性能预算](../phase1/core/01-运行时核心/角色智能体/09-运行时服务拆分、模型路由与性能预算.md)。
- 完整心智模型的正式源头：见 [Complete Character Mind Core Design](../superpowers/specs/2026-06-29-complete-character-mind-core-design.md)。
- 本目录进一步细化 Laya 快循环、思考模式、协同和表达，不把这些规划内容误写成当前实现。
- 通用玩法时序模型由 [16-通用玩法时序模型与编辑器设计](角色/16-通用玩法时序模型与编辑器设计.md) 唯一负责；战斗、经济、生态、社交和角色心智只定义各自 adapter 与领域结算，不重复建立专属时钟。
- 战斗对象标签与元标签的统一 owner 是 [对象标签、编辑与版本治理设计](战斗系统与角色技能，状态和资源/08-对象标签、编辑与版本治理设计.md)；01–07 只定义领域接点，复用 INF 注册、受限 selector 和原有 authority，不另建标签真值系统。
- 编辑器与能力权限治理由 [编辑器与能力权限治理](编辑器与能力权限治理/00-README.md) 独立负责；它消费 08 的标签治理合同，配置战斗目录 01–10 的能力、规则和权限，不重复定义技能、资源、状态或结算 owner。

### 4.18 A-Cognition 前置准备（2026-10-13）

四角色评估前置已拆为 `development_ready=true`、`calibration_ready=false`、`final_ready=false`。本轮只生成仓库外 preparation package：固定输入/MindFrame、U/P、candidate order、acceptable action provenance、target/visibility、split、分母和 provider/checkpoint pins；threshold 明确为 `not_frozen`。`char_d` 继续是隔离 authored fixture，字段缺口保持 `unknown/unavailable`，不进入 loader、roster、Godot Actor 或 active-control。当前无 runtime legal target，动作质量分母为 0，诊断/安全行为单独统计。A-Cognition 仍 `blocked/not_assessable`，A-Embodied 继续 blocked；provider 未启动、无动作执行、未修改 owner。
- 编辑器目录的跨领域同步矩阵登记 01–16、标签/元标签、角色能力/学习、时间、生命/灵魂和 Combat prefill 的接入边界；详见 [04-十月分析领域接入与编辑器同步矩阵](编辑器与能力权限治理/04-十月分析领域接入与编辑器同步矩阵.md)。

## 统一状态标记

战斗关系、条件、倾向和群体状态的增量设计见 [09-战斗动态原语、关系状态与战斗倾向设计](战斗系统与角色技能，状态和资源/09-战斗动态原语、关系状态与战斗倾向设计.md)，其中区分已实现基础与尚未实现的战斗合同。

- `[current]`：仓库已有代码、文档或验证入口可以支撑的边界。
- `[planned]`：本轮收敛的目标设计，尚未代表实现完成。
- `[deferred]`：明确暂缓，避免在本轮设计中隐式承诺。

### 4.17 四角色正式评估状态（2026-10-12）

本轮四角色正式评估未进入 development/calibration/final/independent holdout：新鲜 preflight 为 `evaluation_blocked`，provider calls `0`，final labels 未读取，policy/threshold/calibration revision 未冻结。固定 provider 恢复证据和本轮 preflight 路径见审查03 §4.17。A-Cognition 保持 `blocked/not_assessable`；A-Embodied、B/C、Godot 动作场景及动作执行继续关闭。

### 4.19 A-Cognition development 切片状态（2026-10-13）

本轮全量 `python -m pytest -v` 新鲜通过（`7862 passed, 2 skipped`）；固定 Laya 在 Windows→WSL localhost forwarding 下完成 CUDA health 和真实 `/v1/systemone=200` 服务探针。development 输入审查发现同场景四角色的 wire state 相同，故按题集缺陷停止当前切片，development calls `0`、质量指标未测量。已生成仅含 development 的 v2 角色可见输入候选，仍待来源审查；旧 calibration acceptable pairs 在检查源文件时暴露，须重建盲 calibration split。`action_target_quality_denominator=0`、`threshold=not_frozen`、`development_ready=false`（修订候选）、`calibration_ready=false`、`final_ready=false`；A-Cognition-diagnostic、动作质量门、A 完整验收和 A-Embodied 均 blocked。证据及修订包路径见审查03 §4.19。


### 4.23 Calibration 前置收口（2026-10-13，RW-29）

当前结论见[审查12](审查/12-calibration前置收口与独立题集门禁.md)。历史r2 reviewer自身未批准，lead日志复核批准另记，历史formal truth不可用；保留48条v4 CPU请求及digest，不把16条诊断4命中作为角色质量。新建独立v2输入24条/6个trajectory/三轨，独立reviewer已冻结22条fixture选择分母并个人批准；char_d缺口保持unknown，v5实际option token必须严格小于48。历史full pytest exit1不clean，本轮全量/Harness/token/wire/pins结果另记。calibration仍blocked，本轮不运行calibration/final/holdout、微调、具身、owner、Godot、B/C、玩法包、编辑器、自走棋或AD/Blender。详细设计回写见[RW-29](回写/README.md)。


### RW-29 v2独立审查与前置证据更新

新v2全新独立reviewer先冻结标签并亲自批准，实际verifier确认 reviewer_independent_approval=true、lead_audit_approval=true、formal_truth_usable=true，严格仅22条fixture选择（autonomous8、explicit6、role-sensitive8）；runtime动作/legality/owner/话语/receipt均0。角色敏感仅各参与者authored当前/过时可见证据，不是人格验证；char_d缺口unknown。24题实际token max46 <48，v4 48条digest精确重建；CPU health通过但live checkpoint revision未证明、阈值未预登记，calibration仍blocked、provider新调用0。docs/backend-contract/change-lifecycle Harness各exit0/cleanup passed。全量最终结果统一见审查12最终工程区块，历史full exit1保留。

### 2026-10-14 RW-32

修复后诊断已使用官方离线 CPU 实例完成 22/22 封存；旧 RW-32 的“18765 无服务、首题连接拒绝”只描述早期失败 attempt，原件保留。当前正式评分仍因独立 truth approval 缺失而阻断。


## 2026-10-15 本轮验证收口

用户要求本轮仅记录验证了 Laya 的 `choice` 输出类型，不再验证 Godot。Godot 与完整 live 链路保持未验证，不据此认定模型质量或领域执行通过。详见 [演示审查登记](审查/13-Laya角色运行演示审查登记.md#2026-10-15-用户收口仅验证-laya-choice-输出类型)与[回写登记](回写/README.md)。
