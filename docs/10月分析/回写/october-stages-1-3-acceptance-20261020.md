# 十月主线阶段一至三统一验收矩阵

状态：**执行中，整体未完成**。授权：用户 2026-10-20 明确要求整体完成阶段一至三；先收尾管理员生产入口，再扩大目标，后端先行，Godot 最后集中验收。本文件是统一剩余工作索引，不替代原规格或原始证据。

**当前执行目标：整体完成十月主线阶段一至三的实现与验收。** Goal ledger 仍 active；当前工具 `update_goal` 仅支持 status，无法修改 objective，不能以虚报旧目标 complete 的方式替换。本文件及[执行计划](../../superpowers/plans/2026-10-20-october-stages-1-3-implementation-plan.md)承载扩展后的权威执行范围。

## 判定与证据复用

- **已完成**：仅指该行精确能力与证据边界已满足；不自动关闭所属阶段。
- **局部实现**：已有可复用实现／局部合同，生产接线或剩余语义仍缺。
- **未验证**：实现存在，但所需真实运行／质量证据未取得。
- **未实现**：当前调用链或 owner 能力不存在；不能用新增测试数量代替实现。
- 既有报告仅复用其输入、来源、实现和参与范围仍有效的部分。修改实际依赖后重验相应路径，不为刷新日期重跑无关领域。矩阵中的历史质量统计保留历史身份，不能充当本轮 final。
- 不统计无依据百分比；报告按后端、模型质量、角色闭环、最终 Godot 四组逐行说明。整体完成要求所有在范围必验行满足；明确延期项不偷偷降格为已完成。

## 一、后端与领域

| ID／来源 | 当前状态 | 可复用实现与证据入口 | 剩余工作与验收条件 |
|---|---|---|---|
| D01 时间／迁移；规格09、计划04 Task1 | 局部实现 | `simulation_clock`、temporal mapping/profile、Population cadence；closure 的 Task1 consumer 矩阵 | 逐个实际 consumer 的 source/clock/revision/expiry/grant 与 receipt；保留 world-time 和 operational timeout 分离，不另造 clock |
| D02 管理员 cadence 撤权生产入口 | 已完成（测试部署边界） | `world_admin_auth_service.py`、`runtime_asgi.py`、`runtime_process.py`、`main.py`；本轮 Task1/Task6/docs 导出见下 | 真正部署 credential/TLS 尚未验证；本行不代表通用 capability/facility grant issuer 完成 |
| D03 SettlementWindow／owner 批次；规格09 | 局部实现 | Population→Inventory custody、Economy tax/calendar、Ecology temporal、Status/Action；[stage3 closure](stage3-closure-20261016.md) | 复核正式启用 consumer 的完整 read-set、cutoff/order/late-input、原子 owner receipt 与重启；不能从一个 consumer 推全域 |
| D04 T07 随机业务；计划04 Task2 | 局部实现 | Economy random owner、版本化 policy、typed self-draw ingress、random replay participant | authenticated lottery/loot/event-choice 实际 producer、公开交付与收据回流；不能把 fixture demand 或 controller binding 当正式业务来源 |
| D05 T09 prediction；计划04 Task2 | 局部实现 | Equipment command/prediction typed ingress、ledger、confirmation、Durable recovery | 正式 demand producer、确认/撤销/冲突与真实 owner receipt；不能把 preview promotion unsupported 改写为通过 |
| D06 资源集中迁移；规格10、计划04 Task3 | 局部实现 | ResourceTemplate materialization、world-time recovery、reservation、modifier interval、v2→v2 migration、conversion；`infra-resource-world-time-recovery` | 正式 capability issuer、Modifier→Resource admission、debt/modifier/conversion 完整生命周期、统一 consumer pins 和集中切换；先复用现有 owner，禁止平行资源真相 |
| D07 状态／效果／装备；规格10 | 局部实现 | Status lifecycle、equipment activation/command、effect/stat projection | 实际角色动作消费的权限/版本/失效链、效果与资源真实 owner 回执及恢复；全领域集中切换不能由装备单例代替 |
| D08 技法／多 owner／物理；规格11、计划04 Task4 | 局部实现 | 既有 ESM、street embodied owner、Durable combat adapter、canonical faction/Threat/encounter | authenticated canonical combat producer、正式 faction/target source、角色合同接线；真实 physics/contact 证据在最终 Godot 阶段取得，禁止伪造 |
| D09 LifeState／Presence；规格12、计划04 Task5 | 局部实现 | LifeState owner、case-death caller、Population activation→Presence、incarnation/replay | 正式场景 source 与角色私有投影/target eligibility、迁移恢复；不从 HP 或 profile 推死亡事实 |
| D10 Soul／identity；规格08/12 | 未实现（完整 Soul owner） | 现有 identity、continuity 和缺 owner 拒绝合同可复用；当前代码未发现 Soul authority | 按原规格补必要 owner/权限/事件/receipt/恢复，再返回角色验收；identity/L1 hint 不能替代 Soul 事实 |
| D11 全域 replay 与故障；计划04 Task6 | 局部实现 | 十领域 shared Durable cut、具名 participant matrix、Task6 fault allowlist | 全部本次正式准入 owner 的同一 global atomic cut，以及恢复/迁移/权限/隐私 parity；42 participant 独立测试不等于共同 cut |

## 二、角色与 Laya 闭环

| ID／来源 | 当前状态 | 可复用实现与证据入口 | 剩余工作与验收条件 |
|---|---|---|---|
| R01 turn／MindFrame／ThoughtMode；规格01–03、计划01 | 局部实现 | turn coordinator、frame builder、cognition coordinator/driver、frozen session stages | 同一真实 turn 的 source→frame→L2/L3→Laya→执行→owner receipt→writeback；background cognition 继续 commands=[]；资源模板 tuple 进入 L2 缓存破坏 JsonValue frame 的问题已从 profile JSON 序列化入口修复，8 项 frame 回归通过 |
| R02 memory；规格04 | 局部实现 | recall、semantic cards、writeback policy、consistency/recovery tests | 真实 outcome 与 authority receipt 绑定，重复、冲突、重开不重复沉淀；保留隐私与来源 |
| R03 官方 Laya 服务与 choice | 已完成（历史 bounded 链路） | `gateway/laya_provider.py`、gateway、[RW-34](backend-choice-foundations-stage3-20261015.md) | 复用服务及接纳证据；首回合为 cognition_unavailable physiology_hint，第二回合空命令，不能计入动作执行 |
| R04 完整输入与预算；规格05、计划01 Task1C | 局部实现 | 完整 token budget gate、RW-32 修复后 22 条无截断诊断 | 生产 L3 默认完整输入预算门已启用（c3fbbf27）；正式运行 tokenizer/config 冻结、同 request usage/pins 仍待真实模型验证，不能靠静默截断解决 |
| R05 完整 U/P 与动作＋目标 | 局部实现（ESM inspect 输入） | 私有 visible refs/source/catalog、ESM inspect policy 只读投影、生产 reset 绑定同一 ESM、原 CandidateCompiler | 已补原生产目录缺口的 inspect 切片：typed roundtrip、action-specific supported intents、空 visibility 拒绝、scope 隔离与 owner 状态 digest；其余领域动作、完整策略覆盖与执行时 revalidation 仍缺，不得用 attention 或当前玩家猜目标 |
| R06 能力包络／cognition policy；规格05、计划02 Task1–3 | 局部实现（durable Siming、三类同步入口及 background L2/L3 同源合同已验证） | stable ability、CapabilityEnvelope、CognitionPolicy；durable Siming 与 background 在 L2 前冻结真实 registry/profile/dynamic 来源，L2/L3/L4 同 turn；background 保持 commands=[] | 冻结召回总条数与既有 token 估算预算已覆盖 L2/L3/gateway；background/dialogue/模型总输入硬预算、真实 memory/input revision、完整 frame/source 对齐仍缺；不能由 digest 一致推断认知差异或模型质量 |
| R07 选择→非 fallback 原动作 L4；规格07 | 局部验证（真实 Laya inspect 切片） | frozen candidate map/digest、canonical execution contract；run 4f2816ada4884a7dabab3644ff878564 | 实际 Laya 选择的 action+target 与非空原动作合同一致；不能由 fallback physiology_hint 或 accepted ack 替代 |
| R08 L4→owner→反馈 | 局部验证（真实 Laya＋plaque inspect owner＋session outcome）；完整闭环未验证 | `CharacterObjectExecution`、main egress/ingress、ESM shared-store receipt、session dispatch-offered event | 原合同来源、后台派发期限、当前私有目标/scope/digest及空间 read CAS后真实 owner提交并回写；仅 public plaque inspect。真实 Laya原动作、多领域权限/生命周期、完整动作和真实 physics仍缺；不以合同测试代替完整纵切 |
| R09 中断／恢复／回放 | 局部验证（真实inspect提交后新进程exact receipt恢复）；完整故障/回放未验证 | durable cognition/session、frozen resume、取消迟到负例 | owner 提交前后中断、新进程重开 exact receipt replay、changed duplicate、旧 worker 迟到零写、writeback 不重复 |
| R10 学习／技能形成；规格06 | 局部实现 | extractor/gate/settlement、capability-action vertical；registered learning owner 前置39项；owner→下一回合冻结能力/旧provider拒绝/生产读取绑定176项隔离验证，见下文 | 四学习路线仍缺生产 source/episode/gate→owner、时间/资源/teacher与grant撤销准入、正式 mastery 语义与共同 cut。工程模型训练不产生角色技能事件 |
| R11 regulation／五通道／episode；规格08 | 局部实现 | regulation projection、expression/observation episodes、资源私有投影 | 真实来源/权限/回执与消费接线；无来源 band/formula 继续 unknown，不凭空填生理结论；可见/听见最后验收 |
| R12 协同／短契约；计划03 | 局部实现 | local coordination signal/contract、recipient filtering | 真实 fact consumer 的可信时钟/context revision/participant 状态；双角色实际接收与连续协同回执 |
| R13 SpeechLease／三路径语音 | 局部实现 | lease、dialogue continuation、TTS adapter | preset/catchphrase 目录、三路径 dispatch、取消/迟到；音频生成不等于空间 played/heard，听见证据最后验收 |
| R14 精神资源／Soul 角色回验 | 局部实现 | Resource/L1 private projection 与缺 owner 拒绝 | D06/D10 就绪后回验；不能另造角色私有 Soul truth |

## 三、正式模型质量

| ID | 当前状态 | 已有证据与限制 | 剩余验收 |
|---|---|---|---|
| Q01 诊断与归因 | 未通过（历史诊断） | [calibration repair](calibration-repair-20261014.md)：autonomous 0/8、explicit diagnostic 0/6、role-sensitive 1/8，未达冻结 6/5/6；22 条已暴露，不是 final/holdout | 先修真实输入/候选，再分析位置、描述、映射。18/22 选 C3 只提供归因线索，不能直接归因为需训练 |
| Q02 来源／隔离／冻结 | 局部实现 | evaluation/calibration contracts、prepare/freeze/run/score 工具；four_role_lock_event 只有 dev trajectory，正式 splits 为空 | 审查原始 source drift，登记新版本而非直接刷新 hash；构造有来源的 dev/calibration/final/independent_holdout，trajectory 隔离、threshold/预算/freeze 先于评分 |
| Q03 完整 action+target 质量 | 未验证 | 既有 22 条信息诊断的 runtime legality/owner receipt 分母为 0 | 完整包络后正式动作/目标/U/P 覆盖与角色轨两轨验收；真实 receipt 与质量评分分列 |
| Q04 final／holdout | 未实现（正式数据集与验收） | 旧轮次关闭已由当前授权解除；不能重用暴露 calibration 为独立集 | 独立来源、冻结、无 truth transport、封存后评分；不自动训练/微调，若必要先提出有证据方案 |

## 四、最终 Godot（后端收口后集中执行）

| ID | 状态 | 接口／场景与证据要求 |
|---|---|---|
| G-A 单角色跨情境 | 未验证，暂不操作 | raw/visual fact ingress、character_agent_output/execution、所选 action+target、owner receipt、事件变化后的新 turn、重启；真实 boundary 消息＋可见结果；复用合格 actor/motion assets |
| G-B 单角色连续 Boss | 未验证，暂不操作 | canonical embodied action/physics、LifeState/Presence/Threat/encounter、资源状态持续消耗/恢复、Boss 连续阶段；非脚本伪成功、receipt＋画面 |
| G-C 双角色连续协同 | 未验证，暂不操作 | B 能力＋真实 coordination/contract/接收方 L1/语音取消；两个独立 actor 保留身份，连续协同、失败/恢复；boundary＋各 owner receipt＋可见结果 |

任一必需 boundary、receipt 或 visible evidence 缺失，整体 Goal 不得 complete。后端定向 profile 不替代 A/B/C。

## 排除与保留

阶段四、通用编辑器、AD/Blender、自走棋及明确延期内容继续排除。facility repair 的四项明确 deferred 决策保留，不自动恢复，也不拿它阻塞不依赖它的角色纵切。旧轮次 choice-only／禁止模型评估／只做阶段三等限制不再限制本目标；authority、隐私、来源、隔离与 freeze 规则永久保留。

历史修改和历史证据不删除。当前工作区原有约 429 条 dirty/untracked，提交只按确认的文件/patch 分批组织；提交不代表整工作树已可独立发布。

## 本轮管理员收尾与提交

- 提交 `c2ebb578`：配置、digest verifier、fresh-process secret-redaction 测试，三文件。
- 凭据聚焦 15 passed；Task1 run `f655b7b782f34f22b27b9afef6bc905c`；Task6 run `2d79296173bc41c394a792b334b4c5ef`；docs run `0748fd411fc341a8af79d3aea2ce36ac`。三个 Harness 均 passed/cleanup passed。
- 原始报告：`D:/Users/User/Documents/paralls-evidence/stage3-admin-reviewed-20261020-01/{task1,task6,docs}/`。对应管理员源码修订，后续文档索引修改不要求重跑无关 backend。没有运行全量 pytest/all、模型评估或 Godot。

## 本轮角色输入与执行投影进展

- `bc946612`：L2 registry/loader 两条 profile cache 路线使用 JSON 值，修复阶段三资源 tuple 阻断 durable cognition frame；聚焦 10 passed。
- `fac6a634`：私有视觉身份/source/catalog、scope 清空、只读 ESM inspect 投影及生产 reset 接线；独立测试 3 passed。12 文件 170 passed 的组合证据为 run `1c29eb21a796483aac675bc7433bc1fa`，目录 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/target-focused/`；cleanup passed。
- 执行投影修复：冻结 choice 的 target、candidate identity/owner route、owner digest、target revision、room/scene/zone 保持到 L4；`inspect_object`＋`action:inspect`映射到注册的 `interact/inspect`，ActionRequest 与 InteractIntent 共享冻结 scope。暂存隔离测试 4 passed（run `b2b503f2b1a94580815bb3724b32b3f3`）；组合回归 75 passed（run `0a932502a9dd40c794b41b9c8127f209`，之后仅增加来源断言与不同 attention 参数）；backend-contract 静态门禁 passed（run `28cedfd8828843cf96e9ab286b281b4a`）。证据分别在同一外部根的 `inspect-staged-unit/`、`inspect-projection-corrected/`、`inspect-backend-contract/`，cleanup passed。
- 独立审查发现暂存版本漏带 candidate identity/owner/target revision，已补齐并由隔离测试核验。第一次隔离尝试的既有集成用例缺少文档夹具；第二次扩大夹具复制遇到 Windows 长路径，导出失败。只清理了本轮隔离副本与失败导出中的副本；后续只隔离所需四项单元用例，未将失败集成用例计为通过。
- R05仍为 inspect 输入切片；R06现已覆盖 durable Siming 的 L2/L3 同源合同；direct/background/dialogue/recall 仍缺。R07无真实 Laya 原动作证据；R08仍缺生产执行准入、实时 owner 重验、领域实际提交与 durable receipt。当前 canonical character interact 路径只 resolve/发布 accepted，不能当成 player interact 路径中的 object transition/commit，更不能据此关闭 R08。
- 未运行全量 pytest/Harness all、真实模型或 Godot；历史 `.harness/verification` 与用户其余 dirty 保留。

## 执行顺序

1. R05/R06：补生产私有目标与同源能力输入，优先复用已有 scene/skill/owner registry；记录 action-specific availability，不能一条 target grant 放行所有动作。
2. R07/R08：选择无需 Godot 的真实 owner 纵切，打通同 turn 的实际 Laya→L4→owner→receipt→writeback；领域缺口转入对应 D 行，完成后返回。
3. R09：沿该纵切完成 durable dispatch/reopen/replay；保留后台零命令与取消隔离。
4. 交错收口 D03–D11、R10–R14；不重复建设已有能力；各 owner 一旦正式准入就加入共同 cut。
5. Q01–Q04：有来源的完整动作/目标开发归因→新 calibration→预算阈值冻结→独立 final/holdout；训练仅经有证据方案单独处理。
6. 后端四组矩阵条件满足后，集中 G-A→G-B→G-C；到此才考虑最终必须的扩大验证，并先说明与用户禁止无意义全量运行的关系。

## 本轮共享认知合同进展

- `2d420aae`：整理并提交稳定技能投影与包络/策略基础；`84f3e668`：提交既有候选编译/Laya 适配基础及 durable Siming 的生产接线。角色、turn、policy revision、source event 和 pair pins 在 L2/L3 网关前共同校验，L4 沿用冻结 turn；旧版 L3 prepared frame 保持恢复兼容。
- 暂存隔离验证：基础 9 passed / 8 deselected，run `d2390709db9640c5a371c9cd36389552`；接线 129 passed，run `96c67549533340c8830d374ba89ea3a8`。均使用 HEAD archive＋暂存后端＋HEAD 角色档案，未混入历史 mind projection 或执行 lifecycle 改动。
- 第一次基础隔离缺少根目录角色档案，配置导入失败，run `936609250ce14ff798177d051e543f80`；随后按真实 loader 路径只补已提交档案，未扩大复制整个 docs。失败不计通过。
- backend-contract 静态门禁 passed，run `855cb5ea59f74891b3ac795707e045e8`。上述证据在外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 的 `cognition-foundation-staged-corrected/`、`durable-cognition-staged/`、`durable-cognition-contract/`；cleanup 均 passed。
- 后端：仅关闭 durable Siming 共享合同子项。模型质量：未运行真实评估、Q01–Q04未关闭。角色闭环：R07–R09仍缺真实原动作、owner提交/回执及端到端恢复。Godot：仍未修改、启动或验收。未跑全量 pytest/Harness all。

- 文档门禁首次因计划文件未用 `-implementation-plan.md` 命名失败（run `6f03d94662194d9c8bb1a158b488e853`）；修正本轮计划名称及链接后 passed，run `8023305d1fd942ebbb991c60609dd9ed`，外部目录 `durable-cognition-docs-corrected/`，cleanup passed。本轮三个临时诊断日志经 run_scope 导出后删除。

## 本轮召回入口与 authority 重验修复

- `10de477f`：perceived-event wrapper 向 L2 传递已有 canonical turn；真实 semantic recall 的 cards/source/revision 进入请求，跨 actor turn 或私有 memory 拒绝。旧 L2 测试 profile stub 同步接受生产已有 JSON dump mode。精确暂存隔离 52 passed（run `e1026efc47b44046a81e8ed90a8896ff`）。
- `4fa9d0ea`：self-body runtime 同样传递 canonical turn；真实 runtime→L2 recall 与相邻恢复回归精确暂存隔离 57 passed（run `609b59d7286b4b2ea1783702b438d13c`）。已有 mappingproxy serializer warnings 仍保留；不据此声明 direct/self-body 的 L2/L3 已共享包络或硬预算。
- `055d5abf`：ESM 的直接执行入口复用既有 policy/state/occupant 检查；未注册对象、非法动作、状态变化及他人占用均拒绝，拒绝结果保留 canonical pins。请求与事件的 actor/scope/target/action 必须一致；canonical idempotency fingerprint 加入 room/scene/zone，拒绝跨场景重复键。12 个新增行为用例先 RED 后 GREEN；与既有 ESM/后果边界用例精确暂存隔离 52 passed（run `f5f7631c131041d9add2b9986391373d`）。工作树中另含 target projection 回归 67 passed，仅作组合兼容证据，不替代隔离结果。
- 原始日志、暂存 patch 和 manifest 分别在外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 的 `perceived-turn-recall-staged/`、`self-body-turn-recall-staged/`、`esm-readmission-staged/`；均 cleanup passed，临时 checkout 已回收。
- 后端：本批补齐 ESM 执行时 policy/state/occupant 重验子项；ESM state 与 settlement cache 仍为内存，缺少 canonical 距离来源时仍不能计作正式动作提交。装备已有真实 durable owner，但调用权限目前绑定 controller，不能直接当角色授权；work intent 仅有合同与事件注册；SocialDelivery 的 delivery receipt 不证明 speech played/heard。R05/R08 保持局部实现，R07/R09 保持未验证。
- 模型质量：本批未运行真实 Laya、calibration/final/holdout，Q01–Q04 未关闭。角色闭环：仍缺完整原动作→真实 owner→receipt→恢复回放。Godot：未修改、启动、操作或验收。没有运行全量 pytest/Harness all；用户历史修改与历史证据保留。

## 三类同步入口共享合同回写

- `19078684`：perceived、self-body、同步 Siming 在 L2 前冻结同一 turn 的 stable ability、CapabilityEnvelope 与 CognitionPolicy，L2/L3 复用一次编译结果；durable Siming 复用同一冻结方法。同步 Siming 同时补齐 L3 所需 background agenda context。turn 以类型对象传递，避免 mappingproxy JSON 序列化失败被 fallback 掩盖。
- 精确暂存隔离四文件 95 passed，保留两条既有 mappingproxy serializer warnings；run `f462954ad3ca4669af07a4b511b61c30`，外部目录 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/direct-shared-contract-staged/`，含 staged patch、pytest.log 和 manifest，cleanup passed。测试 provider 是本地受控 gateway，不是实际 Laya 证据。
- R06 仍局部实现：background/dialogue/recall 硬预算、canonical 可信输入与 memory revision 未完成；Task1 不关闭。R07–R09 未取得真实模型原动作、owner 提交/回执和端到端恢复证据。Q01–Q04 未关闭，Godot 未操作。
- 上一文档批 docs gate passed/cleanup passed：run `47c5f01bc26546fabe42f9068b891408`，同外部根 `recall-readmission-docs/`。本批不重跑不受影响的后端验证，不运行全量 pytest/Harness all。


## ESM object-only owner 前置能力回写

- `4a18a6f9`：原 ESM 增加显式 opt-in durable settlement，复用共享 GameplayEventStore。范围仅 `obj_plaque/inspect`、`obj_worktable/use/finish_use`；不表示生产、工资或工作完成。环境、body、physics 路由拒绝部分提交。请求/event 的身份、scope、动作、目标与 canonical pins 在原回执查询前绑定；有限坐标是 owner 前置条件，不证明到达或角色授权。
- 写入先于状态投影；scope stream 与 caller read revisions 同批 CAS；exact retry 返回原 result/receipt；SQLite 重开恢复；durable 对象禁止旧内存提交入口绕账。显式事件注册支持 strict store。定向组合工作区 80 passed；精确暂存隔离 73 passed，run `368161ea887f43db890f67b12870cb19`，外部根下 `esm-object-owner-staged/` 含 patch、日志、manifest，cleanup passed。首轮 `6ff8b184002c486fb15e52a137fa6ce3` 测试通过但 pytest 临时链接阻止导出，未用作可留存验收证据；临时根已回收，修正临时数据清理后得到上述有效 run。
- 后端：仅完成 R08 的 bounded owner 前置子项。R08 生产闭环仍未实现；不能把 caller 提供坐标当可信 spatial source。原 session 冻结合同可作为角色执行来源，但 session SQLite 与 world store 独立，不能虚报跨库原子；恢复必须查原 world owner receipt，再幂等补记角色侧。R09 仍端到端未验证。
- 模型质量：未运行真实 Laya 或正式 calibration/final/holdout，Q01–Q04 不关闭。角色闭环：原动作→生产准入→owner→反馈及完整回放未验收。Godot：未修改、启动、操作或验证；最终需绑定真实空间来源并取得 A/B/C 可见结果。
- 前一文档批 `8f85692` docs gate passed/cleanup passed：run `0fbe61ed9eee40b597721b837116605f`，同外部根 `direct-shared-contract-docs/`。本批未运行全量 pytest/Harness all；历史修改与历史证据保留。


## 原 session 执行来源准入回写

- `d13994bd`：生产 canonical execution ingress 在生成 ActionRequest、调用 owner 或记录 settlement 前，必须与原 actor session 的 `character_agent_execution_request` 完整合同一致。兼容同步直接合同与 durable plan 内合同两种既有存储形态；跨 actor、未记录合同、改写动作/目标/source/turn/revision/observation 均拒绝，同键冲突记录不能以第一条合法记录掩盖。只返回来源 event ref，不授予 world authority，不替代权限、时钟、空间及 owner 重验；legacy bundle 兼容入口仍存在。
- 先得到 11 项 RED（包含生产入口错误接纳未记录合同），再修复。工作区两文件组合 38 passed；精确暂存隔离四文件 39 passed，run `c7c05088285f48449c7f8ea923dc34fe`，外部根下 `execution-source-staged-short/` 含 patch、日志、manifest，cleanup passed。四条既有 FastAPI lifecycle deprecation warnings 保留。backend-contract passed/cleanup passed，run `5ab8f46639db41faaf4f7dff299f7047`，目录 `execution-source-contract/`。
- 首次扩大隔离运行 `280ae4dc8784414c99a90efdf2f19734` 为 7 failed / 64 passed：五项缺六个已提交的 production manifest 夹具；两项为 HEAD 已有失败。后一次补夹具时遇到 Windows 长路径，run `87e4a6c4c50d41d5a421f6854de4eace` 未运行测试；自有失败导出中的 checkout/tar 已清理。有效运行改用自有短路径 checkout，并只复制 registry 明列的六个 HEAD manifest，没有引入工作区历史修改。
- 两项 HEAD 基线失败单独复现并保留 baseline.log：`test_character_agent_runtime_player_suggestion_path_uses_continuity_floor_under_local_only_planner`（期望 observe_target，实际 physiology_hint）；`test_character_agent_runtime_feeds_previous_goal_portfolio_back_into_next_model_turn`（缺 execution target_ref）。本批不修改其历史混改；不能声称整个 runtime suite 通过。
- 后端：关闭来源绑定子项，R08 生产完整闭环仍未实现；可信 spatial source、L4 实时准入、真实 owner receipt 与 session 补记仍待完成。角色 R07/R09、模型 Q01–Q04、最终 Godot G-A/B/C 状态均不升级。未运行全量 pytest/Harness all、真实模型或 Godot。
- 前一文档批 `eaeda35` docs gate passed/cleanup passed，run `6fdffc0c5cae4eb095cd73eab159dffc`，同外部根 `esm-object-owner-docs/`。


## 冻结召回预算子项回写

- `cdaff0a2`：冻结 policy 限制跨 memory pools 的总召回条数和既有 token 估算预算；strong/requirements 不能扩容。semantic cards 裁剪同时裁 memory，保留 omission；零预算不查询 graph。L3 在首次召回前冻结/校验 policy，使用 semantic 返回的裁剪后 memory；gateway 二次召回不能突破冻结上限。actor/turn 不一致拒绝。
- 精确暂存五文件隔离 163 passed，10 条既有 mappingproxy serializer warnings；run `84939863833b47b7a4a95367f3806e2a`，外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/recall-budget-staged-corrected/` 含 patch、日志、manifest。backend-contract passed，run `c0948577424d45fd8d98015f5df71143`，同根 `recall-budget-contract/`；均 cleanup passed。
- 初始 RED run `3e47dde6404646e9ba7cc62ae14d6a63`（10 failed），L3 RED `dff7558d9a4c49f580aea6c833565516`（2 failed）。扩大组合 run `09ff9274a4d947f39ef1bc8b500a6c55` 为 1 failed/140 passed：既有 strong-memory 测试依赖隐式扩容；改为 profile 显式冻结 2400 后维持原长记忆断言。run `261534c9ee5e420399eb812ec42d523d` 因清单含未提交历史测试文件而零测试，已纠正清单取得上述有效隔离结果；不计作通过。诊断目录分别为 `recall-budget-red/`、`recall-budget-l3-red/`、`recall-budget-layers/`、`recall-budget-staged/`，均已清理本轮临时副本。
- R06/Task1 保持局部实现。这里使用既有 JSON 长度估算，不是实际 tokenizer 或整个 prompt 的硬预算；background、dialogue 和可信输入/memory revisions 仍待补齐。R07–R09 未升级：未运行真实 Laya、未打通生产 L4→owner receipt→恢复。Q01–Q04 与 Godot G-A/B/C 均未关闭，Godot 未操作。
- 上一文档批 `ae613868` docs gate passed/cleanup passed，run `410e806999814d49b9ee1132183edf94`，同根 `execution-source-docs/`。本批未运行全量 pytest/Harness all，保留历史修改和证据。


## 可信空间来源前置回写（Task2 保持开放）

- `cdb424d8`：内部 authored scope、真实 controller/epoch 绑定、首样本/重连位置连续、backend 单调时间与 tick 双重限速、bounds/freshness、持久化 provenance、同 world spine read CAS。旧重复请求返回原 receipt，不刷新 freshness；进程重启须新样本。采样和读取只读取当前 head 一条，旧 retry 直接查询原事务。纳入已有 controller 断连/重连撤销实现，防止旧连接继续被接纳。
- 精确暂存隔离 **62 passed**，4 条已有 FastAPI lifespan warnings；run `93614848ee2e446199c8b2cd369ecd27`，外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/spatial-source-staged-final/`。backend-contract passed run `4693379c1044449c803bc686fc5fd254`，同根 `spatial-source-contract/`。均 cleanup passed。
- 初始 RED `93396480fea54a2eaf9257160336b27e`：16 缺模块与1个测试 context-manager 错误；修正后 SQLite RED `070b10dbb50d48c6b69ce1d618cd16e4` 正确缺模块。局部实现 run `02d58bdc6a6140fd84589b2b43d58bfd` 50 passed。新增有界历史读取 RED `e47d4479ba684dc391d7bb365f56d50b` 1 failed。第一次隔离 `6cd20c5ebdb145b4aefbe1e882feddbf` 3 failed/58 passed：发现未提交 auth 撤销依赖，并缺 production manifests/静态桥文件；补齐后 `5a18bdba6e27496fb6ff76e643e83e93` 1 failed/61 passed，仅还缺 LocalPresentationBus 静态文件。补齐明确 HEAD 夹具才取得上述有效结果；不将失败计为通过。本轮没有修改、启动或操作 Godot；读取已提交静态文本不构成场景验收。
- R08 只补来源前置，生产 composition/消息 ingress、L4 实时准入与 ESM receipt consumer 仍待接。该来源证明有界 controller evidence，不证明 server physics/contact/path clearance。controller auth 是内存状态；撤销与 world append 尚非跨组件原子，不声称全生产准入原子性。R07/R09、Q01–Q04、G-A/B/C 均不升级，未跑真实模型/全量 pytest/Harness all。
- 上一文档批 `58cdc65` docs passed/cleanup passed，run `c70a211dc49144089310ab703cfbbae2`，同根 `recall-budget-docs/`。

- 本批 docs 首跑 `b43940fa31434f0e873872eab9a8fdea` 因门禁要求同名计划缺失而失败；增加链接到统一计划的空间来源 lane 后，`b4f073d817a74d15b796d74cee859a9d` passed/cleanup passed，外部根 `spatial-source-docs-corrected/`。


## 空间生产接线与真实边界子项（Task2 仍未完成）

- `cafeaeed`：内部 `EMBODIED_SPATIAL_SCOPES_JSON` 严格配置、共享 world store/auth 组合、`embodied_spatial_sample` 真实 ingress 和断连接撤权。精确暂存隔离 69 passed，run `61250907b02142a3be805756e75570c9`，`spatial-ingress-staged-final/`；backend-contract passed，run `62f952b0b0094b7fae2ee506a82e4034`，`spatial-ingress-contract/`；两轮 cleanup passed。
- `e7063bcc`：真实网络绑定使用后端 wallclock，禁止默认固定时间绕过已过期 launcher credential；仅内部 direct-handler 测试保留历史兼容时间。回归先 RED（run `14233352e71b43a6bc45ddeb0def9227`，1 failed/7 deselected，`spatial-bind-clock-red/`），再精确暂存隔离 70 passed / 4 既有 FastAPI warnings。
- 真实独立 uvicorn＋HTTP enrollment＋WebSocket bind/sample 验证 passed：首样本得到持久提交 receipt，exact retry 返回原回执，changed duplicate 拒绝。run `2305abd50062465880574e1fc7e281c4`，目录 `spatial-ingress-live/`；manifest 保存原始边界响应和版本 patch。证据根仍为 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/`。
- 此 live run 清理失败：Windows 文件占用使 checkout/backend 与 backend.log 删除失败。随后进程快照未发现本轮 uvicorn；精确路径 PowerShell 清理被自动审批策略拒绝，未绕过。遗留仅本轮 `C:/Users/User/AppData/Local/Temp/oc-2305abd5` 与 `C:/Users/User/AppData/Local/Temp/paralls-harness-2305abd50062465880574e1fc7e281c4`；保留 cleanup failed，不把此 run 总体记为全绿。
- 后端：空间生产准入子项局部实现，默认内部 scopes 为空，尚无 ESM/L4 consumer。角色闭环：R07–R09 未关闭；历史 dirty L4 方法不等于已提交生产基础，下一批先审阅必要依赖，再接 source→L4→owner receipt/recovery。模型质量：未运行真实 Laya 或正式 splits。Godot：未修改、启动或验收；最终 producer 必须发送内部配置匹配的 actor/scope/scene_instance/revision、绑定 epoch、tick、位置，且仍需 A/B/C 可见结果。未运行全量 pytest/Harness all。

- 本批文档门禁 passed/cleanup passed，run `c6d7ea770733488ca9dc1ff79b06b772`，外部 `spatial-ingress-docs/`。

## 有界对象执行 consumer 与回执恢复（Task2/3 子项）

- 仅 public `obj_plaque inspect` 接到生产 canonical egress/ingress、共享 ESM owner commit 和原 receipt 回写。后台派发单独记原 session event，不污染确定性 L4 合同；重发不续期，新进程不能用旧派发提交。新 request（含 legacy）使旧派发失效。已有原 owner receipt 优先恢复，跨库 writeback 失败可补记一次。
- HEAD＋精准暂存补丁隔离：95 passed，run `12b015bce3814ccfa82c53cfa34d57f6`，`object-staged-isolated/`；backend-contract passed，run `5c881ad557714ce293f8890375f1c21b`，`object-consumer-contract/`。均在本页外部证据根，cleanup passed。工作区组合 run `6bfb422ac68743aa9ac0a99601cf5158` 同为95 passed，但不代替隔离证据。
- 覆盖原 receipt、零写拒绝、重复不续期、跨 service epoch 拒绝、生产处理函数、SQLite 关闭重开补记。fixture 注入私有 snapshot与冻结合同，没有真实模型选择或新网络纵切；不关闭 R07/R08/R09。未跑全量 pytest/all、真实模型或 Godot。
- 后端：有界生产 consumer 和原receipt修复已测试；模型质量：Q01–Q04仍未通过；角色闭环：继续真实 Laya生产纵切，完整生命周期/多领域和full/checkpoint-tail待验；Godot：A/B/C均未执行，仍最后集中验收。既有空间live run清理失败的两条路径保持原记录，本批未尝试绕过审批清理。

## Background 共享认知合同子项

- `22522948`：同步 background 与 durable background 在 L2 前冻结同一 turn 的 CapabilityEnvelope/CognitionPolicy，L2/L3 复用该合同；durable provider-pending 重开读取原冻结请求，source event ref 绑定原 cognition child key。后台仍不产生执行命令。
- HEAD `249a9eed` archive 加精确方法补丁隔离 **58 passed**，run `ae1be16c6a024afd9a625a60cefa9d76`；证据为 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/background-staged-isolated/` 中 manifest、patch、pytest.log、JUnit。cleanup passed。提交前以独立 Git index 重建证据 tree，与 staged tree `413be97d7a91517b415f8e3ad95bafeda6648639` 完全一致；用户原有 MindFrame projection、frame 参数和 coordinator 重验修改没有并入本批。
- 后端：仅关闭 background 同源合同子项，R06/Task1 仍局部实现；background/dialogue/总输入硬预算及可信 revision 未关闭。模型质量：未运行真实 Laya 或正式 splits。角色闭环：R07–R09 未升级。Godot：未修改、启动或验收，A/B/C 留到后端及模型门完成后。不重复运行无关全量 pytest/Harness all，历史修改和证据保留。

## Laya 生产默认完整输入预算子项

- `c3fbbf27`：L3 生产 Laya request 无论环境变量缺失、空值还是空白，都冻结完整输入预算（默认 max_len=2091、head_max_len=256）；显式配置仍冻结到原 request。复用现有 provider tokenizer gate，缺 pinned tokenizer 或总输入超限在 HTTP 前拒绝。
- RED 5 failed，run `ffc3cc6569954313bf3943a5e61724e0`；HEAD `2cb97f5f` archive＋精确两文件 GREEN/回归 **72 passed**，run `0ed5fd71ca7d4902944c73f41f9f1384`。提交前核对两文件 SHA 与隔离 manifest 一致。backend-contract passed，run `be6de26f061046ec93a3ea9b57925a98`；各 run cleanup passed。证据在既有仓库外根目录的 `laya-default-budget-{red,isolated,contract}/`。
- 后端：只关闭生产默认预算门子项，R04/R06仍局部；4 条既有 mappingproxy serializer warnings保留。模型质量：受控 tokenizer 测试不能替代正式 tokenizer/usage 或 calibration/final/holdout，Q01–Q04未关闭。角色闭环：R07–R09未升级，下一步真实 Laya→L4→ESM receipt纵切。Godot：未修改、启动或验收；没有运行全量 pytest/Harness all。


## Laya 冻结认知输入修复与真实诊断

- `4c4b65e7`：L3 原已准备的 actor-scoped goal frame/tags、current goal、已裁剪 memory/semantic cards、need/dynamic state、supervision/background/tension 通过显式 allowlist 进入 Laya state；不复制整个 context、原始档案或 grading。所有新增输入仍经过既有 pinned tokenizer 总预算门，超限在 HTTP 前拒绝。此批不宣称所有 frame/source 输入已完整。
- 10 项新增输入保留用例先 RED（10 failed）；精确两文件 HEAD 隔离验证 **131 passed**，run `12803a3e4a944604b32fca4cf96d15c7`，外部根下 `laya-frozen-context-isolated/`。backend-contract passed，run `d99751bd2d32491aa7fd6acc671a8937`，目录 `laya-frozen-context-contract/`；均 cleanup passed。
- 修复前真实 backend 诊断 runs `5abeca21340a4cfd8af623044b66044a`、`6f05c7a2b03a4db29fb84184ef9d4016` 各两次 Laya HTTP 成功，均选择合法 observe，未到 owner。前者目录 `laya-object-production-diagnostic-exact-manifests/`，后者 `laya-object-production-diagnostic-action-request/`。缺 manifest 的前次 launcher 失败不计通过。
- 修复后 HEAD 真实 backend WebSocket raw fact→L2 local baseline→official pinned Laya run `f0fe891b98174b5f8936e4d5e69ddc5b`：原冻结三候选顺序不变，选择 `inspect_object:obj_plaque`（0.7819），完整输入 **5844 tokens**，服务 usage 与本地预算完全一致、无截断、无 provider error。目录 `laya-object-production-frozen-context/`，cleanup passed。本次 15 秒观察窗口在 L3 返回附近结束并取消 pending，未形成 L4/owner 闭环；不能把模型选择计为 R07/R08完成。L2 是 continuity baseline，正式 L2质量未验。
- 上述输入只属开发诊断，不能进入 final/holdout；单例选择变化不能证明统计质量或唯一归因。Q01–Q04仍未关闭。Godot未修改、启动或操作。未跑全量 pytest/Harness all；用户历史修改与 `.harness` 产物保留。

- 上述输入修复的 docs gate passed/cleanup passed：run `5e3d1323da2f4d8bb419afc16eb0402e`，目录 `laya-frozen-context-docs/`。
- 延长真实观察窗口后的 run `114fc8b34fc745ae93edb2932f821a44`，目录 `laya-object-production-owner/`，Laya仍选择 inspect，但生产 L3 legacy mapping 把原语义改为 observe_target，而合同保留 action:inspect/candidate pins；没有调用 inspect owner。该 run 是定位证据，不是闭环通过，cleanup passed。开发 controller已绑定，但条件按inspect合同发送的空间sample未触发，不能宣称新鲜空间或owner提交。后续修复必须让正式冻结候选保持原 semantic intent，并从planner一路覆盖到L4。

- `628f05c2`：正式带 candidate_digest/Laya evidence 的冻结选择直接保留 compiler semantic intent，不再套历史表现映射。新回归从真实 planner prepare→受控冻结 choice→decision→L4 contract验证 inspect/action/target/owner pins；未把受控 choice标作真实模型。行为 RED为 observe_target!=inspect_object，修复后精确两文件隔离 **136 passed**、4条既有FastAPI deprecation warnings，run `f115f41572eb4e33b4dfe5161826f274`，目录 `laya-frozen-choice-isolated-corrected/`，cleanup passed。首次隔离 `20602e90a4c64c758039583a1652333d`为1 failed/135 passed（新增用例空revision夹具不合法），修正测试为非空真实形态后重跑；不计前者通过。

- `628f05c2` 的 backend-contract passed/cleanup passed：run `6a86b07f718043d0a81a9ecc6dae104a`，目录 `laya-frozen-choice-contract/`；docs passed/cleanup passed：run `6f6621990c1642c88cab8c8e5eca1fc4`，目录 `laya-frozen-choice-docs/`。
- 真实纵切前 run `0232edbf21964d9195d8ed094eb5517b`（目录 `laya-object-production-owner-original-intent/`）已保持 inspect 原合同，但 launcher 在 app/config 导入后才设置scope环境变量，导致 scope mismatch，零owner写；修正launcher将scope置于所有app导入前，未放宽生产准入。该失败不计通过。
- 有效纵切 run **`4f2816ada4884a7dabab3644ff878564`**（HEAD `628f05c2`，目录 `laya-object-production-owner-configured/`）：真实 WebSocket raw fact→L2 local baseline→官方 Laya `inspect_object:obj_plaque`→同一turn/source/candidate/digest的 L4 inspect/action:inspect→认证开发controller空间sample→原 shared-store ESM owner提交→world_result与角色session settlement outcome。空间receipt位于global sequence 9，ESM receipt位于10；owner transaction为 `transaction:esm-object:5efe5d357f4378db0475365744a690496317250267f93e6fc161f855e4d8ba90`，world_result和session outcome均引用原transaction。服务输入5822 tokens无截断。cleanup passed，本轮Laya服务已正常关闭。
- 该空间sample为认证开发controller报告，**不是Godot/physics/contact证据**；L2是local baseline。仅升级 R07/R08 的公开plaque inspect子项，R09完整恢复/回放、其余动作/owner覆盖与Q01–Q04、G-A/B/C仍开放。不能从此单例推正式模型质量、通用owner admission或整个角色闭环完成。


## 真实 inspect 纵切的新进程恢复子项

- run `e9c21eb2ffa945c18fb95a289d14c8aa`（HEAD `143799c`），外部根下 `laya-object-production-owner-recovery/`。先运行同一真实 backend/Laya/认证开发空间source/ESM owner路径，关闭backend后，新 Python 进程重开原 world SQLite＋原 character session SQLite，以原冻结合同查询执行；没有新模型调用、派发offer或新鲜pose。原 receipt逐字段一致，重复执行不重复提交，改写目标在source校验拒绝。
- `new-process-recovery.json`：世界 global sequence **10→10**，session event count **17→17**，settlement outcome **1条**；changed duplicate错误 `execution_source_mismatch`。recovery exit=0，主backend exit=0，run cleanup passed；本轮Laya进程正常退出，18765/18766无listener。
- R09只完成真实提交后的新进程exact retry/changed duplicate子项。fixture已有的丢writeback修复不等同于该真实模型run经历了提交前后中断；checkpoint＋tail、共同cut、旧worker迟到、多owner和完整角色生命周期仍待验。正式模型Q01–Q04与Godot三项状态不升级。下一批依据D06/D10/R10–R14的实际consumer依赖推进，不为已有inspect子项继续堆叠无新增风险的测试。

- 本批恢复索引 docs gate passed/cleanup passed：run `c5b229b132a9453f98edbf26e49b0da2`，外部根下 `laya-owner-recovery-docs/`。仅精准提交本轮矩阵回写，不提交历史dirty/untracked领域文件。

## R10 registered learning owner 前置

- [设计](../../superpowers/specs/2026-10-20-registered-learning-authority-design.md)与[计划](../../superpowers/plans/2026-10-20-registered-learning-authority-implementation-plan.md)：新增独立 `skills/learning_authority.py`，复用现有 shared GameplayEventStore、技能 registry 和 stable compiler，不依赖历史未提交 episode/settlement 改动。
- 内部对象规则绑定 skill、方法/阶段/operation、来源 owner/type/version、actor/world、最低证据与注册 outcome；每条 evidence 必须有同库原事件、transaction membership 和已提交 receipt。来源 read CAS 与 actor learned stream write CAS 原子校验。原 receipt exact retry 可跨 source advance、rule removal 和 SQLite 重开；changed duplicate、同 actor/object 重复证据与坏 projection 拒绝。
- 受限 `granted/locked` 技能不能被对象注册直接授予；`evolution` operation 和 `evolved` stage 都要求注册 Siming source。补充 RED 先复现受限技能授予、可变 dict 的 bool revision 被 JSON dump 转整数，以及 evolved stage 绕过；改为原 Python 值严格重验并补门禁。两处新增测试曾误读 receipt 顶层 error_code，已按实际 failure 合同修正，不作为产品缺陷。
- 最终隔离 run `060b10b09b334dd7bc372a20bcb6cb69`，HEAD `e23c917a`＋精确两新增后端文件，**39 passed**（owner 29＋既有 service 10），exit=0/cleanup passed；外部根下 `registered-learning-owner-receipt-scope-final/` 有原始日志、JUnit、source 与 SHA256 manifest。覆盖缺来源/错误 subject/principal/outcome/privacy/stale、零写拒绝、前置技能成功链、source 并发变更、写入前故障、提交后丢响应、strict schema opt-in、损坏 projection、SQLite 恢复及 existing compiler 消费。较早36项与38项隔离结果由最终39项取代，不重复计入。最终复核 RED 复现其他 stream 回执被 exact retry 接纳；已补 owner stream/type/version/transaction 作用域门禁。
- backend-contract run `76752ae4862a4223be71c49ca28593b5` passed/cleanup passed，外部根下 `registered-learning-owner-contract/`。这是静态边界门禁，不能代替运行时学习路线。
- **R10仍局部实现**：schema 仅 opt-in，尚无生产 shared-store registration/caller。episode、时间/资源、teacher 可见性、八维 mastery/七维 difficulty、fusion/evolution 图语义、下一回合 capability 刷新和共同 checkpoint cut 均待后续接线。测试 source 为受控提交，非真实角色/Laya学习证据；无正式模型质量或Godot升级。未运行全量 pytest/Harness all，未启动模型训练或Godot。

## R10 owner→冻结能力与生产读取绑定增量

- 在上批前置上新增同次 history read 的 actor/world `LearningStateSnapshot`，包含 learned stream revision、state 与原 learning event refs。runtime 将 learned 与 authored 交给既有 stable compiler，保留既有优先级与 profile。新回合 envelope 冻结学习 snapshot digest；sync 与 durable coordinator 都在 provider handoff 与结果接纳时检查原 pin。冻结和交付之间提交也拒绝；旧结果沿用 `stale_context` requeue，不能续用新能力解释旧选择。原已冻结合同不重新编译。
- 真实 backend lifespan 已将只读 learning owner 绑定到 shared gameplay store、runtime skill registry 和显式 bakery world；该 reader 没有注册学习规则或新增 mutation endpoint。测试中的学习 source仍是受控owner提交，**不是四条生产学习路线或真实Laya学习证据**。旧持久化pending frame若不含学习pin，在新绑定部署后拒绝；已完成owner原receipt仍按原合同恢复。
- 行为 RED先确认snapshot/runtime binding不存在；另单独RED确认真实lifespan未绑定reader。新增用例验证新/旧回合与profile不变、actor/world隔离、sync pending拒绝、freeze→handoff竞态、durable pending重开保留原请求与旧结果拒绝、durable handoff竞态零pending写、真实backend lifespan共享owner。组合工作树57项通过仅作兼容；最终验收使用精确源码隔离。
- 最终隔离 run `9c33cb1d2e5f4c27837ca583005ff547`，HEAD `a801ae8d`＋五份精确源码快照，**176 passed**，exit=0/cleanup passed；外部根下 `learning-cognition-binding-isolated-final/` 有source、规范化SHA256 manifest、JUnit、日志与patch。覆盖owner/service和既有sync/durable合同、completion revision、coordinator回归。较早174项 `c6a2bd321d2d472286a4b752817a5bdd`被最终176项取代；`66f5138bcc274812bba5f45490008e5d`在解包时触发Windows路径长度失败，未执行测试，不计通过；缩短临时目录且只取HEAD必要JSON夹具后修正。暂存五文件内容hash逐项与最终manifest一致，历史runtime/coordinator/main改动均保留在工作树。
- backend-contract run `7ce51c1176ad49ba8d7c7a17f665e836` passed/cleanup passed，外部根下 `learning-cognition-binding-contract/`。R10仍局部实现：实际ESM object receipt为authority_only，nested request/result；不得为复用它直接放宽隐私。下一依赖是owner授权的actor-private学习披露与scene/world归属、episode/time/resource/teacher gate，再接完整四路线。schema生产注册、grant/revocation、mastery/fusion/Siming语义与共同cut仍缺。Q01–Q04、完整角色闭环、Godot A/B/C均未升级；未全量pytest/Harness all，未训练或操作Godot。
