# 线程 B 设备核对清单（2026-11-20 更新版）

> 取代此前的"第二台设备核对清单"。旧清单里的 `49f52dd5`、`codex/g0-b3-ingress-20261109`、338 节点、"以可编辑方式安装"均已过时，原因见第三节。
> **用法：** 在 B 负责人的设备上逐项执行，把"实际值"填进表格，贴回给 A 负责人。**任何一项与基线主机不一致：先记录，不要修**，由 A 负责人判断是否影响验收；记录同时写进 `docs/v2-coordination/comms/YYYY-MM-DD-thread-b.md`。
> 所有"基线主机值"都是 2026-11-20 在基线主机上实际运行或读取所得（Windows，Git Bash 环境）。未采集到的项标明"未采集"，不要当成已确认。

## 一、版本与远端

| # | 检查命令 | 预期值（基线主机） | 实际值（B 填） |
|---|---|---|---|
| 1 | `git --version` | `git version 2.49.0.windows.1`（版本不必相同，但要记录） | |
| 2 | `git remote -v` | `origin git@github.com:Dancing-coin/Paralls-phase0-1.git`（fetch 与 push 各一行，两台必须同一远端） | |
| 3 | `git ls-remote --heads origin` | 成功返回；基线主机 2026-11-20 返回 16 个分支（数量会变，成功与否才是判据）。**只验证读权限，不推送** | |
| 4 | 在其中确认三个引用 | `integration` = `3934bba6548300aee8489aacd938fa6d653de064`；`coord/v2-protocol-20261120` = `59eca3c0314ebc85fd42e821480bbf21d5722e90`；`absorb-main` = `3934bba6…` | |
| 5 | 新目录克隆或 `git worktree add`，不复用旧目录；`git status --porcelain=v1` | 空输出 | |
| 6 | 推送权限 | 只检查 SSH 能连、账号对该仓库有写权限（例如向 GitHub 确认协作者权限）；**不得推送测试分支** | |

> 分支保护状态**未核实**（基线主机无 `gh`），不要假定 `integration` 或 `main` 受保护。

## 二、解释器与依赖

| # | 检查命令 | 预期值（基线主机） | 实际值（B 填） |
|---|---|---|---|
| 7 | 显式用 Python 3.12.2 的可执行文件：`<python312> -c "import sys;print(sys.version)"` | `3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]`。**必须是 3.12.2**，次版本不同也要记录 | |
| 8 | `<python312> -c "import sqlite3;print(sqlite3.sqlite_version)"` | `3.43.1`。低于 3.51.3，所以冻结选集里有 2 个并发 WAL checkpoint 节点会跳过。若 B 的设备 ≥ 3.51.3，这 2 个节点会真正运行，**结果是新信息**，如实记录，不要计作"与基线一致" | |
| 9 | `pip freeze`（在验收用环境里） | 见下方快照；重点比 `httpx==0.28.1`、`pytest==9.1.1`、`pytest-asyncio==1.4.0`、`pydantic==2.13.5`、`PyYAML==6.0.3`、`websockets==17.1`、`zlib-ng==1.0.0` | |
| 10 | **导入路径**（见第三节，在 checkout 的 `backend` 目录下运行）：`<python312> -c "import sys;sys.path.insert(0,'.');import app;print(app.__file__)"` | 必须落在该 checkout 的 `backend/app/__init__.py`，**不能**落在 `site-packages` | |
| 11 | 默认 `python` 的版本 | 基线主机在本次会话的 Git Bash 里 `python --version` 为 `3.12.2`，但此前记录写的是 `3.13.5`，两者矛盾，**原因未查明**。结论：不要依赖默认 `python`，一律用显式路径 | |

基线主机 pip freeze 快照（只列第三方包，已去除本机路径；`paralls-phase0-backend` 另见第三节）：

```text
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
certifi==2026.7.22
click==8.5.0
colorama==0.4.6
fastapi==0.141.1
h11==0.16.0
httpcore==1.0.9
httptools==0.8.0
httpx==0.28.1
idna==3.19
iniconfig==2.3.0
packaging==26.3
pluggy==1.6.0
pydantic==2.13.5
pydantic_core==2.46.5
Pygments==2.21.0
pytest==9.1.1
pytest-asyncio==1.4.0
python-dotenv==1.2.3
PyYAML==6.0.3
starlette==1.6.0
typing-inspection==0.4.4
typing_extensions==4.16.0
uvicorn==0.52.4
watchfiles==1.2.0
websockets==17.1
zlib-ng==1.0.0
```

依赖声明在 `backend/pyproject.toml`：`requires-python >=3.11`；`fastapi>=0.115`、`uvicorn[standard]>=0.30,<0.53`、`pydantic>=2.7`、`PyYAML>=6.0`、`websockets>=12.0`、`zlib-ng==1.0.0`；dev 额外 `pytest>=8.2`、`pytest-asyncio>=0.23`、`httpx>=0.27`。这些是下限，没有锁文件，所以新装的环境**很可能**与上面快照的版本不同，务必对比。

## 三、导入路径：旧清单这里要改

旧清单写"以可编辑方式安装 backend"。基线主机的实际情况不是这样：

- 验收用的虚拟环境里，`site-packages` 下有一个**普通复制进去的 `app` 目录**和 `paralls_phase0_backend-0.1.0.dist-info`；`pip show` 没有 `Editable project location` 一行，**不是可编辑安装**。（读取于 2026-11-20；复制的 `app` 来自哪一次安装、内容是否与当前代码一致，未核对。）
- 所以基线靠的是**把 `PYTHONPATH` 设为当前 checkout 的 `backend`**，让它排在 `site-packages` 之前，并且每次运行前核验 `app.__file__`。若不设 `PYTHONPATH`，导入的可能是 `site-packages` 里那份旧副本，测试结果就不是当前代码的结果。

B 的设备上做法：**二选一，并写明用的是哪种**：
- (a) 与基线一致：设 `PYTHONPATH=<checkout>/backend`，每次运行前核验第 10 项；
- (b) 在新环境里用 `pip install -e backend` 做可编辑安装，同样核验第 10 项。

两种都必须在第 10 项通过。无论哪种，**第 10 项失败就停止验收**。

## 四、行尾、时区、区域

| # | 检查命令 | 预期值（基线主机） | 实际值（B 填） |
|---|---|---|---|
| 12 | `git config --show-origin --get-all core.autocrlf` | `file:<Git 安装目录>/etc/gitconfig  true`（来自**系统级**配置，不是仓库或用户配置） | |
| 13 | `git config --show-origin --get core.eol` | 无输出（未设置） | |
| 14 | `git config --show-origin --get core.longpaths` | 基线主机命令无输出（该项未设置）。仓库里有较深路径，若 B 的设备在检出时报路径过长，如实记录 | |
| 14b | `git config --get core.symlinks` | `false`（基线主机，Windows 默认；B 若在支持符号链接的系统上会是 `true`，记录即可） | |
| 15 | `<python312> -c "import locale;print(locale.getpreferredencoding(False))"` | `cp936` | |
| 16 | `<python312> -c "import time;print(time.timezone, time.tzname)"` | `-28800`，中国标准时间（UTC+8）。时区名在 Git Bash 里显示为乱码，只比较 `-28800` | |
| 17 | 操作系统 | `MINGW64_NT-10.0-26200`（Windows 11），Git Bash | |

`core.autocrlf=true` 是 Git for Windows 的系统默认，不是项目要求。B 若在非 Windows 设备上，该项必然不同，**这不是缺陷**，但行尾差异会影响哈希类比较（如源码指纹、文件摘要），要如实记录。

## 五、冻结选集与失败集合

**旧的 338 节点、39 项基线失败已不再作判据。** 新判据：

| # | 检查 | 预期值 | 实际值（B 填） |
|---|---|---|---|
| 18 | 在 checkout 根目录，对五组各跑一次 `--collect-only`（用 `docs/verification/g0-939c6746/run_baseline.py`，节点清单是 `docs/verification/absorb-main-3bf3418e/<组>-nodeids.txt`，每个节点一个 `--test`，输出目录必须尚不存在） | 收集数量：`ownership` 24、`modifier` 12、`equipment` 87、`inventory` 56、`shared-replay` 990，合计 1,169（五组有重叠，不能去重后声称唯一节点数） | |
| 19 | 实际运行五组，用 `docs/verification/absorb-main-3bf3418e/compare_selection.py`（`--repo`、`--selection <组>.json`、`--output` 不存在的新目录） | 与冻结记录逐节点一致；比较脚本会校验收集、状态与失败阶段/错误类型 | |
| 20 | 全量（可选，不强制） | 基线 M `3bf3418e`：10,392 收集，10,366 通过，22 失败，2 跳过，2 xfailed。22 个失败的清单与堆栈哈希在 `docs/verification/absorb-main-3bf3418e/README.md` 与 `evidence.zip`，全部是 P、G 共有的既有失败 | |

注意：
- 全量跑的是哪个提交要写明；冻结基线的被测代码是 `3bf3418e`，而 `integration` 在 `3934bba6`（只多了冻结记录里补来源提交的文档），**两者的差只有文档**，但这是从提交说明推出的，我没有对 `3bf3418e..3934bba6` 的 diff 范围逐项核对。需要严格时请用 `git diff --stat 3bf3418e 3934bba6` 自己确认。
- 冻结记录里 22 个失败中，13 个是 `test_siming_heavenly_godot_static.py` 的 `FileNotFoundError`，另有 `character_agent_runtime_persistence_wiring` 的 `FileNotFoundError`。这些很可能与路径或 Godot 工程文件有关，**我没有逐个查明原因**，所以 B 的设备上它们可能表现不同。如实记录，不要修。
- task45 与 task8 两个 Godot 探针的堆栈哈希随 worktree 路径变化，按（节点、阶段、错误类型）比较，不比较哈希。

## 六、磁盘

基线主机的磁盘剩余空间**未采集**（本次 `df` 对含空格或盘符路径报错，没有可用输出）。B 请记录：checkout 所在盘剩余空间、`TEMP` 所在盘剩余空间、输出目录所在盘剩余空间。基线运行使用独立的 `TEMP` 与输出目录（M2 在 F 盘），全量日志和 JUnit 体积较大，**具体需要多少我没有测过**，不要按空间"应该够"处理。

## 七、回报格式

分三节，不要替自己宣布通过：
- **已验证**：每项附命令和原始输出；
- **仅静态检查**：没跑只读了的；
- **与基线主机不一致的项**：逐项列出，只记录，不修，不下"不影响"的结论。
