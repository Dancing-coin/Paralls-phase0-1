# M5-1 受击剖面、聚合模型与技能消耗绑定

| 内容 | 工作分支代码提交 | 临时检出代码提交 | 定向输出 |
|---|---|---|---|
| `impact_profiles` | `f9c64f99` | `e710023a` | 7 个红测，接入后 88 passed |
| `aggregation_models` | `cf373ea8` | `8fbc0a41` | 6 个红测，接入后 94 passed |
| `bindings` 的技能消耗模型 | `2bfc6bd2` | `01128d20` | 5 个红测，接入后 99 passed |

三片各修改 `backend/app/gameplay/rule_pack_validator.py` 和 `backend/tests/test_rule_pack_validator.py`，可按代码提交逐片回退。各切片只在加载边界构建不可变声明并参与现有内容哈希。受击剖面校验目标槽位、登记的 FactType、Resolver 写集、结算顺序及宿主原子性。层必须按 FactType 结算顺序递增。多层有 `either` 宿主时，静态加载无法证明会落在同一提交端，要求 `obligation`。聚合沿用《聚合与精度》的四种模式，`distribution` 引用已登记 refold Resolver。技能消耗绑定按分水岭实验 A 的 `applies_to` 与 `cost_model` 声明加载，校验目标格式及 Resolver 引用。运行时槽位挂载、受击结算、refold 执行与技能目录解析未接入。

## 已验证

Python 3.12.2、SQLite 3.43.1。在 F 盘临时检出运行时，`PYTHONPATH` 指向该检出的 `backend`，`app.__file__` 已核验为 `F:/codex-temp/a-ip-f759a465/backend/app/__init__.py`。迁入 A 分支后使用 `git diff --exit-code 01128d20 2bfc6bd2 -- backend packs` 核对两个目录与已测内容一致。

定向命令为 `python -m pytest -q -p no:cacheprovider`，接入前按 `test_rule_pack_validator.py` 的 impact、aggregation、binding 子集运行。接入后同时覆盖 validator、Pool runtime、Credential pack schema boundary、reference chain 与 FactType registry。原始输出在 `F:/paralls-verification/thread-a/` 下的以下运行目录。

| 内容 | 红测 | 接入后 |
|---|---|---|
| `impact_profiles` | `et-1866a073c1`，`7 failed, 51 deselected` | `et-48727f9417`，`88 passed, 2 warnings` |
| `aggregation_models` | `et-665ff06a17`，`6 failed, 58 deselected` | `et-4a49722a05`，`94 passed, 2 warnings` |
| 技能消耗绑定 | `et-80b37efdc9`，`5 failed, 64 deselected` | `et-f97253040e`，`99 passed, 2 warnings` |

在临时检出 `01128d20` 用 `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>` 逐组运行，五组冻结选集 1,169 节点，加七组已登记单元选集 54 节点，总计 1,223。每组均 `problems=0 improvements=0`，退出 0。各组结果在 `F:/paralls-verification/thread-a/et-6f9a13a359`。

## 后端全量

前一切片 `1f6aff2e` 的后端全量见 [实体类型证据](m5-1-entity-types-20261122.md)。本文件三片的合并状态全量待运行。

## 单元 DoD

U4 加载器复用与 U8 声明加载均有定向证据。U6 仅静态定位到加载入口。U10 为本文件，U11 按三个切片登记选集。U1、U2、U3、U5、U7 的域级工作及 U9 声明探针未做。
