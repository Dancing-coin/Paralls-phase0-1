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
| R01 turn／MindFrame／ThoughtMode；规格01–03、计划01 | 局部实现 | turn coordinator、frame builder、cognition coordinator/driver、frozen session stages | 同一真实 turn 的 source→frame→L2/L3→Laya→执行→owner receipt→writeback；background cognition 继续 commands=[] |
| R02 memory；规格04 | 局部实现 | recall、semantic cards、writeback policy、consistency/recovery tests | 真实 outcome 与 authority receipt 绑定，重复、冲突、重开不重复沉淀；保留隐私与来源 |
| R03 官方 Laya 服务与 choice | 已完成（历史 bounded 链路） | `gateway/laya_provider.py`、gateway、[RW-34](backend-choice-foundations-stage3-20261015.md) | 复用服务及接纳证据；首回合为 cognition_unavailable physiology_hint，第二回合空命令，不能计入动作执行 |
| R04 完整输入与预算；规格05、计划01 Task1C | 局部实现 | 完整 token budget gate、RW-32 修复后 22 条无截断诊断 | 正式运行配置冻结、同 request usage/pins，超预算明确失败；不能靠静默截断解决 |
| R05 完整 U/P 与动作＋目标 | 未实现（生产目录）；compiler 已有 | `l3_planner.py::_candidate_records/CandidateCompiler`、输出映射合同 | `CharacterPrivateWorldSnapshot` 尚无 target_catalog/visible_target_refs，生产者缺失。由真实私有感知与已有 domain admission 提供目标、权限、affordance、revision、owner route；不得用 attention 或当前玩家猜目标 |
| R06 能力包络／cognition policy；规格05、计划02 Task1–3 | 局部实现 | stable ability、CapabilityEnvelope、CognitionPolicy、L3 gate | 同源 envelope/policy 进入 L2/L3/dialogue/recall，绑定 turn/frame/revision；L2 尚未消费 L3 编译合同，不能虚构 profile 认知差异 |
| R07 选择→非 fallback 原动作 L4；规格07 | 未验证 | frozen candidate map/digest、canonical execution contract | 实际 Laya 选择的 action+target 与非空原动作合同一致；不能由 fallback physiology_hint 或 accepted ack 替代 |
| R08 L4→owner→反馈 | 未实现（生产闭环）；adapter 合同已有 | `l4_adapter.py::admit_execution_contract/build_action_attempt/accept_execution_feedback` | 三方法当前未被 main/runtime 调用。先接无需物理造证的真实领域纵切；再以真实 physics 接近战。执行成功必须有 domain owner receipt |
| R09 中断／恢复／回放 | 未验证（端到端） | durable cognition/session、frozen resume、取消迟到负例 | owner 提交前后中断、新进程重开 exact receipt replay、changed duplicate、旧 worker 迟到零写、writeback 不重复 |
| R10 学习／技能形成；规格06 | 局部实现 | extractor/gate/settlement、capability-action vertical | 四学习路线目前到缺 owner 拒绝；正式对象/策略注册与真实 skill owner 结算。工程模型训练不产生角色技能事件 |
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

## 执行顺序

1. R05/R06：补生产私有目标与同源能力输入，优先复用已有 scene/skill/owner registry；记录 action-specific availability，不能一条 target grant 放行所有动作。
2. R07/R08：选择无需 Godot 的真实 owner 纵切，打通同 turn 的实际 Laya→L4→owner→receipt→writeback；领域缺口转入对应 D 行，完成后返回。
3. R09：沿该纵切完成 durable dispatch/reopen/replay；保留后台零命令与取消隔离。
4. 交错收口 D03–D11、R10–R14；不重复建设已有能力；各 owner 一旦正式准入就加入共同 cut。
5. Q01–Q04：有来源的完整动作/目标开发归因→新 calibration→预算阈值冻结→独立 final/holdout；训练仅经有证据方案单独处理。
6. 后端四组矩阵条件满足后，集中 G-A→G-B→G-C；到此才考虑最终必须的扩大验证，并先说明与用户禁止无意义全量运行的关系。
