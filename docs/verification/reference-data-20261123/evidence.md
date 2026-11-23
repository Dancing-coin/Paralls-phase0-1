# ReferenceData 单元证据

- 基线：`810a46c1249918c09b42fa1fe0c12d7d784579d2`，标签 `integration-2026-11-23`。
- 分支：`thread-b/reference-data-20261123`。
- 扫描命令：`rg -n "ReferenceDataset|reference_data|dataset_ref|license_status|allowed_scopes|FrozenReferenceDatasetInput" backend/app backend/tests/test_infra_reference_data_license_admission.py backend/tests/test_infra_population_branch_preview.py backend/tests/test_world_prediction.py`；`rg -n "gameplay_schema_event_types|FACT_TYPE_REGISTRY|AuthorityGraphProjector" backend/app backend/tests`；`git diff --check`。
- 验证时间：2026-11-23 Asia/Shanghai。
- 结论：ReferenceData 局部机制、声明候选及回归证据已形成；多个 U 项仍未完成。本文不是 v2 完成或验收声明。

## U1–U11

| 项 | 状态 | 证据与剩余工作 |
|---|---|---|
| U1 Owner 声明与分类 | 部分 | `Information` 在 `backend/app/gameplay/fact_type_registry.py:11-34` 登记，规范文档 `04-Owner/01-Owner定义.md:17,29-32` 将其归 native。当前无完整 Owner L3 声明、writes/denies、不变式与 Resolver 清单。 |
| U2 FactType 声明 | 部分 | `packs/reference_data/fact_types/dataset_status.yaml:1-15` 是 dataset lifecycle 的 machine 候选，加载测试验证 `owner_ref`、primitive、machine ref 与生成顺序。许可、来源、digest、scope 等字段仍在 runtime 事件模型内，未完成事实拆分。 |
| U3 事件 schema 与 P-3 | 已验证，范围有限 | `backend/app/gameplay/reference_data_event_schema.py:3-7` 声明三个既有事件名。新增测试分别断言注册表成员、domain=`reference_data`，并将同名 `AuthorityEvent` 经 event bus 送入 `HeavenlyAuthorityEventProjector` 后查询到图节点，见 `backend/tests/test_infra_reference_data_license_admission.py:255-286`。这证明 schema discovery 和 projector 处理，不证明 GameplayEventStore outbox 已接 AuthorityEvent bus。 |
| U4 共享 Owner 机制 | 部分 | Runtime 使用 `SettlementPlan`、Owner fragment 与 atomic batch，见 `backend/app/gameplay/reference_data_runtime.py:120-137`。没有 `OwnerRuntimeBase` 的通用 replay/reject 接入，也未统一 digest 机制，保持现状不改运行语义。 |
| U5 R1/R2/R3 | 部分 | R1 有精确重试/变更重试测试：`test_infra_reference_data_license_admission.py:214-229`。R2 有 stream revision、outbox/event 对应与事务追加断言：同文件 `160-184`。R3 有 full 与 checkpoint-tail projection hash 对照：`151-158`。未覆盖删除 checkpoint 后独立恢复/`state_digest` 复核及完整 durable reopen 路径。 |
| U6 读取方与专项测试 | 已验证读取清单及所列专项测试 | 设计文档 `design.md` 的读取方表列出唯一生产导入者 `backend/app/population_continuity/branch_preview.py:10-12,64-90`，并列出独立的 World Prediction 输入路径。定向运行覆盖 ReferenceData admission、branch preview、world prediction 与 pack。动态反射/外部消费者未核实。 |
| U7 可见性与读取边界 | 未做，偏离已登记 | 包候选写 `private`，runtime 查询只接受 authority scope，outbox audience 为 `authority_only`，但面向主体读取未分类，production `read_as` 不存在于本单元边界。见 `packs/reference_data/fact_types/dataset_status.yaml:5-9`、`reference_data_runtime.py:87-97,134`。 |
| U8 规则包与 Resolver | 部分 | 新包可加载 machine 状态候选，`backend/tests/test_reference_data_pack.py:9-17` 验证加载。runtime 未路由到包中 Resolver，当前 loader 的能力差异记录在 `design.md`。 |
| U9 探针与基线比较 | 部分 | 临时副本只增加一个 machine FactType 与包数据，`load_pack` 接受两项事实；没有改 backend 源码。五组冻结选集与既有 LifeState、ReferenceData 单元选集比较均 `problems=0`。探针只验证当前 loader 增量声明能力，不能证明 v2 完整零代码迁移。 |
| U10 文件清单及验证等级 | 完成记录 | 本文“变更文件”逐项列出路径与验证状态。 |
| U11 单元选集 | 已登记并比较 | `docs/verification/selection/reference_data.json` 有 15 个唯一节点；比较结果 `selected=15 problems=0 improvements=0`。 |

## 运行环境与原始输出

环境命令输出：

```text
3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]
F:\codex-temp\paralls-v2-thread-b-reference-data-20261123\backend\app\__init__.py
```

定向测试命令：

```powershell
$env:PYTHONPATH = '<current worktree>\backend'
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -m pytest `
  backend/tests/test_infra_reference_data_license_admission.py `
  backend/tests/test_infra_population_branch_preview.py `
  backend/tests/test_world_prediction.py `
  backend/tests/test_reference_data_pack.py
```

原始摘要：

```text
58 passed, 2 warnings in 2.27s
exit_code=0
```

五组选集与已有登记单元选集，均使用 `docs/verification/absorb-main-3bf3418e/compare_selection.py`：

```text
ownership: selected=24 problems=0 improvements=0
modifier: selected=12 problems=0 improvements=0
equipment: selected=87 problems=0 improvements=0
inventory: selected=56 problems=0 improvements=0
shared-replay: selected=990 problems=0 improvements=0
life_state: selected=12 problems=0 improvements=0
reference_data: selected=15 problems=0 improvements=0
```

密钥扫描原始输出：

```text
tracked_model_secret_offender_count=0
harness_cleanup=passed run_id=275334d176cc4c9f9847bdc33c59fccd
```

没有命中项，因此没有匹配子串或“是否已公开”条目。SQLite 版本与 Godot runtime 未核实。未运行全量 pytest。

P-3 RED 阶段先运行三个真实 event type 的参数化断言，当时结果 `3 failed, 2 warnings`，失败均为注册表缺少 schema 声明。加入域模块声明后相同三例 `3 passed, 2 warnings`。输出目录位于 `F:\paralls-verification\thread-b\reference-data-20261123-red\` 与 `...\reference-data-20261123-schema-p3\`。

零 backend 代码探针在 `F:\paralls-verification\thread-b\reference-data-20261123-probe-run01\pack-probe\` 的临时包副本运行。首次临时夹具漏列 `machine_defs/license_status`，loader 正确报 `pack_content_undeclared`；补齐临时 manifest 后输出：

```text
facts=fact:information:*:dataset_status,fact:information:*:license_status
count=2
```

探针仅新增临时包数据，无生产代码变化。

全部测试日志与选集批次输出在 `F:\paralls-verification\thread-b\reference-data-20261123-targeted-run01\` 和 `F:\paralls-verification\thread-b\reference-data-20261123-g5-run01\`。所有 pytest 临时目录、日志和 probe 副本均在 F 盘。

## P-2 基线失败节点检查

对照 `docs/verification/absorb-main-3bf3418e/README.md` 的 22 个冻结失败节点，ReferenceData runtime、branch preview、world prediction、pack 与 P-3 测试没有修改这些节点的断言合同。当前单元未触及冻结失败节点，不新增 `claims/thread-b.md` 条目。

## 变更文件

| 文件 | 状态 |
|---|---|
| `backend/app/gameplay/reference_data_event_schema.py` | 新增域内事件声明；定向 P-3 通过 |
| `backend/tests/test_infra_reference_data_license_admission.py` | 增加三个事件逐项注册和图投影测试；58 项定向测试通过 |
| `backend/tests/test_reference_data_pack.py` | 新增规则包加载测试；通过 |
| `packs/reference_data/pack.yaml` | 新增包 manifest；加载测试通过 |
| `packs/reference_data/fact_types/dataset_status.yaml` | machine 候选事实；静态内容由 loader 测试验证 |
| `packs/reference_data/machine_defs/dataset_status.yaml` | 生命周期状态与转移候选；loader 测试通过 |
| `docs/verification/reference-data-20261123/design.md` | 事实清单、候选拆分、读取方、偏离、探针及三张 Mermaid 图；静态检查 |
| `docs/verification/reference-data-20261123/evidence.md` | 本证据；静态检查 |
| `docs/verification/selection/reference_data.json` | 15 节点单元选集，比较无新增失败 |
| `docs/v2-coordination/board.md` | 单元状态与产物链接；待门禁 |
| `docs/v2-coordination/daily/2026-11-23.md` | 单元进度记录；未申报 integration 合并 |

最终状态检查：`git diff --check` 无输出。未改 A 独占注册表/validator、存储核心、`main.py`、事件名、schema version、已有持久事件字段或语义。
