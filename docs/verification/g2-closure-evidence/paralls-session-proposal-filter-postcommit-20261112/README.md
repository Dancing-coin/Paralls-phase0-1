# Session 提案过滤：提交后全量对照

2026-11-12，测试提交 `38e571198deae2767d0d0e91142cbf2ebccb347a`。命令：

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-session-proposal-filter-postcommit-20261112 --freeze
```

收集 **10,079**，**10,036 passed、39 failed、4 skipped（含 2 xfailed）**，0 collection errors；pytest 退出码 1 是保留 39 项基线失败的结果。相对 G0 run2 的 9,937 个原节点，缺失/结果或阶段改变均为 0，新增 142 项全通过；相对 `56ac6eb5` 的 10,077 节点，缺失/改变均为 0，新增 2 项全通过。两份对照的 39 个失败节点、阶段、类型、消息、归一化堆栈均一致。堆栈额外归一化 pytest 临时目录编号、十六进制地址和 AnyIO cancel-scope ID，不改写任何原始运行文件。

结果及机器可读比较见 `results.json`、`comparison.json`。参照为 `../../g0-939c6746/full-4c641876.zip` 中 run2，以及同级归档的 `../paralls-epoch-fence-postcommit-20261111/results.json`。全量运行期间 HEAD 保持 `38e57119`，`source_unchanged=true`；后台和测试源码来自提交树。运行期间文档测量脚本有未提交改动，未改 backend 源码、未启动性能采样；这是范围明确的测试提交对照，不声称整个工作树无文档改动。

`results.json`、`invocation.json`、`environment.json`、`junit.xml`、`failures.jsonl` 从上述仓库外目录逐字节复制，均小于 50 MB；比较和扫描汇总另存 `comparison.json`、`scan.json`。本次扫描令牌、私钥、凭证字面值模式均 0 命中；环境变量字段检查了 `PYTHONHASHSEED`、`PYTHONPATH`、`PYTEST_ADDOPTS`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD`，没有密钥类名称。模式扫描不证明不存在所有形式的凭证；不输出或保存匹配值。公开 origin 与本机路径披露限制沿用上级 README，未推送。

原始 JUnit 含 4 行 pytest 失败文本尾随空白，原样保留；Git 空白检查在这些原始行上有提示，未通过改写原始证据消除提示。新增脚本及 Markdown 的空白检查通过。
