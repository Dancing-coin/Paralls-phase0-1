# 文件归属与边界

- 版本 2（2026-11-22）。基线：`integration-2026-11-21` @ `0e67fe812280e7e518c84c27653153f5a69f2330`。配套：[PROTOCOL.md](PROTOCOL.md)。
- 路径均相对代码仓库根目录。版本 1 的路径在 `3934bba6` 核实存在；本版沿用，未逐个重新核对。
- 分工原则：线程 A 改"所有域共用的东西"，线程 B 迁移"各个域"。

## 一、线程 A 独占（B 只读，不得改，也不得本地临时改）

| 文件或目录 | 说明 |
|---|---|
| `backend/app/gameplay/owner_runtime_base.py` | 共享 Owner 前序；B 可导入并调用 |
| `backend/app/gameplay/fact_type_registry.py` | FactType 注册表（含 `REGISTERED_OWNER_IDS`） |
| `backend/app/gameplay/rule_pack_validator.py` | 规则包校验器，**加载器 `load_pack` 在此文件内** |
| `backend/app/models/fact_type.py` | main 的 FactType 注册机制，图投影器入口 |
| `backend/app/gameplay/event_schema_registry.py` | 事件 schema 注册；B 在自己的域模块声明事件，不改此文件 |
| 将来新建的 L1 原语实现、`read_as`、L5 引擎目录 | 路径由 A 在任务卡中确定后补入本表（补入由 A 在同一提交里完成） |

B 的调用不算修改。B 需要这些文件发生变化时，走 `handoff.md`。

## 二、各线程自有（对方不得改）

| | 线程 A | 线程 B |
|---|---|---|
| 域 runtime | `credential_runtime.py`、`ownership_runtime.py`（Bond 工作属 L1），以及依赖它们的 `land_right_runtime.py`、`adventure_basic_reference.py`、`adventure_basic_closure.py` | 其余各域 runtime，按迁移计划的波次推进；当前为 `debt_runtime.py`、`contract_runtime.py` |
| 规则包 | `packs/credential_reference/`、将来的 `packs/ownership*/` | `packs/<其余域>/` |
| 域测试 | 对应域的 `backend/tests/` | 对应域的 `backend/tests/` |

规则包以 `packs/<域>/` 为单位，每个包自包含（`pack.yaml` 逐个声明内容文件），没有全局包清单。

## 三、共同禁区（两线程都不改，直到对应波次获项目负责人放行）

- `backend/app/gameplay/economy_runtime.py`
- `backend/app/gameplay/inventory_runtime.py`
- 迁移计划第 4 波枢纽：`patch_runtime.py`、`resource_body_runtime.py`、`organization_government_runtime.py`。
- 存储核心：`backend/app/gameplay/event_store.py`、`backend/app/gameplay/models.py`。沿用此前每轮施工的纪律；确需改动，先停下报告项目负责人，并记入 `claims/`。

**未明确归属：** `backend/app/gameplay/econ1_economy_runtime.py`（与 `economy_runtime` 相邻，也导入 `owner_runtime_base`）。迁移计划把它排在第 3 波；在此之前，改动先在 `handoff.md` 说明并取得项目负责人确认。

## 四、交叉文件

- `backend/app/main.py`：吸收 `main` 时两边都改过，语义交互只有全量测试作证据。任何线程改它之前，先在 `handoff.md` 说明。
- 事件 schema 声明：B 可在自己的域模块声明事件，并按 P-3 验证图可见性；若事件族与其他域或禁区 runtime 共享，按 P-4 先说明归属。

## 五、线程 A 的前置交付队列

| 序号 | 交付 | 依据 | 状态 |
|---|---|---|---|
| 0 | Owner 登记泛化：校验器从代码控制的已登记名单读取，规则包不能自我登记 Owner；新增 Owner 仍受待决项 D5 管辖 | 合并提交 `3d6c72095fdcd2cbc9e0e4484e70a6010e7cdc87` | 已完成 |
| 0.5 | 图可见性发现机制：图投影器发现域模块声明的事件 schema，credential v1/v2 事件纳入可见集合 | 同上 | 已完成 |

后续 A 的队列以迁移计划 M1（原语）、M2（L0）、M3（共享机制）、M5（规则包）、M6（L5）为准；A 每完成一项，在 `handoff.md` 追加通告，写明合并 SHA。完整 Bond 的 scope、term、attributes 与撤销/到期/supersede 生命周期属 M1-1。

## 六、变更本文件

由项目负责人一人决定。改动在 PROTOCOL.md 的"变更记录"追加一行。
