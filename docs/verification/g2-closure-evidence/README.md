# G2 收口全量运行归档

事实：代码仓库 origin 当前为公开仓库。本归档含本机 Windows 用户名的绝对路径；若仓库或其拆分产物将公开，须先脱敏或排除这些文件。脱敏会改变堆栈哈希，不能再与原 G0 失败签名逐字比较。

三次运行的 `invocation.json`、`environment.json` 与其他归档文件均已扫描令牌、私钥、凭证赋值及授权头模式，未命中。逐个扫描的 `invocation.json` 与 `environment.json` 文件均无上述命中；`environment.json` 中未发现密钥类环境变量名。扫描基于模式，不能证明不存在所有形式的凭证。结果、JUnit 和失败清单中含本机用户名路径，按项目负责人决定原样保留。

以下命令均使用 `D:/Temp/paralls-g0-py312/Scripts/python.exe` 运行 `docs/verification/g0-939c6746/run_baseline.py --repo . --output <对应 D:/Temp 运行目录> --freeze`。原始结果中 xfail 计入 skipped；以下拆分为 2 skipped、2 xfailed。

| 运行目录 | HEAD | 收集 | passed | failed | skipped | xfailed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `paralls-epoch-fence-postcommit-20261111` | `56ac6eb558444e4867cbcd688b214140b0d370ca` | 10077 | 10034 | 39 | 2 | 2 |
| `paralls-epoch-registry-postcommit-20261111` | `e8c430b2767728cceb789b4a8b40c91529aa3c60` | 10052 | 10009 | 39 | 2 | 2 |
| `paralls-session-slice-20261111-corrected-postcommit` | `84c237d3fea5b6060a3d98688c10566924948e9c` | 10048 | 10005 | 39 | 2 | 2 |

2026-11-12 以 `docs/verification/g0-939c6746/full-4c641876.zip` 中 `paralls-g0-4c641876-run2/results.json` 和 `failures.jsonl` 为 G0 原始对照，逐节点比较三份归档：G0 原有节点均未缺失，outcome 与 setup/call/teardown 阶段均未变化；新增节点分别为 140、115、111，全部通过。39 项失败的节点、阶段、异常类型、消息及堆栈在归一化 pytest 临时目录编号和运行时地址后均一致。方法与结论见本次只读比较记录；比较不代表重新运行测试。

各归档目录只包含对应运行的 `results.json`、`invocation.json`、`environment.json`、`junit.xml`、`failures.jsonl`。15 个文件均小于 50 MB，归档保持原始字节；目录局部 `.gitattributes` 禁止文本换行转换。
