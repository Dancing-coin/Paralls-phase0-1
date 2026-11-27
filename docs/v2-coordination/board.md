# 迁移任务账本

### Current A-tip verification update (2026-11-27)

- M6-5 focused startup/runtime recheck with explicit F-drive pytest `--basetemp`: `55 passed, 6 warnings`; evidence H-A-130.
- Current A-tip full backend suite at `3e87cadb`: `10,806 passed, 11 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. Seven nested harness evidence failures from the long F-drive temp path passed when rerun with a short F-drive temp root (`7 passed`); the remaining four are known dependency/Godot/runtime failures. Full details: H-A-173 and `docs/verification/a-tip-full-backend-20261127.md`. This is not a full-suite pass.
- M6-1 through M6-4 combined offline composition regression: `162 passed, 2 warnings`; evidence H-A-127. Production application activation and deployment dispatch remain unverified.

### M2-2 Morale event-time producer selection follow-up (2026-11-27)

- Code commit `4b2caed1` is now covered by registered U11 selection `docs/verification/selection/m2-2-morale-event-time.json`; frozen-baseline comparison returned `selected=2 problems=0 improvements=0`.
- Evidence: `docs/verification/m2-2-morale-event-time-20261127.md`. M2-2 remains blocked on shared principal/selector semantics, event-to-FactType visibility mapping, and a subject-facing reader.

### M2-2 Morale event-time producer (2026-11-27)

- Morale casualty refold now forwards an optional trusted `event_time` through the Pool adjustment commit. Evidence: `docs/verification/m2-2-morale-event-time-20261127.md` and H-A-121.
- M2-2 remains `阻塞` because the shared principal qualification/selector contract, event-to-FactType visibility mapping, and a subject-facing `read_as` entry point are still absent.

### M2-2 event-time producer inventory (2026-11-27)

- Static search and M6-5 call-path trace found source-time writes only for Information report publication and Morale propagation from an already timed casualty event. Signed physics `physics_tick` has no established mapping to session `world_tick`; Facility and Presence events have no demonstrated authoritative event-time producer. Evidence: `docs/verification/m2-2-event-time-producer-audit-20261127.md`, H-A-143. No tests ran and M2-2 remains blocked.

### M3-3 shared Owner replay receipt validation increment (2026-11-27)

- Commit `78fa4548`: `replay_duplicate` now validates the durable transaction and all committed event references before returning a duplicate receipt. Credential's local R2 check moved to the shared helper while preserving legacy/current event-type expectations. Focused shared and domain tests: 112 passed; other helper callers: 87 passed. New M3-3 selection `9/0/0`; frozen five selections `1,169` nodes with zero differences. Evidence: `docs/verification/m3-3-shared-owner-replay-validation-20261127.md`, H-A-144. M3-3 remains in progress because replay paths not using this helper still need inventory and validation. Full backend suite not run.

### M3-3 A-owned current-tip audit (2026-11-27)

- At current tip `684b4b1f`, Credential, Ownership, LandRight, Holdings, Pool, and package migration migrated command paths use `replay_duplicate`. The municipal drought assessment certificate remains a special settlement-plan path whose durable digest derives from the full command envelope after advisory/contract admission. It was classified without changing its contract. Focused municipal certificate and shared-helper tests returned `17 passed, 2 warnings`. Evidence: `docs/verification/m3-3-a-owned-current-tip-audit-20261127.md`.
- The municipal certificate retry gap was then closed in `7ba82daf`: the complete command-envelope digest and expected command/transaction/event type are validated through `replay_duplicate`. Focused tests returned `18 passed`; the new selection returned `1/0/0`; frozen five selections returned `1,169/0/0`. Evidence: `docs/verification/m3-3-municipal-certificate-replay-20261127.md`.
- The Morale casualty refold retry gap was closed in `11fd1754`/`2d0ef9c6`: shared replay validation now covers the durable Pool receipt while preserving historical-input retry behavior. Focused tests returned `27 passed`; the new selection returned `1/0/0`; frozen five selections returned `1,169/0/0`. Evidence: `docs/verification/m3-3-morale-refold-replay-20261127.md`.
- Facility layered impact and legacy/signed Presence retry paths now validate durable receipts through `replay_duplicate` in `32373b52`. Focused Facility/Presence/physical-input/M6-5 tests returned `76 passed, 6 warnings`; new selection `4/0/0`; frozen five selections `1,169/0/0`. Evidence: `docs/verification/m3-3-facility-presence-replay-20261127.md`. M3-3 remains in progress because other direct/custom replay paths remain.
- Information siege-report publication now validates its durable report receipt through `replay_duplicate` in `094669f1`, preserving retry at the committed publication tick. Focused Information/M6-5 tests returned `51 passed, 6 warnings`; new selection `1/0/0`; M6-5 Information selection `25/0/0`; frozen five selections `1,169/0/0`. Evidence: `docs/verification/m3-3-information-report-replay-20261127.md`. Knowledge-update and signed physical-input paths remain outside this increment.
- Signed siege physical-input retries now validate the durable receipt through `replay_duplicate` in `81e047e0`. Focused physical-input/Facility/Presence/M6-5 tests returned `77 passed, 6 warnings`; new selection `1/0/0`; M6-5 impact-gate selection `26/0/0`; frozen five selections `1,169/0/0`. Evidence: `docs/verification/m3-3-physical-input-replay-20261127.md`.
- M3-3 remains `进行中`; repository-wide direct/custom paths outside the A-owned migrated set still need inventory and validation.

- 版本 1（2026-11-22）。配套：[AUTONOMY.md](AUTONOMY.md)（自主推进规则与门禁）、[PROTOCOL.md](PROTOCOL.md)、[BOUNDARIES.md](BOUNDARIES.md)。
- 上位文档（文档仓库）：`docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md`（成功标准 1–11、单元 DoD U1–U10）、`docs/superpowers/plans/2026-11-22-architecture-v2-migration.md`（里程碑 M0–M8）。
- **本文件是"现在在做什么"的唯一权威。** 状态只在这里更新；线程每完成一个单元或换任务，改本文件对应行，不要只在对话里说。
- 状态取值：`待开工` / `进行中` / `待门禁` / `已合并` / `阻塞`。
- "标准"列指本任务服务的成功标准编号（规格第三节）。

## 一、当前里程碑

线程 A 已提交 M0.5、M1-1、Pool、共享提交构造与快照读取、部分规则包内容校验和 L5 声明编译。M5-3 deployment contract/startup archive wiring 已提交，listener 查询修复提交 `4d366b9e` 后，冻结 shared-replay 990 节点为零差异（H-A-081）。Pool 与 M6-5 后续均未进入 `origin/integration`。生产部署、生产执行与域级 U1–U11 仍有缺项，具体状态见任务表及各单元证据。线程 B 的进度以其交付的账本更新为准。

## 二、任务表

| 任务 | 归属 | 状态 | 产出 | 阻塞 / 放行条件 | 标准 |
|---|---|---|---|---|---|
| M0-1 runtime→Owner 映射（含 Combat 落点、Contract 事实清单） | B | 待门禁 | `docs/verification/m0-inventory-20261122/m0-1-runtime-owner-map.md` | 提交 `a7a66301`；只读，未跑测试 | 1、2 |
| M0-2 共享机制采用表 | B | 待门禁 | 同目录 `m0-2-mechanism-adoption.md` | 提交 `a7a66301` | 3 |
| M0-3 第二真相复核 | B | 待门禁 | 同目录 `m0-3-second-truth.md` | 提交 `a7a66301` | 11 |
| M0-4 读取方静态图 | B | 待门禁 | 同目录 `m0-4-readers.md` | 提交 `a7a66301`；993 调用 / 115 文件 | 4 |
| M0-5 Command 信封抽查 | B | 待门禁 | 同目录 `m0-5-command-envelope.md` | 提交 `a7a66301` | 1 |
| M0-6 波次表 | B | 待门禁 | 同目录 `m0-6-waves.md` | 提交 `a7a66301`、`c4a53e75`；静态输入，未验证 | 全部 |
| **M0.5 Owner 登记名单扩展** | A | 待门禁 | 规范短名名单 + validator 测试 + `docs/verification/m0.5-owner-registry-20261122.md` | 提交 `4b876f3d4dd92deba72aa2b49685fa4c39920ce2`；允许名单不表示 Owner 已实现 v2 声明 | 1、2 |
| M1-1 Bond 分片提交 | A | 待门禁 | 两个代码提交（片 1+3 合并、片 2）+ `docs/verification/m1-1-bond-slices-20261122.md` | 代码 SHA `b700f8c8`、`ae7d650e`；逐片选集无差异，全量 exit 1。混合账本兼容补丁 `e349187e` 定向 38 passed，16 组选集 1,258 节点零差异 | 3 |
| M1-2 Holdings 原语 | A | 阻塞 | Holdings runtime、v1 事件投影、FactType primitive 接受、checkpoint_at 前缀/后缀回放、按 item sum 聚合；docs/verification/m1-2-holdings-runtime-20261125.md 与 24 节点登记选集 | H-A-056 可追加事件合同已实现。定向测试 24 passed；G5 五组选集 1,169 节点均零差异。生产迁移需将现有 Inventory 命令消费接到 Holdings/Pool FactType，但正式映射要求 `inventory_runtime.py` 保留为 Inventory Owner 领域规则层，且该文件属于 A/B 共同边界。按边界协议暂停该集成。M1-2 选集 24 与 M5-5 选集 18 零差异；26 组登记选集和全量 backend suite 未运行 | 3 |
| M1-3 Pool 原语 | A | 待门禁 | Pool runtime `e6cb728c`、`022f1772`；Stormnight schema factory `39ecc2bb`；casualty refold `84d12a87`；[原语证据](../verification/m1-3-pool-runtime-20261122.md)、[factory 增量](../verification/m1-3-pool-production-registry-20261123.md)、[casualty 增量](../verification/m1-3-casualty-refold-trigger-20261123.md)、[正式规格静态审计](../verification/m1-3-pool-spec-audit-20261124.md)；当前 tip G5 `17` 节点零差异见 `../verification/a-current-tip-g5-20261126.md`；当前调用与内容审计见 H-A-074 | 原有 Pool 与冻结选择、全量结果保持原记录。阈值转换事件在调整时原子提交；生产没有非零 `rate_per_tick` Pool 内容或加载后的 Pool 注册表，故没有可合法调度的目标。`SimulationDriver.current_tick` 尚未接入 Pool `integrate` 或生命周期边界调度。U1/U2/U5/U7/U8 和生产调度仍未闭环 | 3 |
| M1-4 Place 原语 | A | 待决 | 静态合同审计 `docs/verification/m1-4-place-contract-audit-20261127.md`；当前仅有 Presence 通行性路径 | 需要空间注册表、通用 Place Owner/权限、持久事件字段及生产读写合同。不得复用 Presence 作为通用 Place 权威 | 3 |
| M1-5 Process 归并 | A | 待开工 | 同上 | S-5 已定：排在域迁移之后 | 3 |
| M2-1 读取边界清单更新 | A | 进行中 | Ownership / Credential 及 M6-5 Information、Morale、Presence、impact Pipeline 当前调用静态分类见 `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`；H-A-074、H-A-086、H-A-109、H-A-116、H-A-170 | Information 报告与知识已有窄版主体读取，经 session-bound `GameplayReadAs`；其他域读者分类随迁移继续更新。M2-2 的通用 selector/visibility 和 U7 仍未完成 | 4 |
| M2-2 `read_as` | A | 阻塞 | 静态合同审计、event-time source audit、schema-ref resolver `c55b009f`、FactType candidate index `b42a1c24`、compiled FactType identity `57d8f4f4`、event-to-instance resolver `9520808e` + strict null rejection `244a1209`；Information readers `97c21f06`、delay/distortion rejection `e941b91b`、`secret`/`debug_only` explicit denial `76a55dd2` / `docs/verification/m2-2-information-read-as-20261127.md`；current-tip G5 `docs/verification/a-current-tip-g5-20261127.md` | Information 两类 recipient-private FactType 经窄版共享 `read_as`；未实现的 delay/distortion 模型及 `secret`/`debug_only` 显式拒绝。当前定向 81 passed，新增选集 `3/0/0`，冻结五组 1,169 节点零差异。M2-2 总项仍阻塞：其他 selector 的历史资格解析、FactType-wide visibility 执行、legacy domain stream attribution 与 U7 未完成。全量未运行；以前记录的 `01b0d1c3` G5 和全量结果不代表本提交的验证 | 4 |
| M2-3 known_time 推广 | A | 待开工 | 同上 | 随 M2-2 | 4 |
| M2-4 投影增量推进 | A | 待门禁 | 现有 `GameplayProjectionReplay` / `GameplayProjectionStartup`；证据 `docs/verification/m2-4-projection-incremental-20261123.md` | replay/startup 定向 15 passed；cursor、stream 连续性、失败关闭与 checkpoint-free rebuild 有测试；未修改共享 replay 源码。缓存性能方案已由共享 Owner 文档改列 M3-2 `StoreReadSnapshot` | 7 |
| M2-5 B4 前置设计 | A | 待门禁 | `docs/verification/g2-visibility-budget/b4-handoff-design-20261122.md` | 当前调用链与事务接口已静态核对。实施须负责人确认。 | 4 |
| M2-6 首条生产流受 epoch 保护 | A | 阻塞 | 实现 + 证据 | 待负责人选流并确定存储核心变更边界，见 H-A-008 | 4 |
| M3-1 `OwnerCommitBuilder` | A | 待门禁 | `docs/verification/m3-1-owner-commit-builder-20261122.md`；当前 tip `caa062aa` 重验证定向 23 passed，ownership/shared-replay `24/0/0`、`990/0/0`；raw `F:/paralls-verification/thread-a/m3-1-current-tip-20261127-03/` | 共享机制当前 tip 已重验证；全量未运行，仍需合并门禁 | 3 |
| M3-2 `StoreReadSnapshot` 推广 | A | 待门禁 | `7c24d136`，Credential supersede 与 LandRight presentation；`docs/verification/m3-2-store-read-snapshot-20261122.md` | 定向 33 passed，七组选集 1,191 节点零差异。全量退出 1，24 失败与 M1-3 同签名，比 22 节点冻结基线多两项既有本地失败 | 3 |
| M3-3 R2 推广 | A/B | 进行中 | Shared `replay_duplicate` R2 validation and static audit, H-A-144/H-A-146; municipal certificate `7ba82daf`; Morale `2d0ef9c6`; Facility/Presence `32373b52`; Information report `094669f1`; signed input `81e047e0`; Information knowledge `33a1c38a`; evidence `docs/verification/m3-3-information-knowledge-replay-20261127.md` | A-owned Credential, Ownership, LandRight, Holdings, Pool, package migration, municipal certificate, Morale, Facility, Presence, Information report/knowledge, and signed physical-input replay paths use the shared helper. Other direct/custom paths remain to inventory and validate. No domain completion implied. | 7 |
| M3-4 `pinned_revisions` 校验 | A | 阻塞 | — | S-4 未决 | 3 |
| M4 第 1 波其余域 | 未定 | 待开工 | 每域一份设计与证据 | 待 M0-6 | 1–11 |
| M4 第 2 波 | 未定 | 待开工 | 同上 | 待 M0-6 | 1–11 |
| M4 第 3 波（含 debt） | 未定 | 待开工 | 同上 | debt 归属 Economy/Market，枢纽 | 1–11 |
| M4 第 4 波（枢纽） | 未定 | 待开工 | 同上 | 前序波次回归证据 | 1–11 |
| M5 规则包完整化 | A | 进行中 | M5-1 已接入 6 种离线声明，最新 `eebd34e5`。M5-2 父包叠层与哈希 `4747acaf`。M5-3 控制面事件/authority/archive hash-pin/global-sequence replay 实现 `aa871168`，可信 archive bootstrap API `2a5d6640`；世界级 M6-5 package consumer 接线 `29492189`，部署合同与启动 archive wiring 提交 `45480fb2`，exact-tip 定向 71 passed，证据 `docs/verification/m5-3-startup-contract-20261126.md`。项目负责人确认 `pack.migrated` 属平台控制面事件，不新增玩法 Owner；当前 tip migration 定向 21 passed 见 H-A-087。listener 查询修复 `4d366b9e` 后 shared-replay `990/0/0`（H-A-081）。M5-5 已提交 `facttype_refold_missing`、`facttype_scope_missing`、`primitive_missing`、`pack_defines_primitive`、`primitive_unknown`、`primitive_count_exceeded` 结构保证、FactType ID naming limits、`facttype_process_kind_invalid`、`event_schema_ref` 注册解析和 Resolver 确定性策略（`14f4fbd7`）；当前 tip M5-5 登记选择 `22` 节点零差异见 `../verification/a-current-tip-g5-20261126.md`，`temporal_effects` 正式合同审计见 `../verification/m5-5-temporal-effects-contract-audit-20261126.md`。M5-3/M6-5/Morale/Presence/Information 当前 tip 定向组合 `128 passed, 6 warnings`（H-A-120）。全量 at `7ab4d72e` collected 10,745, exited 1 with 23 failures; see H-A-097. | M5-3 runtime、bootstrap API、显式 M6-5 consumer 和可选部署合同已验证；冻结 shared-replay 990 节点在 `4d366b9e` 为零差异。真实服务器仍需提供四项环境输入，可信外部 manifest 来源、跨语言 hash canonicalization、生产启动和 UE transport 未验证。M5-5 仍在进行中；Credential 历史 schema 符号保留；M1-2 生产接线仍受共同 `inventory_runtime.py` 边界阻塞。`temporal_effects` 缺条目字段、引用空间、校验规则/拒绝码和消费者合同，生产命令注册及 package-version 写边界仍未完成，详见 H-A-079。生产 Gate 数值未配置；A worktree 的 `.env` 仅为本地演示配置。详见 H-A-066、H-A-068、H-A-069、H-A-076、H-A-077、H-A-078、H-A-079、H-A-081、H-A-087、H-A-097、H-A-120 | 5 |
| M6 L5 引擎 | A | 进行中 | M6-1 reaction dispatch `dabb7f4e`、精确输出校验 `90af2255`、Place machine 输出兼容 `4023c182`；声明加载 `6e7da420`；M6-5 main startup 注册、三个 trusted output、Morale/Presence/Information handlers、规则包/condition 装配、signed input recovery 及基于 durable receipts 的 obligation metadata 投影已实现，证据见 `docs/verification/m6-5-production-assembly-audit-20261126.md` 与 H-A-091；原始四流 `input_revision_vector` 可从 signed input 的 event-sequence snapshot 重建并 durable replay，提交 `4cf77e5d`，证据见 `docs/verification/m6-5-shared-pipeline-input-vector-20261126.md`；M6-5 versioned Pipeline declaration/consumer 和 Resolver handler 接线在当前工作区验证，见 `docs/verification/m6-5-impact-gate-pipeline-20261127.md`、H-A-115 | 生产 Gate 数值只在 `.env.example` 中作为演示值，无部署目标或权威参数来源。`deadline_world_tick` 保持 unknown。无生产部署、UE 实机传输或完整 siege run 证据；全量 backend suite 未运行 | 6 |
| M6-1 Reaction 离线校验 | A | 待门禁 | `40df5929`、`7b0d69bf`；[证据](../verification/m6-1-reaction-20261123.md) | 定向 113 passed，17 组选集 1,268 节点零差异。全量 31 failed，其中 7 项额外路径错误在同 SHA 短路径复跑通过。异步触发前置见 H-A-011 | 6 |
| M6-2 Pipeline 声明与输入绑定 | A | 待门禁 | `abfe1443`；[证据](../verification/m6-2-pipeline-20261123.md) | 定向 121 passed，18 组选集 1,276 节点零差异。全量 24 个既有失败。生产前置见 H-A-012 | 6 |
| M6-3 Workflow 声明校验 | A | 待门禁 | `9eb80fe9`；[证据](../verification/m6-3-workflow-declarations-20261123.md) | 定向 129 passed，19 组选集 1,284 节点零差异。全量 10,530 passed、24 个既有失败，退出 1。生产重建需要可查询的步骤命令、回执及义务证据，见 H-A-013 | 6 |
| M6-4 Play pattern 声明与包加载 | A | 待门禁 | 编译器 `b7bb3605`，正常包加载 `6e7da420`；[加载证据](../verification/m6-composition-pack-loading-20261123.md) | 定向 133 passed，19 组选集 1,288 节点零差异。全量 10,534 passed、24 个既有失败、2 skipped、2 xfailed，退出 1，相对 `9eb80fe9` 无新增失败。应用注册与激活未做 | 6 |
| M6-5 守城 Demo 最小集 | A | 进行中 | H-A-020；Organization roster 9cb0cbd5、Facility integrity 34d7e734、Morale 7ff3a3cb、Presence d7ae1d38、L5/dispatcher 4506d907、signed input/recovery 6cf4ea86/102e4380、Information report 0fd74b4c/f442c1f9/3fe50ca5；layered Gate a9f5385a + Presence-v2 obligation settlement e246f2c0；formal obligation metadata projection H-A-091；shared input vector snapshot projection `4cf77e5d` / H-A-113；Place schema reference H-A-114；versioned `impact_gate` declaration, production Resolver consumer and fail-closed Owner checks verified in current worktree by H-A-115; registered selection `26/0/0`; production input audit H-A-171 | M6-5 Pipeline declaration and production consumer are implemented in the current worktree; frozen Ownership/shared-replay selections returned `24/0/0` and `990/0/0`. Production Gate values and deployment target remain unavailable: official demo sources define the four-layer order but no numeric profile, and `.env.example` values are demonstration-only. UE transport, complete siege run and full backend suite remain unverified. `deadline_world_tick` remains unknown. | 6 |
| M7 第二真相收口 | A/B | 阻塞 | — | S-2、S-3 未决 | 11 |
| M8 综合验收 | 负责人 | 待开工 | 逐条对照 | 全部里程碑完成 | 1–11 |

### M5-5 FactType primitive-field increment (2026-11-26)

- 本增量证据：`docs/verification/m5-5-facttype-primitives-20261126.md`。在 exact tip `30c4bf50` 定向 136 passed；M5-5 selection 38/0/0；冻结 ownership/modifier/equipment/inventory/shared-replay 选择分别 24/0/0、12/0/0、87/0/0、56/0/0、990/0/0。
- 合并工作区全量在 `1be69ba3` collected 10,759，exit 1：10,693 passed、62 failed、2 skipped、2 xfailed。失败尚未逐项对照 parent 基线，保持未分类。M5-5 仍进行中。

### M5-5 failure triage follow-up (2026-11-26)

- `955fd258` aligns the M1-2 Holdings test fixtures with the required FactType identity and primitive-field rejection contract. Focused validator/registry/Holdings tests: `139 passed`; M5-5 selection: `38/0/0`.
- The prior 62 full-suite failure node IDs now return `57 passed, 5 failed`; those five node IDs reproduce at parent `9cee2f25`. This is a sampled parent comparison, not full-suite or frozen G0 baseline evidence. Full backend suite at exact tip `955fd258` remains unrun. Details: `docs/verification/m5-5-facttype-primitives-20261126.md` and H-A-106.

### M5-5 exact-tip backend regression follow-up (2026-11-26)

- Backend suite at `8febee38`, scoped to `backend/tests`: `10,750 passed, 7 failed, 2 skipped, 2 xfailed`, exit 1. Three failures match frozen G0; `cold_ready` is the known out-of-scope H-A-098 failure; recovery-measurement reproduces at parent `c0f85969`; two repeated-profile variants conflict with the existing `D:\cl-laya` backend on Port 8000. No new M5-5 failure was identified.
- Raw output: `F:/paralls-verification/thread-a/m5-5-current-tip-backend-full-20261126-01/full.log`. Full suite is not a zero-failure pass. M5-5 remains in progress.

### M5-5 rule-catalog current-tip correction (2026-11-26)

- At A tip `27c2aaa0`, resolution-order uniqueness/density and all four FactType identity values have regression coverage; the earlier H-A-099 statement that direct ordering assertions were absent is superseded by H-A-101/H-A-102. Current-tip validator/registry tests: `136 passed, 2 warnings in 3.32s`; evidence is `docs/verification/m5-5-rule-catalog-coverage-20261126.md` and raw output is `F:/paralls-verification/thread-a/m5-5-rule-catalog-current-tip-20261126-01/focused.log`.
- M5-5 remains in progress. Formal Owner declaration fields exist, but code has no machine-readable declaration registry/compiler or complete code-consumable declaration set. Invariant expressions lack a complete grammar; Resolver purity lacks a consumed capability/side-effect attestation. Impact-profile cycles are not expressible in the flat format, and `temporal_effects` still lacks its entry/consumer/persistence contract. Clarified in H-A-110 and `docs/verification/m5-5-rule-catalog-coverage-20261126.md`.

## 三、待决（负责人需表态）

### M6-5 最新进展（2026-11-24）

- A 已提交并独立验证三片。signed physical evidence `22bf0615` + replay decoder `6cf4ea86`，Owner consumers 和 HTTP Gateway `43490816` + Presence route assertion `da7d9a1b`，可选 gate content config `55161d47`。各片定向与冻结选集结果见 `docs/verification/m6-5-siege-physical-inputs-plan-20261124.md`。
- `SIEGE_FACILITY_GATE_PROFILES_JSON` 已接入生产启动。未提供权威配置时仍保持 `not_configured`，不采用测试值写完整度事实。Presence 缺可信证据仍 unknown 且零写入。
- 当前 HTTP handler 在有效签名 evidence 入库后直接调用 Facility Owner。正式 `impact_gate` 的耐久 obligation executor 尚未接入现有 L5 生产路径。因此 M6-5 仍未端到端完成；全量未运行，shared-replay 每片各有两项 Port 8000 外部服务失败。
- Information report source delivered in A commits `0fd74b4c`, `f442c1f9`, and `3fe50ca5`. Exact-tip focused tests: 199 passed, 6 warnings; the Information report selection: 25 selected, 0 problems, 0 improvements. The merged-worktree full suite had 10,603 passed, 21 failed, 2 skipped, 2 xfailed, exit 1. Failures were not rerun on the parent SHA, so they are not classified as baseline failures. Details: `docs/verification/m6-5-information-report-source-20261124.md`.

### M6-5 本地 Gate 配置 follow-up（2026-11-25）

- A worktree 根 `.env` 配置了 `gate-03`，三层耐久各为 0–100、初始 100；完整度破口进出阈值为 40/45；攻城槌输入为 -20。该文件被 Git 忽略，配置目前只作用于 A worktree。
- 配置运行探针 14 次签名输入后，门扇和门闩耐久为 0，完整度为 20，产生一次 breach-enter；没有自动写 Place。定向 184 passed, 6 warnings，M6-5 选集 21 节点零差异。原始输出与边界见 `docs/verification/m6-5-impact-gate-layered-execution-20261124.md`。
- 这不是服务器部署值，也没有完成 UE 实机传输或完整 siege playthrough。M6-5 仍进行中。

| 编号 | 事项 | 影响 | 状态 |
|---|---|---|---|
| S-2 | B0 六字段的 Owner 归属 | M7；涉及 B0 的域迁移 | 未决，等 M0-3 事实 |
| S-3 | 司命 Heavenly Graph 保留或砍 | M7 | 未决，等 M0-3 事实 |
| S-4 | `pinned_revisions` 补校验是否算行为改变 | M3-4 | 未决 |
| S-1 | Combat 分类 | M4 波次、M0-1 | 未决，等 M0-1 |
| S-7 | 11-09 的逐域探针并入成功标准 8 | 验收口径 | 未决 |
| — | 谁做 M4 各波（A 或 B 或轮换） | 全部域迁移 | 未决，等 M0-6 |
| — | M2-6 选哪条生产流受 epoch 保护 | L0 强制 | 未决 |
| M5-3 | `pack.migrated` 的 authority 分类及初始包版本/归档/replay 接线 | M5 L4 | 平台控制事件分类已决定；运行切片 `aa871168`、目录/hash bootstrap API `2a5d6640`；`main.py` 启动合同与 archive consumer 已在 `45480fb2` 接入，exact-tip M5-3/Ownership 选择 22/24 零差异（H-A-078）；修复验证 listener 查询后，精确 A 代码提交 `4d366b9e` 的 shared-replay `990/0/0`（H-A-081）。历史多次迁移回放修复 `c9a22c53` 定向 35 passed，冻结选集 1,169 节点、28 组登记选集 309 次节点选择均零差异（H-A-095、H-A-096）。仍需部署侧提供真实 world 上下文、初始 pin、archive 目录和可信 hash，并完成生产启动与历史 replay |

## 四、更新规则

- 线程开工某任务：状态改 `进行中`，填单元名。
- 单元完成且自测通过：改 `待门禁`，填提交 SHA。
- 合并后：改 `已合并`，填合并 SHA 与标签。
- 遇到 AUTONOMY §二"必须停"的项：状态改 `阻塞`，并在对应行写清卡在哪，同时在 `handoff.md` 记一条。
- 本文件由两个线程共同追加/修改；同一行同一时间只有一个线程在改。


### M6-5 本地 Gate→Presence obligation follow-up（2026-11-25）

- 已在配置探针的 14 次签名 Gate impact 后提交签名 Presence assessment。输出确认 `breach_events=1`、完整度保持 20、`place_commits=1`、`passability=passable`、`latest_impact_obligation=settled`。原始日志在 `F:/paralls-verification/thread-a/m6-5-gate-presence-obligation-20261125-01/runtime.log`。这是本地运行时闭环，未覆盖 UE 实机传输、生产部署或完整 siege playthrough。

### M6-5 tracked Gate profile follow-up（2026-11-26）

- 已将本地验证过的 `gate-03` integrity/durability 初始值、阈值与 battering-ram delta 写入跟踪的根 `.env.example`。配置 JSON 通过 `FacilityGateProfileSettings` 验证；A worktree 定向配置/runtime 测试 `52 passed, 6 warnings`，原始输出 `F:/paralls-verification/thread-a/m6-5-gate-profile-template-20261126-02/pytest.log`。应用启动通过 `SIEGE_FACILITY_GATE_PROFILES_JSON` 消费该配置。仓库没有生产部署清单或服务器目标，故不声称生产实例已加载。M6-5 保持进行中。

### M5-3 shared-replay revalidation（2026-11-26）

- 当前 A 代码状态下 frozen shared-replay `selected=990 problems=0 improvements=0`。停滞节点单独通过。根因为 `common._find_listener_pid` 的 PowerShell listener 查询挂起；独立 `netstat` 确认端口 8000 无监听后，通过 F 盘临时 shim 完成完整比较，没有停止外部进程。原始输出在 `F:/paralls-verification/thread-a/m5-3-shared-replay-complete-20261126-01/shared-replay/`。M5-3 的部署 manifest 与 package startup wiring 仍未完成。

### M5-3 shared-replay current-tip attempt（2026-11-26）

- At `bd02be3c`, the frozen 990-node comparison completed 10 of 25 batches, then stopped in batch 0010 at `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`. The run has no aggregate result and is incomplete. Evidence: `docs/verification/m5-3-shared-replay-current-tip-20261126.md`; raw output: `F:/paralls-verification/thread-a/m5-3-shared-replay-exact-tip-20261126-02/`.
- This partial attempt was superseded by the completed exact-code comparison at `4d366b9e`, recorded in H-A-081.

### M6-5 versioned Gate profile contract（2026-11-26）

- Commit `d693686b` adds compatible `schema_version=1` parsing and rejects invalid or unknown Gate profile fields. Focused tests returned `71 passed, 6 warnings`; the 19-node registered selection returned `problems=0 improvements=0`.
- The backend full-suite attempt was interrupted at about 31% after roughly 40 minutes. The first failure was reproduced on parent `6d31a831` as the same missing-`tokenizers` baseline failure; the second marker remains unclassified. Evidence: `docs/verification/m6-5-gate-profile-contract-20261126.md`.
- Follow-up triage located the second marker at node 2308, `test_task45_headless_probe_observes_shared_path_and_contact_contract`. It fails with the same Godot `CharacterMotor` parse errors on current `cdf99158` and parent `6d31a831`. Both visible failures are pre-existing for this change; the interrupted full suite is still incomplete. See H-A-073 and the evidence addendum.
- Production Gate values remain unset under H-A-039. The profile values in `.env.example` are explicitly a demonstration profile; M6-5 remains in progress.

- M3-2 current-tip revalidation: A tip `259314e2`, focused `34 passed, 2 warnings`; registered selection `7/0/0`; frozen ownership/modifier/equipment/inventory/shared-replay selections `24/12/87/56/990`, all `problems=0 improvements=0`. Evidence: `docs/verification/m3-2-store-read-snapshot-20261122.md`. The M3-2 task remains pending integration gate.

- M2-1 current-tip static increment: A tip `bc639342` enumerated `OwnerCommitBuilder` callers in Credential, Holdings, Ownership and Pool, and `StoreReadSnapshot` callers in Credential and LandRight. Evidence appended to `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md` and H-A-134. No tests ran; M2-2 contracts remain open.

- M2-4 current-tip revalidation: A tip `74a291c4`, replay/startup focused `15 passed, 2 warnings`, explicit F-drive basetemp. Evidence `docs/verification/m2-4-projection-incremental-20261123.md` and H-A-135. No code changed; task remains pending integration gate.

- M6-1 current-tip revalidation: A tip `1e318bb5`, focused `154 passed, 2 warnings`; Reaction selection `14/0/0`; L5 dispatch selection `5/0/0`. Evidence `docs/verification/m6-1-reaction-20261123.md` and H-A-136. Offline behavior is current-tip verified; production dispatch remains unverified and task stays pending gate.

- M6-2 current-tip revalidation: A tip `9f4cfd82`, focused `154 passed, 2 warnings`; Pipeline selection `8/0/0`; ownership `24/0/0`; shared-replay `990/0/0`. Evidence `docs/verification/m6-2-pipeline-20261123.md` and H-A-137. Offline behavior is current-tip verified; production activation remains unverified and task stays pending gate.

- M6-3 current-tip revalidation: A tip `8ff452c7`, focused `162 passed, 2 warnings`; Workflow selection `8/0/0`; ownership `24/0/0`; shared-replay `990/0/0`. Evidence `docs/verification/m6-3-workflow-declarations-20261123.md` and H-A-138. Offline behavior is current-tip verified; production workflow/obligation recovery remains unverified and task stays pending gate.

- M6-4 current-tip revalidation: A tip `90e72a67`, focused `162 passed, 2 warnings`; Play Pattern selection `12/0/0`; ownership `24/0/0`; shared-replay `990/0/0`. Evidence `docs/verification/m6-4-play-pattern-20261122.md` and H-A-139. Offline behavior is current-tip verified; production activation remains unverified and task stays pending gate.

- M6-5 current-tip regression at `cd1b1c9b`: focused `228 passed, 6 warnings`; layered impact/production wiring/Information selections `26/6/25`, each zero differences; frozen ownership/shared-replay `24/990`, zero differences. Evidence `docs/verification/m6-5-impact-gate-pipeline-20261127.md`, H-A-140. Production Gate values, deployment target, UE transport and complete siege execution remain unverified; `deadline_world_tick` unknown; M6-5 remains in progress.

- M5-5 current-tip validator/registry revalidation at `e002eb24`: focused `165 passed, 2 warnings`; M5-5 selection `38/0/0`; frozen five selections 1,169 nodes, all zero differences. Evidence `docs/verification/m5-5-facttype-primitives-20261126.md`, H-A-141. Machine-readable Owner declarations, invariant grammar, Resolver capability attestation and `temporal_effects` remain unspecified; M5-5 remains in progress.

- M5-5 principal selector registration increment at current worktree: FactType `learnable_by` selector syntax and nested `group_of` rejection. Evidence `docs/verification/m5-5-selector-registration-20261127.md`; new selection `6/0/0`; focused FactType/RulePack/package/Information tests `218 passed, 6 warnings`. All 30 existing registered selections plus frozen five selections completed with zero differences. Runtime principal qualification and `read_as` remain unimplemented; M2-2 remains blocked and M5-5 remains in progress. Full backend suite not run for this increment.

- M5-3 current-tip package migration/archive revalidation at `e09bcf1a`: focused `74 passed, 6 warnings`; M5-3 selection 23/0/0; Ownership 24/0/0; shared-replay 990/0/0. Evidence `docs/verification/m5-3-startup-contract-20261126.md`, H-A-142. Production manifest trust source, cross-language hash canonicalization, Gate values, deployment target, UE transport and complete siege execution remain unverified; M5-3/M6-5 remain in progress.

### M5-5 FactType identity contract increment (2026-11-26)

- A 将正式 FactType identity contract 接入 `fact_type_registry.py`。缺失 identity、未知 identity、singleton 与非 global scope、以及非 singleton 与 global scope 均有专用拒绝路径和回归测试；直接编译测试 fixture 已补齐 `entity_ref`。证据：`docs/verification/m5-5-facttype-identity-20261126.md`。
- 本增量状态为待门禁。定向 124 passed；M5-5 登记选集 27/0/0；冻结五组选集 ownership 24/0/0、modifier 12/0/0、equipment 87/0/0、inventory 56/0/0、shared-replay 990/0/0。全量 10,745 节点未因本增量重跑，M5-5 broader catalog 仍进行中。
- 后续测试断言增量已提交 `7690df59deb49f5af179dcca92f552a1caaf890f`，验证 resolution order 唯一且从 10 连续递增。M5-5 broader catalog 仍进行中。
- 四种 FactType identity 的正反例现均登记在 M5-5 selection，validator 定向 123 passed，29 节点选择零差异；增量提交待创建。全量未重跑，M5-5 broader catalog 仍进行中。

### M6-5 B Information checkpoint-tail replay verification (2026-11-27)

- At A baseline `99c7be5f`, B added a durable Information report/knowledge checkpoint-tail test and persisted the existing top-level `event_time` on the knowledge event. Focused Information tests returned 24 passed. Full backend regression returned 10,769 passed and 22 failed; 17 failed on the unchanged parent, while five other failures passed in isolated reruns on parent and current worktrees. Evidence: `docs/verification/information-replay-20261127/evidence.md`. The Information unit remains pending gate.
