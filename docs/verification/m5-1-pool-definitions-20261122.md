# M5-1 Pool 定义加载与校验

代码提交 `40afef40c11143b50ae9cf9f2ecfc50f79ca1d40`。本切片可通过 `git revert 40afef40` 单独回退。

`load_pack` 支持清单中的 `pool_defs`。合法声明的原始数据冻结后由 `LoadedPack.pool_defs` 返回，并按现有内容哈希算法计入哈希。校验复用 `PoolDefinition` 与 `PoolThreshold` 的范围和滞回不变量。 `decimals` 按规则包文件格式第五节要求必填，参与计算的数值共用该精度，允许整数和带引号的普通十进制字符串。 `none` 与 `rate` 的字段分别校验。规则包仍通过已有 YAML 限制与 FactType 校验，失败时不会返回部分内容。

这个切片把 Pool 声明带到加载边界。Pool 到 FactType 的绑定、运行时采用和其余 M5 内容类型尚未接入。现有 Credential 包没有 `pool_defs`，走空映射路径。

## 定向

Python 3.12.2，SQLite 3.43.1，`PYTHONPATH` 为 `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`。`app.__file__` 已核验为同 worktree 下 `backend\app\__init__.py`。

`python -m pytest -q -p no:cacheprovider` 运行 `test_rule_pack_validator.py`、`test_pool_runtime.py`、`test_credential_pack_schema_boundary.py`、`test_credential_reference_chain.py`、`test_credential_fact_type_registry.py`。原始结果 `76 passed, 2 warnings in 2.72s`。新增 9 条用例在未接入加载器前全部失败。定向原始输出分别位于 `F:\paralls-verification\thread-a\m5-1-pool-red-20261122-001` 和 `F:\paralls-verification\thread-a\m5-1-pool-targeted-20261122-001`。

## 冻结选集与后端全量

使用 `compare_selection.py` 在 `40afef40` 上串行运行五组冻结选集（ownership 24、modifier 12、equipment 87、inventory 56、shared-replay 990）和三个登记单元选集（M1-3 15、M3-2 7、本切片 9）。共 1,200 个节点，逐组 `problems=0 improvements=0`。本切片的九条定向测试已登记在 `docs/verification/selection/m5-1-pool-definitions.json`。

使用 `docs/verification/g0-939c6746/run_baseline.py --freeze --repo <worktree> --output <run>/full` 串行收集 10,474 个后端节点。原始结果 `24 failed, 10446 passed, 2 skipped, 2 xfailed, 239 warnings in 1237.43s`，退出码 1，收集错误 0。代码 SHA 与源码在运行期间一致。

按节点、阶段和错误类型对照 M3-2 全量，新增 0、消失 0。相对正式冻结基线有两个先前已存在的本地失败，分别是 `test_population_cold_ready_gate.py::test_cold_ready`（call / KeyError）和 `test_population_recovery_measurement.py::test_recovery_owner_probe_measures_original_startup_before_full_oracle`（call / AssertionError）。原始控制台、JUnit、冻结清单与 `full-comparison.json` 在 `F:\paralls-verification\thread-a\m5-1-pool-40afef40`。

## 覆盖范围

本切片只改 `backend/app/gameplay/rule_pack_validator.py` 和 `backend/tests/test_rule_pack_validator.py`。U4 的加载器复用及 U8 的 Pool 声明加载已定向验证，Resolver 接入未做。U6 仅核对加载入口。U10 见本文件。U1、U2、U3、U5、U7 的域级工作未做。U9 的声明探针未做，回归单列。
