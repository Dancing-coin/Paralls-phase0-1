# 每日合并记录模板

复制为 `daily/YYYY-MM-DD.md`。合并时才写，不按日。申报部分由各线程填写；执行部分由合并执行者填写。**如实记录，不替任何人宣布通过，只写"满足 / 不满足"加证据。**

## 申报（合并前）

| 线程 | 要合并的 SHA | 自选验证深度（选集 / 全量） | 备注 |
|---|---|---|---|
| A | | | |
| B | | | |

## 执行

- 起点：`integration` SHA：
- 解释器与环境：Python 版本、`app.__file__`、SQLite 版本：
- 合并顺序与临时分支：先 A 后 B，`merge/YYYY-MM-DD`

### 合并前检查

| 检查 | 线程 A | 线程 B | 证据（命令与原始输出） |
|---|---|---|---|
| G0 账本与标准挂钩（`board.md` 有行且标成功标准编号） | 满足 / 不满足 | 满足 / 不满足 | |
| G1 范围检查（对照 BOUNDARIES.md） | | | |
| G2 claims 检查 | | | |
| G3 事件可见性（P-3 断言） | | | |
| G4 单元 DoD（U1–U11，仅域迁移类） | | | |
| G6 密钥扫描（P-1，含"是否已公开"列） | | | |
| G7 单元选集登记（`docs/verification/selection/<unit>.json`） | | | |

### 验证

- 实际执行深度：选集 / 全量（**只跑选集时不得写"全量回归通过"**）
- 比较对象：冻结基线 M `3bf3418e`（22 个失败）+ 各单元登记文件里的 outcome
- 逐组结果（**每组都列，不得只写总数**）：

| 选集分组 | selected | problems | improvements |
|---|---:|---:|---:|
| absorb-main/ownership | | | |
| absorb-main/modifier | | | |
| absorb-main/equipment | | | |
| absorb-main/inventory | | | |
| absorb-main/shared-replay | | | |
| selection/&lt;unit&gt; | | | |

- 新增失败：
- 失败转通过（只记录，不计进度）：
- 环境未验证项：

### 判定

- 结果：快进 `integration` 并打标签 `integration-YYYY-MM-DD` / 移出某线程 / 未推进
- 若有新增失败的归属定位（仅 A / A+B）：
- 基线变更（仅当 claims 登记了有意修复且验证通过）：

### 已知盲区提示

- 当天未覆盖的区域：
