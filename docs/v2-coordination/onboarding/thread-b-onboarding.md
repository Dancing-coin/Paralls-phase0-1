<!-- 入库副本，2026-11-20。仓库外原件在基线主机 Temp 目录，以本文件为准。 -->
# 线程 B 开工清单

> **2026-11-20 更新（以下为新增，下方原有内容保留）：** 双线程协作协议已写好并推送到分支 `coord/v2-protocol-20261120`（提交 `59eca3c0314ebc85fd42e821480bbf21d5722e90`，= `integration` 的 `3934bba6` + 一个只加文档的提交）。**协议尚未并入 `integration`，且是草稿，等你审阅。**

> **设备核对：** 开工前请先按同目录 `thread-b-device-check.md` 逐项核对你的设备并回报；它取代了旧的"第二台设备核对清单"。注意其中第三节：基线环境不是可编辑安装，靠 `PYTHONPATH` 加每次核验 `app.__file__`。

## 〇、开工前必读（按顺序）

先取到协议分支，再读文件（均在代码仓库内）：

```powershell
git fetch origin
git switch -c thread-b/debt-survey origin/coord/v2-protocol-20261120
git rev-parse HEAD    # 预期 59eca3c0314ebc85fd42e821480bbf21d5722e90
```

说明：协议并入 `integration` 之前，从协议分支开分支（它只比 `integration` 多一个文档提交）。分支名 `thread-b/<主题>` 是协议要求的前缀，主题自定。

| 顺序 | 文件 | 为什么读 |
|---|---|---|
| 1 | `docs/v2-coordination/PROTOCOL.md` | 全部规则：分支、交流记录、请求回应、每日合并、P-1/P-2/P-3 |
| 2 | `docs/v2-coordination/BOUNDARIES.md` | 哪些文件你不能改、哪些是你的、线程 A 的前置交付队列 |
| 3 | 本文件下方各节 | 环境、冻结基线、选集比较命令 |
| 4 | `docs/verification/absorb-main-3bf3418e/README.md` | 冻结基线、22 个基线失败节点、三项已定合同、已知缺口 |
| 5 | `docs/verification/g3-credential-design.md` | 首个域（credential）的完整迁移记录，是你做 debt 的参考；重点看"探针发现的缺陷"与"读取方清单"两类内容，那是上一轮踩过的坑 |
| 6 | `backend/app/gameplay/rule_pack_validator.py`、`fact_type_registry.py`、`owner_runtime_base.py`、`packs/credential_reference/` | 现有共享机制与规则包样例（只读） |
| 7 | `backend/app/gameplay/debt_runtime.py`、`contract_runtime.py` | 你的两个域现状 |

## 〇·一、你必须遵守的（完整条文见 PROTOCOL.md，这里只列要点）

1. **共享文件只读**：`owner_runtime_base.py`、`fact_type_registry.py`、`rule_pack_validator.py`、`app/models/fact_type.py`、`event_schema_registry.py`。需要它们变化，只在 `docs/v2-coordination/requests/thread-b.md` 写请求；**不许改，也不许做"临时、不合入"的本地改动**。
2. **共同禁区**：`economy_runtime.py`、`inventory_runtime.py` 两线程都不改。`debt` 依赖 `economy_runtime`，所以 debt 的设计里凡碰到它的地方，只能记录为"依赖"，不能改。`econ1_economy_runtime.py`、`land_right_runtime.py`、`main.py` 改前先在交流记录里通知线程 A。存储核心 `event_store.py`、`models.py` 不改。
3. **只推自己的分支** `thread-b/*`，不推 `integration`，不推 `main`；暂存用显式路径，不用 `git add -A`；未经你放行不推送。
4. **聊天没有约束力**：和线程 A 负责人聊的结论，涉及共享机制、独占文件、基线失败节点合同的，必须落成请求或 claim；每天把自己参与的沟通记入 `docs/v2-coordination/comms/YYYY-MM-DD-thread-b.md`（模板见 `comms/TEMPLATE.md`）。
5. **改基线失败节点的合同前先登记**到 `claims/thread-b.md`（P-2），并推到自己的分支后才能提交改动。
6. **推送或合并前做密钥扫描**，输出要带"匹配子串是否已存在于已公开的 base/main"一列（P-1）。
7. **新增或改名 event_type 要核对它在 `FACT_TYPE_REGISTRY.event_types()` 里**（P-3）。已知：未登记的类型不会报错，只是静默地不进图投影器；credential 的事件现在就是这样，线程 A 会在 0.5 项修。
8. **每日合并**：默认 21:00 前在 `daily/YYYY-MM-DD.md` 申报要合并的具体 SHA 与自选验证深度（选集或全量，全量不强制），22:00 起由合并执行者合并；`daily/` 必须如实写当天跑了选集还是全量。

## 〇·二、第一天能做什么，不能做什么

**线程 A 的第 0 项（Owner 登记泛化）完成前**：当前 `rule_pack_validator.py` 硬编码只接受 `owners == ["Credential"]`，任何 debt 或 contract 的规则包都加载不了。A 完成后会在 `docs/v2-coordination/responses/thread-a.md` 的"完成通告"表里写日期与合并 SHA，**你凭此开工写规则包与迁移代码**。此前只能：

- 读现状、写需求、写设计文档（设计文档放在自己分支的 `docs/` 下，路径自定，不要往 `docs/v2-coordination/` 里别人的文件里写）；
- 建议的第一件事（仅为建议，你和 A 负责人可调整）：**只读盘点 `debt`**——它发出和读取哪些事件类型、写哪些流、谁读它、对 `economy_runtime` 的依赖点有哪些，用 `rg` 与 AST 证据，不凭印象。盘点方法参考 `g3-credential-design.md` 的"读取方清单"两节；
- 盘点中发现需要共享机制配合的，立即写成 `R-B-001` 起的请求；
- 不要提交会依赖共享机制改动的代码。

## 〇·三、与线程 A 的联系

- 线程 A 负责人是你的对接人；两位可直接互发消息，但结论必须落到仓库里的文件（见上第 4 条）。
- A 每天开工会 `git fetch` 并只读你分支上的 `requests/thread-b.md`，所以请求写完要推到自己的分支。
- 第 0 项与 0.5 项（图可见性发现机制）的完成通告以 `responses/thread-a.md` 为准，聊天里说"做完了"不算。

## 〇·四、未核实项（不要当成已确认）

分支保护状态；协议文件尚未经过你审阅；存储核心不改、`land_right_runtime.py` 暂视为 A 的、`econ1_economy_runtime.py` 归属未定，这三处是起草时加的，**你有异议请直接提给 A 负责人**，不必先遵守再说。

## 克隆与版本

```powershell
git clone git@github.com:Dancing-coin/Paralls-phase0-1.git paralls-thread-b
Set-Location paralls-thread-b
git switch integration
git rev-parse HEAD
```

预期 HEAD：`3934bba6548300aee8489aacd938fa6d653de064`。使用 `integration`；核验 SHA 后再开始工作。

## 解释器与导入

基线主机解释器：

```text
3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]
D:\Temp\paralls-g0-py312\Scripts\python.exe
SQLite 3.43.1
```

第二台设备选择自己的 Python 3.12.2 解释器。后续验收一律使用 3.12.2；本机默认 `python` 是 3.13.5，不用于验收。每次运行前在 checkout 根目录执行（将 `python312` 设置为本机 3.12.2 的可执行文件）：

```powershell
$python312 = 'C:\path\to\python312\python.exe'
$repo = (Get-Location).Path
$env:PYTHONPATH = Join-Path $repo 'backend'
& $python312 -c "import sys;print(sys.version);print(sys.executable)"
& $python312 -c "import sqlite3;print(sqlite3.sqlite_version)"
& $python312 -c "import app;print(app.__file__)"
```

`app.__file__` 必须落在当前 checkout 的 `backend/app/`，不得落在 `site-packages`；否则停止验收。

## 冻结记录与比较

冻结记录：`docs/verification/absorb-main-3bf3418e/README.md`；完整证据：同目录 `evidence.zip`。五组选集及节点清单均在该目录：`ownership.json` / `ownership-nodeids.txt`、`modifier.json` / `modifier-nodeids.txt`、`equipment.json` / `equipment-nodeids.txt`、`inventory.json` / `inventory-nodeids.txt`、`shared-replay.json` / `shared-replay-nodeids.txt`。旧 39 项不作为判据。

以下在 checkout 根目录运行，每组使用尚不存在的独立输出目录：

```powershell
$groups = 'ownership','modifier','equipment','inventory','shared-replay'
foreach ($group in $groups) {
  & $python312 docs/verification/absorb-main-3bf3418e/compare_selection.py `
    --repo $repo `
    --selection "docs/verification/absorb-main-3bf3418e/$group.json" `
    --output "F:\paralls-verification\selection-$group-NEW"
}
```

## 已知环境差异

- SQLite 3.43.1 低于 3.51.3，两个并发 WAL checkpoint 节点跳过，属于环境未验证项，不计通过。
- task45 与 task8 两个 Godot 探针的堆栈哈希随 worktree 路径变化，按节点、阶段和错误类型比较；详见冻结记录。
- 基线主机 `core.autocrlf=true`（系统 Git 配置）。第二台设备检查 `git config --show-origin --get core.autocrlf`，记录实际值。

## 基线主机 pip freeze 快照（本机路径已去除）

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
paralls-phase0-backend @ <local source path omitted>
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
