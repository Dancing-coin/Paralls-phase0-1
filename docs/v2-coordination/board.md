# 迁移任务账本

- 版本 1（2026-11-22）。配套：[AUTONOMY.md](AUTONOMY.md)（自主推进规则与门禁）、[PROTOCOL.md](PROTOCOL.md)、[BOUNDARIES.md](BOUNDARIES.md)。
- 上位文档（文档仓库）：`docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md`（成功标准 1–11、单元 DoD U1–U10）、`docs/superpowers/plans/2026-11-22-architecture-v2-migration.md`（里程碑 M0–M8）。
- **本文件是"现在在做什么"的唯一权威。** 状态只在这里更新；线程每完成一个单元或换任务，改本文件对应行，不要只在对话里说。
- 状态取值：`待开工` / `进行中` / `待门禁` / `已合并` / `阻塞`。
- "标准"列指本任务服务的成功标准编号（规格第三节）。

## 一、当前里程碑

线程 A 已提交 M0.5、M1-1、Pool、共享提交构造与快照读取、部分规则包内容校验和 L5 声明编译。当前 A 分支 tip 为证据提交 `4fcdde27`，最新代码为 FactType Owner 顺序 tie-break `64421f00`；M6-5 的 gate-03 profile 已写入本地 A worktree `.env` 并完成配置探针。Pool 与 M6-5 后续均未进入 `origin/integration`。生产部署、生产执行与域级 U1–U11 仍有缺项，具体状态见任务表及各单元证据。线程 B 的进度以其交付的账本更新为准。

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
| M1-2 Holdings 原语 | A | 阻塞 | 原语实现 + 固定向量 | 事件 schema 未定义 reservation release/settlement、transfer 与 reservation 关联及总量账本；见 H-A-006 | 3 |
| M1-3 Pool 原语 | A | 待门禁 | Pool runtime `e6cb728c`、`022f1772`；Stormnight schema factory `39ecc2bb`；casualty refold `84d12a87`；[原语证据](../verification/m1-3-pool-runtime-20261122.md)、[factory 增量](../verification/m1-3-pool-production-registry-20261123.md)、[casualty 增量](../verification/m1-3-casualty-refold-trigger-20261123.md)、[正式规格静态审计](../verification/m1-3-pool-spec-audit-20261124.md) | 原有 Pool 与冻结选择、全量结果保持原记录。阈值转换事件在调整时原子提交；当前无生产调用点将 `SimulationDriver.current_tick` 接入 Pool `integrate` 或按生命周期边界调度。U1/U2/U5/U7/U8 和 G5 仍未闭环，详见审计及既有证据 | 3 |
| M1-4 Place 原语 | A | 待开工 | 同上 | 第 3 波后 | 3 |
| M1-5 Process 归并 | A | 待开工 | 同上 | S-5 已定：排在域迁移之后 | 3 |
| M2-1 读取边界清单更新 | A | 进行中 | Ownership / Credential 切片静态分类见 `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`，基于 `e349187e` | 随各域迁移继续更新 | 4 |
| M2-2 `read_as` | A | 阻塞 | 读取层入口 + 拒绝码 | 缺 event_time、principal 资格解析、event_type→FactType/visibility 映射及可接入的已迁移域读取方；见 H-A-005 | 4 |
| M2-3 known_time 推广 | A | 待开工 | 同上 | 随 M2-2 | 4 |
| M2-4 投影增量推进 | A | 待门禁 | 现有 `GameplayProjectionReplay` / `GameplayProjectionStartup`；证据 `docs/verification/m2-4-projection-incremental-20261123.md` | replay/startup 定向 15 passed；cursor、stream 连续性、失败关闭与 checkpoint-free rebuild 有测试；未修改共享 replay 源码。缓存性能方案已由共享 Owner 文档改列 M3-2 `StoreReadSnapshot` | 7 |
| M2-5 B4 前置设计 | A | 待门禁 | `docs/verification/g2-visibility-budget/b4-handoff-design-20261122.md` | 当前调用链与事务接口已静态核对。实施须负责人确认。 | 4 |
| M2-6 首条生产流受 epoch 保护 | A | 阻塞 | 实现 + 证据 | 待负责人选流并确定存储核心变更边界，见 H-A-008 | 4 |
| M3-1 `OwnerCommitBuilder` | A | 待门禁 | `docs/verification/m3-1-owner-commit-builder-20261122.md`；Ownership + Credential 调用点接入 | 定向 21 passed，ownership/shared-replay 24/990 problems=0；全量 10,418 passed、24 个既有失败，逐节点对照新增 0 | 3 |
| M3-2 `StoreReadSnapshot` 推广 | A | 待门禁 | `7c24d136`，Credential supersede 与 LandRight presentation；`docs/verification/m3-2-store-read-snapshot-20261122.md` | 定向 33 passed，七组选集 1,191 节点零差异。全量退出 1，24 失败与 M1-3 同签名，比 22 节点冻结基线多两项既有本地失败 | 3 |
| M3-3 R2 推广 | A/B | 待开工 | 按域并入 | 每域单独提交 | 7 |
| M3-4 `pinned_revisions` 校验 | A | 阻塞 | — | S-4 未决 | 3 |
| M4 第 1 波其余域 | 未定 | 待开工 | 每域一份设计与证据 | 待 M0-6 | 1–11 |
| M4 第 2 波 | 未定 | 待开工 | 同上 | 待 M0-6 | 1–11 |
| M4 第 3 波（含 debt） | 未定 | 待开工 | 同上 | debt 归属 Economy/Market，枢纽 | 1–11 |
| M4 第 4 波（枢纽） | 未定 | 待开工 | 同上 | 前序波次回归证据 | 1–11 |
| M5 规则包完整化 | A | 进行中 | M5-1 已接入 6 种离线声明，最新 `eebd34e5`。M5-2 父包叠层与哈希 `4747acaf`。M5-5 已提交 `facttype_refold_missing`、`facttype_scope_missing`、`primitive_missing`、`pack_defines_primitive`、`primitive_unknown`、`primitive_count_exceeded` 结构保证、FactType ID naming limits、`facttype_process_kind_invalid`，相关提交分别为 `f0c9108d`、`3907d4eb`、`a5823c4b`、`553c35bd`、`888ec615`、`1fb14ba4`、`3a0e35b6`、`d02e8c73`；原语登记整理 `cbee0c6c`。Owner-ordered resolution `64421f00`；Resolver rejection regression coverage `964cc5e4`。证据 `docs/verification/m5-5-facttype-refold-20261125.md`，回归选集 `m5-5-facttype-refold.json` | Exact M5-5 selection: 18 nodes, zero problems/improvements; two Resolver rejection tests are now registered. Prior follow-up targeted 136 passed, 6 warnings; registered 25 manifests/237 nodes zero differences; frozen four selections 179 nodes zero differences. shared-replay only completed 400 nodes plus 5 isolated nodes; full suite stopped around 31% with no final summary or exit status. `event_schema_ref` registry contract, other Validator rules, `temporal_effects`, production command registration, package-version write boundary, M5-3/M5-4 remain open. See H-A-051 and H-A-054 | 5 |
| M6 L5 引擎 | A | 进行中 | M6-1 reaction dispatch `dabb7f4e`、精确输出校验 `90af2255`、Place machine 输出兼容 `4023c182`；[dispatch evidence](../verification/m6-1-l5-dispatch-runtime-20261124.md)、[Place 输出 evidence](../verification/m6-5-place-machine-output-type-20261124.md)；声明加载 `6e7da420` 待门禁 | 新增 Place 输出单元定向 20 passed、ownership 24 零差异、自有选集 3 零差异；shared-replay 990 有两项外部 Port 8000 失败。`main.py` 生产注册、Morale/Presence handlers、条件/规则包加载、持久义务恢复未做；gate-impact 输入来源待项目负责人确认 | 6 |
| M6-1 Reaction 离线校验 | A | 待门禁 | `40df5929`、`7b0d69bf`；[证据](../verification/m6-1-reaction-20261123.md) | 定向 113 passed，17 组选集 1,268 节点零差异。全量 31 failed，其中 7 项额外路径错误在同 SHA 短路径复跑通过。异步触发前置见 H-A-011 | 6 |
| M6-2 Pipeline 声明与输入绑定 | A | 待门禁 | `abfe1443`；[证据](../verification/m6-2-pipeline-20261123.md) | 定向 121 passed，18 组选集 1,276 节点零差异。全量 24 个既有失败。生产前置见 H-A-012 | 6 |
| M6-3 Workflow 声明校验 | A | 待门禁 | `9eb80fe9`；[证据](../verification/m6-3-workflow-declarations-20261123.md) | 定向 129 passed，19 组选集 1,284 节点零差异。全量 10,530 passed、24 个既有失败，退出 1。生产重建需要可查询的步骤命令、回执及义务证据，见 H-A-013 | 6 |
| M6-4 Play pattern 声明与包加载 | A | 待门禁 | 编译器 `b7bb3605`，正常包加载 `6e7da420`；[加载证据](../verification/m6-composition-pack-loading-20261123.md) | 定向 133 passed，19 组选集 1,288 节点零差异。全量 10,534 passed、24 个既有失败、2 skipped、2 xfailed，退出 1，相对 `9eb80fe9` 无新增失败。应用注册与激活未做 | 6 |
| M6-5 守城 Demo 最小集 | A | 进行中 | H-A-020；Organization roster 9cb0cbd5、Facility integrity 34d7e734、Morale 7ff3a3cb、Presence d7ae1d38、L5/dispatcher 4506d907、signed input/recovery 6cf4ea86/102e4380、Information report 0fd74b4c/f442c1f9/3fe50ca5；layered Gate a9f5385a + Presence-v2 obligation settlement e246f2c0；[Presence follow-up evidence](../verification/m6-5-presence-impact-followup-20261124.md) | Prior exact commit focused 169 passed; M6-5 21, Information 25, siege Information 25 and ownership/modifier/equipment/inventory 179 nodes zero differences; shared-replay 990 zero differences. Exact backend suite: 10,628 passed, 19 failed, 2 skipped, 2 xfailed; same 19 nodes reproduced at parent 9b46742e. New local A worktree `.env` configures `gate-03` with three 0–100 layers, breach 40/45 and battering-ram -20. Configured signed-input smoke: 14 impacts, one breach, no automatic Place write; focused tests 184 passed, M6-5 selection 21 nodes zero differences. The `.env` is ignored and is not a deployment or branch artifact. No production-server deployment, live UE transport or full siege session. Root pytest collection separately lacks jsonschema. M6-5 remains incomplete and unmerged to integration | 6 |
| M7 第二真相收口 | A/B | 阻塞 | — | S-2、S-3 未决 | 11 |
| M8 综合验收 | 负责人 | 待开工 | 逐条对照 | 全部里程碑完成 | 1–11 |

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

## 四、更新规则

- 线程开工某任务：状态改 `进行中`，填单元名。
- 单元完成且自测通过：改 `待门禁`，填提交 SHA。
- 合并后：改 `已合并`，填合并 SHA 与标签。
- 遇到 AUTONOMY §二"必须停"的项：状态改 `阻塞`，并在对应行写清卡在哪，同时在 `handoff.md` 记一条。
- 本文件由两个线程共同追加/修改；同一行同一时间只有一个线程在改。
