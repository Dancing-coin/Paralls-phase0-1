# M1-1 Bond 分片提交证据

日期：2026-11-22

## 基线

| 项目 | 值 | 状态 |
|---|---|---|
| 起点 | `0e67fe812280e7e518c84c27653153f5a69f2330` | 已核实 |
| 分支 | `thread-a/ownership-bond-followup-20261121` | 已核实 |
| integration 对照 | `9b09084c5adccc2367f2d5da9f438af9d80393b4`（本地 origin/integration） | 已核实；本地 branch 与 integration 的 backend/packs 无差异，不 rebase/merge |
| Python | 3.12.2 | 已核实 |
| `app.__file__` | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` | 已核实 |
| SQLite | 3.43.1 | 已核实；低于冻结记录 WAL checkpoint 要求 3.51.3 |

## Hunk 映射

| 文件 | hunk / 函数 | 分片 | 能否单独成立 | 理由 |
|---|---|---|---|---|
| `backend/app/gameplay/ownership_event_schema.py` | `OWNERSHIP_EVENT_TYPES` 增加五类 Bond 事件 | A（片 1 + 3） | 是 | Bond 投影事件的发现声明 |
| `backend/app/gameplay/ownership_runtime.py` | `OwnershipBond`、`OwnershipProjection.active_bonds`、`OwnershipProjector.rebuild/_reduce/_validate_bond_links` | A（片 1 + 3） | 是 | Bond 投影、多权利和生命周期 reducer |
| `backend/app/gameplay/ownership_runtime.py` | `OwnershipAuthorityService.grant_bond/revoke_bond/transfer_bond/build_land_right_bond_transfer_fragment/supersede_bond/expire_bond` 与事件构造辅助函数 | A（片 1 + 3） | 是 | 新 Bond 命令和授权片段依赖上述投影 |
| `backend/app/gameplay/ownership_runtime.py` | `_bond_attributes` 及 Decimal import | A（片 1 + 3） | 不能拆 | 同一函数同时承载 Bond 属性基础校验、移除类型白名单和 Decimal 规范化；依任务卡规则不跨提交拆函数 |
| `backend/tests/test_ownership_bond_lifecycle.py` | `test_scoped_bonds_coexist_and_do_not_grant_legacy_title`、`test_bond_lifecycle_rebuilds_all_history_after_snapshot_restore`、source-event 测试 | A（片 1 + 3） | 是 | 验证 Bond 生命周期、多权利、生命周期事件和重建 |
| `backend/tests/test_ownership_bond_lifecycle.py` | 扩展属性键与 Decimal round-trip 测试 | A（片 1 + 3） | 是 | 记录属性行为变化及持久化/重试语义 |
| `backend/tests/test_ownership_runtime.py` | `test_initial_title_and_independent_transfer_are_event_derived` 的投影摘要预期 | A（片 1 + 3） | 是 | Bond 空投影进入确定性投影摘要；节点在冻结 ownership 选择集中基线为 passed |
| `backend/app/gameplay/credential_runtime.py` | `BondCredentialLink`、Credential projector/presentation、签发和 v3 事件 | B（片 2） | 依赖 A | 消费 Bond projection，保留 legacy `right_id` 投影路径 |
| `backend/app/gameplay/credential_v2_event_schema.py` | v3 issued schema、注册和 payload 校验 | B（片 2） | 依赖 A | Credential v3 用 `bond_ref` 持久化 |
| `backend/app/gameplay/credential_reference_chain.py` | `credential_command_condition`、`freeze_inputs` 的 Bond 输入 | B（片 2） | 依赖 A | resolver 读取 ownership Bond 投影 |
| `backend/app/gameplay/land_right_runtime.py` | `LandRightTransferAuthority.transfer` Bond 分支和 ownership fragment 提交 | B（片 2） | 依赖 A | 调用 Bond 转让授权片段并 pin 跨域读向量 |
| `backend/app/gameplay/adventure_basic_closure.py` | `_json_ready` 对 Bond 投影的序列化 | B（片 2） | 依赖 A | closure/checkpoint 消费 Bond projection |
| `packs/credential_reference/models/credential_command.yaml` | 增加 `ownership.bonds@1` reads | B（片 2） | 依赖 A | 声明 Credential resolver 的 Bond 读依赖 |
| `backend/tests/test_credential_runtime.py`、`test_credential_v2_event_schema.py` | v3 签发、presentation、旧事件兼容及 schema 用例 | B（片 2） | 依赖 A | 覆盖 Credential v3 写入和双读 |
| `backend/tests/test_credential_reference_chain.py`、`test_credential_reference_rebuild.py` | Bond 引用条件、重放和 checkpoint 重建 | B（片 2） | 依赖 A | 覆盖 reference-chain 消费路径 |
| `backend/tests/test_credential_v2_land_right_revision_vector.py` | Bond 转让、跨域 revision pin、拒绝零写入 | B（片 2） | 依赖 A | 覆盖 land-right 消费和事务读向量 |
| `backend/tests/test_adventure_basic_closure_evidence.py` | closure/checkpoint Bond 序列化与证据 | B（片 2） | 依赖 A | 覆盖 closure 消费路径 |

分片裁定：原片 1 与原片 3 合并为提交 A，原片 2 为提交 B，顺序 A → B。若将 `_bond_attributes` 拆到第三个提交，会违反“不拆同一函数”的约束。该合并让属性白名单与 Decimal 行为改变和 Bond 原语同提交，提交说明明确标注行为改变。

## 兼容策略

- 旧 Ownership right 事件和旧 Credential v1/v2 `right_id` 事件保留原样读取；Credential projector 按事件 schema version/payload 选择 legacy right link 或 Bond link。
- Credential v1 `gameplay.credential.issued`（schema v1）和 v2 `gameplay.credential.link_issued`（schema v2）仍要求 `right_id`；新增的 `gameplay.credential.link_issued` schema v3 要求 `bond_ref`。既有事件不重写、不升级 schema。v3 后续撤销/替代沿用既有 v2 `link_revoked` / `link_superseded` payload schema。
- 属性行为由窄白名单放宽为任意字符串键、最多 8 项；值仍限字符串、整数、布尔和有限 Decimal。Decimal 以固定格式十进制字符串写入事件，既有字符串属性无需迁移。
- 属性校验与规范化发生在幂等 digest 构造前；重复提交以相同规范值重放。禁止非有限 Decimal，避免无效或非确定性 JSON。
- `event_store.py`、`models.py`、`economy_runtime.py`、`inventory_runtime.py` 与 `fixed_offer_purchase.py` 不在改动范围。

## Credential v3 读写方枚举

| 角色 | 文件与入口 | 读写内容 | 证据等级 |
|---|---|---|---|
| 写入方 | `backend/app/gameplay/credential_runtime.py`：`CredentialAuthorityService.issue_credential` | 写 `link_issued` schema v2 + `right_id`，或 schema v3 + `bond_ref`；按 Bond 输入 pin Ownership revision | 静态源码 + 专项测试 |
| 写入方 | `backend/app/gameplay/credential_runtime.py`：`CredentialAuthorityService.supersede_credential` | 从旧 Credential 投影继承 `right_id` / `bond_ref`，并写对应 v2 / v3 issued schema | 静态源码 + 专项测试 |
| Schema 校验 | `backend/app/gameplay/credential_v2_event_schema.py`：`validate_credential_v2_event` | 同时验证 v2 right payload 和 v3 Bond payload；v3 不接受 `right_id` | 静态源码 + Schema 测试 |
| 核心读取方 | `backend/app/gameplay/credential_runtime.py`：`CredentialProjector.rebuild` | 读取 legacy v1、v2 和 v3 issued 事件，重建 `CredentialLink` 或 `BondCredentialLink`；撤销/替代对两种 link 使用同一状态迁移 | 静态源码 + 专项测试 |
| 面向主体读取方 | `backend/app/gameplay/credential_runtime.py`：`CredentialPresentationValidator.verify_right_holder_presentation` | 通过投影读取 Credential，分别校验 ownership right 或 Bond subject/term，并返回兼容的 presentation 决策 | 静态源码 + 专项测试 |
| Resolver 读取方 | `backend/app/gameplay/credential_reference_chain.py`：`CredentialReferenceChain.freeze_inputs` 与 `credential_command_condition` | 为发证命令读取 ownership rights/bonds、状态和 term；拒绝过期、主体不匹配或缺失 Bond | 静态源码 + reference-chain 测试 |
| 跨域读取方 | `backend/app/gameplay/land_right_runtime.py`：`LandRightTransferAuthority.transfer` | 读取 Credential 投影与 presentation，匹配 Bond 后调用 Ownership 转让片段 | 静态源码 + revision-vector 测试 |
| Closure/checkpoint 读取方 | `backend/app/gameplay/adventure_basic_closure.py`：`_build_domain_facade`、`_json_ready` | 将 Credential 与 Ownership 投影纳入 closure/checkpoint-tail 证据序列化 | 静态源码 + closure 测试 |
| 声明读取方 | `packs/credential_reference/models/credential_command.yaml` | Resolver 声明 `ownership.bonds@1` 输入 | 静态包声明 + Resolver 测试 |

专项测试还覆盖旧事件双读（`test_credential_dual_read.py`）、v3 schema 拒绝错误载荷、Bond 签发与 presentation、revocation、supersede、reference replay/checkpoint rebuild、land-right revision pin 与拒绝零写入。

关键生产行号（Credential v3 提交 `ae7d650eb93baa35748bbf9a97c3c021d89a0fd4`）：

| 文件 | 符号 / 行 | 读写 |
|---|---|---|
| `backend/app/gameplay/credential_runtime.py` | `CredentialProjector.rebuild` 97；按载荷选择 link 121–144；`verify_right_holder_presentation` 192–227 | 读 legacy right 和 v3 bond |
| 同上 | `issue_credential` 296；v3 event 生成 353–399；`supersede_credential` 437–510 | 写 v2/v3 issued 和继承引用 |
| `backend/app/gameplay/credential_v2_event_schema.py` | `_ISSUED_V3_FIELDS` 37；v3 schema 68–73；注册 102–106；验证 109–132 | 登记并校验 v3 payload |
| `backend/app/gameplay/credential_reference_chain.py` | 条件 26–55；输入冻结 97–131 | 消费 ownership bond snapshot |
| `backend/app/gameplay/land_right_runtime.py` | transfer 73；Credential project 56；bond 匹配 145–165；transfer fragment 203–217 | 读取 Credential 并提交 Bond 转让片段 |
| `backend/app/gameplay/adventure_basic_closure.py` | Credential projection 253；`_json_ready` 318–330 | closure/checkpoint 证据读取 |
| `packs/credential_reference/models/credential_command.yaml` | reads 6 | 声明 `ownership.bonds@1` |

RG 全仓调用与 schema 搜索还覆盖测试和脚本。未发现除上述 production reader 外按 Credential event type/payload 消费的 production 读者；`fixed_offer_purchase.py` 仍只读旧 Ownership right，不在片 2 改动范围。

## 逐片验证

| 提交 | 文件与行数 | 定向测试 | ownership 选集 | shared-replay 选集 | 回退 |
|---|---|---|---|---|---|
| A：Bond 原语 + 属性行为 | `b700f8c8788d04ccffbc9dcd8ebb909aca768584` | `test_ownership_runtime.py test_ownership_bond_lifecycle.py`：12 passed, 2 warnings | selected=24 problems=0 improvements=0 | selected=990 problems=0 improvements=0 | 代码提交可独立 revert；在 A detached worktree 实测，临时 worktree 已移除 |
| B：Credential v3 `bond_ref` 迁移 | `ae7d650eb93baa35748bbf9a97c3c021d89a0fd4` | 7 个 Credential/closure 测试文件：44 passed, 2 warnings | selected=24 problems=0 improvements=0 | selected=990 problems=0 improvements=0 | 代码提交可独立 revert；临时 worktree `F:\codex-temp\a-slice2-verify-44360973f69f4371b444219a6233f4e2` 已移除 |

上表只记录各代码提交在 detached worktree 的逐片结果。输出均在 `F:\paralls-verification\thread-a\` 的唯一运行目录，选集使用冻结基线 `docs/verification/absorb-main-3bf3418e/`，ownership 24 节点、shared-replay 990 节点。

## 合并状态全量（独立于逐片验证）

此结果是包含代码提交 `b700f8c8788d04ccffbc9dcd8ebb909aca768584` 与 `ae7d650eb93baa35748bbf9a97c3c021d89a0fd4` 的工作区合并状态全量运行，不是任何一个单独切片的验证结果；它与上文 detached worktree 中逐片定向测试和冻结选集证据分开记录。在当时工作区用 `docs/verification/g0-939c6746/run_baseline.py --repo <worktree> --output <new-dir> --freeze` 串行运行。环境 Python 3.12.2，`app.__file__` 在当前 worktree，SQLite 3.43.1。实际收集 10,417 项：**24 failed, 10,389 passed, 2 skipped, 2 xfailed，退出码 1**。原始日志、results、environment、JUnit 在 `F:\paralls-verification\thread-a\m1-1-full-ae7d650e-de7850922c1140ae9b19a7483ab7281b\full\`。

冻结记录原有 22 个失败；另外 `test_population_cold_ready_gate.py::test_cold_ready` 与 `test_population_recovery_measurement.py::test_recovery_owner_probe_measures_original_startup_before_full_oracle` 在未含 M1-1 改动的 `0e67fe81` worktree 单独复跑仍失败，前者为 `KeyError: resource_bounds`，后者在隔离复跑时因 pytest 临时路径 / 继承 Git 配置而失败。清除空 `GIT_CONFIG_VALUE_0` 并将 `TMP/TMPDIR/--basetemp` 指向 F 盘后，这两项单测为 2 passed。全量退出码仍为 1；全量命令意外沿用环境 `TMPDIR` 在 D 盘创建约 935 MB 的 pytest 临时数据，真实目录已移至 F 盘，残留仅为指向本轮目录的 `*current` 符号链接。**因此全量不记作通过，也不替代逐片结果。**

## 未覆盖与结论

- 全量实际收集 10,417 项，运行结果见上节；未通过。
- SQLite 3.43.1 低于 3.51.3，冻结基线中的两个并发 WAL checkpoint 节点属于环境未验证项，不计通过。
- Bond 事件 schema 的 payload 细节由 Ownership projector/runtime 校验；本次不修改共享 event store/schema registry。
- 分片映射为静态审查；两项代码提交分别做了 detached 定向/冻结选集验证，未逐个执行 `git revert` 实验；回退判定基于提交路径独立且无跨片共享路径。

## M1-1 U1–U10 状态

以下状态按 M1-1 Bond 原语单元记录；它不代表 Ownership 或 Architecture v2 已完成迁移。

| DoD | 状态 | 依据或缺口 |
|---|---|---|
| U1 Owner 声明及分类 | 仅静态 | Ownership 已有 Owner/runtime；native/stewarded 分类尚无本单元新裁定证据 |
| U2 FactType 与偏离登记 | 仅静态 | Bond projection 与 `ownership.bonds@1` 已声明；未完成正式偏离清单 |
| U3 事件注册与 P-3 | 已验证 | Credential v3 event type 在 `gameplay_schema_event_types()` 内；五类 Bond 事件均注册且经事件总线投影 |
| U4 共享机制采用 | 仅静态 | 使用现有 Owner/append/replay 机制；未完成逐项机制采用对照 |
| U5 R1/R2/R3 | 未做 | 本 M1-1 分片没有运行完整 R1/R2/R3 验收 |
| U6 读取方清单及专项测试 | 已验证 | 本节列出 v1/v2/v3 读写方；Credential detached 定向测试 44 passed |
| U7 主体读取分类 | 未做 | `read_as` 与 visibility 分类属于后续 M2 工作 |
| U8 规则包设定及 Resolver | 仅静态 | Credential resolver 声明 Bond 输入；尚无 Ownership Bond 自有完整规则包 |
| U9 探针及冻结基线对照 | 已验证但全量未通过 | 当前代码提交 `8bdf01dc` 的登记选择 `12/0/0`，冻结五组 `1,169` 节点零差异；完整 backend 全量有 5 项失败，均在代码父提交 `dbaae2c7` 定向复现 |
| U10 证据文件完整 | 已记录 | 原始 Bond/Credential 代码 SHA、Population expiry、属性行为收敛提交与测试、文件路径、环境、父提交失败对照和未覆盖项均有记录；不含全量通过声明 |
| U11 单元选集登记 | 已验证 | `docs/verification/selection/m1-1-bond-expiry.json` 包含 12 个 Bond 属性和 scheduler 回归节点；当前比较 `selected=12 problems=0 improvements=0`。这不关闭 Bond 单元其他 U 项 |

## 旧版转让入口混合账本兼容补测

`e349187e56be87b1df729cf807162657a886cff6` 将旧版 `right_id` 转让入口的凭证匹配限定为 `CredentialLink`，与 Bond 入口要求 `BondCredentialLink` 对称。使用真实 Store 发行 v3 Bond 凭证后将其提交给旧版入口。修复前在 `land_right_runtime.py:136` 抛出 `AttributeError`，修复后返回已有拒绝码 `land_right_credential_required`，事件序列、事务和幂等记录均无新增。没有更改持久事件字段或成功批次。

- Python 3.12.2、SQLite 3.43.1，`PYTHONPATH` 与 `app.__file__` 已核对在临时检出 `F:/codex-temp/a-ip-f759a465/backend`。
- `python -m pytest -q -p no:cacheprovider backend/tests/test_credential_v2_land_right_revision_vector.py -k legacy_land_right_transfer_rejects`。修复前 1 failed、6 deselected，见 `F:/paralls-verification/thread-a/et-e4c044021a/red.txt`。
- `python -m pytest -q -p no:cacheprovider` 运行 LandRight revision vector、Credential reference chain/runtime、Ownership Bond lifecycle 和 Adventure closure 五个文件，38 passed、2 warnings，退出 0。原始输出 `F:/paralls-verification/thread-a/et-218d73ce84/targeted.txt`。
- `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>`。五组冻结选集 1,169 个节点，十一组登记选集 89 个节点，合计 1,258 个节点，各组 `problems=0 improvements=0`。原始输出 `F:/paralls-verification/thread-a/et-9be8cff326/`。本补丁未跑全量。

## Bond 到期调度接线（2026-11-28）

此增量在 Population 已确认的 cadence boundary 上调用现有 `OwnershipAuthorityService.expire_bond`，不直接写事件。新增的 `ownership` grant 只授权 `actor_gameplay.ownership_domain`；读取 durable cadence pins 后验证 issuer、timeline、boundary、scope 和 digest。到期筛选使用 Bond 的 `term_expires_at`，实际提交的 `world_tick` 使用确认处理 tick，迟到处理不回写未经观察的历史时间。到期命令身份由 `bond_ref` 和 `term_expires_at` 稳定派生，重复 boundary 不增加第二个事件。

代码提交：`aba7dea902a7eb757aaff23b2b4f01334bac1673`。测试可靠性修正：`616d9815053e9309e996cd81998c1c47fc2906e2`。父提交 `6276757fe1629deb772d4444166836c54a9cef88` 上运行同一测试文件，预期缺失 consumer 的 6 项全部失败；当前 consumer 文件 `6 passed`，Bond/Population/temporal 定向组合 `106 passed, 6 warnings`。Bond expiry 独立 U11 选集登记在 `docs/verification/selection/m1-1-bond-expiry.json`，结果 `selected=10 problems=0 improvements=0`。

| 验证 | 结果 | 原始输出 |
|---|---|---|
| 父提交 RED | `6 failed`，均因父提交没有 Ownership expiry consumer | `F:/paralls-verification/thread-a/ownership-bond-expiry-red-20261128-13/red.log` |
| 当前 consumer GREEN | `6 passed, 6 warnings` | `F:/paralls-verification/thread-a/ownership-bond-expiry-green-20261128-14/consumer.log` |
| Ownership / Population / temporal 定向组合 | `106 passed, 6 warnings` | `F:/paralls-verification/thread-a/ownership-bond-expiry-green-20261128-14/focused.log` |
| Bond expiry 登记选集 | `selected=10 problems=0 improvements=0` | `F:/paralls-verification/thread-a/ownership-bond-expiry-unit-selection-20261128-16/selection.log` |
| 冻结 ownership / modifier / equipment / inventory / shared-replay | `24/12/87/56/990` 节点，全部 `problems=0 improvements=0` | `F:/paralls-verification/thread-a/ownership-bond-expiry-current-selections-20261128-12/` |
| 当前 A 的 Information 三文件重测 | `32 passed, 6 warnings`；`siege_information selected=26 problems=0 improvements=0` | `F:/paralls-verification/thread-a/bond-expiry-information-recheck-20261128-15/` |
| 合并状态全量 backend | `10,835 passed, 6 failed, 2 skipped, 2 xfailed, 227 warnings`，退出码 1 | `F:/paralls-verification/thread-a/ownership-bond-expiry-full-20261128-02/full.log` |
| 全量失败节点父提交对照 | 6 个节点中 5 个在父提交以相同类别失败，character recovery 单节点通过 | `F:/paralls-verification/thread-a/ownership-bond-expiry-parent-failures-20261128-03/parent.log` |

全量六个失败节点为 calibration repair contract、Task45 Godot probe、`test_cold_ready`、character recovery probe、recovery measurement 和 Task8 Godot probe。character recovery 节点在父提交隔离复跑和当前提交隔离复跑均通过，当前全量中的 PermissionError 未归因；其余五项在父提交定向对照中同样失败。该比较不是父提交全量运行，也不构成全量通过结论。

环境为 Python 3.12.2，`app.__file__` 为 A worktree 下的 `backend/app/__init__.py`，SQLite 3.43.1。`PYTHONPATH` 指向 A worktree；pytest 临时目录和验证输出位于 F 盘。解释器仍使用既有 D 盘虚拟环境路径，本次没有在 D 盘创建验证产物。比较器第一次调用因预先创建了它要求保持不存在的输出目录而在执行节点前退出，随后使用独立 run id 完成上述选集比较。

此增量只验证 A 本机 Population cadence 到 Ownership expiry 的应用接线，不是 Unreal 实时世界时钟验证。M1-1 仍未完成门禁：Bond 属性白名单的任务卡行为与正式规格封闭属性集合存在差异，U1/U2/U4/U5/U7/U8 仍有未覆盖项，详见 H-A-196。

## Bond 属性类型约束收敛（2026-11-28）

正式规格 `docs/architecture-v2/02-原语/02-六原语规格.md` §4 为五类 Bond 定义封闭属性键。代码提交 `8bdf01dc4539b3f67898a9c4276fa941be90bdda` 使新 grant/supersede 写入按此集合拒绝未知键，行为改变仅限新写入。Ownership projector 继续读取历史事件中的扩展键，避免旧存档重建失败；可变的 obligation `outstanding_amount` 必须由独立 FactType 表达。该实现收敛到正式规格，与 M1-1 任务卡“移除属性白名单”的旧指令不一致，本次在全权持续授权下选择正式 Architecture v2 合同作为最终目标。

TDD RED 在旧实现上重现：obligation Bond 接受 `outstanding_amount` 且未拒绝。GREEN 定向 Ownership/Bond/expiry/Credential 测试 `37 passed, 6 warnings`，U11 更新后 `12/0/0`。Python `3.12.2`，`app.__file__` 在 A worktree，SQLite `3.43.1`。新增测试覆盖非法写入零写入拒绝、旧事件扩展属性 projector 回放、正式 `obligation.amount` Decimal 规范化与精确重试。

冻结 ownership/modifier/equipment/inventory/shared-replay 选择分别为 `24/12/87/56/990` 个节点，均 `problems=0 improvements=0`。完整 backend suite 为 `10,837 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`，退出码 1。五个失败节点在代码父提交 `dbaae2c7` 的隔离 worktree 全部复现；该对照是定向复现，不是父提交全量运行。

原始 RED、focused、选集、full suite 与父提交对照输出分别位于 `F:\paralls-verification\thread-a\bond-closed-attributes-20261128-01\`、`-02\`、`-03\`、`-04\`、`-05\`。本行为变更不修改持久事件 schema，旧事件 payload 继续可读。M1-1 仍待门禁，Bond 生命周期之外的 U1/U2/U4/U5/U7/U8 缺口及全量五项失败仍需单独处理。
