# 计划 A：运行时连续性与共享基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 执行时使用 superpowers:executing-plans；明确采用子代理方式时使用 superpowers:subagent-driven-development。按复选框逐项取证，不因计划已写完而勾选实施任务。

**Goal:** 人员甲交付同一角色跨 B0–B3 的共享合同、连续性账本、安全交接、受控读取，并为一个日供给分片计算器提供最小冻结/模式/审计合同；负责公共入口集成与共同验收。

**Architecture:** 扩展现有 Character Core、population_continuity、world_runtime、Siming 与 GameplayEventStore。纯计算与事实提交分离；复用现有 CharacterContinuityService、activation lock、读写 revision、幂等和 replay。人员乙通过明确接口提交模块与领域结果。

**Tech Stack:** 项目现有 Python、Pydantic、pytest、SQLite、Harness；不增加调度框架、求解器、Ray 或 GPU 依赖。

**Spec:** [整合规格](../../specs/world-character-siming-authority-mainline/2026-09-18-character-population-social-causality-integrated-design.md)，组织修订 `2026-09-18-r3`。配套为[计划 B](2026-09-18-character-simulation-domain-vertical-implementation-plan.md)。

**Status:** `implementation_in_progress`。2026-10-08 用户明确要求继续优化并实施计划 A；采用本会话顺序执行。甲、乙仍是职责占位，任务只按实际代码和新鲜验证勾选，计划 B 的业务实现及 Godot 不因此自动完成。

**核查基线:** 原文静态复审为 `d9b810f3`；2026-10-08 实施核对 main 为 `6a03a0fdcbba66096b2756a1a500442209af48eb`，当时优化候选为 `74f91d13eea5b4ac009dc88fe5895f999a466cc8`。2026-10-10 用户要求以当前代码优先实现计划A，继续同一Goal，在已有 `codex/population-c9-acceptance` 工作树以 `bc016b8ea1c7d6c5e52fd426f34f6b88506457d7` 为代码基线实施；原 `population-hotpath` 的未提交内容和10/04不可变帧设计保留，main 不直接修改。

## Global Constraints

- “同一角色最多一个有效推进者。”角色身份、档案、状态和记忆不因精度切换复制。
- “不新增第二套 runtime、clock、scheduler、event store、event bus、万能 router 或 generic settlement coordinator。”
- “模块、模型、Siming、图谱和 Godot 不直接写库存、账户、关系、法律、人口、空间或角色私有记忆。”
- 仿真 tick、来源 revision、角色 revision、状态游标和记忆游标分别校验；新增窗口使用 `(from_tick, to_tick]`。
- Owner 在实际提交点重验完整 read-set；通知失效和读取最新 head 不能替代旧 expected revision 校验。
- `schedule_gated_supply` 只证明组织供应承诺；实际粮食、药品、床位与迁移各需真实能力和 receipt。
- C0–C7 仍是连续性基线跟踪范围；本轮不实现群体报告到个人的分摊。AM1/BM1 是单个日供给分片计算器，shadow 和 advisory 分阶段验收；M-active 可选且须 G-M 准入，E/F 保留原 spec 前置门禁。
- 当前 advance_b0_row 是按 actor 连续积分，不能作为安全群体聚合/分摊已完成的证据。A2 首期仅锚点、分片、明确 actor 结果消费与交接；模型报告不更新个人状态或游标。
- 保留现有历史合同，新增严格校验不能追溯改义旧事件。Pydantic `frozen=True` 不等于嵌套字典已隔离，帧及计算输入必须做嵌套不可变或防御复制验证。
- 六项生产工程沿用[既有计划](../2026-09-16-population-production-runtime-closure-implementation-plan.md)，新任务不得复制其执行隔离、恢复或表现框架。该旧计划的证据路径和文档提交表述如与当前 AGENTS.md 不一致，以当前仓库规则为准。
- 执行时按 [Harness 指南](../../../harness.md) 和项目 harness-verification skill 选入口、导出和清理。Godot/all 按用户要求暂停，相关门禁分别记未运行；后端与性能按实际修改重新验收。清理不了的本轮已导出文件按用户要求归档、核验并标记可清理。

开源依据沿用[项目与开源对照](../../../reference/2026-09-18-social-simulation-open-source-comparison.md)：A1/A3 借鉴 Mesa 的激活/事件机制，A5 借鉴状态与执行对象分离；不引入另一套 Model runtime。性能优化以当前瓶颈和等价证据为准，不因人口数增加迁入 Ray/FLAME GPU。

### 2026-10-08 实施适配

- 三份用户附件与仓库 9/18 原文 SHA256 完全一致；原附件保留。本次授权覆盖计划 A 的实施，附件内旧的“只写文档”等会话指令不覆盖当前用户要求。
- `CharacterSimulationFrame` 是按需装配的角色输入；B0 常规窗口不逐人展开档案。10/04 候选帧仅可作为默认人口链的临时不可变传输表示，不能成为第二份角色状态或另一个提交合同。
- 帧继续消费原 `PopulationReadSet` 和其 canonical 算法，来源版本冲突或内容与旧 digest 不一致时拒绝。冻结只作用于新帧，不改 world 公开缓存及旧模型的可变/别名行为。
- `ModuleDefinition.state_schema` 复用已有 `StateGroupDefinition`，不运行 JSON schema 生成的动态代码；新增 builder 参数 `module_definitions: tuple[ModuleDefinition, ...] = ()`，非空模块状态必须有相应声明。未知字段拒绝；未声明字段策略视为 `individual_only`。
- 新命令使用成对的 `activation_lock_ref`/`activation_lock_revision`；实际 Core 接纳点校验原 authority 的当前凭据。旧命令不带这两个字段时，其序列化和历史摘要保持原值；幂等重放先恢复原提交结果，不因锁已释放而重做业务。
- 建议 V1 载荷和 `validate_module_proposal` 使用 spec 6.1 的 10/08 适配记录；闭合的候选引用和已声明模块字段不自动产生 Owner 写入。提交包/交接包使用原 `held_revision` 作为 `lock_revision`，个人/群体凭据严格分开。解析结果到复核/B0 截止后不得继续构帧，必须重新解析。
- `validate_module_proposal` 返回经过 schema 复核与隔离的 ModuleProposal，消费者只能使用返回值；仅重新检查小型候选，不重复展开 frame。model_copy 绕过校验的载荷/期限必须拒绝，合法副本的可变输入不能传入后续提交链。
- A2 从现有已确认 actor 结果和 Core receipt 派生锚点/消费索引，不镜像状态或从群体报告生成个人结果。AM1 保持固定模板、无缓存起步；B5/BM1 未交付的真实消费者分别记依赖未满足，不伪造输入或通过。
- 每项生产变更先 RED/GREEN 和受影响回归；全部验收及报告完整后再集成 main 和推送，任务级提交步骤不覆盖用户的这一提交约束。

### 2026-10-08 优化优先级复核

本次独立计数与外部采样证据位于 `D:/ParallsEvidence/paralls-owner-profile-audit-20261008T083219Z`，对应运行时源码 `sha256:24c834a288f1d138d7482930b9f1b7127537d14cad408347d09bcf564b6f204c`；属于定位，不是性能通过。原 `cProfile` 的部分调用计数与独立计数冲突，其耗时排名不采用。每窗两次 B0 构建分别来自 public 的 1000 个 B0 投影和 organization:summary 的 28 个领域投影（0 个 B0），不是同一人口重复推进，不删除领域校验。

- 当前优先量化完整 owner 的编码、持久化与模型复制成本，以及百人档窗口间隔；采用同源原窗口、独立无探针对照和持久事实 oracle 检查收益。world raw Unicode 摘要与发布/read-set typed ASCII 摘要保留各自算法，采样热点不自动授权复用。
- A1 保持按需构帧；真实批量消费者接线时再证明独立快照可按批验证，避免为 N 个角色重复展开 N 行读集。当前不增加没有消费者的批量接口或跨窗缓存。
- A2 仅保存身份/许可锚点、分片引用和已确认 actor 结果的消费游标，按原 receipt 增量更新；不镜像个人状态、逐 tick 复制整份账本或从群体均值回填。
- A3 在原 activation/held_revision/Core 接纳链补交接，保留实际提交点重验与旧推进者拒绝；A4/AM1 复用最小获权冻结输入，按 shadow → advisory 逐门验收，无缓存起步。
- 每个优化分别证明行为等价和完整 owner 净收益；短诊断、采样和框架接口完成均不勾选 A2–A5/AM1 总验收。当前两档原 10× 仍失败，新候选完整 7200 秒/600 秒复验尚未执行。

补充诊断 `D:/ParallsEvidence/paralls-owner-native-20261008T091000Z`：50Hz 外部 native 采样捕获实际 owner 的 198 个窗口内样本，只按模块归因；无完整符号时不把最近导出符号当作实际 SQLite/Pydantic 函数。原 `_rows` 改为 native cursor.fetchall 的三组同源对照平均改善 -0.862977%（两组退化），停止该候选，生产不修改。

百人原 3 秒/30 窗口实际 owner 队列探针记录 347 条命令，最长测量期窗间隔约 30.7ms，多数剩余空档没有 owner 命令执行。进一步捕获 ProactorEventLoop 请求等待 4.35ms、实际等待 20.08ms（额外 15.73ms）；时钟读数精度不能代表唤醒精度。外部线程等待原型沿用原时钟和阈值，三组仅一组性能通过，第三组仍有约 15ms 迟延并失败，尚不进入生产。继续优先减少完整窗口内已证实的编码/模型转换成本，保留样本中的实际 FULL 提交及竞争证据；不以单次定时器改善、SQLite fetchall 或删除不同事件的领域校验宣称闭环完成。

补充诊断 `D:/ParallsEvidence/paralls-projection-input-20261008T095821Z`：默认千人投影的原 TypeAdapter 校验中位数为 1.79ms，直接分配模型的微实验为 0.73ms；约 1.06ms 的差值尚未计入来源资格检查，也未覆盖非法输入、自定义校验器和完整 owner。因此不增加绕过模型校验的生产分支。两次实际 owner 读取探针各执行 30 窗并通过原片段摘要及冷开审计；探针与摘要 oracle 自身有开销，不用于净收益判断。

尾部事件读取已经按游标增量推进：公开与组织投影各读 5,893 条、组织到期来源读 5,893 条，合计 17,679 条的读取/解码/模型校验约 95ms/30 窗；另有冲突来源的点读。首尾序列范围从 1–176 推进到 5,697–5,893，不能将累计读取量描述为每窗全历史扫描。不同 scope 保留各自的缺口、流版本和可见性校验，不引入可变事件模型缓存或共享消费游标。计划 A 后续实现继续优先 A1 按需构帧、A2 按真实 actor receipt 更新账本及消费游标、A3 原锁接纳链、A4/AM1 最小获权输入；这些是实现约束，尚不是性能通过或任务完成证据。

后续同源候选筛选见 `D:/ParallsEvidence/paralls-owner-topology-20261008T102300Z`：30 窗 SQL 查询边界采样 776 次，均位于较高 EfficiencyClass 核心，未据此调整亲和性或将混合核心调度认作本轮根因；单个采样未记录线程身份，结论限于观察到的执行点。默认 5ms GIL 切换间隔改为 1ms 的三组完整 owner 对照平均改善 -4.849989%，两组退化，停止该候选。Windows 手动复位高精度 timer 经现有 Proactor/IOCP 的外部原型将三次百人档原 30 窗额外等待均降至 1ms 以下，但三次完整窗口性能仍失败，最大 lag 为 5.285619/2.290825/1.286961，未接入生产。后续优化须降低完整 fixture/cadence 临界路径和尾延迟，不能以计时精度、CPU 绑核或调整 GIL 替代整窗净收益；原时钟、FULL 提交和验收阈值保持。

SQL 与真实 spawn 输出链补充诊断见 `D:/ParallsEvidence/paralls-sql-prepare-20261008T110800Z`：热连接仅 36 个 SQL 模板，编译回调集中在带参数 LIMIT 的读取；原生 sqlite_stmt 确认固定绑定值也发生 reprepare，不扩大默认 128 个 statement cache。QPSG 三组完整手动 owner 对照将 reprepare 从 1,119 次降至 2 次，但均变慢，平均改善 -5.211282%，停止该候选；固定 LIMIT 的只读微测外推仅约 0.134ms/窗，不改生产查询。减少编译次数本身不能签署性能收益。

同源原时钟千人档两次各 30 个完整 measurement 窗仍失败：p95 cadence 89.4912/88.4048ms，max lag 9.564907/9.148299，结束积压均 9。仓库外探针记录实际 child 的 IPC 编解码及 queue feeder pickle；3 秒测量期累计约 2.66/2.55ms，单窗重叠最多 0.38ms，不能解释每窗约 25ms 的缺口。完整 owner 均值 126.11/124.68ms，fixture 约 40ms、cadence 约 84ms；后续仍量化该同步临界路径的编码、持久化与复制成本，不凭手动基准和历史原时钟时长差异认定 IPC 根因。含探针的时长只作归因，两次 integrity 通过不替代性能通过或正式 clean-source 门，provider 实际调用为 0。

实施前又发现热字段快路的字段保留缺口：原 `_commit_batch_atomic` 仅按更新字段数等于 6 就替换整行，实际 B0 推进会删除已注册的模块列，六个不同字段的更新也会删除未更新基础字段。四个真实反例先失败后修复；只有完整基础字段且未注册扩展列时仍替换，其余按原子批次合并，版本/锁与零写入校验保持。61 项 focused 回归、原 hot-state-equivalence profile 和千人 30 窗默认输入的同源五库事实/冷热快照/FULL/结果等价已通过；全量回归为 7729 passed / 2 skipped，两个历史 spawn 用例在全量通过，证据 `D:/ParallsEvidence/paralls-hotstate-fields-20261008T115900Z`。旧方法控制从封存原文件加载，双方 kernel 源码身份同为当前修复版；这不证明旧 kernel 检查点可被新源码接受，也不证明模块状态已持久恢复，A2 仍需真实 receipt 消费与恢复。该修复属于连续性正确性，不签为 10× 净性能提升；后续原时钟复验独立记录，当前修复版尚未重跑完整长窗。

当前 ed6ecab7 修复版在 `D:/ParallsEvidence/paralls-small-json-20261008T124600Z` 重新执行原时钟千人 10×/3 秒/30 个完整 measurement 窗及原 verifier：integrity passed，performance failed，p95 cadence 97.4202ms、max lag 13.371704、结束积压 13；strict formal 另因 dirty blocked。短正文改用原读取端支持的 TEXT 的仓库外原型，1KB/2KB 各三组完整 owner 配对平均改善 2.864852%/4.155595%，数据库分别增大 9.445823%/23.093466%，均未达到既有 5% 筛选门，不进入生产。原阈值、FULL、时钟和输入未改；只有新的热点/消费者证据才重开这类候选，不以微小编码收益叠签正式性能通过。

## 1. 两人责任与文件所有权

| 责任 | 人员甲 | 人员乙 |
| --- | --- | --- |
| 共享 schema、参与解析、连续性与锁 | 主责，维护唯一合同 | 提供玩法约束，评审真实消费者 |
| 角色模块、原型、洪灾与领域协议 | 提供接纳端口，评审越权与重复提交 | 主责，维护规则和 Owner 映射 |
| Character Core | 独占公共接纳与运行循环修改 | seed_planner 中构造输入；不得直接写 Core 状态/记忆 |
| 首个计算器 | 最小 grant、冻结/失效、模式隔离、报告与审计合同 | 固定日供给语义、现有 Owner 输入适配和纯计算 |
| 验收 | 公共 Harness、回放、集成与汇总 | 模块/领域 focused tests、洪灾与 Godot 样板 |
| 后继 E/F | 依赖版本、impact 调度接入、通用隔离合同 | 操作证据、领域确认、Godot 与阵营场景；门禁满足后细化 |

**甲单一编辑的现有文件：** `backend/app/population_continuity/models.py`、`siming_contracts.py`、`batch.py`、`continuous.py`、`hot_state.py`、`world.py`、`activation.py`、`activation_policy.py`（前述缩写均在同一 population_continuity 目录）；`backend/app/world_runtime/population_driver.py`、`simulation_clock.py`；`backend/app/character_agent/models/simulation_seed.py`、`services/character_continuity.py`、`runtime/runtime_loop.py`；`backend/app/main.py`、`backend/app/services/siming_runtime.py`、`siming_population_capability.py`。

甲拥有共享 profile、验证脚本和 CI 接线修改责任。`GameplayEventStore` 当前已有 read-set 重验；默认消费其接口，不为本任务重写 store。若查出实际缺口，由甲在对应任务中以复现测试做最小修复。

乙拥有 `seed_planner.py`、`owner_adapters.py`、`inventory_owner_adapter.py`、`social_owner_adapter.py`、`domain_projection_sources.py` 及其新增角色模块、洪灾/日供给计算文件。`vertical.py` 是既有大型样板文件，乙只提取必要复用，新增洪灾场景放独立窄文件。`social_input.py` 和 `source_inputs.py` 首期作为共同只读依赖；必要读取补验放乙的窄输入适配，不能两人分别改造。详细文件清单见 B。

**并行规则：** 两人不同时修改相同公共文件。乙提交接口需求、领域代码和 focused tests 后，由甲顺序接线。若既有 P 生产工程仍在修改同一入口，先取得其接口/提交交接再接线，不平行替换其实现。一个变更若影响共享合同，先更新 spec、A 的接口记录及 B 的消费者，再实现；不私加字段。工作树以 cherry-pick 集成，提交按可独立审查的交付组织，中文说明，不使用全仓 `git add .`。

## 2. 交接批次与依赖

| 批次 | 甲交付 | 乙交付 | 下一批的硬门 |
| --- | --- | --- | --- |
| D0 | 确认本稿共享接口、文件归属、源码基线 | 确认模块字段策略、样板事实范围 | 双方使用同一 spec 修订；每个跨人接口有唯一生产者 |
| H1 | A1 帧/参与/建议合同与 Core 接纳规则 | B1 模块声明、B2 原型/情境 | H1 接口与 focused tests 通过后才写依赖生产代码 |
| H2 | A2 账本，A4 受控读取可独立推进 | B1/B2 行为测试、B4 现有 Owner 窄闭环 | 账本 replay 只证明锚点和已确认 actor 结果消费，不授权群体均值回填 |
| H3 | A3 交接 | B3 洪灾群体与玩家交集 | 唯一推进权、身份连续、旧执行者拒绝 |
| H4 | A5 公共接线、DOD 等价与总验收 | B4/B5 receipt 回流与可见样板 | C0–C7 对应证据齐全；Godot 单独标记 |
| HM0 | AM1 最小输入/报告/预算/权限合同 | BM1 固定场景与八维算例 | 纯计算先过；不依赖 A1–A4 全部实现 |
| HM1 | AM1 shadow 旁路和重验审计 | BM1 真实 Owner 窄读取、与既有 planner 同输入对照 | 不投递候选、不改 planner 选择、不调用 Owner/Core 写入 |
| HM2 | AM1 advisory 只读可见入口 | BM1 覆盖率、阻塞和复核/升级类别报告 | HM1 通过后打开；无自动执行/交接；active 可长期关闭 |

依赖不是简单的 A 完成后才做 B：B1/B2 的内容可在 D0 后与 A1 合同实现并行；B4 对既有供应操作的回归可提前；AM1/BM1 的 HM0→HM1→HM2 可以先做，不要求先建完角色帧、成员账本或通用密码本。最小来源授权/版本/内容/时间验证不可省略，A4 后续复用这些合同而不是另造版本。B3 的真实交接等 A2/A3。H4 明确拆为 A5 公共接线 → B5 完成真实回流/场景 → A5 总验收。

每次交接附：提交 ID、改动文件、接口修订、通过与失败命令、对应 AC、仍关闭的 gate。接收方先运行消费者测试再集成，不把对方口头“完成”作为运行证据。

## 3. A1：共享帧、参与解析和提交合同

**2026-10-10 后端进度：** `shared_contract_implemented_verified`。当前候选已包含严格共享合同、按需不可变帧、参与策略交集、提案校验和原Core接纳规则；帧、参与、提案及seed continuity用例均包含在最终7956 passed/2 skipped的全量回归中，源码身份为`sha256:093a3109ae88477b6e1d5915cf461eea8559b127904179f103086c974ca63dc2`。证据见 `D:/ParallsEvidence/paralls-plan-a-social-contract-20261010T041500Z`；本轮这四份测试重新运行95 passed，退出0，见 `D:/ParallsEvidence/paralls-native-flush-20261010T060422Z/a1-focused`。本条补齐原计划未记录的实际后端状态；未重新证明早期RED步骤，也不勾选B1/B2算法或A5生产消费者交付。

**对应：** C0/C1；AC-01、AC-02、AC-03。**依赖：** D0；乙提供 B1 字段策略和 B2 规则内容。

**Files**

- Create: `backend/app/population_continuity/simulation_contracts.py`、`simulation_frame.py`。
- Modify: `backend/app/population_continuity/activation_policy.py`、`backend/app/character_agent/models/simulation_seed.py`、`backend/app/character_agent/services/character_continuity.py`、`backend/app/character_agent/runtime/runtime_loop.py`。
- Test: `backend/tests/test_character_simulation_frame.py`、`test_character_participation_resolution.py`、`test_character_agent_seed_continuity.py`。

**Interfaces — Produces（当前共享接口，业务消费者仍未接线）：**

```python
def resolve_participation(
    *, policies: tuple[ParticipationPolicy, ...], tick: int,
) -> ParticipationResolution: ...

def build_simulation_frame(
    *, actor_ref: str, profile_ref: str, profile_revision: str,
    character_revision: int, tick_cursor: int,
    read_set: PopulationReadSet,
    module_states: Mapping[str, Mapping[str, object]],
    participation: ParticipationResolution,
    codebook_refs: tuple[str, ...], activation_lock_ref: str | None,
    module_definitions: tuple[ModuleDefinition, ...] = (),
) -> CharacterSimulationFrame: ...
```

`ParticipationPolicy` 是本任务新增严格输入：`policy_ref`、`revision`、`allowed_tiers`、`allowed_modules`、`forbidden_dimensions`、`upgrade_triggers`、`b0_expiry_tick`、`review_tick`。策略来源固定为原型、个体、情境和确认约束；首版仅交集/收紧，不实现任意策略插件。无合法层级时 resolution 的 recommended_tier 为空、status=defer；调用者 requeue。

`CharacterSimulationFrame`、`ParticipationResolution`、`ModuleProposal`、`SimulationCommitPacket`、`IntersectionPacket` 的字段使用 spec 第 6 节；本文件定义全部共享类型，乙仅 import。`ModuleDefinition` 同处声明，字段按 spec 6.3；字段策略限定为 aggregatable/distributable/individual_only/group_summary_only 的显式组合，不能从统计许可推导回填许可。

**Consumes：** 既有 PopulationReadSet 和 Character Core 读取；乙的 ModuleDefinition。Core 接纳复用 `CharacterAgentRuntime.apply_character_continuity_command(command: CharacterContinuityCommand) -> CharacterContinuityReceipt`，不复制第二个 service。

- [ ] 在新测试文件建立最小两来源策略数据，证明推荐层级属于交集、缺省保护、到期 B0 被去除；构造帧后修改原 module_states，帧 digest 和内容保持不变。

```python
def test_late_input_mutation_cannot_change_frame(frame_case):
    frame, original_states = frame_case.build()
    before = frame.frame_digest
    original_states["needs"]["fatigue"] = 1.0
    assert frame.module_states["needs"]["fatigue"] == 0.2
    assert frame.frame_digest == before
```

`frame_case` 在同文件定义，仅组装真实 PopulationReadSet 和上述 build 函数；`build()` 返回 `(CharacterSimulationFrame, 原始输入字典)`，不 mock 输出。

- [ ] 在 backend 运行 `python -m pytest tests/test_character_simulation_frame.py tests/test_character_participation_resolution.py -v`，先确认新行为失败；导入失败仅是初始红灯，接入后必须看到语义断言能捕获浅拷贝/策略放宽。
- [ ] 最小实现：严格模型、规范 digest、输入隔离、策略交集；Core 运行时依据当前 revision/锁拒绝 stale。schema 只判格式，不在 model validator 中查询世界或“证明版本新鲜”。

```python
allowed = set(policies[0].allowed_tiers)
for policy in policies[1:]:
    allowed.intersection_update(policy.allowed_tiers)
if any(tick >= p.b0_expiry_tick for p in policies):
    allowed.discard("B0")
```

- [ ] 运行以上新测试与 `tests/test_character_agent_seed_continuity.py`，覆盖额外字段、非有限数、跨 actor、旧 revision、重复键不同载荷；拒绝前后业务事件和角色 revision 不变。
- [ ] `git diff --check`，交付 H1；提交边界为“共享帧与参与约束接入角色连续性”，不包含乙的模块算法。

## 4. A2：B0 成员账本、分片与消费游标

**2026-10-10 后端进度：** `backend_implemented_verified`。32项新增账本/恢复测试、147项相关回归，以及新鲜 `phase3b-world-mode-continuity`、`population-data-oriented-persistence` profiles通过；全量7852 passed/2 skipped/19 warnings、退出0，两个历史spawn用例均passed，证据已封存。初始导入红灯后，分片语义1 failed/5 passed；严格revision与真实来源版本边界3 failed/21 passed；联合receipt与原始索引核验2 failed/30 passed，均已修复。证据 `D:/ParallsEvidence/paralls-plan-a-member-ledger-20261010T025000Z`；A5的生产装配、其他领域按actor适配和安全分摊未完成。

**V1 适配：** 原World Owner在既有GameplayEventStore登记 `population.world.member_ledger_recorded@1` 的封闭schema，入组写一次锚点，确认/消费仅写对应member流；可见性为authority_only。不在每窗热路径复制千人账本，热状态仍由原连续积分更新。来源首期仅原Organization `record_schedule` 的明确recipient确认事件：核验真实transaction/principal、事件digest与实际Owner提交revision vector，组织commerce总量及模型报告返回unknown/拒绝。成员游标是原确认事件的global sequence，与Core仿真tick分开。消费须原Core持久化receipt、原幂等键与匹配来源版本；联合receipt用其明确actor来源的实际提交版本上界，不读取最新head代替来源pin。账本full与原checkpoint+tail均从真实store重建，检查点只包含元数据及refs，没有私有事实正文。`get_character_continuity_receipt`为原Core新增只读入口，并核对原提交事件与原始receipt摘要，保持旧事件/命令语义。

**本批最终复核修复：** 只读评审确认两个Important：合法world/cohort/key的冒号分割会碰撞，撤销当前actor授权后仍能新增成员写入。11项真实Owner/Core回归先失败后通过，整批306项相关回归通过。尚未部署的A2新元数据采用显式`v1`地址，根流绑定完整(world, cohort)，成员子流绑定actor，幂等键绑定(world, cohort, key)；重放额外核对record scope。统一append接纳点复核当前roster/授权，历史duplicate仅恢复原回执、零新增事件。原Owner/Core地址、请求及@1事件schema不改变；旧实验存档与封存证据保留，不自动迁移或以新地址重解释旧存档。最终全量、review ruling与封存结果见 `D:/ParallsEvidence/paralls-plan-a-social-contract-20261010T041500Z/reports/report.md`，报告生成前不宣称该最终版本全量通过。

**对应：** C3；AC-04、AC-05。**依赖：** A1 与 B1 字段策略；B2 可提供样板身份。

**Files:** Create `backend/app/population_continuity/member_ledger.py`；Modify `backend/app/population_continuity/world.py`、`hot_state.py`；Test `backend/tests/test_population_member_ledger.py`、`test_population_member_ledger_replay.py`。

**Interfaces — Produces：** `PopulationMemberLedger`/`MemberEntry`（spec 7）、`partition_members(ledger: PopulationMemberLedger, *, seed: str, partition_revision: str) -> PopulationMemberLedger`、`pending_member_results(ledger: PopulationMemberLedger, *, actor_ref: str) -> tuple[str, ...]`。成员 entry 保存 actor_ref、entry_character_revision、policy pins、shard_ref、保护引用、last_consumed_result_cursor 与生命周期。

pending_member_results 只返回来源已明确关联该 actor 的真实确认结果；分片总量 receipt 或模型报告不满足这一条件。首期 distribution_policy=none。报告可作为临时读取/审计引用，但不能进入待物化个人增量或推动 group/individual 的业务消费游标。甲负责原 actor 确认结果的幂等消费，乙不提供“群体均值分摊器”。

- [x] 构造 3 人账本：普通成员、照护成员、individual_only 成员；打乱输入顺序、相同 seed 分片结果不变；保护字段不进入聚合输出。

```python
def test_replay_preserves_unconsumed_member_results(ledger_case):
    ledger_case.commit_actor_result("character:ordinary", "result:1")
    ledger_case.commit_actor_result("character:carer", "result:2")
    ledger_case.consume_for("character:ordinary", "result:1")
    full = ledger_case.restore_full()
    tail = ledger_case.restore_checkpoint_tail()
    assert full == tail
    assert pending_member_results(full, actor_ref="character:carer") == ("result:2",)
    assert pending_member_results(full, actor_ref="character:ordinary") == ()
```

`ledger_case` 在测试文件定义，封装真实 store/world 的 append、checkpoint 和恢复；commit_actor_result 走原已准入按 actor 连续性/Owner 链，consume_for 只有该 actor 的 Core receipt 成功后记录消费，两个 restore 返回重建账本，不得仅复制当前内存对象。另输入一份 BM1 覆盖率报告，断言全部 actor 状态、记忆和消费游标不变。

- [x] 运行 `python -m pytest tests/test_population_member_ledger.py tests/test_population_member_ledger_replay.py -v`，验证消费重复/崩溃点、顺序敏感和保护字段断言在未实现时失败。
- [x] 最小实现：复用既有持久化/回放链保存锚点与按 actor 结果消费凭据；新增事件载荷如不可由当前 schema 表达，先在原 Owner 下登记明确 schema、迁移和 replay，不用任意 payload 绕过注册。分片只读取许可字段；没有可按 actor 归因的来源返回 unknown/升级，不能按人数除出个人效果。

```python
ordered_members = sorted(ledger.member_entries, key=lambda item: item.actor_ref)
unconsumed = tuple(ref for ref in confirmed_refs if ref not in consumed_refs)
```

- [x] 运行新测试及 `tests/test_population_checkpoint_closure.py tests/test_population_persistence_regression.py`；在 Owner 已提交/Core 未接纳、Core 已接纳/消费标记未写两个断点重启，均不重复世界效果。
- [ ] `git diff --check`，交付 H2；提交边界为“成员账本与确认结果消费回放”。不把账本做成另一份个人库存或记忆库。

## 5. A3：唯一推进权与 B0–B3 交接

**2026-10-10 后端进度：** `backend_implemented_verified`。新增34项真实Core/authority/成员账本与独占启动恢复回归及186项相关测试，共220 passed；锁恢复、同actor有效锁保护、晚到无凭据B0拒绝、原lease超时/幂等、World成员流交接包和真实重启/ACK丢失/CAS已实现。原激活profile首次失败暴露常规lease扫描历史，已修复为折叠本人的实际提交；重新运行激活及持久化profiles通过，首次失败保留。交接额外核对Core实际绑定的world凭据，不能借用另一个world的锁；A2原事件schema摘要与封存版本一致。修复后全量7886 passed/2 skipped/19 warnings，退出0，激活/持久化profile在修复后源码重新passed/cleanup passed；31commands/31cleaned/0owned，seal=59ffb97129b66d0391e629bfd070a62edebff4edf6d8153d0eb752b45649f76f。证据 `D:/ParallsEvidence/paralls-plan-a-handoff-20261010T034200Z`。A5生产装配、B3/B5与Godot仍未由此完成。

**V1 适配：** 纯构包复核严格帧/账本、当前actor保护引用、入组revision/policy pins及允许目标精度；unresolved_proposals首期仅列该actor尚未接纳Core的真实确认来源refs，不表示已经执行业务或自动重试。last_confirmed_tick来自Core实际连续性提交，不使用世界global sequence。新 `population.world.member_handoff_recorded@1` 沿原成员流保存refs-only包，A2的原@1 schema不改义；World返回包及原append结果，拒绝包不授权接管。重复请求仅恢复原提交，读取历史包不证明旧锁当前有效。原authority按world补原流尾部恢复held_revision/pending，普通本地lease只折叠自己的提交；释放前超时不会启动第二推进者。新命令必须由A5实际装配完整锁凭据；历史无凭据命令的wire保持，锁有效期间禁止新写、已提交幂等重放保留。重新进入B0仍须新解析和新锚点，不把旧handoff成员改回active。

**对应：** C4；AC-06、AC-08。**依赖：** A1/A2；消费 H1 已冻结的触发/连续性输入合同。B3/B5 的真实消费者联调在 H3/H4 完成，A3 不等待 B5 整体验收。

**Files:** Create `backend/app/population_continuity/handoff.py`；Modify `backend/app/population_continuity/activation.py`、`activation_policy.py`、`backend/app/character_agent/runtime/runtime_loop.py`；Test `backend/tests/test_population_handoff_continuity.py`，保留 `test_character_agent_activation_handoff.py`。

**Interfaces:** `prepare_intersection(*, frame: CharacterSimulationFrame, ledger: PopulationMemberLedger, trigger_kind: str, target_fidelity: str, lock: ActivationLock) -> IntersectionPacket`。此函数纯构包；锁取得、释放、pending、Core 接纳均调用既有 authority/runtime。甲新增只读公共接口 `ProfileActivationAuthority.active_lock(*, world_ref: str, profile_ref: str) -> ActivationLock | None`，返回隔离后的凭据，避免消费者访问 `_locks`。甲在原 activation 合同中补足可在提交时验证的锁代次/凭据；乙不得另造锁管理器。

- [x] 测试覆盖旧 B0 执行者晚到、重复 handoff、释放前超时、重启后重入队；断言同一 actor identity digest 和未决义务保留。

```python
def test_old_b0_writer_cannot_commit_after_handoff(handoff_case):
    old = handoff_case.capture_b0_command()
    identity = handoff_case.identity_digest()
    handoff_case.to_tier("B3")
    before = handoff_case.business_event_count()
    receipt = handoff_case.submit(old)
    assert receipt.status == "rejected"
    assert handoff_case.business_event_count() == before
    assert handoff_case.identity_digest() == identity
```

`handoff_case` 在测试中使用真实 ProfileActivationAuthority、CharacterAgentRuntime、A2 账本；这些方法仅包装原公共调用，不能直接改 `_locks` 或伪造 receipt。

- [x] 运行 `python -m pytest tests/test_population_handoff_continuity.py tests/test_character_agent_activation_handoff.py -v`，确认新旧执行者竞争测试先红。原语义14 failed/7 passed；World缺API 5 failed/21 passed；入组revision边界1 failed/27 passed，原失败保留。
- [x] 最小实现顺序固定为：取得凭据 → 固化最后确认游标 → 接纳原按 actor 合法连续性 → 构包 → 接管；不从 cohort 压力均值还原个人状态。旧提交同时检查 character revision 和凭据。拒绝保持原正式结果，不将超时当自动成功。真实Owner/Core接纳顺序测试已通过；公共入口接线仍属A5。

```python
if command_lock_ref != current_lock.lock_ref or command_lock_revision != current_lock.held_revision:
    return self._continuity_refusal(command, revision, "handoff_lock_stale")
```

该拒绝沿原运行循环返回 CharacterContinuityReceipt，不新增并行拒绝模型；无 active_lock 同样按正式 stale/锁冲突拒绝。

- [x] 新测试及 `tests/test_population_activation_policy.py tests/test_character_agent_seed_continuity.py` 全过；证明交接中收到的新世界事件只进入下一帧。220项相关回归通过；真实强制终止/恢复与锁相关52项通过。首次全量2 failed/7879 passed，Character原请求被持久旧锁挡住而到期；仅在持有原RuntimeStorageLease的fresh启动后正式release，再恢复原admission/request，普通Authority重建继续保留锁。首次profile及全量失败均保留。
- [ ] `git diff --check`，交付 H3；提交边界为“交接凭据与旧推进提交隔离”。

## 6. A4：通用密码本与历史读取

**2026-10-10 本批状态：** `backend_implemented_verified`。按用户最新优先级，先推进仅依赖A1、可与A2独立交付的A4；不继续性能候选筛选。新增通用codebook模型及受控读取服务，36项A4测试和56项既有帧/参与/Core/激活回归共92项通过；本批完整后端7820 passed/2 skipped、退出0，独立只读评审无可复现Critical/Important，证据已封存。A2/A3/AM1/A5、真实公共业务接线和总验收未由此完成。

**V1 适配：** 新`CodebookReadPolicy`使用封闭字段`policy_ref/policy_revision/code_ref/reader_ref/reader_roles/purposes/scopes/level_fields/issued_at/expiry/historical/source_ref/source_type/source_revision/source_digest/summary_digest`。`CodebookReadService`由原Owner绑定policy/source读取函数，公开`read(request, *, entry)`不接受调用者授权或正文；纯`expand_codebook`仍只用于可信Owner上下文的过滤，不能作为客户端传参端点。`source_projection=None`明确表示缺来源，历史返回`replay_input_unavailable`，绝不回退最新内容。source revision使用非空字符串，digest为SHA256；L0只过滤安全摘要，L1/L2只过滤原Owner投影。`history_audit`须当前独立historical授权，不能复活普通运行授权。读取期间授权内容变化（即使revision未改）拒绝；摘要和返回基于同一独立内容快照。

**对应：** C6；AC-09、AC-13 的输入前置。**依赖：** A1 合同；消费乙的领域读侧来源。

**Files:** Create `backend/app/models/codebook.py`、`backend/app/services/codebook.py`；Test `backend/tests/test_codebook_authorized_expansion.py`、`test_codebook_historical_replay.py`。沿现有来源读取接口接入，不建立 population 专属私有内容库。

**Interfaces:** `CodebookEntry`、`CodebookReadReceipt` 使用 spec 6.1；新增 `CodebookReadRequest(reader_ref, code_ref, requested_level, purpose, scope, expected_revision, expected_digest, at_tick)`。`expand_codebook(request: CodebookReadRequest, *, entry: CodebookEntry, source_projection: Mapping[str, object], current_policy: Mapping[str, object]) -> tuple[Mapping[str, object], CodebookReadReceipt]` 只做封闭 policy schema 的过滤/验证；来源装配由原 Owner 完成，调用者不能自签 current_policy。

- [x] 表驱动测试 reader/purpose/scope/expiry/revision/digest 任一不匹配不得返回隐藏字段；拒绝也有脱敏读取回执。

```python
def test_expired_normal_grant_does_not_block_authorized_history(codebook_case):
    denied = codebook_case.read_current(at_tick=101)
    audit = codebook_case.read_history(at_tick=101, audit_grant=True)
    assert denied.receipt.status == "expired"
    assert denied.content == {}
    assert audit.receipt.source_revision == codebook_case.original_revision
    assert audit.content_digest == codebook_case.original_digest
```

`codebook_case` 创建 expiry=100 的原读取授权、仍保留的历史版本及独立有效审计授权；两个 read 方法调用本任务展开函数并以命名结果暴露 receipt/content/content_digest。另删去历史输入验证 replay_input_unavailable，不以最新内容代替。

- [x] 运行 `python -m pytest tests/test_codebook_authorized_expansion.py tests/test_codebook_historical_replay.py -v`，确认越权泄露、历史回退断言先失败。初始导入红灯后，语义红灯12 failed/15 passed；读取边界红灯3 failed/32 passed，最终交付边界红灯1 failed后修复。
- [x] 最小实现按 L0/L1/L2 声明选择字段；内容留在原 store，entry/receipt 只存 refs/digests（entry仅另含声明的safe_summary）。历史审计单独验证当前审计权限。

```python
visible = {name: source_projection[name] for name in granted_fields if name in source_projection}
```

- [x] 所有拒绝 case 断言 content 为空、无角色/业务写入；缺历史与无权限状态可区分。运行新测试，`git diff --check`。A4本批全量7820 passed/2 skipped，退出0；独立只读评审无可复现Critical/Important，证据 `D:/ParallsEvidence/paralls-plan-a-codebook-20261010T022752Z` 已封存。未完成A5生产装配。
- [ ] 提交边界为“通用受控展开与历史输入审计”，交付给 B4/BM1/AM1。

## 7. A5：公共接线、语义 oracle 与基线验收台账

**2026-10-10 接线进度：** 用户已明确授权“计划A及必需的最小依赖完整落地”。B1八模块、B2受信洪灾内容、B3–B5公共纵切和BM1固定八维算法已有实现及语义回归。`FloodPopulationFixture`实际装配原World、持久Gameplay/Core、Siming.tick、班表Owner和schedule_gated_supply capability；组织承诺不冒充粮食入库，仅另一份明确actor归因的班表事件进入成员消费。个人角色凭原held锁提交，B0只推进当前参与策略准入的成员；独立固定窗标量算例、零预算/恢复、Owner已确认/Core拒绝重投、交接及重新入组分别测试。新的opt-in `character-population-integrated-loop`核对这些真实后端证据，完整验证结果以 `D:/ParallsEvidence/paralls-plan-a-integrated-20261010T072557Z/reports/report.md` 为准。Godot/all继续暂停，C3安全分摊deferred，C整体与生产P门槛不因本轮后端实现打开。

**恢复/重新入组适配：** 原默认全人口V1不变；仅显式装配使用V2，保存各角色真实游标、上一确认窗B0成员及参与配置digest，每窗保存完整恢复投影。窗口回执绑定稳定推进合同，当前入组pins另绑恢复状态。B0→B3后旧账本保留handoff；回B0需当前策略允许、真实Core锚点/游标、自身状态同步、无未消费结果、原锁已释放及新的成员Owner根记录。原publisher在同一确认窗刷新恢复投影，不推进时钟，不从群体均值回填。成员根/全部actor流和activation流进入原准入事务读集；源改变在执行Owner前拒绝。

**最终评审适配：** 首次晚到的旧窗不得倒退Core仿真游标；已提交命令仍先走原幂等回放。延迟回组从该角色自身Core确认needs同步热行，客观phase/due沿原内核，不重复推进个人needs。同一World Owner新增显式`population.world.member_reentry_recorded@1`，只重锚返回者，原init/member/handoff事件schema不改义；其他成员及已消费/未消费结果按固定来源向量继承。原锁释放、成员根提交或恢复checkpoint失败后可重启重试，checkpoint失败回滚热表和参与配置。旧离线V1 verifier显式提供无参与配置，保持历史验收合同。

V2恢复态另保存`cohort_ref`：持久回组成功但进程尚未收到ACK时，publisher只沿真实World reentry来源链选择成员根，并以当前受信参与策略重验digest；checkpoint不签发新权限。默认V1不加入此字段。该场景RED→GREEN及原恢复回归见本轮报告。

**对应：** C5/C7；AC-01–AC-09、AC-18–AC-20。**依赖：** 公共接线依赖 A1–A4、B1–B4 与 B5 已冻结的转换接口；公共接线交付后乙完成 B5，最终总验收再等待 B5 的真实结果。

**Files:** Modify `backend/app/main.py`、`backend/app/services/siming_runtime.py`、`siming_population_capability.py`、`backend/app/world_runtime/population_driver.py`、`backend/app/population_continuity/batch.py`、`continuous.py`、`hot_state.py`；Create `backend/tests/test_character_population_integrated_loop.py`、`scripts/verification/verify_character_population_integrated_loop.py`、`.harness/profiles/character-population-integrated-loop.json`；相关现有测试/profile 按实际影响更新。

**Interfaces:** 消费乙的 `evaluate_modules`、`FloodPopulationFixture`、原 `CharacterSeedPlanner.derive` 和真实 `PopulationOwnerReceipt`；公共入口仍为 `SimingRuntime.tick(inputs: list[SimingInput]) -> SimingTickResult`，世界时间仍由已有 driver/clock 管理。输出 report 使用 `overall_passed` 和明确的 backend/godot 状态，不将新模式默认套到所有旧场景。

- [ ] 新集成测试从真实已准入 cadence/投影进入公共入口，验证不经 fixture 私有 shortcut；同样本的标量 oracle 和热状态执行比较候选、Owner receipts、Core 状态、游标与 replay digest。

```python
def test_scalar_and_batch_preserve_same_authority_results(integrated_case):
    scalar = integrated_case.run(execution="scalar")
    batch = integrated_case.run(execution="batch")
    assert scalar.owner_receipts == batch.owner_receipts
    assert scalar.character_states == batch.character_states
    assert scalar.replay_digest == batch.replay_digest
```

`integrated_case.run` 在同一初始快照、固定规则/seed 上分别创建新 runtime，并收集真实提交结果；标量模式使用 B 模块纯规则，batch 消费同一规则，不能用同一实现运行两次冒充 oracle。

- [ ] `python -m pytest tests/test_character_population_integrated_loop.py -v` 先验证尚未接线或保护字段损坏会失败。
- [ ] 最小接线到现有 cadence、capability、Core 端口；先跑通标量语义，随后仅扩展已有列式热状态，避免为 DOD 创建第二模型。失败保持 requeue/receipt，不吞错误继续报完成。

```python
if owner_receipt.committed:
    continuity_receipt = continuity_port.apply_command(command)
    # 只有接纳成功后才确认角色消费游标；重试复用同一 command 身份。
```

- [ ] 在 backend 运行 `python -m pytest -v`；仓库根通过 runner 运行新增 `character-population-integrated-loop` 及下表 profile。规模测试单独顺序运行，记录 100/1000/10000、1×/10×、窗口数、p95、最大推进延迟和积压；不把旧报告当新证据。生产阈值沿既有 P 计划。

| 验收范围 | 显式 profile |
| --- | --- |
| 原链路与 Owner | phase3-population-continuity、siming-led-population-seed-continuity、siming-population-domain-owner-adaptation |
| 连续推进与 DOD | population-continuous-runtime、population-hot-state-equivalence、population-data-oriented-persistence、population-data-oriented-incremental-read |
| 规模 | population-runtime-scale |
| 全仓与主线 | all、mainline-unified-runtime |

命令格式为 `python scripts/verification/harness.py --profile <上表单个实际名称>`；尖括号用于说明选项，不是要求执行的占位命令。典型完整调用：

```powershell
python scripts/verification/harness.py --profile character-population-integrated-loop
python scripts/verification/harness.py --profile population-hot-state-equivalence
python scripts/verification/harness.py --profile population-runtime-scale
python scripts/verification/harness.py --profile all
```

- [ ] 乙交付 B5 Godot 证据后由甲核对同一后端修订、边界消息与可见结果；缺失时 C backend 可分别记录通过，整体 C 保留 godot_unverified，E gate 不打开。C3 原基线要求的安全分摊若尚无独立任务/证据，则标为 deferred，不将本轮“只读汇总+按 actor 回放”替代它，C0–C7 整体门禁仍不通过。
- [ ] 检查本轮 Harness 退出码、证据输入版本及清理结果；`git diff --check`，提交边界为“共享推进与洪灾纵切集成验收”。不在本提交混入既有六项生产工程重构。

## 8. AM1：日供给计算的最小冻结、模式和审计合同

**2026-10-10 共享契约进度：** `shared_contract_implemented_focused_verified`。固定模板/草案、grant、FactCard/Proof、冻结向量/输入、只读报告、计算状态和脱敏receipt已实现；新增59项AM1测试，加上整批复核修复的11项成员边界回归，共306项相关回归通过。纯校验拒绝自修改模型、额外IR/事实、期限/预算/窗口越界和内容篡改；没有生产授权签发、BM1算法、Owner输入适配或Siming模式接线。新增opt-in `social-model-compiler-contract`只核对共享契约，报告明确HM0总门未完成、shadow/advisory未集成、active关闭。全量、评审处理及封存结果以本批 `D:/ParallsEvidence/paralls-plan-a-social-contract-20261010T041500Z/reports/report.md` 为准。

**当前AM1/BM1适配：** 固定计算器已实现[48,62]/[3428,5167]语义、八维有界预算、未知来源无完整报告、已知阻塞零可达及整数舍入。受信服务不接受客户端grant/事实；off不读取，shadow仅审计，advisory在取用前重验当前授权、全部source pins、冻结内容/查询/名单/观察时间，仅暴露无个人分配的只读报告。可选旁路接原Siming cadence，不增加Owner/Core/交接操作，默认关闭；审计复用SimingAuditWriter。数量/预算/窗口与原合同一致。完整真实来源尚缺路线、供应流程、承诺优先级、完整分片名单的窄读取及生产ModelRunGrant签发；实际来源不可得返回context_insufficient/source_contract_missing。纯计算和模式边界通过不能替代HM1真实对照/HM2真实advisory完成，active保持blocked；不顺手新增事实Owner或分配协议。

**对应：** M shadow/advisory；AC-10、AC-11 输入部分、AC-13、AC-21/22。**依赖：** D0 后与 BM1 冻结最小接口；直接复用现有社会/领域读侧，不等待 A1–A4 全部实现。消费者保持一份合同，A4 完成后复用相同读取结果与权限语义。

**Files:** Create `backend/app/models/social_model.py`、`backend/app/services/social_model_execution.py`；Modify `backend/app/services/siming_population_capability.py`（先只读旁路），`siming_runtime.py` 仅有 grant 接线缺口时修改；Test `backend/tests/test_social_model_execution_contract.py`、`test_social_model_replay.py`、`test_daily_supply_shadow_comparison.py`；Create `scripts/verification/verify_social_model_compiler_contract.py`、`.harness/profiles/social-model-compiler-contract.json`。不修改 graph projector 或建立实体关系图服务。

**合同范围：** spec 10.2 的名称是逻辑职责，不要求九个全功能框架。甲在单个 social_model.py 中用严格模型/既有类型组合表达这一固定调用，字段如下；BM1 仅 import。SocialModelDraft 的 V1 参数只允许 shard_ref、window、template_ref 和 correlation，禁止请求体携带任意 IR、事实数值或 callable。

| 新类型 | 固定字段/限制 |
| --- | --- |
| SocialModelTemplate | template_ref=`daily-shard-supply@1`、definition/operator pins、固定八维目录、max_analysis_window、输入/输出声明；不支持自由模板图 |
| ModelRunGrant | reader_ref、purpose、scope、mode、template/policy pins、issued_tick、expiry_tick、预算与单日窗口；由既有治理入口签发 |
| InputVersionVector | 相关来源与查询/分片版本、projection/content digests、policy/template/operator pins、observed_at、from_tick/to_tick、expiry_tick、input_digest |
| FrozenModelInput | 获权 cards、vector、固定分片/单资源/单路线输入；以现有 FrozenSocialPlanningInput、HouseholdScheduleInput、OrganizationScheduleInput 作来源，不复制社会事实库 |
| DailySupplyReport | shard_ref、from_tick/to_tick、demand_units、confirmed_supply_units、reachable_supply_units、coverage_bps、blocking_reasons、upgrade_categories、input_digest/source revisions、expiry_tick；没有 actor allocations |
| ModelComputation | status、report（DailySupplyReport 或空）、work_units、diagnostics；正式失败不返回伪完整报告 |
| ModelRunReceipt | 输入/输出摘要、mode、grant、读取 refs、预算/降级、source validation、correlation；沿现有获权审计路径保存 |

数量区间用有界整数二元组；coverage_bps 范围 0–10000，已确认零需求时为空并在原因中标 not_required。FactCard/Proof 只包装原来源、授权和过滤后内容；CandidateEnvelope/ModelProjection 的只读内容引用同一 report，不建立第二报告 schema。报告不写世界或成员账本。

```python
def validate_model_run(
    *, template: SocialModelTemplate, grant: ModelRunGrant,
    inputs: FrozenModelInput, tick: int,
) -> None: ...
```

### AM1.1 / HM0：最小纯计算准入

- [x] 新测试拒绝未知模板、额外字段、动态代码、超窗/预算、错误 reader/scope、错 digest；构造后修改原嵌套字典不改变输入/报告。固定来源版本、观察时刻、规则和输入顺序得到同一摘要。仅共享契约证据，不是HM0数值算法通过。
- [x] 运行 `python -m pytest tests/test_social_model_execution_contract.py tests/test_social_model_replay.py -v`，导入红灯后实现最小校验；status 使用 spec 10.4 集合，缺必需上下文与无权分别拒绝context_insufficient/policy_denied，失败计算无完整报告。新增verifier测试拒绝空/缺失/跳过/旧JUnit，不将contract profile通过当BM1完成。

```python
if inputs.vector.to_tick - inputs.vector.from_tick > template.max_analysis_window:
    raise ValueError("policy_denied")
if tick >= min(grant.expiry_tick, inputs.vector.expiry_tick):
    raise ValueError("stale_input")
```

- [ ] 与乙对齐 BM1 的精确数值算例和固定求值顺序。先无缓存，不实现模板编排、通用 IR 解释器、片段失效或后台重算队列。交付 HM0 后双方可独立写语义/模式测试。

### AM1.2 / HM1：真实冻结输入与 shadow 对照

- [ ] 在同一 Owner 读边界取得乙的窄读集，完成来源/内容/recipient/时间/名单 pins 校验；off 不读取。保持现有 planner 输入与输出不变，shadow 只追加脱敏审计；对照不另跑一遍写入流程。

```python
def test_shadow_observes_same_input_without_changing_planner(shadow_case):
    frozen = shadow_case.freeze_once()
    baseline = shadow_case.plan(frozen, mode="off")
    observed = shadow_case.plan(frozen, mode="shadow")
    assert observed.planner_selected_refs == baseline.planner_selected_refs
    assert observed.planner_input_digest == baseline.planner_input_digest
    assert observed.model_receipt.input_digest == frozen.vector.input_digest
    assert observed.owner_submit_calls == baseline.owner_submit_calls == 0
    assert observed.core_apply_calls == 0
```

`shadow_case` 用 BM1 真实输入适配与现有 PopulationPlanner 的只读选择方法，关闭模式间用同一不可变输入、同一初始快照；记录差异但不强迫计算器报告等于 planner 的语义。两者可对不同问题给不同建议；禁止用改 planner 规则“对齐”结果。

- [ ] 执行 `python -m pytest tests/test_daily_supply_shadow_comparison.py tests/test_social_model_execution_contract.py tests/test_social_model_replay.py -v`。覆盖正常供给、路线受限、期限不足、保护义务、缺权限/必要卡；拒绝和降级必须可审计。
- [ ] 对每一项声明依赖分别通过合法 Owner 改 revision，再次取用旧报告必须返回 stale_input；同样测试授权撤销、分片名单版本和时间到期。仅审计历史读取可保持旧报告，其标记不能成为 current。未来 active 仍须在 append 点再验；没有变化通知不影响正确性。
- [ ] 测试图谱缺失且 Owner 输入齐全可继续、receipt 标 graph_degraded；必需来源不可得时不产完整覆盖率；不会自动补建关系图。验证被冻结内容的 digest 不匹配、浅层可变、观察时刻变化不能沿用原报告。
- [ ] 历史原输入保留/可重建时重算同一报告；缺失返回 context_insufficient 并记录 replay_input_unavailable 原因。观测到的知识置信度依赖 observed_at，不能只以 stream revision 当缓存键。HM1 取证前不得打开 advisory。

### AM1.3 / HM2：advisory 只读入口

- [ ] 消费者只在当前获权 scope 内看到 report、阻塞和复核/升级类别；不进入自动调度、handoff 或 capability submit 分支。

```python
def test_advisory_report_cannot_change_any_authority(advisory_case):
    before = advisory_case.authority_snapshot()
    result = advisory_case.run(mode="advisory")
    assert result.receipt.status == "ok"
    assert result.report.coverage_bps == (3428, 5167)
    assert advisory_case.authority_snapshot() == before
    assert advisory_case.owner_submit_calls == 0
    assert advisory_case.core_apply_calls == 0
    assert advisory_case.handoff_calls == 0
```

该 fixture 使用 BM1 实际固定输入和真实 store/Core 状态；只包装写入口计数，不以 mock Owner 证明 active 成功。snapshot 包含角色/成员游标与记忆，审计记录另计。

- [ ] 验证取用前重验和脱敏，再执行上述三个测试文件与 `python scripts/verification/harness.py --profile social-model-compiler-contract`。profile 分列 HM0/HM1/HM2，不将纯计算通过写成真实 Owner 输入或 active 通过。
- [ ] `git diff --check`。提交按“最小冻结合同”“shadow 对照”“advisory 可见”独立审查结果组织；精确缓存仅在重复计算需求成立后追加，不能阻塞首个结果或绕过重验。

## 9. 覆盖、后继与共同完成条件

| Spec 验收 | 甲责任 | 乙责任/依赖 |
| --- | --- | --- |
| AC-01–03 | A1/A5 | B1/B2 真实消费者 |
| AC-04–06 | A2/A3/A5 | B3 洪灾与交集 |
| AC-07–08 | A3/A5 Core 接纳与恢复 | B4/B5 真实 Owner 和 receipt 转换 |
| AC-09 | A4 | B4/BM1 最小领域读侧 |
| AC-10–13、AC-21/22 | AM1 的 HM0/HM1/HM2 | BM1；AC-12 的真实 aggregate 提交及 AC-11 提交部分等 G-M |
| AC-14–17 | G-E/G-F 满足后，甲负责共享版本和影响调度 | 乙负责领域证据与场景；当前不生成可执行代码任务 |
| AC-18–20 | A5 汇总，与既有 P 计划分别列证据 | B5 Godot 和领域样板 |

**G-M：** 乙出具 spec 8.2 的已有真实 aggregate 操作准入表，甲核验冻结读集能够到提交点；缺合法能力保持 proposal_only/capability_unavailable，可以长期以 advisory 交付。不为打开 active 顺手新增通用供给/分配协议。出现另行批准的业务操作后，才在本 A/B 两份计划补充 active 任务。

**G-E：** 原 C0–C7、replay、privacy、zero-write、handoff 和 Godot 确认投影证据全部满足后，甲补依赖索引/有界反应接线，乙补低/中影响交互和高影响环境变化任务。本轮推迟安全分摊后，不能将收窄的 A2 验收当原 C3 全完成；缺失项继续关闭门禁。现在只记录责任，不提前设计新的 writer。

**G-F：** E 的真实回流成立、领域冲突窗口和可见性合同确定后，甲补共享隔离/恢复，乙补双阵营四主体场景。门禁解除后仍在这两份计划追加任务，保持一份共享合同。

共同退出报告分别标 C、M-shadow/advisory、M-active、E、F、P。计划 A 不是独立业务上线声明；必须与 B 的结果共同证明第一条连续性闭环。代码完成、后端通过、Godot 通过和生产门槛分别记录，不能互相替代。
