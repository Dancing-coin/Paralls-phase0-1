# M6-4 Play pattern 声明校验

代码提交 `b7bb36056bf1efe192c7d7d248d0b5dbd340d375`。以《组合总纲》第六、七、九节和《守城 Demo 的组合定义》第一节为依据。

`compile_play_pattern` 接收解析后的 YAML 映射，以及可信调用方提供的已登记 Reaction、Pipeline、Workflow ID 和规则包版本。结果是保序的不可变引用。两份正式文档分别使用 `{pack: id@version}` 和 `id@version`，编译器兼容两种输入并统一为 `id@version`。未提供的引用列表按空列表处理。重复引用拒绝，避免同一计划重复激活同一条目。

H8 / C6 由严格的声明字段和输出类型约束。发现顶层 `writes` 返回 `pattern_declares_writes`。其他未知字段、内联定义和无版本的包引用返回 `pattern_schema_invalid`。名称必须已在对应目录登记。运行时入口尚未接线。

## 验证

Python 3.12.2，SQLite 3.43.1。`PYTHONPATH=F:/codex-temp/a-ip-f759a465/backend`，`app.__file__` 核验为该检出内的 `backend/app/__init__.py`。

- `python -m pytest -q -p no:cacheprovider backend/tests/test_l5_play_pattern.py` 在实现前因模块未存在结束于 1 个收集错误，退出 2。原始输出 `F:/paralls-verification/thread-a/et-be6cca3aa9/red.txt`。
- `python -m pytest -q -p no:cacheprovider backend/tests/test_l5_play_pattern.py backend/tests/test_rule_pack_validator.py` 实现后为 `103 passed, 2 warnings`，退出 0。原始输出 `F:/paralls-verification/thread-a/et-49e4815971/targeted.txt`。
- `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>`。五组冻结选集 1,169 个节点，十组登记选集 88 个节点，合计 1,257 个节点。各组 `problems=0 improvements=0`，全部退出 0。原始输出 `F:/paralls-verification/thread-a/et-f3f762d193/`，本单元登记 12 个节点。
- `rg -n 'compile_play_pattern' backend/app backend/tests` 只找到入口定义和定向测试，生产调用未接入。本切片全量未运行。

## DoD 与后续依赖

U4、U8 验证了离线声明编译，U6 仅静态核对调用点，U10 为本文件，U11 已登记。U1–U3、U5、U7 的域级交付未做。U9 已覆盖 C6 及以 YAML 数据提交不同声明的校验路径。C8 的应用注册和激活、M6-1 至 M6-3 执行、M6-5 Demo 联调均未做。

Reaction 循环检查依赖可信的命令输出 FactType 清单。《Command 信封与回执》的命令目录和 `_command_violations` 目前只登记处理 Owner、payload schema、权限、幂等方式及版本。Resolver 的 `writes_fact_types` 只描述其自身写集。接线前需要从命令处理方得到可验证的输出集合并确认提交后的 Gateway 命令入口。

## 正常包加载接线增量

`6e7da420221c8a7ca4f3fb762153b2542e5b004c` 已在 `load_pack` 中从本次解析的 Reaction、Pipeline、Workflow 和规则包版本构建 Play pattern。新增包加载测试覆盖有效组合、未知组合引用、未知命令与 Reaction 循环。独立检出定向 133 passed，19 组选集共 1,288 节点零差异，完整版本和全量结果见 [组合包加载证据](m6-composition-pack-loading-20261123.md)。

本增量交付加载入口。C8 的应用注册和激活、组合生产执行、M6-5 Demo 仍待 H-A-011 至 H-A-014 所列接线。
