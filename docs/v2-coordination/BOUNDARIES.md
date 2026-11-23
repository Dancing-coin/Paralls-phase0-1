# 文件归属与边界

- 生效起点：`integration` @ `3934bba6`（2026-11-20）。配套：[PROTOCOL.md](PROTOCOL.md)。
- 路径均相对代码仓库根目录，已在起点核实存在。

## 一、线程 A 独占（B 只读，不得改，也不得本地临时改）

| 文件 | 说明 |
|---|---|
| `backend/app/gameplay/owner_runtime_base.py` | 共享 Owner 前序，30 行；被 10 个 runtime 导入，含 `debt_runtime`、`contract_runtime`、`ownership_runtime`、`credential_runtime`，也含禁区 `economy_runtime` 与 `econ1_economy_runtime` |
| `backend/app/gameplay/fact_type_registry.py` | G3 的 FactType 注册表 |
| `backend/app/gameplay/rule_pack_validator.py` | 规则包校验器，**加载器 `load_pack` 在此文件内** |
| `backend/app/models/fact_type.py` | main 的 FactType 注册机制，图投影器入口 |
| `backend/app/gameplay/event_schema_registry.py` | **在 A 的 0.5 项完成前**属 A 独占；完成后 B 在自己的域模块里声明事件，不碰此文件 |
| `backend/app/gameplay/l5_play_pattern.py`、`backend/tests/test_l5_play_pattern.py` | M6-4 玩法声明校验 |
| `backend/app/gameplay/l5_reaction.py`、`backend/tests/test_l5_reaction.py` | M6-1 Reaction 声明校验 |

B 的调用不算修改：B 迁移 `debt`、`contract` 时导入并调用 `owner_runtime_base` 是允许的。B 需要这些文件发生变化时，走 `requests/thread-b.md`。

## 二、各线程自有（对方不得改）

| | 线程 A | 线程 B |
|---|---|---|
| 域 runtime | `credential_runtime.py`、`ownership_runtime.py`（以及依赖它们的 `land_right_runtime.py`，见第四节） | `debt_runtime.py`、`contract_runtime.py` |
| 规则包 | `packs/credential_reference/`、将来的 `packs/ownership*/` | `packs/debt*/`、`packs/contract*/`（新建） |
| 域测试 | 对应域的 `backend/tests/` 测试 | 对应域的 `backend/tests/` 测试 |

规则包目录以 `packs/<域>/` 为单位，每个包自包含（`pack.yaml` 逐个声明内容文件），**没有全局包清单**，新增包不需要改任何注册文件。

## 三、共同禁区（两线程都不改）

- `backend/app/gameplay/economy_runtime.py`
- `backend/app/gameplay/inventory_runtime.py`

**未明确归属，改动前先在 `comms/` 向对方说明：** `backend/app/gameplay/econ1_economy_runtime.py`（与 `economy_runtime` 相邻，也导入 `owner_runtime_base`）。

**存储核心**：`backend/app/gameplay/event_store.py`、`backend/app/gameplay/models.py`。此前每轮施工的纪律是不改存储核心；本协议沿用，两线程都不改。若确需改动，先在 `comms/` 商定并记入 `claims/`（此条沿用旧纪律，起草时未单独征求 B 负责人意见）。

## 四、未归属或有交叉的文件

下列在起草时没有明确归属。**不得默认当作自己的。** 需要改动时先在 `comms/` 向对方说明，并在 `daily/` 的申报里标注。

- `backend/app/gameplay/land_right_runtime.py`：读取 credential，写 ownership 事件。它同时跨 A 的两个首域，暂视为 A 的；B 不改。
- `backend/app/gameplay/adventure_basic_reference.py`、`adventure_basic_closure.py`：构造或读取 credential 链路，暂视为 A 的。
- `backend/app/main.py`：两边在吸收时都改过，语义交互只有全量测试作证据。任何一方改它之前，先在 `comms/` 通知对方。
- 事件 schema 声明：在 A 的 0.5 项完成前，B 的新事件类型只能走请求。

## 五、线程 A 的前置交付队列

B 在第 0 项完成前只能做：读现状、写需求、写设计文档，不能提交会依赖共享机制改动的代码。

| 序号 | 交付 | 依据 | 状态 |
|---|---|---|---|
| 0 | **Owner 登记泛化**：`rule_pack_validator.py:175-176` 当前硬编码 `owners != ["Credential"]` 即拒绝，任何非 credential 域的规则包都加载不了。最小改动：从已登记名单读取。不在此步设计 Owner 注册流程，新增 Owner 仍受待决项 D5 的门槛管辖 | 在起点读源码核实 | 未完成 |
| 0.5 | **图可见性发现机制**：`gameplay_schema_event_types()` 目前只扫 `event_schema_registry.py` 单文件的模块级 tuple，域模块里声明的事件对图投影器不可见。改为能发现各域模块，并把 credential 的 v1/v2 事件补进去。完成后 B 可在自己的域模块声明事件 | 在起点实跑核实 credential 事件类型均不在注册表 | 未完成 |

完成后，A 在 `responses/thread-a.md` 追加一条，写明完成日期与合并 SHA，B 凭此开工。0.5 必须先于 B 的第一批新事件类型。

## 六、变更本文件

只有 A、B 负责人一致同意才能改。改动在 PROTOCOL.md 的"变更记录"追加一行。
