# 世界基础设施增量指导

状态：`已批准的 INF 窄纵切完成并验证；八月 INF 主线仍未完成；extends existing world_runtime/ESM/event-replay paths; no new runtime is authorized`

命名与执行坐标：[`INF mainline and substrate mapping guide`](../../superpowers/specs/world-character-siming-authority-mainline/2026-08-17-inf-mainline-substrate-mapping-guide.md) 规定 `INF-1..4` 为领域主线、`INF-C1..5` 为跨领域可复用合同层；二者不是重复任务。

执行顺序调整（2026-08-16）：在继续增加新的领域 consumer、obligation 或
branch row 之前，先执行 [INF reusable contract substrate design](../../superpowers/specs/world-character-siming-authority-mainline/2026-08-16-inf-reusable-contract-substrate-design.md)
及 [implementation plan](../../superpowers/plans/world-character-siming-authority-mainline/2026-08-16-inf-reusable-contract-substrate-implementation-plan.md)。该层只统一已有的纯状态规划、closed obligation lifecycle、owner-fragment settlement recipe、有限 ecology admission 和 deterministic branch replay；不开放 caller registration、generic writer、second runtime/store 或 population truth owner。
其中 INF-1C1 已先完成纯 `StateTransitionPlan`：同一规划器覆盖 add/replace/refresh/reject、expiry、dispel、transform，并由 Survival、Construction、Ecology 的已登记定义复用；其独立证据为 `infra-reusable-state-transition-plan`。这只是可复用 proposal 层，不等于 INF-1 lifecycle closure。
随后 INF-2C2 完成了同一抽象顺序下的 closed lifecycle substrate：`ObligationLifecycleRegistration.event_type_for()` 统一 settle/cancel/expire/retry/compensate 合同，`from_closed_registry()` 提供显式 canonical reader；Survival 与 Economy wage 使用同一合同形状，旧的空注册调用仍维持 zero-write。它仍不开放 caller policy registration 或 generic settlement。
INF-2C3 再将既有 owner-fragment batch adapter 与 append-derived receipt factory 收敛为纯 `AppendDerivedSettlementRecipe`，并接入 obligation planner；单 owner 与既有多 owner 组合共用同一形状，recipe 仍不 append、不选 owner，也不开放任意跨域业务结算。
INF-2AA 另完成一个严格的 Economy-owned commerce delivery payment/compensation 行：付款只从已提交的 Inventory delivery、Economy delivery/commerce obligation 与同一 commitment 已登记的 budget reservation 推导；补偿只接受其后的已提交 rejection/cancellation evidence，并反转已记录的账户与金额。两者均经唯一 `append_batch()`、authority-only outbox、scoped projection 与 full/checkpoint-tail replay 证明；不开放任意付款、策略注册、通用补偿或跨域 writer。
INF-C4 随后把已登记 weather-front consumer 的共同 source pin、target owner/stream/event/scope、revision、idempotency 与 receipt/replay reader 校验收敛为只读 `EcologyConsumerAdmissionCheck`；Construction 与 Organization 仍各自验证 opaque admission、构造 fragment 并经唯一 append spine 提交。该层拒绝未知/伪造/private/stale 输入且零写，但不建立 consumer registry、generic fanout 或 Ecology 对目标领域的写权。
INF-C5 (INF-4) 现已完成：`FixedBaseBranchReplayContract` 将既有 isolated branch 的 fixed base revision、calibration/source digest、family/candidate deterministic ordering 与 full/checkpoint-tail projection digest 收敛为纯只读合同；既有 Organization supply promotion admission 在 owner 构造 fragment 前重读并验证该合同。其独立证据为 `infra-fixed-base-branch-replay-contract`；不开放 generic branch settlement、generic promotion 或 branch writer。

当前实现映射：见 [../12-实现收口与证据映射.md](../12-实现收口与证据映射.md#世界基础设施增量指导)。INF-1 至 INF-4 的文档化纵切已有独立 spec、plan、测试和 Harness 证据：语义/实体/因果、caller-driven obligation、frost/crop 生态灾害、以及隔离人口分支预览。它们不等同于通用元规则语言、完整生态传导、完整群体模拟或文明演进；这些广域能力仍是后续设计与 owner-scoped 实现工作。

八月 INF 主线的未完成项必须显式保留，不能被 `INF-*X/Y/Z` 窄包名称遮蔽：

正式 owner/stream/event/privacy/revision/receipt 缺口见
[`INF Remaining Scope Dependency Design`](../../superpowers/specs/world-character-siming-authority-mainline/2026-08-12-inf-remaining-scope-dependency-design.md#mainline-closure-owner-contract-matrix)。
该矩阵中的 `blocked` 不授权创建 generic router、coordinator 或新 truth owner；缺少
任一合同字段时只能维持 zero-write。

- INF-1：`SurvivalAuthority` 的 `state:cold@1`、`state:overheated@1`、
  `state:dehydrated@1` 与 `state:fatigued@1` 四条 closed
  行已分别验证 event-derived expiry、add/replace/refresh/reject、stack limit、dispel/
  transform、due settlement、privacy 和 replay；两条闭源 semantic bridge 也把 proposal
  交给同一 owner 并提交 `ScheduledObligation` open/expiry/settled/cancelled 事实。
  仍未完成的是跨 owner 的 effect/state matrix、未注册 effect 的正式结算、通用 lifecycle
  policy 与更广 selector 语义。纯 semantic evaluator 的 expiry 字段仍只是 proposal，不能据此
  宣称通用 lifecycle 或直接写领域真相。
  `INF-1G` 另验证一条既有 `ConstructionProductionAuthority` 的
  `effect:maintenance_required -> state:maintenance_due@1` facility-state 行：owner 自行
  固定 effect/state/vector、拒绝未获取设施流，并允许已获取但尚未启动 run 的设施结算。它不把
  Survival matrix 扩成通用跨 owner matrix，也不创建 maintenance scheduler 或 lifecycle policy。
  `INF-1H`/`INF-1I` 进一步 materialize 并验证四条已注册 row 的 closed owner matrix/route；dispatch 和 public owner helper 都拒绝非
  `{"semantic": 1}` 向量及非 canonical Survival `StateDefinition`，并委托同一 Survival/Construction
  owner。它仍不是通用 owner dispatch。
  INF-1I 已将通用 owner matrix/lifecycle 的缺失 owner、event family、receipt 和 replay
  合同记录为 blocked；在合同批准前维持 unsupported-input zero-write。
  `INF-1J` 另验证一条实际注册的
  `effect:wage_accrual_due -> EconomyAuthority` 行：语义层只接受固定
  owner/stream/privacy/vector 和有效 wage 输入，再委托既有 Economy owner 写入其已存在的
  event-derived obligation lifecycle。它证明第三个既有 owner 的闭源行，不解除通用
  owner matrix/lifecycle blocker。`INF-1K` 另验证 `state:cold`、`state:overheated`
  与 `state:dehydrated` 上的两条闭源 Survival action：`state_dispel` 与固定
  `state_transform_recovery`。其完整 semantic command 指纹被纳入既有 append
  idempotency digest；它仍不准入任意 action、替换状态或通用 owner router。
  `INF-1L` 另验证既有 `EcologyHazardAuthority` 在
  `gameplay:ecology:{region_ref}` 上的固定
  `effect:frost -> state:frosted@1` apply/open/expiry/settled 行；它以现有
  coordinator 的单 store receipt 结算，且具有 refresh、幂等、privacy、revision、
  scoped outbox 与 full/checkpoint-tail replay 证据。它不使历史 semantic frost
  payload 成为通用 lifecycle，也不准入其他 ecology state/effect、scheduler、retry、
  compensation 或 consumer edge。
  `INF-1M` 已被后续疲劳行与 `INF-1AA` drought 行扩展为七条 finite
  state-owner contract matrix；三个既有 authority 在其
  append 前查询并校验各自行，篡改的 stream/event contract 均有零写证据。它仍是
  finite matrix，不是任意 effect 注册、generic dispatch 或 generic writer。
  `INF-1N` 另验证同一既有 Construction facility stream 的固定状态生命周期：
  committed `maintenance_state_applied` source 只能由 Construction owner
  开立 event-derived obligation，并通过其 expiry fragment 以一次
  `append_batch()` 写入 `expired/settled`。它有 stale/wrong-source、second-active、
  retry/cancel/compensation 零写，project outbox、receipt privacy 与
  full/checkpoint-tail replay 证据；settlement registration 额外要求 expired 与 settled
  成对同批提交，并独立拒绝非 owner fragment；不授权通用 effect/state matrix、scheduler 或其他
  owner policy。
  `INF-1O` 进一步验证三条既有 Survival row 的 `StateDefinition` 动作语义：
  仅 `dispel_allowed` 和固定 `state:recovering` transform target 可由纯 evaluator
  决定，semantic action path 必须在 existing Survival fragment 前读取闭源合同。
  `INF-1P` 进一步验证既有 Construction facility stream 的唯一
  `maintenance_state_dispel`：它只撤销 active maintenance state 与其 exact open
  expiry obligation，二者由同一 owner batch 提交；普通取消、transform、repair/payment
  事实和通用 action 注册仍保持 zero-write blocked。
  该 package 独立验证 action policy/target 拒绝、contract-before-fragment zero-write、
  owner settlement、幂等、revision/privacy 与 full/checkpoint-tail replay；它没有新增
  action registry、state writer 或其他 owner row。
  `INF-1Q` 已将上述五条既有 state contract 与既有 Economy wage-obligation
  contract 收敛为只读的六合同生命周期表，固定 terminal event、action allowance、
  outbox、revision、idempotency 与 replay reader metadata；现有 semantic route/action
  在 owner fragment 前读取该表。它没有创建注册入口、通用 writer 或 Ecology generic
  dispatch；任何新增 state/effect/action 仍需要逐行 owner 合同与 RED 证据。
  `INF-1S` 已将 `effect:fatigue_exposure -> state:fatigued` 作为第四条
  现有 Survival row 收口：closed contract、semantic dispatch、owner append、
  privacy/revision/duplicate zero-write 与 full/checkpoint-tail replay 均有独立
  Harness 证据；它不开放 generic registration 或 router。
  `INF-1T` 进一步将该已注册 row 纳入既有 `state_dispel` 与固定
  `state_transform_recovery` action route；两个 action 仍只委托现有 Survival
  fragment，具有 privacy、duplicate/revision 与 replay 独立证据，不开放 action 或
  transform-target 注册。
  `INF-1U` 原本确认 `weather-front -> Survival` 缺少 committed、replayable 的
  `region_ref -> profile_ref` target projection；该前置由 `INF-4AC` 回填：既有
  `ProfileActivationAuthority` 只接受 project-visible committed
  `gameplay.ecology.region.recorded`，将已 active 的既有 `CharacterProfile` 通过 owner
  fragment 写入既有 `population:{world_ref}` 的
  `population.activation.region_assigned`，并从同一事件流回放 project-scoped 映射。
  `INF-1AC` 再以该映射为目标证据，令既有 `SurvivalAuthority` 消费同一 existing
  Ecology source family 的 project-visible `weather:frost`，写入既有
  `effect:cold_exposure -> state:cold` state/obligation events。`INF-1AD` 以完全相同的
  existing-owner/revision/privacy/receipt 边界新增 `weather:heat -> effect:heat_exposure -> state:overheated`；
  两条 receipt 都仅来自 Survival 的一次 append。
  `CharacterProfile.homeland`、Godot/client position 与 household `residence_ref` 仍不能
  代替该世界事实。其他 weather/front、state、consumer outcome 与 fanout 仍没有
  owner/source-event/stream/privacy/receipt 合同，继续 unsupported-input zero-write。
  effect/state matrix、泛化 lifecycle 或支付/account truth 的 blocked 状态。
- INF-2：construction、Survival 与 Economy wage 已有 event-derived lifecycle；Survival
  及 Economy wage 的已注册行分别覆盖 retry/cancel/compensation，Economy 另覆盖 expired，
  Economy 的 wage lifecycle registration 现由同一既有 `EconomyAuthority` 闭源持有，
  caller-driven catch-up 和每次唯一 `append_batch()` 的 `SettlementReceipt` 已验证。
  INF-2B/2E/2F/2N 的 `cold`、`dehydrated`、`overheated` 与 `fatigued` activation release 与 Survival settlement 都是两次正式 append，故 receipt
  必须保持分离，不能伪称跨 stream 原子 receipt。仍未完成的是通用
  activation-obligation binding、未注册 owner policy、payment/account truth 与跨 stream
  业务原子性，而不是缺少 receipt 模型或第二个时钟/store。`INF-4AB` 再将其中一条
  released、project-scoped `survival_state_expiry` pending -> existing Survival owner
  settlement 作为 INF-4 的第二条 exact batch row 独立收口：activation 记录只提供读取
  证据，返回的 receipt 只派生自 Survival 的一次 append，不能与 activation receipt 合并。
  `infra-released-survival-expiry-batch-closure` 独立断言 owner path、receipt boundary、
  幂等、revision/privacy/terminal 零写入和 full/checkpoint-tail replay。它不准入
  generic pending merge、branch promotion 或群体真相 owner。`INF-2G` 已将三条 Survival
  expiry 和一条既有 Organization schedule-gated supply 的 activation pending admission
  收敛为不可扩展的四行 event-derived binding reader；它不是开放注册或通用 dispatcher，
  未注册 Survival compatibility pending 仍没有 binding 且在 target owner 边界零写。
  `INF-2F` 已实现并验证第三条现有 owner 的 `state:overheated@1` activation row；它不改变上述通用 binding 的未完成状态。
  `INF-2I` 另验证一个既有 `CommerceAuthority` 的命名 Organization/Economy
  commitment：所有领域事件仍来自固定 Organization、Economy、Inventory 和可选 Wage
  owner fragment，并在一个 append batch 内原子提交；同键变更、owner revision、预算与
  privacy/replay 均有独立零写或成功证据。它只解决这一被命名的跨 owner 业务合同，
  不解决开放 policy、payment 或任意跨域原子结算。
  `INF-2J` 另验证既有 `EconomyAuthorityService` 的固定 same-currency scheduled
  account-transfer obligation；event-derived open/due/settled/cancelled/expired 只写
  `gameplay:economy`，并由 single append result 派生 authority receipt。该行不实现
  generic payment、caller policy registration、reservation release 或跨域结算。
  `INF-2K` 再由既有 `GovernmentAuthority` 在既有 organization government stream 上
  登记/撤销唯一固定 commercial-inspection policy，并可从事件重建 project-scoped view；
  这不是任意 policy kind、payment、义务结算或跨域 writer。
  `INF-2L` 再将既有 `DebtAuthorityService` 的固定 simple-debt event family 迁移到
  `GameplayCommandEnvelope -> DebtSettlementPlan -> owner fragments -> one
  append_batch()`；四条既有 Economy/Contract/Debt/Commerce stream 的 read/expected
  revision、authority-scoped redacted outbox、append-derived receipt 和 replay 均由
  独立 Harness 验证。它仍不是 caller-open policy、任意 payment 或 generic
  cross-domain settlement。
  `INF-2M` 再将既有 obligation coordinator 的 registration admission 收紧为六条
  owner policy，并封闭每条 owner-local event family；policy-less、unknown、forged、
  widened caller registration、terminal-plus-smuggled-event fragment 与 owner privacy
  scope override 以及未提交 Construction `run_started` 的 due terminal 均 zero-write。
  它修复 generic writer admission，但不实现 caller-open policy
  registration、payment 或任意跨域原子结算。
  `INF-2O` 另将既有 `EconomyAuthorityService.publish_dynamic_quote()` 从 raw helper
  迁移到 `GameplayCommandEnvelope -> SettlementPlan -> append_batch()`；项目可见 quote
  只允许 Economy revision pin，拒绝 account/payment 字段，且 formal outbox、幂等、revision
  conflict、privacy 与 replay 均由独立 Harness 验证。它不是 Ecology consumer admission；该
  consumer 合同只由独立 INF-3J 持有。
  `INF-2P` 再将既有经营窗口的 owner 边界收正：
  `OrganizationAuthority` 独占 `gameplay:organization:window:{window_ref}` 的
  `operating_window_opened/closed/due_recorded`，通过
  `GameplayCommandEnvelope -> SettlementPlan -> append_batch()` 写入 scoped projection；
  `EconomyAuthority` 仅保留工资义务、应计、支付/逾期和账户账本事实，旧窗口 helper 只作
  兼容委托。十五项独立断言覆盖 owner split、已验证 evidence、支付的 command-plan
  materialization、幂等、revision、privacy、支付/逾期和 full/checkpoint-tail replay。它不开放
  scheduler、generic payroll、policy registration
  或任意跨域原子结算。
  `INF-2V` 在同一 owner split 上重新执行独立闭环：已提交且验证的
  production-completed evidence 才能进入工资应计，支付成功或资金不足后的逾期
  都走既有 Economy owner；覆盖 17 项 focused tests、15 项独立 Harness checks、
  append-derived receipt 与 full/checkpoint-tail replay。它仍不是通用 payroll、
  caller-open policy 或任意跨域结算。
  `INF-2R` 将这两个已验证 owner 行加入只读的 governed contract catalog，并要求
  Organization 与 Economy 在各自正式 batch 前验证固定 owner/stream/event/scope 合同。
  catalog 只保存 source-controlled metadata，不能注册、选择或 append；其独立 Harness
  分别断言两行元数据、两条 pre-append zero-write fence、scope/receipt、幂等/revision
  与 full/checkpoint-tail replay。它建立后续实名 owner-contract 扩展基础，不等同于
  generic payroll、caller-open policy 或任意跨域结算。
  `INF-2W` 再将已注册 lifecycle 投影 read-only materialize 为带 opening provenance
  与 source revision 的 `ScheduledObligation` 输入；它不 append、不推进时钟、不选择 owner。
  `INF-2Y` 则将此前合成的 lifecycle catalog placeholder 替换为 Survival、Construction
  maintenance、Ecology frost/drought 与 Economy wage 五条 exact existing-owner 行，并在其
  既有 append 前强制 immutable contract admission。两者都不开放 caller policy、泛化
  lifecycle、scheduler 或任意跨域业务结算。
  `INF-2Z` 在同一既有 `EconomyAuthorityService` 上新增一条固定税务 obligation 行：
  只接受已提交的 `gameplay.economy.tax_due_recorded` 作为 source，open/settled/cancelled/
  expired 全部写入同一 `gameplay:economy` stream，并由 `ObligationLifecycleProjection`
  event-derived materialize。settled 只记录终态，不扣款、不入账；authority-only outbox
  不暴露金额或 evidence。它仍不是 payment、caller-open policy 或任意跨域结算。
  `INF-2AB` 随后的只读 owner-contract 审计确认这不是漏接的付款实现：当前没有 canonical
  treasury account/account-holder，也没有税款 payment marker、privacy/revision/receipt/replay
  合同。不得临时选择账户或发明政府金库 owner；在上述既有 owner 合同存在前，税款付款继续
  zero-write blocked。
  `INF-2C2` 再将 lifecycle terminal-operation admission 收敛到一个封闭的
  `event_type_for()` 合同，并提供显式 canonical registry factory；Survival 与 Economy
  wage 的 event-derived projection、due view、privacy、幂等和 checkpoint-tail replay
  继续复用既有 owner 事件。旧 coordinator 的空注册默认保持 policy-unregistered
  zero-write，因此该层只是可复用 substrate，不是 caller-open policy 或通用 settlement。
- INF-1：`INF-1AA` 已把同一既有 `EcologyHazardAuthority` 扩展为第七条有限
  state-owner row：严格 `SemanticEcologyDroughtCommand` 只能引用已提交且 project-visible 的
  `gameplay.ecology.drought_process_advanced`，固定写
  `drought_state_applied/opened/expired/settled` 到同一 `gameplay:ecology:{region_ref}`
  stream，并要求 source event id/revision 与 stream head 同时钉死。missing/private/forged/stale
  source、wrong effect/definition、wrong owner/stream、non-project、changed duplicate 与
  second active obligation 都在 append 前 zero-write；exact duplicate replay、owner-only due
  expiry、append-derived receipt/outbox 和 full/checkpoint-tail replay 由
  `infra-ecology-drought-state-obligation` 独立证明。它是第七条有限 row，不是 generic
  lifecycle closure。`INF-1AB` 已使 expiry fragment 从 event-derived obligation 的
  `opening_event:*` 回读 committed drought opening/source，而不是接收 caller source ID；
  缺失 opening provenance 保持 zero-write。
- INF-3：既有 `EcologyHazardAuthority` 已验证 region/environment/resource/crop/hazard
  canonical record/retire/update、一个 seasonal environment/resource/crop 过程、一个
  caller-driven weather-front step、显式无环 path、三目标 fanout 和两轮最多六边 wave fanout，
  以及三条固定的 Construction target-owner edge：frost -> construction finish、
  seasonal_process -> construction maintenance、weather-front -> construction maintenance，
  并新增 INF-3I 一条固定 weather-front -> Organization commerce commitment edge 和 INF-3J
  一条 source-pinned weather-front -> Economy dynamic quote edge。
  第三条 Construction edge 由 INF-3G 独立证明，INF-3I 的 Organization edge 与 INF-3J 的
  Economy edge 各有独立 Harness 证明；
  `INF-3N` 在同一已存在 `EconomyAuthorityService` 上新增一个独立 contract row：一个
  project-visible committed weather-front source 只能经 Ecology 签发的 opaque admission
  绑定到两个不同且排序固定的既有 `quote_ref`，Economy 在一个 `gameplay:economy` batch
  写两条既有 `dynamic_quote_published`。缺失/伪造 admission、private/stale source、错误
  arity、target missing、catalog mismatch 与 changed duplicate 均 zero-write；它不开放
  generic fanout、价格公式、账户写入或新的消费者。
  仍未完成的是通用 consumer registry、其他领域 owner rows、
  autonomous propagation、以及未注册 edge 的 retry/compensation；INF-3H 另证明固定双设施、同一
  Construction owner 的 weather-front consumer fanout。INF-3I 仍由 OrganizationAuthority
  独立复核预算授权并写入既有 Organization stream；生态模块不得直接改经济、身体、社会或人口真相。
  `INF-3L` 将 weather-front -> Construction maintenance、Organization supply、Economy quote
  三条既有 target-owner row 收束到 immutable governed contract catalog。Construction 的单设施/
  两设施 batch 与 Economy quote 在构造既有 batch 前各自验证 owner/stream/event/scope；Organization
  保持原有验证。三条 matrix metadata、三个 pre-append zero-write fence 和同 owner 两设施 batch
  由独立 Harness 断言。它不开放 consumer registration、任意 fanout、retry/compensation 或 Ecology
  对目标领域的直接写入。
- INF-4：至少一条真实家庭或组织日程的 owner-bound 结算并与玩家 activation lock 合并
  已有一条 released `schedule_gated_supply` 窄行；隔离 branch 已可从两条既有 owner
  fragment 的 accepted evaluation 重建脱敏的 planned commitment/inspection 本地 consequence，
  并在既有 Organization/Government owner 上各验证了固定的非生产 scenario 行，包括 failed
  inspection 的 `follow_up_required` remediation record。INF-4L 现在将 accepted
  inspection 固化为同一 `GameplayEventStore` 上的 `creator_debug` preview-evidence
  event，再由 Government 重读并要求 evidence stream 与 payload `branch_ref` 精确一致后写
  scenario；passed/failed forged cross-branch admissions 均为独立 zero-write 证据。INF-4K 仅从该固定 remediation
  event 重建一个 branch-local receipt。INF-4M 还允许既有 `BranchPreviewAuthority`
  显式将已接受的脱敏分析 buffer 写入同一 store 的 `creator_debug`
  branch stream，并由新实例重建其 isolated projection；它不结算领域 fragment。
  INF-4N、INF-4S 与 INF-4O 各自验证固定例外：`GovernmentAuthority` 只在 durable
  passed-inspection admission 与同 branch scenario event 精确匹配、source revision 未变时
  写既有 production Government stream，或在 durable failed-inspection admission 与 fixed
  remediation scenario 精确匹配时写同一 production inspection stream 的 `passed=False` 行；
  `OrganizationAuthority` 只在同样封闭条件下写既有 production commerce commitment stream，
  并从同一 append 结果重建 receipt。它们都不是
  generic branch receipt、remediation lifecycle 或通用 promotion；其他 owner、其他 promotion
  与完整群体模拟仍 blocked。该剩余 blocker 见 INF-4E/INF-4G/INF-4J/INF-4N/INF-4O formal
  records。INF-4P 进一步把既有 creator-debug branch snapshot 扩展为一个固定的
  `owner_consequence_applied` branch event：仍由 `authority:branch_preview` 写同一
  `gameplay:branch_preview:{branch_ref}` stream，fresh authority 可从 snapshot + evolution
  replay；它不是 production truth、branch-domain settlement、generic receipt 或 promotion。
  INF-C5 (INF-4) 进一步完成该 branch path 的 deterministic fixed-base replay contract：
  descriptor 固化 base/checkpoint/tail、calibration/source/input digest，reader 对 full 与
  checkpoint-tail projection 计算相同 digest；只有既有 Organization supply admission
  复用该合同，未知 promotion 仍 zero-write。

创新、文明传播、branch promotion、外部数据摄取、generic work、population/NPC/social
truth，以及 SOC-1、GAME-1、P6/P7 不在本主线实施范围内；缺少明确 owner 合同即保持
blocked，不能以样板对象代替实现。

`INF-1R` 的 semantic proposal -> construction production finish 窄纵切已完成并由
`infra-semantic-cross-domain` 独立验证；它只准入
`ConstructionProductionAuthority.build_due_finish_fragment`，不构成通用跨域规则写权。
后续正式设计先保留 `INF-2R`、`INF-3R`、`INF-4R` 的窄纵切，再拆成
`INF-1X`（闭源规则/effect/resistance/owner matrix）、`INF-2X`（义务生命周期与策略注册）、
`INF-3X`（区域生态真相与生命周期）、`INF-3Y`（灾害消费者边）、`INF-4X`（家庭/组织来源投影）、
`INF-4Y`（文明 capability 只读接口）和 `INF-4Z`（完整群体 world-mode）。这些文件是
implementation gate，不表示广域能力已开工；`INF-3X` 已在既有 `EcologyHazardAuthority`
完成单一 ecology stream 的 canonical record/retirement/projection/replay 窄切，但 `INF-3Y`
`INF-4X` 已在既有 `SocialFactAuthority` 与 `OrganizationAuthority` 上完成 bounded
household/organization source projection，并由 `infra-household-org-source-projection`
独立验证；它不扩展为完整家庭、组织、照护、人口或文明能力。`INF-4Y`
已在用户单独批准下完成两条 authority-scoped、capability-gated `supply` 与
`inspection` consumer edge；`INF-4Z` 另已验证 Production 在既有 production stream 上记录
actor-scoped `production-completed` source evidence 的窄入口，但它尚未准入
wage 或 generic `work` consumer；现只额外准入该 frozen worker-scoped Production
source -> existing Economy wage stream 的单一 consumer row，所有其他 `work`
source/evidence kind/mapping 仍 zero-write；inspection、semantic 与所有未列 consumer 仍是
blocked-design。每包
仍必须先满足自己的 owner、零写入、privacy、replay 和独立 Harness 条件。`INF-3R-A`
已在 2026-08-13 以既有 owner 的 committed frost source 和 read-only construction target
selection 解除原始 admission 缺口，并由 `infra-frost-production-admission` 独立验证。
它不写 frost -> production consequence。`INF-3R-B` 已由同一 construction owner 在既有
`run_started` event 上记录 fragment 所需的最小 immutable recipe snapshot，并通过 authority-only
revisioned reader、privacy/rejection 与 checkpoint-tail replay 的独立 Harness 证据。`INF-3R`
现已通过 `infra-regional-ecology` 验证一个固定 committed frost source -> one due construction
finish fragment -> append/outbox/replay/scoped projection 边，含 source/target/privacy/retry/
compensation 零写入、幂等和 replay。该窄边不能作为后续 hazard consumer edge 的通用 baseline。

`INF-2R` 的 construction due-completion policy 已完成并由
`infra-multi-domain-obligation` 验证；`INF-2X` 现已对唯一注册的
`policy:construction_due_completion@1` 追加 owner-stream settled/cancelled
correlation events；取消只能关联既有 construction `run_started` 中已提交的 obligation
identity。`infra-obligation-lifecycle` 独立验证注册、fragment stream/revision、该 identity
zero-write、幂等、revision、project privacy 与 checkpoint-tail replay。生态 retry/compensation 及其他
owner rows 仍没有 event family，维持 unsupported-input zero-write。

`INF-1X` 已完成 one-shot production-finish 的闭源 RuleSet/effect/resistance/
owner mapping 纵切，且 INF-1A/1D/1E 已增加三条明确注册的 Survival scheduled owner rows：
`state:cold@1` / `effect:cold_exposure` 与 `state:overheated@1` /
`effect:heat_exposure`，以及 `state:dehydrated@1` / `effect:dehydration_exposure`，证据为 `infra-general-semantic-rule`、
`infra-survival-state-obligation`、`infra-survival-heat-state-obligation` 与 `infra-survival-dehydration-state-obligation`。其 guard 只解释固定 snapshot predicate，禁止自由
表达式。除这两条显式 row 外，durable lifecycle 仍没有已命名 owner event 与完整
registration；这不是通用规则或状态生命周期已经实现的声明。`INF-1X` 还验证一条
严格的 `SemanticEcologyFrostCommand -> EcologyHazardAuthority.apply_crop_state()` 入口：
提案不能提供 owner、stream 或事件类型，Ecology 重新从已提交 hazard/crop relation 推导
stream 并独自 append；伪造 region、source privacy、revision/snapshot 与 changed duplicate
均 zero-write。证据为 `infra-semantic-ecology-frost-adapter`。它只覆盖
`effect:frost -> state:frosted@1`，不开放通用 Ecology semantic adapter。
`INF-1Y` 随后把同一已验证 strict entry 纳入不可变 state-lifecycle adapter matrix，并让
该 semantic entry 在构造 Ecology envelope 前读取 matrix 的 apply-only row；generic
`SemanticEffectCommand` 因缺少 committed hazard/crop/region relation 仍不能路由该 row。
证据为 `infra-ecology-semantic-adapter-matrix-admission`。这扩展的是现有 owner mapping
的受限覆盖，不是 caller-open registration 或通用 effect/state writer。

本目录不是新的“世界运行时”模块，也不授权创建第二套 world loop、event store、
clock、scheduler、authority 或持久化真相源。它只记录如何在现有
`backend/app/world_runtime/*`、ESM、`raw_fact_event`、`GameplayEventStore`、
outbox、checkpoint/replay 和既有领域 authority 上做增量扩展。

持续执行前置 `infra-continuation-gate` 已通过：它逐项断言唯一 ecology owner、
`gameplay:ecology:{region_ref}` canonical stream、五类 record、十条 event rows、
canonical write path，以及当前有限的八条已登记 consumer-edge set。该 gate
只读取 owner contract 和既有 predecessor reports，不创建 runtime/store/bus/clock/
scheduler，也不把 INF-3R 窄边升级为通用 consumer 能力。证据：
`.harness/verification/infra-continuation-gate-report.json`。

`INF-3Y` 现只启用一条独立注册的 canonical edge：
`ecology-hazard:frost-to-construction-finish:v1`。它从 project-visible
`gameplay:ecology:{region_ref}` 的 canonical hazard/crop event vector 产生 proposal，
由既有 `ConstructionProductionAuthority` 独立校验、选择唯一 due run 并通过既有
construction fragment/append/outbox/replay/scoped projection 写入。它不复用 INF-3R
semantic crop command，不授权另一个 hazard/consumer，也不启用 retry、compensation 或
fanout。consumer 仅在 ecology authority 调用路径内发放并登记 exact transient
admission identity；即使同进程导入真实 admission 类复制公开字段，或手工调用内部
issuer 的 module API，也会 zero-write reject。它不是任意已获 backend 进程执行权的
反射/monkey-patching sandbox。证据：
`.harness/verification/infra-hazard-propagation-report.json`。

内容按三类阅读：

- `implemented`：代码和 Harness 已证明的现有路径；
- `reusable`：可以直接复用的协议、投影或边界，但目标业务能力尚未完成；
- `planned`：必须进入正式 spec/plan 并通过验证后才能实现的扩展。

`INF governed authority contract catalog` 已建立为 `implemented` 的只读
扩展底座：它固定现有 state lifecycle、Government policy、Debt settlement、
Ecology -> Organization consumer、Organization supply promotion 和 Government
passed-inspection promotion 的
owner/stream/event/privacy/receipt/replay 元数据，并在参与 owner 的 append 前
执行 admission。Government promotion 的 catalog mismatch 会在 fragment/append
前零写拒绝。它不提供 runtime registration、动态 consumer、通用 settlement
或 generic branch writeback；完整群体模拟仍为 deferred。独立证据：
`.harness/verification/infra-governed-authority-contract-catalog-report.json`。
INF-4Q 的独立证据为
`.harness/verification/infra-government-promotion-owner-contract-catalog-report.json`。

这里的“世界”是共享事实、语义、调度和环境基础设施的职责范围，不是一个拥有
所有领域写入权的总运行时。文明能力、制度采用和六轴传导属于
[社会与制度玩法](../玩法系统/社会与制度玩法/README.md) 的后期玩法层；本目录只
约束它们如何消费既有事件/revision/调度基础。

规范入口为 [../全域架构/00-系统边界与责任矩阵.md](../全域架构/00-系统边界与责任矩阵.md)。

1. [00-标签体系与元规则引擎.md](00-标签体系与元规则引擎.md)
2. [13-实体档案语义因果与元规则.md](13-实体档案语义因果与元规则.md)
3. [12-时间调度跨域结算与回放.md](12-时间调度跨域结算与回放.md)
4. [14-群体模拟世界模式与文明演进.md](14-群体模拟世界模式与文明演进.md)
5. [18-生态环境与灾害系统.md](18-生态环境与灾害系统.md)
