# 迁移任务账本

- 版本 1（2026-11-22）。配套：[AUTONOMY.md](AUTONOMY.md)（自主推进规则与门禁）、[PROTOCOL.md](PROTOCOL.md)、[BOUNDARIES.md](BOUNDARIES.md)。
- 上位文档（文档仓库）：`docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md`（成功标准 1–11、单元 DoD U1–U10）、`docs/superpowers/plans/2026-11-22-architecture-v2-migration.md`（里程碑 M0–M8）。
- **本文件是"现在在做什么"的唯一权威。** 状态只在这里更新；线程每完成一个单元或换任务，改本文件对应行，不要只在对话里说。
- 状态取值：`待开工` / `进行中` / `待门禁` / `已合并` / `阻塞`。
- "标准"列指本任务服务的成功标准编号（规格第三节）。

## 一、当前里程碑

M0 盘点 + M1-1 分片提交。两者都是准备性质：**尚未迁移任何域**，对成功标准 1–11 的直接贡献为零。

## 二、任务表

| 任务 | 归属 | 状态 | 产出 | 阻塞 / 放行条件 | 标准 |
|---|---|---|---|---|---|
| M0-1 runtime→Owner 映射（含 Combat 落点、Contract 事实清单） | B | 待门禁 | `docs/verification/m0-inventory-20261122/m0-1-runtime-owner-map.md` | 提交 `a7a66301`；只读，未跑测试 | 1、2 |
| M0-2 共享机制采用表 | B | 待门禁 | 同目录 `m0-2-mechanism-adoption.md` | 提交 `a7a66301` | 3 |
| M0-3 第二真相复核 | B | 待门禁 | 同目录 `m0-3-second-truth.md` | 提交 `a7a66301` | 11 |
| M0-4 读取方静态图 | B | 待门禁 | 同目录 `m0-4-readers.md` | 提交 `a7a66301`；993 调用 / 115 文件 | 4 |
| M0-5 Command 信封抽查 | B | 待门禁 | 同目录 `m0-5-command-envelope.md` | 提交 `a7a66301` | 1 |
| M0-6 波次表 | B | 待门禁 | 同目录 `m0-6-waves.md` | 提交 `a7a66301`、`c4a53e75`；静态输入，未验证 | 全部 |
| **M0.5 Owner 登记名单扩展** | A | 已合并 | 规范短名名单 + validator 测试 + `docs/verification/m0.5-owner-registry-20261122.md` | 合入 SHA：`9e0ff06c`；标签：`integration-2026-11-22-8`；允许名单不表示 Owner 已实现 v2 声明 | 1、2 |
| M1-1 Bond 分片提交 | A | 待门禁 | 三个本地提交 + `docs/verification/m1-1-bond-slices-20261122.md` | 按 AUTONOMY §二、§三 自判；不推送 | 3 |
| M1-2 Holdings 原语 | A | 待开工 | 原语实现 + 固定向量 | 由波次表决定是否需要 | 3 |
| M1-3 Pool 原语 | A | 待开工 | 同上 | 同上 | 3 |
| M1-4 Place 原语 | A | 待开工 | 同上 | 第 3 波后 | 3 |
| M1-5 Process 归并 | A | 待开工 | 同上 | S-5 已定：排在域迁移之后 | 3 |
| M2-1 读取边界清单更新 | A | 待开工 | 更新的清单 | 随各域迁移 | 4 |
| M2-2 `read_as` | A | 待开工 | 读取层入口 + 拒绝码 | 无具体依赖时优先做 | 4 |
| M2-3 known_time 推广 | A | 待开工 | 同上 | 随 M2-2 | 4 |
| M2-4 投影增量推进 | A | 待开工 | cursor + 区间校验 | — | 7 |
| M2-5 B4 前置设计 | A | 待开工 | 设计文档 | 实现须负责人确认 | 4 |
| M2-6 首条生产流受 epoch 保护 | A | 待开工 | 实现 + 证据 | 依赖 M2-5、负责人选流 | 4 |
| M3-1 `OwnerCommitBuilder` | A | 待开工 | 模块 + 测试 | 无依赖时的默认下一项 | 3 |
| M3-2 `StoreReadSnapshot` 推广 | A | 待开工 | 逐域接入 | 先测再改 | 3 |
| M3-3 R2 推广 | A/B | 待开工 | 按域并入 | 每域单独提交 | 7 |
| M3-4 `pinned_revisions` 校验 | A | 阻塞 | — | S-4 未决 | 3 |
| M4 第 1 波其余域 | 未定 | 待开工 | 每域一份设计与证据 | 待 M0-6 | 1–11 |
| M4-1 LifeState | B | 已合并 | `docs/verification/life-state-20261122/`；`docs/verification/selection/life_state.json` | 合入 SHA：`94c979998803bf52d24d8a8a8288caebdf1f4db4`；U1/U7/U8 偏离见证据，未作 v2 完成声明 | 1–11 |
| M4-2 ReferenceData | B | 待门禁 | `docs/verification/reference-data-20261123/`；`docs/verification/selection/reference_data.json` | 本地单元提交后等待门禁；U1/U2/U4/U5/U7/U8/U9 保留偏离，详见 evidence.md；P-3 三事件 projector 断言通过 | 1–11 |
| M4 第 2 波 | 未定 | 待开工 | 同上 | 待 M0-6 | 1–11 |
| M4 第 3 波（含 debt） | 未定 | 待开工 | 同上 | debt 归属 Economy/Market，枢纽 | 1–11 |
| M4 第 4 波（枢纽） | 未定 | 待开工 | 同上 | 前序波次回归证据 | 1–11 |
| M5 规则包完整化 | A | 待开工 | 加载器 + 校验规则 | — | 5 |
| M6 L5 引擎 | A | 待开工 | reaction/pipeline/workflow/play_pattern | 须在对应探针前落地 | 6 |
| M7 第二真相收口 | A/B | 阻塞 | — | S-2、S-3 未决 | 11 |
| M8 综合验收 | 负责人 | 待开工 | 逐条对照 | 全部里程碑完成 | 1–11 |

## 三、待决（负责人需表态）

| 编号 | 事项 | 影响 | 状态 |
|---|---|---|---|
| S-2 | B0 六字段的 Owner 归属 | M7；涉及 B0 的域迁移 | 未决，等 M0-3 事实 |
| S-3 | 司命 Heavenly Graph 保留或砍 | M7 | 未决，等 M0-3 事实 |
| S-4 | `pinned_revisions` 补校验是否算行为改变 | M3-4 | 未决 |
| S-1 | Combat 分类 | M4 波次、M0-1 | 未决，等 M0-1 |
| S-7 | 11-09 的逐域探针并入成功标准 8 | 验收口径 | 未决 |
| — | 谁做 M4 各波（A 或 B 或轮换） | 全部域迁移 | 未决，等 M0-6 |
| — | M2-6 选哪条生产流受 epoch 保护 | L0 强制 | 未决 |

## 四、更新规则

- 线程开工某任务：状态改 `进行中`，填单元名。
- 单元完成且自测通过：改 `待门禁`，填提交 SHA。
- 合并后：改 `已合并`，填合并 SHA 与标签。
- 遇到 AUTONOMY §二"必须停"的项：状态改 `阻塞`，并在对应行写清卡在哪，同时在 `handoff.md` 记一条。
- 本文件由两个线程共同追加/修改；同一行同一时间只有一个线程在改。
