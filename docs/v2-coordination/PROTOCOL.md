# v2 迁移双线程协作协议

- 版本：2（2026-11-22）。版本 1（2026-11-20）按"两位负责人、两台设备"起草；现在改为**一位项目负责人、一台设备、两个 Codex 线程**。改动见文末变更记录。
- 生效基线：`integration-2026-11-21` @ `0e67fe812280e7e518c84c27653153f5a69f2330`。
- 本文自包含：读者不需要读过任何对话或个人记忆文件。
- 配套文件：[AUTONOMY.md](AUTONOMY.md)（自主推进的决策表与门禁 G1–G6，**每个线程必读**）、[board.md](board.md)（任务账本，"现在在做什么"的唯一权威）、[BOUNDARIES.md](BOUNDARIES.md)（谁能改哪些文件）、`handoff.md`（需求与回应）、`claims/`、`daily/`（单元记录与合并记录）。
- 上位文档（文档仓库）：`docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md`、`docs/superpowers/plans/2026-11-22-architecture-v2-migration.md`。

## 一、背景与角色

| 名称 | 含义 |
|---|---|
| 项目负责人 | 唯一的人类决策者，裁定归属、放行提交与推送、解决分歧 |
| 线程 A（机制线） | 一个 Codex 线程：共享机制、L1 原语、L0、校验器/加载器、L5 引擎 |
| 线程 B（域线） | 一个 Codex 线程：单个域的迁移（runtime、`packs/<域>/`、域测试、探针） |
| 合并执行者 | 把线程提交合并进 `integration` 的操作者：第三个 Codex 线程或项目负责人本人 |
| `integration` | 汇合分支，只由合并执行者写 |
| 基线失败节点 | `docs/verification/absorb-main-3bf3418e/README.md`「失败集合」表中的 22 个节点 |
| 选集 | 两部分：①`absorb-main-3bf3418e/` 下 `ownership/modifier/equipment/inventory/shared-replay` 五组，共 1,169 个节点；②`docs/verification/selection/*.json` 下各迁移单元自行登记的分组。**选集随迁移增长**（规格 U11），不再固定 1,169 个节点 |

**为什么仍有协议：** 两个 Codex 线程互相看不到对方的上下文。归属、登记与交接必须落在仓库文件里，聊天和记忆不算数。

线程分工按依赖性质，不按首域：A 改所有域共用的东西，B 迁移各个域。版本 1 的"A=credential→ownership、B=debt→contract"作废；ownership 的 Bond 生命周期属于 L1，仍归 A。

## 二、分支与推送

1. 线程只推各自的 `thread-a/<主题>`、`thread-b/<主题>` 分支。**不得直推 `integration`，不得推 `main`。** `main` 不允许合入。
2. 暂存只用显式路径，不用 `git add -A` 或 `git add .`。
3. 工作区若混有他人未提交文件，提交只暂存自己指定的文件。
4. 线程可自由提交并推送**自己的分支**，不需要逐次请示。`integration` 只在门禁通过后由合并执行者推进。需要人工表态的只有 [AUTONOMY.md](AUTONOMY.md) §二"必须停下升级"列出的情形。

## 二·一、本机双 worktree 并行施工

1. A、B 各用独立 worktree 和自己的分支，从同一个 `origin/integration` 提交起步；不得在同一目录切换分支，不得复用旧线程 worktree。
2. 同机共享 Python 安装不代表共享导入路径。每次运行前将 `PYTHONPATH` 指向当前 worktree 的 `backend`，核验 Python 为 3.12.2，且 `app.__file__` 位于当前 worktree 的 `backend/app/`。
3. 两线程的 pytest 临时目录、冻结选集输出目录和证据输出目录各自命名并带唯一 run id；需要服务时用不同端口。
4. 全量测试串行约需二十多分钟（G0 实测 1436 秒），两线程同时跑会争用资源，**全量错开执行**。
5. 提示词与临时验证产物不进入代码提交。

## 三、交接：需求、回应与取舍

版本 1 的 `requests/thread-b.md`、`responses/thread-a.md` 合并为单个 `handoff.md`（旧文件保留作历史，不再追加）；`comms/` 交流记录取消。

- B 需要 A 独占文件发生变化，或需要 A 回答一个问题时，在 `handoff.md` 追加 `H-B-nnn` 条目，不得改共享文件，也不得做本地临时改动。
- A 在同一文件追加 `H-A-nnn` 回应，引用对应的 `H-B-nnn`：接受 / 拒绝 / 换方案 / 推迟；拒绝和换方案写理由，推迟写重新评估时间。
- A 也可主动追加"机制已可用"通告，供 B 判断何时开工。
- 文件只追加，不改旧条目。状态只记在回应里。
- 两线程只能通过 `handoff.md`、`claims/` 与代码互相知情。线程分歧由项目负责人裁定，裁定结果追加到 `handoff.md`（"项目负责人决定：……（日期）"）；口头决定未抄入则另一线程不受约束。

## 四、合并流程（按需，不按日）

1. 线程完成一个可合并的提交范围后，在 `daily/YYYY-MM-DD.md` 的"申报"里登记**具体 SHA** 与自选验证深度（选集或全量）。`daily/` 只在合并时写。
2. 项目负责人认为可合并时触发合并，无固定时刻。合并执行者：
   1. 范围检查：对照 [BOUNDARIES.md](BOUNDARIES.md)，用 `git diff --name-only` 核对每个申报 SHA 相对其与 `integration` 合并基点所改的文件。某线程改到不属于自己的文件，则该线程本次不合并。
   2. claims 检查：改动涉及基线失败节点合同却没有对应 `claims/` 条目，则该线程本次不合并。
   3. 密钥扫描：见 P-1。
   4. 合并到临时分支 `merge/YYYY-MM-DD`（同日多次加序号），**先 A 后 B**，不直接合到 `integration`。
   5. 门禁：按 [AUTONOMY.md](AUTONOMY.md) §三 的 G1–G6 执行；六项全过才可合并。G4（单元 DoD）只对域迁移类提交要求。
   6. 文本冲突：线程自有文件交给所属线程处理；共享文件不自行裁决，停下并报告项目负责人。
3. **验证（在临时分支上）。**
   - 选集：五组共 1,169 个节点，用 `docs/verification/absorb-main-3bf3418e/compare_selection.py`，输出目录必须尚不存在。
   - 全量：沿用 G0 `run_baseline.py`，串行。不强制，但**涉及共享机制的合并建议跑全量**。
   - 比较：按（节点、阶段、错误类型）对照冻结基线。基线失败节点仍失败且类型相同不算新增；先前通过而现在失败，或失败类型变化，算新增失败。失败转通过只记录，不计进度。
   - 环境：必须使用 Python 3.12.2，核验 `app.__file__` 落在当前 checkout，不在 `site-packages`。
4. **判定。** 范围检查、claims 检查、密钥扫描无新增暴露、验证无新增失败，四项都满足：`integration` 快进到临时分支并打标签 `integration-YYYY-MM-DD[-n]`。**不设审查人，不需要签字。** 有新增失败：分别跑"仅 A"与"A+B"定位归属，把肇事一方移出，另一方照常推进。
5. **基线不自动更新。** 只有 `claims/` 登记了对某基线失败节点的"有意修复"，且该节点验证通过，才从基线失败集合移除。
6. **事后发现问题：** 用新提交 revert 合并提交，不强推。
7. **如实标注验证深度。** 只跑选集时只能写"选集 1,169 节点无新增失败"，不得写"全量回归通过"。

## 五、协议规则

### P-1 密钥扫描输出必须带"是否已公开"列

推送或合并前的密钥扫描，每条命中的输出必须包含：

`文件:行号` ｜ 命中的规则类型 ｜ **匹配子串的 SHA-256 前 8 位（不写子串本身）** ｜ **该子串是否已存在于已公开的 base/main：是 / 否 / 未核实** ｜ 处置。

- 全部为"是"：记录后继续。
- 有"否"或"未核实"：停下，由项目负责人决定。"未核实"按新增暴露处理。
- "已公开"的参照点：`main`，以及 `integration` 起点 `3934bba6`。

### P-2 改基线失败节点的合同前，必须先登记

**节点的合同**指它所断言的行为：错误码、返回值、事件集合等。线程在修改任何基线失败节点的合同之前（改代码使其通过、改测试使其通过、改断言方向，都算），必须先在 `claims/thread-a.md` 或 `claims/thread-b.md` 追加一条，并推到自己的分支，之后才能提交实际改动。

- 两边登记了同一节点且方向相反：双方都不改，报告项目负责人裁定。
- 以下三项合同已在吸收 `main` 时定过，不需要再登记，但**要改动它们则必须先登记**：①`get_event` 的 closed 与损坏单行读取用 `gameplay_snapshot_row_invalid`，保留 `__cause__`，批量读取保留细分；②普通 action window 写四类事件，终局事件归具名 Owner；③未登记事件类型映射 `None`。
- 背景：2026-11-09，两边在互不知情下对同一批基线缺陷做了相反方向的修复。

### P-3 未登记的 event_type 不会进入图投影器

事实（在 `3934bba6` 核实）：`FACT_TYPE_REGISTRY`（`backend/app/models/fact_type.py`）的 gameplay 事件类型有固定来源；`main.py` 只订阅 `FACT_TYPE_REGISTRY.event_types()` 枚举出的类型。**没有声明的类型不会报错，只是静默地不进入图投影器。** 线程 A 已在 `3d6c72095fdcd2cbc9e0e4484e70a6010e7cdc87` 完成"图可见性发现机制"；当前状态以 `origin/integration` 上的注册表与图投影断言为准。

迁移某个域时，凡新增、改名、拆分 event_type，提交前核对：

1. 该类型出现在 `FACT_TYPE_REGISTRY.event_types()` 中，且其域不是 `unknown`；
2. 图投影器确实收到它。

每个域的迁移提交要么附一条"事件进入图投影器"的断言，要么在 `daily/` 或提交说明写明"未覆盖"。核对 1：

```powershell
& $python312 -c "import sys; sys.path.insert(0,'.'); import app; print(app.__file__); from app.models.fact_type import FACT_TYPE_REGISTRY as R; print('gameplay.xxx.yyy' in set(R.event_types()))"
```

### P-4 共享事件族的归属须先说明

一个域声明的事件类型若同时被其他域或共同禁区 runtime 写入（例如 `gameplay.commerce.*` 与 economy），该域在提交这些声明前，必须在 `handoff.md` 说明归属与读取方，并取得项目负责人确认。（版本 2 新增，来自线程 B 未提交的 `debt_contract_event_schema.py`。）

## 六、验证环境

- 解释器：Python 3.12.2，显式指定路径。
- 已知环境差异：SQLite 低于 3.51.3 时，两个并发 WAL checkpoint 节点跳过，属环境未验证项，不计通过；两个 Godot 探针（task45、task8）的堆栈哈希随 worktree 路径变化，按节点、阶段、错误类型比较。
- 旧的 338 节点选集与 39 项基线失败**不再作判据**。

## 七、已知风险与盲区

1. 只跑选集时，选集之外出现的新增失败发现不了。G3 探针曾暴露过这类情况。涉及共享机制的合并，建议全量。
2. 不设审查人与签字，`integration` 的推进依赖第四节的机器可核检查；检查项之外的问题靠事后 revert。
3. 未核实项：`main` 分支保护状态；Godot 探针未运行；两边都改但 Git 无冲突的文件内容只抽查过一处；终局事件 `terminal_outcome_recorded` 在生产代码无写入者；`FACT_TYPE_REGISTRY` 对已登记事件取 schema 名第二段为域，与 v2 Owner 命名不同。
4. 一线程退化：若上一里程碑中 B 有一半以上时间在等 A，下一里程碑改单线程顺序执行（见迁移计划第二节）。

## 变更记录

| 日期 | 变更 | 决定者 |
|---|---|---|
| 2026-11-20 | 初版草稿，两位负责人、两台设备 | 草稿，B 负责人未审阅 |
| 2026-11-22 | 版本 3：改为自主推进。新增 [AUTONOMY.md](AUTONOMY.md)（决策表、门禁 G1–G6、探针归因表）与 [board.md](board.md)（任务账本）；线程可自由提交并推送自己的分支，取消逐次放行；合并前按门禁 G1–G6 执行 | 项目负责人（会话口头，2026-11-22） |
| 2026-11-22 | 版本 2：改为一位项目负责人、一台设备、两个 Codex 线程。取消 `comms/`；`requests/`、`responses/` 合并为 `handoff.md`；取消 21:00 申报与 22:00 合并时点，改按需合并；取消"对方称"措辞与双负责人同意条款；线程分工改为机制线/域线；新增 P-4 | 项目负责人（会话口头，2026-11-22） |
