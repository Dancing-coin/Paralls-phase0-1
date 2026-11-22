# M5-1 实体类型构成槽位

代码提交 `1f6aff2e3c4ec98809ba334b4f7085a0253162f0`，可单独 `git revert 1f6aff2e`。修改 `backend/app/gameplay/rule_pack_validator.py` 和 `backend/tests/test_rule_pack_validator.py`。

加载器使用《规则包文件格式》第四节的条目 ID 映射及《受击剖面》第五节的 `slots[].fact_type_pattern`。引用按包内 FactType 声明的完整标识匹配，包含 `*` 的模板标识作为登记键。重复槽位、无效条目或未登记的引用会导致整个包加载拒绝。合法声明冻结后随 `LoadedPack.entity_types` 返回，并参与既有内容哈希。现有包没有此分区时返回空映射。L0 实体实例登记、槽位运行时挂载与 Pool FactType 绑定待做。

## 已验证

Python 3.12.2，SQLite 3.43.1。每次设置 `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend`，已核实 `app.__file__` 位于同目录下的 `app/__init__.py`。临时文件和原始诊断均放在 F 盘。

- `python -m pytest -q -p no:cacheprovider backend/tests/test_rule_pack_validator.py -k entity_type`，实现前 5 failed、46 deselected、2 warnings。输出 `F:/paralls-verification/thread-a/et-18e9df64b4/red.txt`。
- `python -m pytest -q -p no:cacheprovider` 运行 `test_rule_pack_validator.py`、`test_pool_runtime.py`、`test_credential_pack_schema_boundary.py`、`test_credential_reference_chain.py`、`test_credential_fact_type_registry.py`。81 passed、2 warnings。输出 `F:/paralls-verification/thread-a/et-96fc20b9fa/targeted.txt`。
- `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>`。五组冻结选集 ownership 24、modifier 12、equipment 87、inventory 56、shared-replay 990，加登记选集 Pool runtime 15、StoreReadSnapshot 7、Pool 定义 9、实体槽位 5，共计 1,205，逐组 `problems=0 improvements=0`。输出 `F:/paralls-verification/thread-a/et-870c60e760`。

## 后端全量

在 `1f6aff2e` 上运行 `docs/verification/g0-939c6746/run_baseline.py --freeze --repo <worktree> --output <run>/full`。实际收集 10,479 节点，`24 failed, 10451 passed, 2 skipped, 2 xfailed, 239 warnings in 1302.67s`，退出码 1，收集错误 0。Python 和依赖摘要与 `40afef40` 的 Pool 定义全量一致，源码与 HEAD 在运行期间固定。按节点、阶段、错误类型对照 `40afef40`，新增 0、恢复 0。相对正式冻结基线 `3bf3418e` 多出两项既有失败，即 `test_cold_ready` 的 `KeyError` 与 `test_recovery_owner_probe_measures_original_startup_before_full_oracle` 的 `AssertionError`。原始日志和 `full-comparison.json` 在 `F:/paralls-verification/thread-a/et-23b4f91014`。

## 单元 DoD

U4 加载器复用与 U8 实体槽位声明已由定向用例验证，U6 仅静态核对加载入口。U10 为本文件，U11 在 `docs/verification/selection/m5-1-entity-types.json` 登记。U1、U2、U3、U5、U7 的域级工作及 U9 的声明探针未做。回归结果单列。
