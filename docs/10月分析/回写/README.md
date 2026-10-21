# 十月分析设计回写登记

状态：`analysis/planned/non-authorizing`。本目录登记收敛规格/计划相对四个原始分析域设计的新增约束、实现顺序调整、范围收缩和未决差异；它不替代原始设计文档，也不授权运行时代码。

## 当前阶段三入口（2026-10-17）

阶段三 Task1–Task6 当前唯一汇总索引为[阶段三总收口审查](stage3-closure-20261016.md)。用户已授权继续整个阶段三，并确认产品政策由用户决定；因此历史条目中的“Task5/6 不启动”“须另行授权才能实施”只描述当时轮次，不覆盖当前授权。closure 中逐项验收矩阵、RW-50/51 更正及集中产品决策包为当前准据。阶段三仍 incomplete；不得将 deferred 改成非阻断。RW-44、facility repair deferred、禁止工作流及既有证据保护边界继续有效。

## 使用规则

1. 原始设计文档仍是语义来源；本目录只登记本批次为何采用当前 spec/plan 表述。
2. 每条回写必须包含来源文档、相对原设计的变化、当前状态、对应规格/计划和解除条件。
3. `aligned` 表示收敛文档与原设计一致；`narrowed` 表示在原设计允许范围内收缩；`changed` 表示改变实施路径但保留原目标；`deferred` 表示本批明确关闭；`blocked` 表示有设计方向但没有实现证据。
4. 回写登记不等于用户批准、provider 准入、owner admission 或运行时完成。

## 回写覆盖

| 回写编号 | 原始设计文档 | 变化 | 状态 | 收敛规格/计划 |
|---|---|---|---|---|
| RW-01 | 角色01、角色02 | Laya 采用官方 multilingual 基线；本地先探测，未发现可用本地 LLM 时走 API；模型协议、候选预算和微调由实测冻结。2026-10-10 已固定官方源码/权重 revision 并取得仓库外 WSL2/CUDA 裸服务探针；接入设计复用现有持久 L3 provider stage、driver/slots/gateway，choice 映射与生成式合同分开，显式取消与停机恢复分开。两持久来源与 staged job 四来源不可混算；角色 receipt 不代替领域 receipt | `changed; 接入责任设计已收敛/实施与验收仍blocked` | 规格01 §3.1.2/§3.2/§4/§5；规格02；计划01 Task1B/1A；解除条件：冻结输入/候选/协议映射，实施专用 adapter 和所需同 owner 来源扩展，再取得真实 admission、取消/旧结果/恢复、receipt/replay 与独立质量证据 |
| RW-02 | 角色01、角色02、角色11 | 首版一次选择完整“动作＋目标”；先做包络内完整候选实验，再决定生产受控候选集 | `changed/blocked` | 规格01、02、05、07；计划01、02 |
| RW-03 | 角色02 | A 单角色跨情境 → B 单角色连续 Boss → C 双角色连续协同；B/C 必须独立验证，动作底座复用 StreetCombatActorDemo，新场景不复用 StreetCombatDemo | `changed/blocked` | 总规格00；计划00、01、03 |
| RW-04 | 角色05、角色09、角色10 | 经济/社交作为同一心智模型的输入输出适配；L1 仍是唯一信息入口，不能因模式扩展创建第二套角色脑 | `aligned/narrowed` | 规格03、04；计划01 |
| RW-05 | 角色13 | 四角色评估新增 authored `char_d`，仅作 profile/dossier 评估输入；按审查05逐字段映射现有 schema，认知/compute 缺口不得用默认值填充，隔离 fixture 不进入正式 loader 目录；不自动成为 Actor、roster 成员或 active-control 身份 | `changed/blocked` | 审查05；规格05；计划01、02 |
| RW-06 | 角色15、战斗05 | Life/Presence/Soul owner 未准入时只提供权限过滤后的 unavailable/diagnostic 私有投影，不伪造 gate、灵魂数值或生命结论 | `narrowed/blocked` | 规格08、10、12；计划03、04 |
| RW-07 | 战斗02 | 资源采取集中迁移；capacity/base_capacity/locked/debt/recovery 与当前字段的映射须由 owner 审定，不能把现有 maximum/reserved 当同义项 | `changed/blocked` | 规格10；计划04 |
| RW-08 | 战斗11、玩法包07、编辑器05 | 通用装备编辑和领域合同保留；自走棋棋盘/回合/羁绊/奖励适配移出开放世界批次 | `narrowed` | 规格10、13、14；计划05 |
| RW-09 | 战斗12、玩法包07、编辑器05 | 自走棋作为未来单局运行时来源归档，关闭本批实现、owner 探测、active gate 和完成条件 | `deferred` | 规格15；计划06 |
| RW-10 | 角色16、玩法包/编辑器各域 | 通用时间、批次、receipt、preview 和 owner boundary 复用既有底座；package/editor 只能消费稳定合同，不能创建第二 clock/event store/authority | `aligned/narrowed` | 规格09、13、14；计划04、05 |
| RW-11 | 角色06、角色07、角色08、角色12、角色14 | 本批将自身状态、传统游戏 AI、ThoughtMode 和学习慢循环收敛到现有 L1-L4、MindFrame、能力/学习 owner；不创建独立 Boss AI、第二心智或独立学习事实库 | `narrowed/blocked` | 规格03、05、06、07；计划01、02、07 |
| RW-12 | 战斗01、战斗03、战斗04、战斗06、战斗07、战斗08、战斗09、战斗10 | 战斗目录的技法、动作、CombatPrefill、装备、影响源、标签、关系和生命设计由通用领域 owner/adapter 消费；规格只锁定边界、投影和验收，不把建议对象当作已存在 API | `narrowed/blocked` | 规格09–12；计划04 |
| RW-13 | 编辑器01、编辑器02、编辑器03、玩法包01–06 | 复用现有 patch registry/lifecycle、revision、event/receipt 主干；通用 catalog、scope application、grant/control-plane、preview sandbox 和缓存同步属于 admission 后的 planned projection，population-specific preview 不是通用 editor | `narrowed/blocked` | 规格09、13、14；计划04、05 |
| RW-14 | 角色动作工作流01 | 确认 XSXB Animation Director 外部工程及现有 Director/Rig 校准/manifest/资产校验基线；计划不再把工程位置当作未知，但完整 RetargetJob→Blender bake→GLB qualification 仍须逐段核实 | `aligned/changed-baseline` | 规格16；计划07 Task1–8 |
| RW-15 | 角色04语音与多模态表达 | 逐项复核后确认本批保留三语音路径、Laya语义控制、表达权限和接收方L1边界；SpeechLease仅细化可验收取消合同，没有路线偏离 | `aligned/no-design-deviation` | 规格08 §8/§11.1；计划03 Task4/6 |
| RW-16 | 编辑器01–05、玩法包01–08、角色16的编辑器部分、角色动作工作流01 | 用户要求第7项编辑器与第8项AD暂不处理；规格14/16与共用计划05/计划07暂不启动，计划05玩法包任务也不在当前1–6中单独启动。原设计目标保留；已有合格动作、领域时间与必要权限校验继续适用 | `changed; execution paused-by-user` | D15；规格00/13/14/16；计划00/04/05/07及索引。用户明确恢复范围后再核对依赖和新鲜证据 |
| RW-17 | 角色01、角色02、角色05、角色10、角色11、角色13 | 本批新增 D16：质量评估拆为关闭受控失误的基础选择质量轨与固定 seed 开启角色失误的表现轨；两轨均保留角色能力上限，输入/题目错误、候选缺陷、模型选错和执行失败分开归因。候选先审计完整 U，再实测受控 P；题型、结构化可接受动作集合、轨迹隔离、覆盖/选择/延迟/校准分母及微调触发写入规格05 §4.2.2–4.2.3，正式阈值在最终留出前冻结，未填猜测数字 | `changed/blocked` | D16；规格05 §4.2–4.2.3；计划01 Task1C；计划02 Task1–3/6；解除条件：来源审核夹具、真实候选 compiler、两轨评估和独立 final 证据 |
| RW-18 | 战斗02 §1.2–1.5、§2、§5 | 第四项细化 D06 集中切换并新增 D17：暂停新资源承诺，已有 reservation 按原合同完成、consume/release，未结清则保持 pending；迁移不主动取消动作或清零。明确 minimum/maximum/current/reserved 的当前语义不等同 capacity/base_capacity/locked/debt/recovery；保留旧历史，提交后按 owner receipt 后继修复，不伪造全局回滚；非 Combat consumer 使用同一合同 | `changed/planned; implementation evidence pending` | 审查06；规格10 §3/§3.1；计划04 Task3；原设计战斗02 §12。解除条件：目标字段映射、兼容 decoder、真实排空/迁移 receipt、full/checkpoint+tail replay、非 Combat consumer 与角色私有投影回验 |
| RW-19 | 战斗05、战斗09、战斗10、角色06/08 | 第五项细化 D11 并新增 D18：实际代码只有资源/BodyInjury、SurvivalAuthority、ProfileActivationAuthority、EntityCausalProjection、RuntimeContinuityState 和角色 L1 continuity 基础；没有完整 LifeState、EntityPresence 或 Soul/identity owner。缺 owner 时只向角色提供权限过滤后的 unavailable/diagnostic；不把 survival、activation、标签、模型输出或未知字段升级成 Life/Soul 事实。真实 owner 准入后回验角色感知、表达、决策及 receipt/replay；不以完整 Soul 验收阻断角色基础 | `changed/planned; owner admission pending` | 审查07；D11/D18；规格12；计划04 Task5；原设计战斗05 §14、战斗10 §13。解除条件：真实 owner/API、事件/receipt/replay、隐私过滤、部分失败恢复和角色私有投影回验 |
| RW-20 | 角色02、角色03、角色07及总规格的 B/C 载体边界 | 第六项细化 D12 并新增 D19：B 单角色连续 Boss、C 双角色连续协同必须使用新的隔离 Godot 场景；`StreetCombatActorDemo` 只复用已验证 Actor、动作库、Motor、authority 和资格证据，`StreetCombatDemo` 不作为 B/C 场景语义来源。模型只产生选择/提案，实际 domain owner 提交世界结果，Godot 只做具身/表现。A、动作底座、静态合同测试不能代替 B/C。 | `changed/planned; scene/owner/runtime evidence pending` | 审查08；总规格00、规格07/08；计划00 Task6A、计划03 Task6A；解除条件：独立 actor admission、Boss/协同 owner、真实 Laya→gateway/admission、owner/authority receipt、replay/checkpoint、Godot boundary message 和可见结果证据 |
| RW-21 | 角色01、角色05、角色10 | Task2A 实施将既有 L1 self-body/percept 事件投影到 actor-private MindFrame workspace，并让 L2/L3 prepared request 携带冻结 frame；为保持旧 runtime 兼容，事件投影先由 runtime 内存缓存承载，正式 Laya/admission 持久来源、expiry 和 wire choice 仍按 RW-01 待后续任务冻结。 | `changed; projection implemented, durable provider boundary blocked` | 规格01–04；计划01 Task2A/4/5/1B；解除条件：同一 admission/coordinator 持久来源扩展、真实 provider request/response、取消/迟到拒绝和 replay 证据 |
| RW-22 | 角色01 Laya/admission | 2026-10-11 Windows backend + WSL localhost forwarding 的 live 输入为 `ingest_siming_output` / `agent_full_auto`，但 15 项候选是无目标意图，`observe` 只到 `stage_ready`；本轮只读 owner 映射发现没有适用于该目标的低风险已准入 L4→domain owner 路径，按 Task1A 停止 live 动作尝试。Activation lock receipt 不是领域 owner receipt。五项 live 负例均未取得本轮真实 evidence（复核时服务停止）。fresh focused Laya 55 passed；受影响测试复跑 4 failed/1 passed，dialogue 单项 5 次及文件 11 项均通过但竞态未复现。旧轮 7821/2/4 原始输出不可追溯；本轮全量 pytest 新鲜运行 7820/2/5；适用 `model-provider-readiness` Harness profile 新鲜通过。HEAD 对照显示四个静态/资产断言差异没有本轮文件改动；dialogue 失败仍未归因。 | `changed; Laya L3 partial evidence; action vertical and live negatives blocked/unverified` | 审查03 §4.9；计划01 Task1B/1A；解除条件：先以现有注册表完成有界 action+target、`CharacterExecutionContract`、L4 映射与真实 owner ingress 只读审查；存在准入合同后再取 Windows→WSL live owner receipt，以及五项零 cognition/L4/owner/writeback 的关联负例证据；全量 pytest 与适用 Harness 新鲜运行并分类。不得新增 owner/动作/权限/协议凑证据 |
| RW-23 | 角色动作资产、Laya A 阶段与 package 替换 | 第二阶段静态资产审计确认 `StreetCombatActorDemo` 仅为动作底座/资格基线；Laya live 请求为 `ingest_siming_output + env_lamp`，没有 Godot Actor、GLB、clip、contact marker 或领域 owner 执行。稳定 Actor/profile/backend identity 与 `semantic_action_id`；资产 package binding 需独立 revision，活跃动作 pin 旧 revision，只在既有安全边界提交替换，失败保留旧 binding。`short_punch` 仅 backend 兼容语义，不是正式资产动作或 `unarmed_punch` 的自动 alias。 | `changed/planned; replacement transaction and A execution admission blocked` | [审查09](../审查/09-资产复用与动作可替换准入矩阵.md)、审查03 §4.10、规格07/16；解除条件：actor/profile/backend identity/control mode 固定、qualified package 和 binding revision、完整语义动作+目标、contact/physics evidence、现有 owner receipt、可见 Godot boundary/Actor/Motor 结果及拒绝/取消/stale 零写入证据。 |
| RW-24 | 角色01/02、角色能力与动作准入 | CandidateCompiler 已接入 L3 prepared request；先形成合法全集 U，再按 envelope/policy/affordance 形成 P，冻结完整动作＋目标记录及 wire label 映射。真实 `/v1/systemone` 字符串 wire 未改；unknown/duplicate/reordered label、stale revision、invalid/不可见/撤权目标和 affordance blocked 均拒绝。L4 保留 semantic action 与 target refs，但既有 owner admission 不存在，结果停在 blocked/diagnostic，不生成 ActionAttempt；无目标不进入动作选择质量分母。 | `changed; candidate freeze implemented, owner ingress blocked` | 规格05、07；计划01、02；审查03 §4.12、审查09 §13；解除条件：现有 owner admission/receipt、完整 ActionAttempt/physics/contact/replay/checkpoint 和 Godot boundary live evidence。 |
| RW-25 | 学习证据、动作承诺、四角色夹具与 live mapping | 学习阶段/八维掌握/七因子难度、source/privacy/expiry/duplicate fail-closed 和 owner settlement gate 已接入现有 store；L4 合同覆盖 stale/expired/revoked/interrupted/rejected/missing/late，owner gap 只生成 diagnostic；char_d 保持隔离 fixture。固定 Laya 端口当前不可达，精确 focused 集合 `59 passed` 但真实 positive mapping 未取得；全量 pytest 新鲜为 `7831 passed, 2 skipped, 7 failed`，7 项单独复跑为稳定的静态/资产输入或旧 runtime/action receipt 合同差异。 | `changed; static contracts ready, live/owner/final evaluation blocked` | 审查03 §4.13、审查05 §7.1、审查09 §14；解除条件：真实 provider/admission receipt、owner ActionAttempt/physics/contact/replay/Godot evidence、四角色 source review 与全量失败处理。B/C、玩法包、编辑器、自走棋、AD/Blender/GLB 继续关闭。 |

### 已逐份核对、未发现实质设计偏离的辅助说明

角色的五份“说明”文件用于实现映射和验证提示，不是额外的独立设计主题。它们已在覆盖矩阵中逐份映射到设计/规格/计划；其中建议接口名和字段仅作为调查线索，实施前仍须映射现有代码，不会因出现在说明中就被冻结为新API。

- [角色01运行时说明](../角色/01-角色心智模型与模型驱动运行时说明.md)
- [角色02快慢循环说明](../角色/02-Laya快循环与快慢思考战斗说明.md)
- [角色03通信说明](../角色/03-协同作战与信息通信说明.md)
- [角色04多模态表达说明](../角色/04-角色语音与多模态表达说明.md)
- [角色05模式适配说明](../角色/05-玩法思考模式适配与L1信息获取说明.md)

覆盖口径：42份设计正文全部有末尾“本批规格与计划回写”审查记录；其中记录设计收敛/基线变化的条目在 RW-01–14，RW-15 明确语音来源无路线偏离，RW-16补记用户要求编辑器/AD及共用计划05暂不启动，并已同步15份相关原始设计；RW-17补记D16两轨评估及候选/质量合同细化，已同步6份角色原设计末尾；RW-18补记D17迁移窗口、字段不等义与提交后恢复边界，已同步战斗02末尾；RW-19补记D18真实 owner 缺口、unavailable/diagnostic 投影和角色基础解锁边界，已同步战斗05与战斗10末尾。另5份辅助说明已逐份核对并在矩阵登记，无额外设计偏离。回写表示审查和可追踪，不等于运行授权。

## 执行资格结论

最新范围以 [D15](../审查/03-实施待决收敛与验证闸门.md) 为准：规格14/16和计划05/07为 `paused-by-user`，不启动编辑器/AD专项调查、实现或验收，也不作为当前待决项1–6的完成条件。下述历史缺口继续登记，暂停不表示已解决；已有合格动作与必要权限边界仍适用。RW-16同步写回相关原始设计末尾。

当前不能把整批 spec/plan 当作已批准的运行时实施授权：所有收敛规格/计划仍是 `non-authorizing`，运行时代码实施需要用户审阅批准对应规格/计划。Laya provider/checkpoint、候选与质量阈值、`char_d` 映射、资源迁移、Life/Presence/Soul owner、Godot 新场景和通用 editor control-plane 仍缺相应证据；这些是各自任务的准入或验收条件，不是必须全部先解除才能启动角色基础的阻断。AD工程位置已确认，未齐的分阶段证据仅限制依赖它的动作专项。处理顺序及阿博档案用途见 [实施闸门 §4.1–4.2](../审查/03-实施待决收敛与验证闸门.md#41-处理顺序与阻断范围)。完成来源回写只解除“设计追踪缺口”，不替代任何相关能力的实施和验证。

允许开展的下一步是只读代码映射、owner/provider admission 和测试夹具准备；进入运行时代码修改前，必须取得用户对规格/计划的审阅批准，再按对应 plan 的局部前置实施，运行 focused tests 和 Harness profile。Goal 仅在用户明确要求时建立；不得将尚未实现能力的最终验收结果反过来作为对应实施任务的开工前置。

## 原始设计回写位置

每个受影响的原始设计文档末尾新增“本批规格与计划回写”小节。该小节只记录变化与门禁，不修改原设计章节的历史语义：

- 角色设计正文：所有变化或无偏离审查均在 01–16 原文末尾留记录；五份角色说明逐份见辅助说明清单和覆盖矩阵。
- 战斗：01–12 中发生通用化、实现边界或延期变化的来源。
- 玩法包：01–08 中发生实现范围或 editor admission 收敛的来源。
- 编辑器：01–05 中发生 control-plane/运行时边界收敛的来源。
- 角色动作工作流：工程位置与代码基线已由 RW-14 回写；实际烘焙及资格链仍逐段准入。

总规格、覆盖矩阵、完整性报告和计划索引均引用本登记，避免仅凭收敛 spec/plan 推断原设计已被完整实现。
# 2026-10-13 A-Cognition 前置合同回写

本轮将原先单一 fail-closed preflight 收敛为 development/calibration/final 三态合同。development-ready 只检查开发输入合同完整，不预设最终阈值；calibration-ready 需要开发结果、冻结候选 policy/分母/候选阈值和非空 calibration split；final-ready 需要冻结 calibration 参数、非空 independent holdout，且不得读取 final labels 后再调参。

准备包新增 char_d 逐字段 source/schema/revision/privacy/required/presence manifest、逐题 U/P/candidate order/acceptable action/target visibility/分母清单。char_d 缺失字段保持 unknown/unavailable；无合法 target 的题目不进入动作＋目标选择质量分母，不补入 `unarmed_punch`、`sword_slash` 或 `short_punch`。本轮没有 provider、模型评估、动作执行或 owner 变更，A-Cognition 与 A-Embodied 状态保持原结论。

## 2026-10-13 A-Cognition development 停止与回写

来源为角色13 §9/§12/§22、规格05 §4.2.3、审查03 §4.18–4.19 和审查05 §7.4–7.5。原 v1 四角色题集的角色投影未进入 Laya wire state，不能测量四角色差异；本轮真实 provider 探针通过后仍停止 development，逐题响应与指标均未产生。development-only v2 候选包位于 `D:\Temp\paralls-preparation-20261013-v2-development\development-preparation.json`，状态 `source_review_pending`，解除条件是独立审查角色提示、acceptable set 与隔离边界后重新运行 development。原 calibration 标签在检查源 YAML 时暴露，解除条件另含重建独立盲 calibration split。变更性质为 `changed/blocked`；`action_target_quality_denominator=0`，候选 policy/threshold 未提出数值且不冻结。A-Cognition-diagnostic、动作质量、A 完整验收及 A-Embodied 均未释放，未启动微调或任何动作 owner。


## RW-26：A-Cognition development 输入链修复（2026-10-13）

来源为角色01/02/13，收敛到规格01/03/05、计划01 Task1B/1C。状态为 `changed; input repair implemented, fresh development/verification pending`：准备器旁路角色投影与实际 provider serializer 的双重丢失改为 MindFrame/gateway 冻结请求及共享 `build_wire_request`；state 复用既有获准 profile summary，并传递注册 envelope/policy，完整 wire 与 U/P/label 映射共同审核。char_d 保持隔离 metadata，缺失值不补造；外部 v2 不作为生成器输入真值。原始设计与上述规格/计划均已有本条实现差异回写。

本轮证据导出根目录 `D:/Temp/paralls-acognition-development-20261013-inputfix/`；逐题结果和新鲜验证待调用完成后追加到审查03/05及本登记。解除本轮 development 阻断需有效来源/隐私/冻结输入审查和真实 fixed provider 请求；完整 A、A-Embodied、动作＋目标质量门仍需各自证据。原 calibration 版本污染不能恢复盲性，必须独立重建；final/holdout 保持封存，policy/threshold 不由本轮16题冻结。


### RW-26 development 实证更新（2026-10-13）

状态更新为 `changed; input repair and 16 real development calls completed; formal quality/embodiment not accepted`。v3 canonical package digest `b579d06613831eaf97ae0faab3e280e67bf4d8b041abe34c5a02ddcb0e09d1a8`；16 有效输入/16真实调用/16成功映射。authored 暂定诊断安全 7/16，独立审查评分、角色敏感及完整动作＋目标分母均为0，provider errors/mapping rejection/truncation 均为0；p50 30.497 ms、p95/max 447.196 ms。逐题与冻结包见 `D:/Temp/paralls-acognition-development-20261013-inputfix/development-live-v3/`，详细来源、边界、unknown 与验证记录见审查03 §4.20、审查05 §7.6。

原始设计/规格/计划回写已在本包 source pin 冻结前完成，冻结后未再修改。相关回归97 passed；本轮全量pytest等待最终值，Harness all五项通过后因Godot runtime环境blocked、后续未执行且cleanup passed。旧calibration永久不具盲性，须独立新题重建；final/holdout封存。阈值/policy未正式冻结，完整A与A-Embodied不释放。


### RW-26 本轮最终工程验证（2026-10-13）

本轮全量 `python -m pytest -v` 已新鲜完成：**7871 passed、2 skipped、106 warnings，1483.60s，exit 0**。原始输出为 `D:/Temp/paralls-acognition-development-20261013-inputfix/pytest-full.log`；相关回归仍为97 passed。本次结果替代本节先前“全量pytest等待”的执行状态，不替换历史记录。

同一证据根目录 `post-call-audit.json` 证明全部16条完整 wire/input digest 与冻结 P/label mapping 一致且无截断；`repeatability.json` 证明重新生成取得相同 package canonical digest；`source-pin-migration.json` 保留来源 hash 迁移历史。Harness all 的范围仍为五项通过、Godot runtime 环境 blocked、后续未执行、cleanup passed，不能将 pytest clean 或 docs 检查解释为 Harness all、完整 A 或 A-Embodied 通过。calibration 独立重建与 final/holdout 封存保持原记录。

### RW-27 Development 真值审查、criteria 合同与有限对照（2026-10-13）

盲审存在已记录局限，未设置 independent approval；7/16 是 authored 暂定数，独立、role-sensitive、完整动作＋目标分母均为 0。criteria 官方允许 `label -> description`，保持稳定 label、candidate/target mapping 和 wire schema；描述、顺序及 digest 进入冻结内容，不能删除候选。baseline、description、anonymous-summary、reversed-order 全部尝试保留：description 支持候选语义不足，匿名摘要无身份名称效应证据，顺序证据不足。旧 calibration retired/contaminated，须独立新题、来源审核、轨迹隔离和封存标签重建；final/holdout、runtime legal、owner receipt 和具身门禁不因 provider 成功而释放。

**批准前历史快照（当前状态由下方RW-28替代）：** 2026-10-13 development v4：候选 description 已冻结到 `CandidateCompiler`，新 reviewer 包生成器已通过泄漏合同测试；旧 reviewer 永久 retired/non-independent。新包未获独立批准，未进行 provider 调用；autonomous_decision、explicit_instruction_diagnostic、完整动作＋目标正式分母均保持 0，calibration 继续 blocked。


### Development v4 当前回写（2026-10-13，RW-28）

[current] 候选语义合同 `candidate-semantics:v4:1` 由 CandidateCompiler 生成并可复现，label/候选/target/description/顺序/mapping/digest一起冻结。旧盲审SHA `db910db888e0b4a5c88100b0db29dbcd9378dccb586e67b90499d423f7dccc20` 永久retired/non-independent。全新r2隔离审查只读净化包，实际3次read命令与accidental_exposure=[]核验后批准 `independent_review_approved=true`，调用前冻结48行真值。

48次真实调用完成：原16条明确指令诊断独立正式分母16、命中4；新增8题×4角色中autonomous16/explicit16分轨，正式分母均0，因为没有来源要求必然角色差异、三个候选都可接受。不得把相同选择判为失败。动作＋目标分母仍0；A/B/C缺认知、hard limits、compute、authority；D另缺人格，均不补默认值。provider error/mapping rejection=0，CPU p50=793.945ms、p95=910.455ms。原v3→v4选择变化6/16，历史description→v4变化11/16，有输入与设备混杂，不能写成质量提升；旧7/16不是正式正确率。

48条完整追溯与wire一致；state无截断，18种label+description中3种被48token上限截去末尾句号，语义完整。候选合同和新审查已通过，但role-sensitive题仍不能区分质量，calibration blocked，不触发微调。A-Cognition仅development证据；A-Embodied未运行/blocked；Godot本批禁止且历史环境blocked；Harness all未运行且不能称通过。backend-contract/change-lifecycle通过并cleanup passed；全量pytest最终重跑结果见后续工程验证记录。

完整来源、逐题覆盖、三张边界图与证据索引见 [审查11](../审查/11-development-v4真值审查与候选语义冻结.md)。本批偏离原设计的部分为先冻结认知fixture语义、分轨审查，不把fixture别名升级为动作注册/owner执行；新增题的来源条件仍不足以要求不同答案。[planned] 先改善有来源可区分development题，满足门禁后才独立新calibration；[deferred] 无新增延期能力。


### RW-28 最终工程验证与清理（2026-10-13）

新鲜全量 `python -m pytest -v`：**7920 passed、2 skipped、1 failed、106 warnings，1464.29s，exit1**。唯一失败为 `test_main_cold_start.py::test_independent_population_fixture_and_verification_cold_entry[seed]`，population offline dialogue fixture 查找 activation_active 事件时 StopIteration。独立复跑 **1 passed、22.09s、exit0**，根因未证实，不能用复跑覆盖全量失败；pytest full gate **not clean**。该模块本批未修改，未扩展到population/owner/B-C修复。

相关focused76项与v4 runner20项通过；backend-contract、change-lifecycle、docs Harness均exit0、cleanup passed。Harness all本批未运行（用户禁止Godot且历史环境blocked），不称通过。本轮自有临时目录已在导出退休preparation及SHA后删除；未创建自有provider/helper，已有用户Laya服务与系统wslrelay保留，git status --short -- .harness无本批改动，已有资料保留。

日志与机器可读状态见外部证据根 `D:/Users/User/Documents/paralls-evidence/october-development-v4-20261013/` 的 pytest-full-final.log、pytest-cold-start-rerun.log、verification-summary.json、repeatability.json和cleanup.json。本记录替代此前“最终pytest正在执行”的状态，不替换历史证据。calibration仍blocked，A-Cognition未正式接受、A-Embodied/Godot未验收。


## RW-29：calibration 前置收口与独立题集重建（2026-10-13）

来源为角色01心智模型、角色02 Laya快循环、角色13能力与算力设计，收敛到规格05、计划01 Task1D、审查03/05/11及新增[审查12](../审查/12-calibration前置收口与独立题集门禁.md)。角色01/02原设计末尾已同步回写。状态为 `changed/blocked; calibration preclosure only`，不授权模型调用或跨域实施。

本记录明确替代RW-28的批准结论：历史r2 `reviewer_independent_approval=false`，`lead_audit_approval=true`，`formal_truth_usable=false`；保留reviewer read log、原始truth和lead复核证据。旧reviewer误见角色级acceptable_paths的污染永久记录，不能通过重命名恢复盲性。v4冻结描述、48条CPU请求与digest保留；诊断结果不升级成角色质量，32条role-sensitive分母0。

新增独立v2输入24条、6个新trajectory、autonomous/explicit diagnostic/role-sensitive三轨，差异逐字段保留来源/revision/privacy/visibility及MindFrame/U/P影响；char_d缺口不补。v5短描述和实际option-token严格小于48门用于新包，description/order/mapping重新冻结。独立reviewer已先冻结acceptable sets并个人签署，lead分别审计，actual verifier通过；仅22条fixture选择真值可用。wire追溯与实际token审计已取得；live checkpoint attestation、预登记阈值与工程clean最终证据仍分别验证。

历史full pytest exit1保留not clean；本轮新鲜完整结果及相关Harness导出待最终验证追加。外部证据根 `D:/Users/User/Documents/paralls-evidence/october-calibration-preclosure-20261013/`。本轮calibration/final/holdout调用0，微调、具身、owner、Godot、B/C、玩法包、编辑器、自走棋和AD/Blender不启动；不回收系统wslrelay或用户已有服务。A-Cognition正式质量未接受，A-Embodied/Godot/Harness all不因离线前置证据通过。


### RW-29 v2独立审查与前置证据更新

新v2全新独立reviewer先冻结标签并亲自批准，实际verifier确认 reviewer_independent_approval=true、lead_audit_approval=true、formal_truth_usable=true，严格仅22条fixture选择（autonomous8、explicit6、role-sensitive8）；runtime动作/legality/owner/话语/receipt均0。角色敏感仅各参与者authored当前/过时可见证据，不是人格验证；char_d缺口unknown。24题实际token max46 <48，v4 48条digest精确重建；CPU health通过但live checkpoint revision未证明、阈值未预登记，calibration仍blocked、provider新调用0。docs/backend-contract/change-lifecycle Harness各exit0/cleanup passed。全量最终结果统一见审查12最终工程区块，历史full exit1保留。

### RW-30 固定Hub缓存身份门与正式calibration阻断

2026-10-14按固定官方缓存离线启动，`snapshot_download(local_files_only=True)`解析固定Hub repo/revision；固定权重大小与SHA匹配。官方源码对已存在本地路径不设置`Agent.revision`，Hub repo ID分支才由snapshot解析revision，故自有provider改用Hub ID并设置固定HF cache/offline/revision与CPU环境，不改官方源码或adapter。独立端口18765的同一实例health仅loaded multilingual、revision精确、checkpoint device CPU，真实`/v1/systemone`为200；请求前后身份稳定。PID 5802为本轮owned并已回收，既有PID 555/8765未触碰。证据在`D:/laya-probe-cache/`。

threshold approval 与 v2 truth approval 已复核，新的同实例 health attestation 补齐 checkpoint 门后，正式calibration已执行。22条请求先逐题封存再读取标签；provider error/mapping error均0。autonomous 0/8、explicit diagnostic 0/6、role-sensitive 1/8，三轨均未达阈值，Policy A失败。archive digest为`sha256:28156259028341ea03b67de11f5b8a97f3daa624808de497b3427edab2caf5b1`，scored digest为`sha256:2113662a7d64ec26dcc3ab78c5abddd78e2e4a97f04fe2dab1a4a66d8a2cd109`。final/independent holdout仍封存，未启动训练、微调或关闭范围；A-Cognition正式质量结论为本轮 calibration fail，A-Embodied独立 blocked。

### 2026-10-14 封存后核对与归因限制

本轮正式calibration实例为PID 6110，启动时间 `Wed Oct 14 15:46:02 2026`、端口18765；前序身份探针PID 5802与正式实例分开记录，两者均已回收。正式实例的前后health记录loaded仅multilingual、固定checkpoint revision、实际checkpoint device CPU。身份attestation与准入记录分别位于仓库外 `D:/laya-probe-cache/checkpoint-live-attestation-20261014.json`、`D:/laya-probe-cache/october-admission.json`，逐题archive/score位于 `D:/laya-probe-cache/october-calibration-run-20261014/`。

封存响应的usage显示21/22条 `truncated=true`，同21条含 `truncated_questions=[choice]`；state丢弃55–1067 token。冻结评分仍为autonomous 0/8、explicit diagnostic 0/6、role-sensitive 1/8，有效样本字段仍为8/6/8，分母、标签、阈值与逐题记录不改。候选option token审计不能证明完整state进入模型；现有输入截断限制将失败全部归因于模型选择能力，必要领域微调触发条件尚未成立。本轮不训练，不修改同批输入后重测，不以慢模型替代质量结论。外部 `post-archive-token-audit.json` 保留逐题usage。

封存完整性复核：score以去除自身digest字段后的canonical JSON（UTF-8、sort_keys、ensure_ascii=false、紧凑分隔符）重算，与登记 `sha256:2113662a7d64ec26dcc3ab78c5abddd78e2e4a97f04fe2dab1a4a66d8a2cd109` 一致。archive采用同口径重算为 `sha256:a9169483075a17220ccd75ea845d507d94327c88fec75cd5e1444e87c639dbb8`，与登记 `sha256:28156259028341ea03b67de11f5b8a97f3daa624808de497b3427edab2caf5b1` 不一致；原封存前image/生成口径尚未恢复，不能称archive digest完整性已验证，也不据此推断篡改。保留原文件及登记值，此证据缺口需关闭后才能接受正式证据链。

A-Cognition保留本轮失败，仍缺完整输入/token门及archive完整性收口、后续独立final/holdout和runtime完整动作＋目标/legality/owner/receipt验收；22条fixture不能证明完整人格、认知上限、算力或具身质量。final/holdout未读取、未运行，A-Embodied独立blocked；Godot及其他关闭范围不启动。


### 2026-10-14 本批规格与计划回写：RW-31 calibration 只读取证

[current] 本轮原证据未重写；新只读诊断与三图见 [仓库外取证报告](D:/laya-probe-cache/calibration-audit-20261014-root/report.md)，逐题/清单/验证见同目录 per-question.json、inventory-expanded.json、verification.json。此项修正前文“archive原口径未恢复”的现状：历史发送命令明确 archive=canonical(records数组)，UTF-8、对象键排序、数组原序、ensure_ascii=false、compact、无末尾换行，185143字节，重算281562…一致。旧审计错误套用全对象去自身digest口径；score211366…与22题request/response digest也一致。records封存不覆盖顶层health/process，原HTTP抓包及服务端token IDs未保存，均unknown，不声称全链verified。

[current] 冻结prepared context state、wire与发送record逐题相同；正式发送直接取冻结wire，绕过runtime backend/provider.complete。固定tokenizer与Laya纯sequence代码离线复现全部22题usage：max_len1024/head_max_len256，题头195/152加SEP后state room828/871；21条在common.build_sequence取state_ids[:room]丢尾55–1067，唯一muted_bell participant04无截断。不是仅审计记录截断。原评分0/8、0/6、1/8及valid_samples8/6/8保持，不删除题、不缩小正式22分母；总观察命中1/22，不称0/22。历史评分漏检usage.truncated，与冻结invalid_handling.truncated合同冲突；calibration完整输入验收blocked，微调触发条件不可评估。另发现发送脚本封存前已加载含标签truth以筛正式ID，“封存后才读取标签”不能证明完整隔离；是否泄漏到模型unknown，不能擅自断言。已暴露calibration不是盲集或holdout。

[planned] 仅提出完整state+head预算门与足够max_len传输方案、truncated评分拒绝、无truth的ID-only准入及明确archive范围测试要求，均未实施；保留fixture/source/truth/U/P/阈值。扩大预算也会使模型看到原未见尾部，必须重新冻结transport/model-input digest、保留原digest，并由fresh独立reviewer复核合同及暴露边界；任何语义/候选/来源改变另冻结对应输入，不能覆盖原证据。细节与对应测试要求见外部报告，不授权下一轮调用。

[deferred] final/independent holdout继续封存未读未跑；A-Cognition质量未验收，A-Embodied/Godot/B/C/玩法包/编辑器/自走棋/AD/Blender保持关闭。阈值 manifest digest 重算一致且锁定 `sha256:a4bb6f41bc165ed1a645550ee54a7e1830ff5f5dbd8843bb73ecfbf6b6517ba1`。本轮provider/训练调用0，无运行时代码变更，不跑全量pytest；本条为取证回写，不是修复或运行时验收。
@@
### RW-32：calibration 输入完整性、评分有效性与标签隔离修复（2026-10-14）

## RW-33：Laya 角色运行演示（2026-10-14）

来源：角色01/02、规格02及本批用户明确演示目标。相对原设计收窄为独立 Godot 观测场景，复用既有 backend 链路和 StreetCombatActorDemo 动作底座，不引入战斗语义、第二调度器或新 owner。状态：`changed/planned; live provider/L4/owner/Godot evidence pending`。对应规格17、计划08、审查13。解除条件：真实 provider 请求/choice、L4返回、Godot边界消息、第二事件回合、失败/取消负例与截图/trace证据。

见 [calibration-repair-20261014.md](calibration-repair-20261014.md)。早期 attempt 因18765服务未监听而停止，其原件保留；后续官方离线CPU实例完成22/22封存。当前正式评分因v3独立truth批准缺失而阻断，旧archive/score保留，final/holdout未读取。

### RW-32修复后诊断更新

工程修复与 focused 回归通过；官方离线 CPU provider 完成合成 preflight 与 22/22 正式请求，完整需求最大 2081、usage 全部未截断。独立 gate 不能从 v3 文件确认旧 truth approval 对预算变更仍适用，正式 scorer 未运行，Policy A 未判定。原 archive/score 保留，final/holdout 未读取。

### RW-32 独立批准后的诊断收口

上段2081为历史预检估算，固定官方规则重算最大2091且22/22对齐封存usage。独立reviewer新签署确认旧truth适用于v3实际输入，仅限已暴露calibration诊断；原archive派生评分为0/8、0/6、1/8，Policy A未通过。普通运行时预算只在显式启用时检查，v2历史执行身份/读日志仍缺绑定；未运行final/holdout或训练。详见[RW-32后续](calibration-repair-20261014.md)。


## 2026-10-15 用户收口：仅验证 Laya choice 输出类型

按用户明确要求，本轮到此收口，不再验证 Godot。验证范围仅记录为 Laya 的 `choice` 输出类型；不扩展到 `score`、`noul` 或其他输出类型。合同/回归测试与历史 provider 证据按原轮次保留，不作为本轮真实运行证据。

Godot editor/runtime、按钮交互、截图/录屏、第二事件回合及完整 `raw_fact_event → backend → Laya → L4 → Godot` live 链路均未验证，本轮不再安排。暂停本轮这些验证要求不等于它们已通过，也不表示领域 owner 执行或角色选择质量已验收。L4/owner receipt 与 A-Cognition 的既有未验收状态保留。本条覆盖前文要求本轮继续取得 Godot 运行证据的安排；实现范围和原始验收设计保留供后续另行推进。

## 2026-10-15 backend 收口与局部阶段三续行

本轮用户授权顺序：真实 backend choice 回合 → 计划02/03角色剩余基础 → 阶段三局部准入。阶段三专指规格09–12／计划04通用领域接入，与计划03和A/B/C不同。先复用当前实现与新鲜证据，仅核对实际依赖；不重做整批静态审计。

真实回合须由事实解析、privacy/visibility投影、cognition admission及原coordinator/driver进入MindFrame、CandidateCompiler U/P与冻结映射、gateway、固定官方离线multilingual CPU Laya、choice、accept/freeze/resume和实际L4。显式启用共享完整预算门，保留同turn/request的实际usage与阶段receipt；模型接纳、L4合同接纳、owner提交分列。第二不同事件及取消/迟到、provider不可用复用现有负例路径。此条恢复backend-only验证，不恢复Godot安排。

计划04 Task1–2按局部API/owner依赖实施，阶段准备、开始实施、合同通过、最终验收分别记录。缺某consumer API仅阻断该consumer；没有soul owner的结果等待计划04，不能反向阻断所有通用工作。Godot、领域执行和模型质量均未验收。Policy A保持autonomous 0/8、explicit diagnostic 0/6、role-sensitive 1/8；真实backend回合不能补算质量。禁止final/holdout、训练、Godot启动或交互/截图/录屏及非choice类型验证；B/C、玩法包、编辑器、自走棋、AD/Blender继续关闭。

验证：focused、完整pytest、适用backend Harness、git diff --check；不运行Godot profile或Harness all，历史all未通过状态保留。证据导出仓库外，仅回收本轮自有进程与临时数据。实现结果另附本批回写，不把此准备登记写为验收通过。


## 本批规格与计划回写：RW-34 backend choice与基础合同局部实施（2026-10-15）

本轮实际结果见[RW-34批次报告](backend-choice-foundations-stage3-20261015.md)：固定官方离线multilingual CPU服务经真实backend事实入口与原coordinator/driver完成choice接纳、冻结续行及L4结果。首回合L4为cognition_unavailable下的physiology_hint，第二不同事件新turn已完成但L4命令为空；不登记领域执行成功。取消后迟到结果zero_write，服务不可用有真实URLError。完整预算门在该backend进程显式启用，普通runtime仍opt-in。

角色新增调节投影、表达/观察episode、协同/短契约、SpeechLease的局部合同，任务证据及剩余项见计划02/03；阶段三严格为规格09–12／计划04，Task1–2已开始实施、局部合同与生产迁移/最终验收分列。原角色03/04/15、规格08、计划02/03及原角色16/规格09–12/计划04分别回写。模型质量仍0/8、0/6、1/8未验收，Godot未验证，领域最终执行未验收；本轮不恢复Godot、其他输出类型、final/holdout或训练。验证与清理以批次报告最终区块为准。


2026-10-16 / 计划04 Task4 设施维修准入：audit complete / implementation blocked / not_verified。Construction 维修事实 owner、direct API receipt/补偿/replay 存在，但应用/服务无实际维修 caller，角色动作语义登记及 owner 对 actor/grant/窗口/read pins 的重验不完整。仅回写[矩阵与三图](stage3-task4-construction-audit-20261016.md)，不造 caller；Task1 既有时间合同只在调查冲突 Action 消费，Task3 资源迁移 blocked，Task2 T07/prediction 与其他 owner 未完成；物理、近战、投射物及其他动作未验证。

### RW-34 阶段三对应回写

阶段三Task1–2的局部前置、真实owner/API、合同测试、三图、回滚与下一项见[阶段三Task1–2报告](stage3-task1-task2-20261015.md)。Task1–2已开始实施、局部合同通过，整项未完成；未启动规格10–12整域验收。总批次验证以[backend/角色/阶段三报告](backend-choice-foundations-stage3-20261015.md)为准。

### RW-34 角色Task6与生命周期审查收尾

计划02 Task6新增现有三角色L2/L3/L4消费者及四学习路线8例合同回归；char_d缺正式profile、作者化认知字段/L2包络接线和真实学习owner的局部缺口保留。对应回写原角色13/14、规格05/06和计划02。L4反馈/取消/过期新增冻结digest与终态保护，6例RED→GREEN及独立复审通过；不将局部合同登记为四角色差异、真实学习成功或领域执行通过。最终套件和清理结果见RW-34批次报告。

最终验证：完整pytest 8010 passed、17 failed、2 skipped；其中1项事实序列化回归已修复并在后续72项定向回归通过，另16项历史评估source pins失配保留开放。完整套件不登记通过；修复后backend-contract Harness与cleanup、git diff --check通过。普通runtime预算门仍opt-in，质量计数/Godot/Harness all与领域验收状态不变。


### RW-35 Status consumer 时间接入（2026-10-16）

[current] `StatusTagAuthorityService` 现支持 temporal context、冻结 expiry、owner 生成的 `ScheduledWork`、到期 request 重验、GameplayEventStore 幂等 receipt 与 projector checkpoint+tail 恢复；旧 applied 事件无 expiry 时保持永久语义。[planned] 将 status registry 接入现有应用生命周期 caller；仍复用已有 clock/scheduler/store。[永久禁止] 第二套 clock、scheduler、event store、tag registry 和新的后台循环，不是 deferred 能力；加载装配既有 `StatusTagRegistry` 不属于新建语义系统。来源：角色16 §2.1–2.4、§4.1、§7.4；规格09 §7.1、规格10 §4.1、计划04 Task1。

2026-10-16 续行：[current] main 已加载原 `status_tag_definitions`，同 store 装配 registry/service/薄 consumer，显式 `status_time_binding` 接既有 population confirmed boundary，经 `RuntimeExecution` 串行写入原 owner；startup/reset/shutdown 引用管理与新 Durable store/service/runtime 重启路径已有应用测试证据。前段 app wiring planned 已由本续行在对应配置范围内覆盖。[planned] 默认 actor configs 为空，真实生产状态内容未配置，其他时间来源未自动准入，Action 与完整迁移未实施。五层验收、三图、测试允许列表、外部证据与最终验证见 [阶段三续行回写](stage3-task1-task2-20261015.md#status-consumer-应用生命周期与-durable-重启闭环2026-10-16)。不宣称 Task1 或阶段三完成，不启动 Task2 prediction/Task3–6；本轮未调用 provider 或 Godot，Laya 仍仅限 choice。



- 2026-10-16：计划04 Task1 Action consumer 接口设计与定向实现，规格09/11、角色11/16已同步；来源、owner、caller、Durable/receipt 与剩余缺口见 [阶段三 Action 回写](stage3-task1-task2-20261015.md#action-consumer-时间接入2026-10-16)。不重复 Status 验收，保留历史 cleanup incomplete 与 HTTP503 审查未完成。

### RW-36 Task1 验收编号与迁移正例（2026-10-16）

来源：[角色16 §2.1–2.3、§4、§6–7](../角色/16-通用玩法时序模型与编辑器设计.md)。修订：计划04原来源表误将规格09 T07 归 Task1；规格09 §11 的 T02 为激活迁移，T07 为随机/顺序确定性，后者归 Task2。原设计、规格09、计划04均已同步并保留此说明。当前 Task1 限 T01/T02/T03；[有限矩阵及接口决定](stage3-task1-task2-20261015.md#task1-有限验收矩阵2026-10-16)逐项记录 caller、owner、已有证据与缺口。状态：`changed/planned; T02 positive migration implementation/evidence pending`。解除条件：同 canonical 单位步长迁移经实际推进 caller、clock/Status owner receipt、Durable 重启及重复恢复验证，历史 Action pins 不变；其他未接线消费领域按设计逐项 planned，不扩成无限 Task1 门。生产内容来源另验，历史 cleanup 拒绝与 HTTP503 审查仍单列 incomplete。

实施接口边界：单配置 actor/world/timeline；原 Status owner 迁移 receipt 在前、原 clock 激活在后，Status 已提交而 clock 异常时保留事实并恢复激活。多 actor/更多 world/timeline 协调为 planned 缺口，不接受全局迁移/回滚声明。

2026-10-16 RW-10 / 计划04 Task2 续行：仅 Organization/Economy 冻结窗口与 Durable 新实例恢复，状态 `aligned/narrowed`，详见 [本轮验收与三图](stage3-task1-task2-20261015.md#task2-冻结窗口与-durable-恢复验收2026-10-16)。其他 owner、随机、完整 snapshot 与 prediction 保持 planned；生产内容未启用。

### RW-37 Task2 限定 checkpoint / replay（2026-10-16）

来源：角色16 §7.4、规格09 T10–T11、计划04 Task2；状态 `aligned/narrowed; declared scoped checkpoint/replay verified`。本轮仅在原 RuntimeExecution/GameplayEventStore/Durable/event projection/batch recovery 上实现 `ReplayCheckpoint@1` / `ReplayTail@1`，范围为显式冻结批次、两个已准入 Organization/econ1 Economy 操作及其确有依赖的 Population cursor、Status 工作和迁移边界。非事件输入/claims 纳入一致切面，历史 pins 按原版本重建；缺参与者或依赖不缩范围。完整参与者 API/序列化版本、权限和架构/时序/数据流三图见[本轮阶段三回写](stage3-task1-task2-20261015.md#task2-限定参与范围-checkpoint-与-replay2026-10-16)，原设计与计划已同步追加。

175项 focused、Durable 实际 caller、故障/权限及 backend-contract 静态合同通过，接受结论仅“声明参与范围内的checkpoint/replay通过”；Task1/Task2/阶段三整体保持独立未完成。T07 随机确定性未验证，prediction、其他 owner、Task3–6、Godot、calibration/evaluation、final/holdout、训练不启动；Laya 仅 choice，无 provider。完整 checkpoint 不获得角色读取权限，历史封存、清理拒绝和 HTTP503 独立审查 incomplete 原样保留。


### RW-38 Task2 T07 真实随机消费者盘点（2026-10-16）

来源：角色16 §7.1、规格09 T07、计划04 Task2；状态 `aligned / blocked / not_verified`。未发现具名 owner 同时具备真实随机消费和可恢复证据，不增加 synthetic consumer。盘点、允许列表、三图与本轮验证见[阶段三回写](stage3-task1-task2-20261015.md#task2-t07-真实随机消费者盘点2026-10-16)。已有 scoped replay 与批次恢复不被扩展为随机通过；Task2 整体未完成，prediction、Task3–6及其他关闭范围不启动，Laya 仍仅 choice。


### RW-39 Task3 真实 owner 与集中迁移前置审查（2026-10-16）

来源：战斗02/04/05/06/07/08/11、规格10§3、审查06、D17、计划04 Task3；状态 `aligned / audit complete / implementation blocked / target migration not_verified`。[矩阵、迁移夹具设计、三图、95项focused与backend-contract证据](stage3-task3-20261016.md)。旧资源owner与恢复存在，但目标字段/schema、持久pause/drain和真实非战斗核心Resource接线不齐；无新增资源实施切片。原设计、规格10、审查06、计划04及阶段三回写同步。Task2限定通过、T07无真实随机owner的阻断及所有历史未完成项保持独立。

### RW-40 Task4 facility repair 动作准入设计（2026-10-16）

来源：规格11 A02–A06、角色11 §3–4/§8、角色16 §2.3–2.4/§4/§7.4、规格09 T01–T06、INF-1AE Construction owner 审查与实际 L4/能力/维修 API。状态 `design-only / blocked / not_verified`。本批完成[十项来源判定、A/B/C 分类、接口草案、责任/兼容矩阵、九项前置与三图](stage3-task4-construction-audit-20261016.md#2026-10-16-动作准入设计收口仅设计未实施)，并完成[四项 B/C 正式收口](stage3-task4-construction-audit-20261016.md#bc-阻断正式收口四项待用户决策-2026-10-16)：四项均为 C（原文与现有 owner 均不足，正式 deferred），同时标记待用户决策。facility repair 保持 deferred；不创建 caller、不提交 repair event、不继续 Task4 该子切片。无默认 grant/角色维修、隐含 target、condition 派生资格、caller 写入 `repair_amount`/`next_condition` 或运行时代码变更。结论已同步[规格11](../规格/11-技法动作结算与非战斗语义适配规格.md)、[角色11](../角色/11-跨玩法动作承诺协议设计.md)、[计划04 Task4](../计划/04-通用合同与领域服务实施计划.md)及[Construction 原审查](../../superpowers/specs/world-character-siming-authority-mainline/inf-1/2026-08-17-inf-1ae-construction-action-owner-contract-audit.md)。Task3 资源迁移继续 blocked；Task2 T07、prediction 和其他 owner 未完成；Task5/6 未启动；Laya 仅 choice；Godot、calibration、final/holdout、训练和微调关闭。历史 cleanup incomplete 与 HTTP503 独立审查 incomplete 原样保留。


### RW-41 Task3 资源前置解阻续记（2026-10-16）

状态 `documentation-only / B design complete / C deferred / implementation admission = 0`。本次逐项区分旧合同 A、可依原文设计的 B 和缺来源/具名责任的 C，完成[Task3 七项矩阵与解除条件](stage3-task3-20261016.md#8-task3-资源切片-abc-准入矩阵2026-10-16rw-41)、[规格10 正式接口设计](../规格/10-通用资源状态效果影响源与装备领域规格.md#rw-41-task3-资源前置接口设计仅文档)及计划04同步；架构/时序/数据流共同使用[Task3 §8.4 三图](stage3-task3-20261016.md#84-rw-41-共同伴随三图)。没有新增资源实现、schema、caller、默认字段/权限/target 或基础设施。

C1–C8：容量来源/政策、锁定、债务、恢复源账与时间准入、持久 pause/drain 责任、目标映射/codec、资源 privacy/revocation、真实非战斗 caller/owner route，全部正式 deferred。A 的旧 decoder/receipt/Durable 历史证据不扩为目标资源通过；B 只形成条件接口设计。下一项最小工作为用户选定已有非战斗入口与真实资源/容量内容的来源决策记录，不默认构造 caller。

阶段三仍未完成：Task1/2 保留局部边界，Task2 T07/prediction/完整 snapshot 未完成且本轮不启动；Task3 缺口未获得运行时证据；facility repair 沿用 RW-40 四项 C/deferred，不重复审查；Task4 其他动作、Task5/6 不启动。Laya 仅 choice 输出类型。只执行文档链接、图表、空白/diff、`.harness` 清单检查；未运行 pytest/Harness/Godot 或任何运行时验收，未运行 calibration/final/holdout/训练/微调。历史证据、source pins、threshold、label、archive、cleanup incomplete 与 HTTP503 独立审查 incomplete 不变。

### RW-43 生产输出入库 C1 用户决策单（2026-10-16）

[本候选决策单与三图](stage3-task3-production-output-c1-decision-20261016.md)核对原设计02、规格10、计划04、Task3 矩阵及真实 caller/owner。原文已定义一般基础容量来源；现有产物实现为 Inventory custody，核心归属、具体容量版本/政策/owner/映射未决。C1 保持 C/deferred；若纳入核心仍受 D06，Task3 可实施切片仍为零。下一最小任务是用户决定核心归属及条件容量责任后仅回写决定。

仅更新决策单、Task3、规格10、计划04与本登记；共同 current/planned/deferred 架构、时序、数据流见决策单。只做文档静态核验，不运行测试或运行时；facility repair 保持 C/deferred，其他阶段不启动，Laya 仅 choice。RW-42 与其他历史记录保留原文。

### RW-44 生产输出继续采用 Inventory custody（2026-10-16）

用户决定当前不把生产输出纳入核心 `ResourceEntry`，保留既有 Inventory custody、Inventory owner 与投影语义。C1 对该候选标记为 `deferred / no admission`；Task3 可实施切片仍为零。只有出现明确核心资源需求、命名资源和容量内容来源后，才重开 C1 与 D06 审查，不因本决定创建字段、caller 或迁移。

完整决策与三图见[生产输出入库 C1 决策单](stage3-task3-production-output-c1-decision-20261016.md)及[Task3 回写](stage3-task3-20261016.md)。其他 Task3 缺口、facility repair C/deferred、Task2 T07/prediction、Task4 其他动作、Task5/6、Godot、calibration、final/holdout、训练和微调状态均不变；Laya 仍仅记录 `choice`。本轮只修改文档，未运行运行时验收。

### RW-45 Task1 Inventory 真实生产输出时间 consumer 审查（2026-10-16）

[Task1 A/B/C 矩阵、真实 caller→owner→store、恢复入口和接线设计](stage3-task1-task2-20261015.md#task1-inventory-真实生产输出-consumer-时间合同专项审查2026-10-16)核对了既有 Inventory custody 路径；[规格09](../规格/09-通用时间权限投影与领域服务接入规格.md#task1-inventory-生产输出时间-consumer-审查2026-10-16)和[计划04](../计划/04-通用合同与领域服务实施计划.md#task1-inventory-真实生产输出时间-consumer-门禁2026-10-16仅文档)同步接线与门禁。领域入库合同为 A；caller/owner/recovery 接线为 B；完整 SettlementWindow、temporal authorization 和 caller 可冻结 content/binding 来源为 C/deferred。没有可接受的 Task1 Inventory 时间 consumer。RW-44 不变：继续 Inventory custody，不进入核心 `ResourceEntry`，Task3 可实施切片仍为零。下一项前置是补齐具名时间窗口与权限来源；来源齐备后再单独授权实现及 Durable/full-replay 验收。facility repair C/deferred、Task2 T07/prediction、Task4 其他动作、Task5/6 和 Laya choice 不变。本轮仅文档静态回写，无运行时验收。

### RW-42 Task3 C8+C1 来源决策包（2026-10-16）

来源：[Task3 C8+C1 来源决策包](stage3-task3-c8-c1-source-decision-20261016.md)、规格10、计划04、战斗资源原设计02及现有领域实现。已核对五类非战斗候选的真实入口、资源字段、内容/容量版本、owner、可见性、时间/read-set/revision pins、receipt/checkpoint/tail/Durable 与 D06。没有候选同时满足 C8+C1，**可实施切片仍为零**；生产输出入库仅列“需要补接口设计”，其余继续 C/deferred。

用户需明确 caller、核心资源及容量内容/policy、映射、owner/read-set/可见性和 D06 迁移责任后再进入接口设计。本轮不选择业务入口或资源，不创建 synthetic caller、默认容量、默认权限、默认 owner、空 registry 或新字段；facility repair 继续 C/deferred。Task2 T07/prediction、Task4 其他动作、Task5/6、calibration、final/holdout、训练、微调和 Godot 不启动，Laya 仍只记录 `choice`。本轮仅做文档静态核验，未运行 pytest、Harness、Godot 或运行时验收。

### RW-46 阶段三既有状态索引与 Task1 专项同步（2026-10-16）

阶段三既有状态与本轮 Task1 Inventory 专项同步集中回写于[阶段三状态索引](stage3-closure-20261016.md)。本轮只审查并同步 Task1 Inventory 时间 consumer，不声称 Task1–Task6 文档审查全部完成，阶段三整体仍未完成；Task2 仅 Organization/Economy 限定 replay 通过，T07/prediction/完整 snapshot 未完成；Task3 无新资源切片且 RW-44 保持 Inventory custody；Task4 facility repair、Task4 其他动作、Task5/6 沿用既有未启动/未验收状态，本轮不新增 A/B/C 决定。

本轮不新增运行时代码、caller、owner、schema、权限或基础设施。只做链接、图表、空白、`git diff --check` 和 `.harness` 状态检查；不运行 pytest、Harness、Godot、calibration、final/holdout、训练或微调。Laya 仍只记录 `choice`。

### RW-47 Task4/Task5 动作与生命连续性 owner 审查（2026-10-16）

Task4 继续沿 RW-40：设施维修为 C/deferred，不创建角色 caller、grant、target 或 repair event。已有 `InvestigationConflictAuthority` 与 `ActionConsequenceBoundary` 提供动作窗口、空间/source revision、事件 receipt 和 consequence source validation 的 A 类边界，但不扩展为非战斗动作完整验收。

Task5 已完成 owner 盘点与[三图回写](stage3-task5-lifecycle-audit-20261016.md)：`RuntimeContinuityState`、actor-private relational memory 及动作结果来源校验可继续使用；LifeState、EntityPresence/spawn/despawn、Soul/identity 与 ThreatRelation 等均因缺真实 owner/API 正式 deferred。解除条件为具名 owner、事件/receipt、Durable 恢复、full/checkpoint+tail replay、privacy/revocation、部分失败恢复和迁移兼容。Focused backend 集合 `16 passed`；不宣称 Task4/Task5 完整验收或阶段三完成。

### RW-48 阶段三最终总门禁（2026-10-16）

[阶段三总收口矩阵](stage3-closure-20261016.md#2026-10-16-当前收口覆盖与历史段落说明)冻结 Task1–Task6 的最终状态。247 项统一 focused 回归通过，但仅证明声明范围内局部 owner 合同；Task6 因跨域参与者、迁移、privacy/revocation 和完整恢复证据缺失保持 blocked，阶段三不能宣称完成。RW-44、facility repair C/deferred、Laya choice-only、Godot/calibration/final/holdout/training 关闭边界继续有效。

### RW-49 Population → Inventory temporal read-set 接线增量（2026-10-17）

PopulationCadenceDriver 已生成的 timeline/profile/mapping/source/window pins 现在随 RuntimeCadencePublisher 的 cadence authority event 持久化，并由 default_population_read_set_builder 保留到 PopulationReadSet digest；Population 决策、重试和 InventoryOutputCustodyOwnerExecutor 重建均沿用同一 pins。Inventory adapter 在 pins 存在时重验采样/接收边界、窗口长度、source revision、timeline 与 mapping revision，冲突 zero-write/requeue。Inventory vertical、Population domain/capability、authorized cadence publication、cadence/Durable recovery 共 134 项相关回归通过，backend-contract/docs/boundaries Harness 均通过并清理。

本记录只解除 Task1 Inventory temporal read-set 的 B 类接线项；完整 SettlementWindow participant/cutoff/confirmation/late-input/order 来源、temporal authorization source、content/binding revision read source仍缺失，Task1 整体和 Task6 继续未完成。RW-44、facility repair、T07/prediction、Task3–5 deferred、Laya choice-only、Godot/calibration/final/holdout/training 关闭边界不变。

### RW-50 Inventory custody replay participant 接线（2026-10-17）

已有 production-output custody 事件现在可作为 scoped replay 的可选 Inventory participant：capture 记录 `production_output_custody_view_for()`、事件 id/global sequence/payload digest 和 source revision vector；只有真实 custody 事件存在时才加入 manifest。应用入口将已装配的 Inventory authority 传入 checkpoint/tail capture 与 validation，恢复时由同一 store 的新 authority 实例重建并比较 custody view；checkpoint boundary 按事件序列过滤，full/checkpoint+tail 仍保持原 digest/fail-closed 合同。

相关 replay participant、scoped checkpoint/tail application、Inventory vertical 共 31 passed，`compileall` 和 `git diff --check` 通过。该证据只扩展声明 replay 范围内的 Inventory custody participant，不解除完整 SettlementWindow、temporal authorization、content/binding revision 来源，也不改变 RW-44 的 Inventory custody 语义；Task1 整体和 Task6 仍未完成。

### RW-51 Population → Inventory caller freeze 与提交前重验（2026-10-17）

本次设计并实现了既有 Population caller 到 Inventory owner 的只读来源冻结：active `GameplayPatchRegistry` 的 manifest/declaration/binding、Construction certification 与 `facility_acquired` 事实、Inventory stream revision 组成 `ProductionOutputCustodyReadSet`；真实 adapter 将 package/content/declaration/binding/active-set/mapping pins 带入 `ProductionOutputCustodyIntent`，Inventory owner 在 append 前重验，撤权、变更或歧义保持 zero-write。RW-44 不变，未写入核心 `ResourceEntry`，未创建第二套 clock/scheduler/store/权限系统。

本轮 focused 证据为 Inventory vertical 12 passed，加上 production-output custody family 回归合计 16 passed。该项只解除 Inventory content/binding caller read source 与提交前重验的 B 类接线；完整 `SettlementWindow` participant/cutoff/confirmation/late-input/order 来源和 temporal authorization issuer 仍缺失，Task1 整体及 Task6 未完成。详见[规格09 Inventory 时间 consumer](../规格/09-通用时间权限投影与领域服务接入规格.md#task1-inventory-生产输出时间-consumer-审查2026-10-16)和[阶段三回写](stage3-task1-task2-20261015.md#2026-10-17-population-inventory-temporal-read-set-增量)。


### RW-50/51 fresh 复核更正（2026-10-17）

RW-50 旧 31 项统计不足以证明同一 Inventory 的 Durable close/reopen。本轮新增并复验应用 checkpoint/tail → 关闭 Durable → 同一路径新 Durable/new authority → full/checkpoint-tail 对照，相关 5 passed；Inventory vertical/custody family 17 passed。缺 authority、删除 participant、篡改 rows/ref/vector/digest 拒绝。未来 Inventory 事件独立时序反例仍待验证；规格09中该项的“均 fail-closed”仅描述实现目标，不能作为该反例已运行的声明。详细证据及限制见 Task1/2 回写末节。

Task5 旧 blanket “没有关系事实 owner”已收窄：P5 SocialFactAuthority 已有 shared/recipient-filtered facts；ThreatRelation、Life/Presence/Soul 等仍缺业务政策与正式准入。用户本轮明确全部产品政策由用户决定；不得以新增 owner 的技术授权推导业务批准。总门禁与集中决策包以 stage3-closure 当前矩阵为准。
