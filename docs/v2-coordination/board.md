# 迁移任务账本

- 版本 1（2026-11-22）。配套：[AUTONOMY.md](AUTONOMY.md)（自主推进规则与门禁）、[PROTOCOL.md](PROTOCOL.md)、[BOUNDARIES.md](BOUNDARIES.md)。
- 上位文档（文档仓库）：`docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md`（成功标准 1–11、单元 DoD U1–U10）、`docs/superpowers/plans/2026-11-22-architecture-v2-migration.md`（里程碑 M0–M8）。
- **本文件是"现在在做什么"的唯一权威。** 状态只在这里更新；线程每完成一个单元或换任务，改本文件对应行，不要只在对话里说。
- 状态取值：`待开工` / `进行中` / `待门禁` / `已合并` / `阻塞`。
- "标准"列指本任务服务的成功标准编号（规格第三节）。

## 一、当前里程碑

线程 A 已提交 M0.5、M1-1、Pool、共享提交构造与快照读取、部分规则包内容校验和 L5 声明编译。最新提交为 Pool casualty refold 触发 `84d12a87`，证据同步提交 `025ef31d`；A 分支已推送。Pool 尚未进入 `origin/integration`。生产执行与域级 U1–U11 仍有缺项，具体状态见任务表及各单元证据。线程 B 的进度以其交付的账本更新为准。

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
| M1-3 Pool 原语 | A | 待门禁 | Pool runtime `e6cb728c`、`022f1772`；Stormnight schema factory `39ecc2bb`；casualty refold `84d12a87`；[原语证据](../verification/m1-3-pool-runtime-20261122.md)、[factory 增量](../verification/m1-3-pool-production-registry-20261123.md)、[casualty 增量](../verification/m1-3-casualty-refold-trigger-20261123.md) | Pool 17 项与冻结 ownership/modifier/equipment/inventory 179 项、其余已登记选集 104 项均零差异；shared-replay 988/990 匹配，两项因外部端口 8000 占用失败。casualty 子单元全量未运行。合并状态既有全量 10,564 节点为 10,532 passed、28 failed、2 skipped、2 xfailed，退出 1，新增 4 签名且未归因完。不得记作 G5 通过。原 U1/U2/U5/U7/U8 缺口见证据 | 3 |
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
| M5 规则包完整化 | A | 进行中 | M5-1 已接入 6 种离线声明，最新 `eebd34e5`。M5-2 父包叠层与哈希 `4747acaf`，M5-5 已做静态盘点 | 122 项定向测试，14 组选集 1,245 节点零差异。合并状态全量 `a750c824` 10,491 passed、24 failed、2 skipped、2 xfailed，退出 1。相对 `47f931fb` 无新增失败。需要补齐 `temporal_effects` 定义合同、生产命令注册与包版本写入边界，见 H-A-009/010。M5-3 生产迁移与 M5-4 应用接线待决 | 5 |
| M6 L5 引擎 | A | 进行中 | M6-1 reaction dispatch `dabb7f4e`、精确输出校验 `90af2255`、Place machine 输出兼容 `4023c182`；[dispatch evidence](../verification/m6-1-l5-dispatch-runtime-20261124.md)、[Place 输出 evidence](../verification/m6-5-place-machine-output-type-20261124.md)；声明加载 `6e7da420` 待门禁 | 新增 Place 输出单元定向 20 passed、ownership 24 零差异、自有选集 3 零差异；shared-replay 990 有两项外部 Port 8000 失败。`main.py` 生产注册、Morale/Presence handlers、条件/规则包加载、持久义务恢复未做；gate-impact 输入来源待项目负责人确认 | 6 |
| M6-1 Reaction 离线校验 | A | 待门禁 | `40df5929`、`7b0d69bf`；[证据](../verification/m6-1-reaction-20261123.md) | 定向 113 passed，17 组选集 1,268 节点零差异。全量 31 failed，其中 7 项额外路径错误在同 SHA 短路径复跑通过。异步触发前置见 H-A-011 | 6 |
| M6-2 Pipeline 声明与输入绑定 | A | 待门禁 | `abfe1443`；[证据](../verification/m6-2-pipeline-20261123.md) | 定向 121 passed，18 组选集 1,276 节点零差异。全量 24 个既有失败。生产前置见 H-A-012 | 6 |
| M6-3 Workflow 声明校验 | A | 待门禁 | `9eb80fe9`；[证据](../verification/m6-3-workflow-declarations-20261123.md) | 定向 129 passed，19 组选集 1,284 节点零差异。全量 10,530 passed、24 个既有失败，退出 1。生产重建需要可查询的步骤命令、回执及义务证据，见 H-A-013 | 6 |
| M6-4 Play pattern 声明与包加载 | A | 待门禁 | 编译器 `b7bb3605`，正常包加载 `6e7da420`；[加载证据](../verification/m6-composition-pack-loading-20261123.md) | 定向 133 passed，19 组选集 1,288 节点零差异。全量 10,534 passed、24 个既有失败、2 skipped、2 xfailed，退出 1，相对 `9eb80fe9` 无新增失败。应用注册与激活未做 | 6 |
| M6-5 守城 Demo 最小集 | A | 进行中 | H-A-020 输入合同 + [A 跨域实施计划](../verification/m6-5-authoritative-input-plan-20261123.md)；Organization roster `9cb0cbd5`、Facility integrity Pool writer `34d7e734`、Pool historical read/pin `da8fa3b8`、Morale refold `7ff3a3cb`、Presence passability `d7ae1d38`、L5 Place 输出类型 `4023c182`、生产 dispatcher/handler `4506d907`；[生产接线证据](../verification/m6-5-production-wiring-20261124.md)、[Presence evidence](../verification/m6-5-presence-passability-20261124.md)、[Place 输出 evidence](../verification/m6-5-place-machine-output-type-20261124.md) | `main.py` 已装配 Morale/Presence reaction dispatcher；生产端首次有效 casualty 初始化并重算 Morale，Presence 无可信输入时返回 unknown 且零写入。定向 80 passed；M6-5 永久选集 4 零差异；ownership 24 零差异。shared-replay 990 有 2 个外部 Port 8000 失败。正式规格给定的城门输入路径是 UE 碰撞证据经 Gateway 进入 `impact_gate` obligation；现有代码只有受击管线编译器和角色战斗接线，没有门 impact Resolver/内容参数或 UE Presence 回执入口。不能将调用方伤害数或 breach 本身当作权威输入。U1–U9 部分或未完成，U10/U11 已记录。全量未在 `4506d907` 运行；M6-5 仍未端到端验证，Pool 也未进入 integration | 6 |
| M7 第二真相收口 | A/B | 阻塞 | — | S-2、S-3 未决 | 11 |
| M8 综合验收 | 负责人 | 待开工 | 逐条对照 | 全部里程碑完成 | 1–11 |

## 三、待决（负责人需表态）

### M6-5 最新进展（2026-11-24）

- A 已提交并独立验证 signed physical evidence slice：`22bf0615` + `6cf4ea86`。定向 13 passed，ownership `24/24 problems=0`；shared-replay `990` 中 2 个 Port 8000 外部服务失败，见 `docs/verification/m6-5-siege-physical-inputs-plan-20261124.md`。
- Facility / Presence 消费与两个 HTTP 输入 route 已提交 `43490816` 并独立验证：定向 20 passed，ownership `24/24 problems=0`，shared-replay `990` 中 2 个 Port 8000 外部服务失败。
- 生产配置仍没有 gate impact profile、Facility initial/threshold 值。未提供这些权威内容前，HTTP Gate route 会持久化已验签回执并明确返回 `not_configured`，不采用测试数值写生产事实。Presence 缺证据仍 unknown 且零写入。

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
