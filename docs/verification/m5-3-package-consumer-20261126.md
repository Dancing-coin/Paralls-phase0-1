# M5-3 世界级规则包消费接线

## 范围

代码提交 `29492189` 为 M6-5 runtime 工厂增加显式的 `PackageArchive` 与 `PackageRef` 输入。配置完整时，Morale/Presence 与 Information 的 L5 reactions 从同一 immutable archive 解析，避免运行时直接从固定目录加载。缺少 archive 或任一 package pin 时，工厂 fail-closed。

该提交不新增玩法 Owner、FactType 或事件总线，也不修改 `event_store.py`、`models.py`。`pack.migrated` 仍是 L4 平台控制面事件。

## 环境

- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`，3.12.2（沿用当前 A 验证环境）
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`
- 临时目录与 pytest basetemp: `F:\paralls-verification\thread-a\m5-3-consumer-20261126-01\`
- 测试导入路径由 pytest 输出确认来自当前 A worktree

## 已验证

命令：

```text
set PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend
set TEMP=F:\paralls-verification\thread-a\m5-3-consumer-20261126-01
set TMP=F:\paralls-verification\thread-a\m5-3-consumer-20261126-01
D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=F:\paralls-verification\thread-a\m5-3-consumer-20261126-01\pytest-temp backend\tests\test_package_migration_runtime.py backend\tests\test_gameplay_event_schema_registry.py backend\tests\test_m6_5_siege_runtime.py
```

原始结果：`66 passed, 6 warnings, exit 0`。

新增行为由以下节点覆盖：

- `test_m6_5_runtime_can_consume_world_pinned_package_archive`
- `test_m6_5_runtime_rejects_incomplete_package_consumer_configuration`

`git diff --check`：exit 0。

冻结选择（当前 tip）：M5-3 登记选择 `selected=22 problems=0 improvements=0`，Ownership 选择 `selected=24 problems=0 improvements=0`。shared-replay 990 本次未完成，runner 在约三分钟无输出后于已知 PowerShell listener 查询停滞处中止，未停止外部进程。

## 仍未完成

- `main.py` 尚未从部署配置读取 `world_ref`、初始 package refs、archive directories 与 trusted content hashes。
- 当前代码没有生产 manifest 的信任来源或跨语言 canonical hash 合同。
- 未运行 backend 全量、UE 实机或生产服务器启动。

因此本证据证明 M6-5 的世界级 package consumer 机制和拒绝路径，不能证明生产启动已加载迁移包。

## 需要外部输入

部署/发布侧仍需提供单一守城 world 的 `world_ref`、初始 package identity 列表、每个 identity 的 archive 目录和可信 content-hash manifest。输入到位后才能在 `main.py` 接入 startup bootstrap，并运行启动、迁移、重启和历史 replay 验证。

## U1-U11

| 项 | 状态 |
|---|---|
| U1-U4 | 继承 M5-3 / M6-5 既有证据 |
| U5-U6 | 既有 migration 与读取方证据；本提交未改持久事件 |
| U7-U8 | 规则包消费路径静态可见，生产启动未接入 |
| U9 | 新增定向测试、M5-3 登记选择和 Ownership 选择通过；shared-replay 本次未完成 |
| U10 | 本文件列出改动与未覆盖项 |
| U11 | `docs/verification/selection/m5-3-package-migration.json` 已登记新增节点 |
