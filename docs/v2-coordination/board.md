# 迁移任务账本

### M1-3 Pool reader inventory current-tip recheck (2026-11-28)

- Static inventory now maps eight A-side production reader/consumer paths across Pool, Morale, Facility integrity/layered settlement, impact obligations, Place passability, siege physical input, and the graph projector. Direct test coverage is mapped per reader. Formal Owner definitions classify Morale/Formation and Production/Facility as domain Owners; Pool remains the shared primitive, not an Owner.
- Eight focused reader test files returned `142 passed, 6 warnings` at code/test tip `0b7852fe`; Python `3.12.2`, SQLite `3.43.1`, and A-worktree import path verified. No runtime or package content changed.
- Evidence: `docs/verification/m1-3-pool-reader-inventory-20261128.md`; raw output under `F:/paralls-verification/thread-a/m1-3-reader-inventory-20261128-01/`. This is complete for the searched A repository paths, static for external services, and does not close U7 or all of U6.

### M1-3 Pool replay receipt consumer check (2026-11-28)

- Test commit `0b7852fe` verifies that Pool maps an unresolvable `committed_event_ids` receipt to `pool_replay_event_missing` and leaves the store snapshot unchanged. Pool U11 is now 34 nodes.
- Pool focused tests returned `20 passed, 2 warnings`; M1-3 Pool selection `34/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections `24/12/87/56/990`, all zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m1-3-pool-r2-receipt-consumer-20261128.md`; raw outputs under `F:/paralls-verification/thread-a/m1-3-pool-r2-receipt-consumer-20261128-01/`. This closes the tested Pool consumer R2 path only; M1-3 remains in progress.

### M1-3 Pool checkpoint-free state digest recheck (2026-11-28)

- Test commits `d9f1206a` and `b398cddf` make the Pool rebuild regression compare a canonical public projection state digest after SQLite ledger close/reopen and full event replay. The durable snapshot has no projection checkpoints; this verifies the Pool no-checkpoint branch, not physical deletion of a Pool checkpoint.
- Pool focused tests returned `19 passed, 2 warnings`; M1-3 Pool selection `33/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections `24/12/87/56/990`, all zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m1-3-pool-r3-checkpoint-free-20261128.md`; raw outputs under `F:/paralls-verification/thread-a/m1-3-pool-r3-checkpoint-free-20261128-02/`. U5 remains partial because physical checkpoint deletion and other M1-3 consumer paths are not covered. M1-3 remains in progress.

### M3-3 Information replay current-tip recheck (2026-11-28)

- Fetched B Information replay tip `e185cfa8`. Its writer, checkpoint-tail test, and selection are already present in A through `07db5404`, `400d4ff9`, and `0c3173f2`; no B branch merge or duplicate cherry-pick was needed.
- At A tip `66bb9116`, focused tests returned `32 passed, 6 warnings`; Information selection `26/0/0`; frozen selections Ownership/Modifier/Equipment/Inventory/shared-replay returned `24/12/87/56/990`, all zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m3-3-information-knowledge-replay-20261127.md`; raw outputs under `F:/paralls-verification/thread-a/information-b-delivery-current-20261128-01/`. M3-3 remains in progress. The next Organization candidate is in a shared fourth-wave ban and was not modified.

### M3-3 Public project execution acknowledgment replay increment (2026-11-28)

- Code commit `a47dacd0` routes acknowledgment retries through `replay_duplicate`; corrupt transaction receipts reject with the existing domain error and no writes. Focused acknowledgment/execution/workshop tests `16 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `24/12/87/56/990`, all zero differences.
- Evidence: `docs/verification/m3-3-public-project-ack-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-public-project-ack-replay-20261128-01/`. Full backend suite was not run. M3-3 remains in progress.

### M3-3 Government public milling notice replay increment (2026-11-28)

- Code commit `5f823c51` routes milling notice retries through `replay_duplicate`; corrupt transaction receipts reject with the existing domain error and no writes. Focused milling/acknowledgement/private follow-on tests `26 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `24/12/87/56/990`, all zero differences.
- Evidence: `docs/verification/m3-3-government-public-milling-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-government-public-milling-replay-20261128-01/`. Full backend suite was not run. M3-3 remains in progress.

### M3-3 Government public workshop notice replay increment (2026-11-28)

- Code commit `e1b520d1` routes public notice retries through `replay_duplicate`; corrupt transaction receipts reject with the existing domain error and no writes. Focused public notice/private follow-on tests `17 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `24/12/87/56/990`, all zero differences.
- Evidence: `docs/verification/m3-3-government-public-notice-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-government-public-notice-replay-20261128-01/`. Full backend suite was not run. M3-3 remains in progress.

### M3-3 Government drought advisory replay increment (2026-11-28)

- Code commit `e2d44b66` routes advisory retries through `replay_duplicate`; corrupt transaction receipts reject with `idempotency_key_reused` and no writes. Focused advisory/assessment/closed-loop tests `13 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `24/12/87/56/990`, all zero differences.
- Evidence: `docs/verification/m3-3-government-drought-advisory-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-government-drought-advisory-replay-20261128-01/`. Full backend suite was not run. M3-3 remains in progress.

### M3-3 Government commercial policy registration replay increment (2026-11-28)

- Code commit `dff05751` routes policy-registration retries through `replay_duplicate`; corrupt transaction receipts reject with `idempotency_key_reused` and no writes. Focused government policy tests `10 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `24/12/87/56/990`, all zero differences.
- Evidence: `docs/verification/m3-3-government-policy-registration-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-government-policy-replay-20261128-01/`. Full backend suite was not run. M3-3 remains in progress.

### M3-3 Organization membership replay integrity increment (2026-11-28)

- Code commit `f1f6b30b` routes Organization admitted membership retries through shared `replay_duplicate`; corrupt receipts retain `ogs_organization_membership_idempotency_reused` and make no writes. Focused tests `25 passed, 3 warnings`; new selection `1/0/0`; frozen five selections 1,169 nodes with zero differences.
- Full backend: `10,836 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. All five failed nodes reproduced on parent `60d206d4` in a targeted comparison. Evidence: `docs/verification/m3-3-organization-membership-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/organization-membership-replay-20261128-01/` through `-04/`.
- M3-3 remains in progress. This increment verifies one Organization custom replay path only.

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

### M3-3 InvestigationConflictAuthority resolve replay increment (2026-11-28)

- Code commit `0bb4b9e7` routes direct `InvestigationConflictAuthority.resolve` retries through shared `replay_duplicate` and preserves `idempotency_key_reused` zero-write rejection. Focused P5, bakery, action-window and scripted-mystery tests: 39 passed; registered selection `1/0/0`; frozen five selections `1,169/0/0`. Full backend: `10,823 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at parent `1127b431` in a targeted run. Evidence: `docs/verification/m3-3-investigation-conflict-replay-20261128.md`; raw logs: `F:/paralls-verification/thread-a/m3-3-investigation-conflict-replay-20261128-01/`. M3-3 remains in progress.

### M3-3 Quest Evidence resolve replay increment (2026-11-28)

- Code commit `9ee8eb23` routes `QuestEvidenceAuthority.resolve` retries through shared `replay_duplicate` and preserves `idempotency_key_reused` zero-write rejection. Focused Quest Evidence/P5 bakery/InvestigationConflict tests: 49 passed; registered selection `1/0/0`; frozen five selections `1,169/0/0`. Full backend: `10,824 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at parent `0bb4b9e7` in a targeted run. Evidence: `docs/verification/m3-3-quest-evidence-replay-20261128.md`; raw logs: `F:/paralls-verification/thread-a/m3-3-quest-evidence-replay-20261128-01/`. M3-3 remains in progress.

### M3-3 world-death confirmation replay increment (2026-11-28)

- Code commit `36d589c4` routes `confirm_world_death` retries through `replay_duplicate`, retaining the exact death-decision payload and causal checks. Focused ActionConsequence/LifeState caller/ActionWindow/P5 tests: 55 passed; registered selection `1/0/0`; frozen five selections `1,169/0/0`. Full backend: `10,825 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at parent `335e85be` in a targeted run. Evidence: `docs/verification/m3-3-world-death-replay-20261128.md`; raw logs: `F:/paralls-verification/thread-a/m3-3-world-death-replay-20261128-01/`. M3-3 remains in progress.

### M3-3 Stormnight legacy action replay increment (2026-11-28)

- Code commit `20934a37` routes the legacy-compatible `StormnightRealtimeSessionService` action retry through `replay_duplicate`. Focused realtime/action-window/world-death/P5 tests: 56 passed; registered selection `1/0/0`; frozen five selections `1,169/0/0`. Full backend: `10,826 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at direct parent `5e178aeb` in a targeted run. Evidence: `docs/verification/m3-3-stormnight-legacy-replay-20261128.md`; raw logs: `F:/paralls-verification/thread-a/m3-3-stormnight-replay-20261128-02/`. M3-3 remains in progress.

### M3-3 shared Owner replay receipt validation increment (2026-11-27)

- Commit `78fa4548`: `replay_duplicate` now validates the durable transaction and all committed event references before returning a duplicate receipt. Credential's local R2 check moved to the shared helper while preserving legacy/current event-type expectations. Focused shared and domain tests: 112 passed; other helper callers: 87 passed. New M3-3 selection `9/0/0`; frozen five selections `1,169` nodes with zero differences. Evidence: `docs/verification/m3-3-shared-owner-replay-validation-20261127.md`, H-A-144. M3-3 remains in progress because replay paths not using this helper still need inventory and validation. Full backend suite not run.

### M3-3 SocialFactAuthority resolve replay increment (2026-11-28)

- Code commit `8b755240` routes direct P5 `resolve` duplicate retries through `replay_duplicate`, preserving the existing `idempotency_key_reused` zero-write contract. Focused tests `22 passed, 2 warnings`; new selection `1/0/0`; frozen five selections `1,169/0/0`.
- Full backend suite `10,817 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five failed nodes reproduced at parent `f34dd3a6` in a targeted five-node comparison. Evidence: `docs/verification/m3-3-social-resolve-replay-20261128.md`; raw logs: `F:/paralls-verification/thread-a/m3-3-social-resolve-20261128-01/`.
- M3-3 remains `进行中`; this closes only the direct `resolve` path. Other direct/custom replay paths remain to inventory and validate.

### M3-3 private follow-on replay increment (2026-11-28)

- Code commit `c48503c1` routes both legacy milling and package-generic workshop private follow-on retries through durable receipt validation. Focused tests `44 passed, 2 warnings`; unit selection `2/0/0`; frozen five selections `1,169/0/0`.
- Full backend suite `10,819 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five failed nodes reproduced at parent `8b755240` in a targeted comparison. Evidence: `docs/verification/m3-3-social-private-follow-on-replay-20261128.md`; raw logs: `F:/paralls-verification/thread-a/m3-3-private-follow-on-20261128-01/`.
- M3-3 remains `进行中`; other direct/custom replay paths still need inventory and validation.

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
| M1-1 Bond 分片提交 | A | 待门禁 | Bond/Credential 原始分片 `b700f8c8`、`ae7d650e`；兼容补丁 `e349187e`；Population expiry `aba7dea9`/`616d9815`；正式 Bond 属性键收敛 `8bdf01dc`。证据 `docs/verification/m1-1-bond-slices-20261122.md`，U11 `m1-1-bond-expiry.json` | Bond/expiry/Credential 定向 37 passed、6 warnings；U11 `12/0/0`；冻结五组 1,169 节点零差异。完整 backend `10,837 passed, 5 failed, 2 skipped, 2 xfailed`，退出 1；五个失败均在代码父 `dbaae2c7` 定向复现。新写入执行正式封闭键集合，历史事件仍可投影；此行为与旧 M1-1 任务卡开放键要求不同。M1-1 仍待门禁 | 3 |
| M1-2 Holdings 原语 | A | 阻塞 | Holdings runtime、v1 事件投影、FactType primitive 接受、checkpoint_at 前缀/后缀回放、按 item sum 聚合；docs/verification/m1-2-holdings-runtime-20261125.md 与 24 节点登记选集 | H-A-056 可追加事件合同已实现。定向测试 24 passed；G5 五组选集 1,169 节点均零差异。生产迁移需将现有 Inventory 命令消费接到 Holdings/Pool FactType，但正式映射要求 `inventory_runtime.py` 保留为 Inventory Owner 领域规则层，且该文件属于 A/B 共同边界。按边界协议暂停该集成。M1-2 选集 24 与 M5-5 选集 18 零差异；26 组登记选集和全量 backend suite 未运行 | 3 |
| M1-3 Pool 原语 | A | 进行中 | Pool runtime `e6cb728c`、`022f1772`；Stormnight schema factory `39ecc2bb`；casualty refold `84d12a87`；Morale D8 窄规则包/装配增量 `f76089a4`；Pool P-3 图投影回归 `2cbe48d5`；[Morale 规则包证据](../verification/m1-3-morale-rulepack-20261128.md)；[原语证据](../verification/m1-3-pool-runtime-20261122.md)、[factory 增量](../verification/m1-3-pool-production-registry-20261123.md)、[casualty 增量](../verification/m1-3-casualty-refold-trigger-20261123.md)、[正式规格静态审计](../verification/m1-3-pool-spec-audit-20261124.md)；当前调用与内容审计见 H-A-074、H-A-204、H-A-205、H-A-206、H-A-207 | Morale package v1.0.2 声明与 Resolver 以及 M6-5 锁定包装配已验证，定向 `200 passed, 6 warnings`；Pool 七种事件的 registry -> graph projector 路径已通过；M1-3 U11 选集 33/0/0，冻结五组选集 24/12/87/56/990 均零差异。新增代码/测试 tip backend 全量为 `10,839 passed, 12 failed, 2 skipped, 2 xfailed`，12 个失败均在代码测试父 `6816a2ee` 定向复现。Pool/Morale/Facility/Impact/Place/物理输入与图投影的 A 侧读者已静态列出，主体读取仍无对应 Pool/Morale `read_as`。U1 完整 L3 Owner 声明、U5 R3、U6 跨仓库完整性、U7 主体 reader、U9 冻结后探针仍未闭环。正式设计把 tick 驱动的 Pool integration 交由 `temporal_process`，Facility 和 Morale 当前包均为 `integration: none`；M1-3 生产调度依赖 M1-5 Process tick 接线与权威非零内容，不直接挂接 `SimulationDriver.current_tick`。M1-3 U1-U11 和生产调度整体仍未闭环 | 3 |
| M1-4 Place 原语 | A | 待决 | 静态合同审计 `docs/verification/m1-4-place-contract-audit-20261127.md`；当前仅有 Presence 通行性路径 | 需要空间注册表、通用 Place Owner/权限、持久事件字段及生产读写合同。不得复用 Presence 作为通用 Place 权威 | 3 |
| M1-5 Process 归并 | A | 待开工 | 同上 | S-5 已定：排在域迁移之后 | 3 |
| M2-1 读取边界清单更新 | A | 进行中 | Ownership / Credential、Holdings / Pool、M6-5 Information / Morale / Presence / impact Pipeline、SocialDelivery 当前调用静态分类见 `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`；H-A-074、H-A-086、H-A-109、H-A-116、H-A-170、H-A-174、H-A-177 | Information 报告与知识经 session-bound `GameplayReadAs` 作窄版主体读取；SocialDelivery projection 只由可信 Information 校验和 checkpoint/tail 重建消费，未发现直接生产查询路由。其他域读者分类随迁移继续更新。M2-2 的通用 selector/visibility 和 U7 仍未完成 | 4 |
| M2-2 `read_as` | A | 阻塞 | 静态合同审计、event-time source audit、schema-ref resolver `c55b009f`、FactType candidate index `b42a1c24`、compiled FactType identity `57d8f4f4`、event-to-instance resolver `9520808e` + strict null rejection `244a1209`；Information readers `97c21f06`、delay/distortion rejection `e941b91b`、`secret`/`debug_only` denial `76a55dd2`、cross-FactType denial order `95a56461` / `docs/verification/m2-2-visibility-denial-order-20261128.md` | `GameplayReadAs` 只读取两个 recipient-private Information FactType；全局先拒绝 unsupported delay/distortion 与 `secret`/`debug_only`，但其余 FactType 仍无 reader。当前相关测试 `32 passed, 6 warnings`；47 组登记选择及冻结五组 1,169 节点零差异。全量 `10,813 passed, 6 failed, 2 skipped, 2 xfailed`，六项在 parent `f709f82e` 完全复现。M2-2 仍阻塞：faction/role 等历史资格解析、FactType-wide 可见性过滤、legacy domain stream attribution 与 U7 未完成 | 4 |
| M2-3 known_time 推广 | A | 待开工 | 同上 | 随 M2-2 | 4 |
| M2-4 投影增量推进 | A | 待门禁 | 现有 `GameplayProjectionReplay` / `GameplayProjectionStartup`；证据 `docs/verification/m2-4-projection-incremental-20261123.md` | replay/startup 定向 15 passed；cursor、stream 连续性、失败关闭与 checkpoint-free rebuild 有测试；未修改共享 replay 源码。缓存性能方案已由共享 Owner 文档改列 M3-2 `StoreReadSnapshot` | 7 |
| M2-5 B4 前置设计 | A | 待门禁 | `docs/verification/g2-visibility-budget/b4-handoff-design-20261122.md` | 当前调用链与事务接口已静态核对。实施须负责人确认。 | 4 |
| M2-6 首条生产流受 epoch 保护 | A | 阻塞 | 实现 + 证据 | 待负责人选流并确定存储核心变更边界，见 H-A-008 | 4 |
| M3-1 `OwnerCommitBuilder` | A | 待门禁 | `docs/verification/m3-1-owner-commit-builder-20261122.md`；四个 A-owned 消费者定向 63 passed；当前 tip 59 个登记选集 + 冻结五组选集共 64 组、1,575 次选中均零差异；raw `F:/paralls-verification/thread-a/m3-1-current-tip-a5e32538/` | backend/packs 与代码 `8bdf01dc` 一致；全量 `10,837 passed, 5 failed, 2 skipped, 2 xfailed`，五项在父提交定向复现，详见 M1-1 证据。仍待合并门禁 | 3 |
| M3-2 `StoreReadSnapshot` 推广 | A | 待门禁 | `7c24d136`，Credential supersede 与 LandRight presentation；`docs/verification/m3-2-store-read-snapshot-20261122.md` | 定向 33 passed，七组选集 1,191 节点零差异。全量退出 1，24 失败与 M1-3 同签名，比 22 节点冻结基线多两项既有本地失败 | 3 |
| M3-3 R2 推广 | A/B | 进行中 | Shared `replay_duplicate` R2 validation and static audit, H-A-144/H-A-146; municipal certificate `7ba82daf`; Morale `2d0ef9c6`; Facility/Presence `32373b52`; Information report `094669f1`; signed input `81e047e0`; Information knowledge `33a1c38a`; SocialDelivery `aeb339a3`; SocialFactAuthority public-milling acknowledgment `93aa1127`, completed-handshake history `f431c896`, direct `resolve` `8b755240`, private follow-on `c48503c1`, scripted mystery phase/outcome replay `8e6d70df`, action-window replay `4409b6fe`, InvestigationConflictAuthority direct `resolve` `0bb4b9e7`, QuestEvidenceAuthority direct `resolve` `9ee8eb23`, world-death confirmation `36d589c4`, Stormnight legacy action `20934a37`; latest runtime evidence `docs/verification/m3-3-stormnight-legacy-replay-20261128.md`; P5 call-path audit `docs/verification/m3-3-p5-replay-path-audit-20261128.md` | Focused Stormnight realtime/action-window/world-death/P5 tests `56 passed, 6 warnings`; new selection `1/0/0`; frozen five `1,169/0/0`. Full backend returned `10,826 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at direct parent `5e178aeb` in a targeted run. P5 adapter candidate calls were traced to helper-validated Owners. M3-3 remains in progress; shared, B/other-domain and remaining repository-wide direct/custom replay paths are outside this audit. | 7 |
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

### M3-3 cross-owner replay finding (2026-11-28)

- H-A-194 records a reproducible corrupt-receipt acceptance in B-owned `contract_runtime.py`, limited to public-milling fulfillment. A did not modify the file. The finding is handed to the owning thread; M3-3 remains in progress. Evidence: `docs/verification/m3-3-contract-fulfillment-replay-audit-20261128.md` and the raw reproduction under `F:/paralls-verification/thread-a/m3-3-contract-r2-static-repro-20261128-01/`.

### M6-5 production Gate numeric inputs (2026-11-28)

- H-A-195 confirms the formal demo does not supply production numbers. Existing test values are not authoritative. The deployment/gameplay authority must provide a versioned target-world Gate profile before production deployment and live siege verification. Evidence: `docs/verification/m6-5-production-gate-profile-source-audit-20261128.md`.

### M5-3 package migration current-tip revalidation (2026-11-28)

- At code tip `4cf42fa3` (documentation HEAD `d24c303e`), package migration/schema/startup/RulePack focused tests returned `213 passed, 6 warnings`; M5-3 selection `23/0/0`; frozen Ownership/shared-replay `24/0/0` and `990/0/0`. Evidence: `docs/verification/m5-3-startup-contract-20261126.md`; raw output: `F:/paralls-verification/thread-a/m5-3-current-tip-recheck-20261128-01/` and selection outputs under `F:/paralls-verification/thread-a/m3-1-four-owner-current-20261128-01/`. Production manifest trust, target-world invocation, Gate values, cross-language hash contract, deployment startup and UE transport remain unverified.

### M1-1 Bond formal delta (2026-11-28)

- H-A-196 records the formal closed-attribute-set discrepancy and the missing production world-clock caller for durable `bond.expired` events. The task-card-approved behavior remains in code; M1-1 stays `待门禁` pending specification reconciliation and an owned scheduler/Process path. Evidence: `docs/verification/m1-1-bond-formal-delta-audit-20261128.md`.

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

### M6-5 A-tip Information delivery recheck (2026-11-28)

- B's `a61c93ad`, `a1719826`, and `e185cfa8` have effective equivalents on A. Event-time and selection changes are patch-equivalent, and the checkpoint-tail test blob is identical. No cherry-pick was needed. At A tip `51d88a4c47e9b92bc8cb24080d540034eecf30b3`, focused Information/checkpoint/wiring tests returned `32 passed, 6 warnings`; `siege_information` returned `selected=26 problems=0 improvements=0`. Python `3.12.2`, A-worktree import path, SQLite `3.43.1`. Raw logs: `F:/paralls-verification/thread-a/information-b-recheck-20261128-01/`. Full backend and frozen five selections were not rerun. M6-5 remains in progress.

### M6-5 B Information delivery rechecked at current A tip (2026-11-28)

- At documentation HEAD `58f5efd8` and backend tip `616d9815`, focused Information checkpoint/runtime/production-wiring tests returned `32 passed, 6 warnings`; the registered `siege_information` selection returned `selected=26 problems=0 improvements=0`. Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` under A were verified. Evidence: `docs/verification/information-replay-a-current-tip-20261128.md`; raw output: `F:/paralls-verification/thread-a/information-current-tip-20261128-02/`. The B test blob and selection match A; no B merge/cherry-pick was needed. Frozen five selections and full backend were not run. M6-5 remains in progress.

### M1-3 current A-tip Pool regression recheck (2026-11-28)

- At A HEAD `72082ffd`, focused Pool/Facility integrity/Morale Pool tests returned `27 passed, 2 warnings`. The M1-3 Pool selection returned `17/0/0`; the domain-owner selection returned `1/0/0`; frozen ownership/modifier/equipment/inventory/shared-replay selections returned `24/12/87/56/990` nodes, all with zero problems and improvements. Python `3.12.2`, A-worktree import path, SQLite `3.43.1`. Evidence and raw output: `docs/verification/m1-3-pool-spec-audit-20261124.md`, `F:/paralls-verification/thread-a/m1-3-current-tip-20261128-01/`. Full backend was not run. M1-3 remains `待门禁`; production scheduling and domain declaration gaps remain open.

### M1-3 Pool regression rechecked after Bond expiry code (2026-11-28)

- At documentation HEAD `6f84de9e` and backend tip `616d9815`, focused Pool/Facility integrity/Morale Pool tests returned `27 passed, 2 warnings`; registered Pool/domain-owner selections returned `17/0/0` and `1/0/0`; frozen five selections returned `24/12/87/56/990`, all zero differences. Python `3.12.2`, SQLite `3.43.1`, A-worktree import path verified. Evidence: `docs/verification/m1-3-pool-spec-audit-20261124.md`; raw output: `F:/paralls-verification/thread-a/m1-3-current-tip-20261128-02/`. An initial frozen-selection path typo was corrected before those five tests ran. Full backend suite not run. M1-3 remains `待门禁`; production scheduling and domain declaration gaps remain open.

### M2-2 Organization qualification source audit (2026-11-28)

- Static review found Organization membership/delegation history can be reconstructed at `global_sequence`, but its event has no effective world tick and does not define faction membership or a complete membership roster. It cannot establish selector qualification at `read_as(as_of_tick)` without an Organization-owned temporal qualification contract. Evidence: `docs/verification/m2-2-selector-qualification-source-audit-20261128.md`; no tests ran. M2-2 remains incomplete.
