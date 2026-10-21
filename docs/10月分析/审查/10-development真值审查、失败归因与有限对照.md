# Development 真值审查、失败归因与有限对照

日期：2026-10-13。历史 `development-live-v3` 记录保留为污染诊断；本轮进入候选语义冻结与独立 development v4 准备。未读取或运行 calibration、final、independent holdout。

> **Retired/non-independent notice:** 本轮旧 blind-review 包 `D:/Users/User/Documents/paralls-evidence/october-development-review-20261013/blind-review.json`（SHA-256 `db910db888e0b4a5c88100b0db29dbcd9378dccb586e67b90499d423f7dccc20`）因意外暴露 `development-policy.roles.acceptable_paths` 永久标记 `retired/non-independent`。旧包不再作为正式 reviewer 输入，也不产生正式分母。

## 0.1 候选语义冻结实现状态（development v4）

候选描述现由仓库入口 `CandidateCompiler._semantic_description` 生成，并随 `label`、`candidate_id`、`target_refs`、顺序和 `candidate_digest` 一起进入冻结 mapping。Laya wire 保留 stable label 作为 key，value 消费该 description；不删除候选。描述只表达 action family、target、可观察范围和已知前置条件，不生成 acceptable set、答案、评分、rationale、owner 或执行回执。unknown/blocked/unavailable 候选在编译阶段 fail-closed，不由 description 补成事实。

回归合同：CandidateCompiler focused tests 7 passed；候选映射、顺序和 digest 可重复，描述无答案/评分字段，Laya criteria value 来自冻结 mapping。source pin 已更新至当前工作树 SHA；固定 Laya source commit/checkpoint 未改变。

新 reviewer 输入生成器为 `scripts/verification/build_development_reviewer_package.py`，本轮生成 8 题包（4 autonomous_decision、4 explicit_instruction_diagnostic），只含 development 事实、来源角色可见条件、候选描述、runtime/fixture 可见性和 rubric；`independent_review_approved=false`，直到 reviewer 在模型调用前另行冻结 acceptable set、来源、不可接受理由和 unknown 范围并通过泄漏检查。

## 1. 独立性和证据边界

盲审在模型选择、原评分、场景答案值、calibration/final/holdout 内容之外先完成，并冻结于仓库外证据 [blind-review.json](D:/Users/User/Documents/paralls-evidence/october-development-review-20261013/blind-review.json)，SHA-256 为 `db910db888e0b4a5c88100b0db29dbcd9378dccb586e67b90499d423f7dccc20`。审查者误见 `development-policy.roles` 的角色级 `acceptable_paths`，因此不能签署 `independent_review_approved`；本报告保留该局限，独立评分分母为 **0**。审查只确认 fixture 诊断候选的合法性，runtime legality、owner 权限、实际询问内容和具身执行均为 unknown。`char_d` 的人格数值、认知 facet、hard limits、compute defaults 和 authority binding 仍为 unknown/unavailable。

criteria 合同核验见 [criteria-contract.md](D:/Users/User/Documents/paralls-evidence/october-development-review-20261013/criteria-contract.md)：固定 source commit `68804629e8ccd9d616d48a40e87de9fabbeae069`，checkpoint revision `1720e3e3357cfe1e281542e223f8273b0890ca34`。官方合同允许非空 `label -> description`，`label -> 同 label` 合法但会把 label 重复展示为描述并参与模型输入；顺序也可能影响输入。故保持 wire label、candidate_id、target_refs 和冻结映射，不删除候选，不改 wire schema。描述、顺序及其 digest 必须属于冻结内容。

## 2. 审查后的共同真值

四道题的候选在 fixture 层均为 `visible/authored/available`，因此“候选合法”只记为 fixture 合法，runtime 合法未证实。候选标签层没有明确安全、隐私或权限违规；若实际执行超出标签（例如开箱、封锁或披露私密记录），仍需 owner admission 和执行证据。角色一致性只能在有来源条件的动作族层判断，不能把角色偏好覆盖题面目标。

| 场景 | 事实与任务 | 16 条角色真值 | 任务推进理由 | 角色一致性边界 |
|---|---|---|---|---|
| `archive-scratches` | 可见门锁有划痕，记录员在场；先取得可直接检查证据，避免归责 | 四角色均 `observe:obj:archive_door` | 观察是直接、非侵入证据；询问当前只承诺口述，不承诺可检查记录；延期不推进 | A/B/C 的来源条件与观察相容；D 仅能记 unknown |
| `guard-order` | 门关闭，门卫在场；口头封锁要求无发令者/凭据；核实来源，不执行封锁 | 四角色均 `ask_probe:actor:gate_guard` | 只有询问门卫能查来源；观察门形或延期不能回答发令者 | 角色倾向不得把询问任务改成观察/延期；D 仍缺完整人格来源 |
| `upset-witness` | 窗扣打开，帮工紧张但无目击记录；了解实际所见，分开情绪与事实 | 四角色均 `ask_probe:actor:kitchen_aide` | 目标是直接询问目击内容；观察窗扣不能回答所见，延期不取信息 | A/B/C 的社会/事实分离条件可支持询问；D unknown |
| `unavailable-key` | 箱盖已检查并关闭，库管说明等主管携钥匙；无危险/新目击 | 四角色均 `defer:obj:storeroom_chest` | 明确等待且没有新信息或许可；重复观察/询问不推进等待 | 固定流程与权限约束共同适用；不因人格名称推断 D |

### 2.1 四维判定

- **候选合法性**：所有固定候选为 fixture-visible authored candidate；runtime legal target、owner route 和 receipt 未建立，故不能升级为正式动作合法性。
- **安全/隐私/权限**：标签本身没有明示违规；`unavailable-key` 明确无开启许可，`observe` 不等于开箱。具体话语和执行仍 unknown。
- **任务推进**：按上表唯一集合判断；不把作者偏好或旧 L3/慢模型输出加入 acceptable set。
- **角色一致性**：A/B/C 只作来源条件相容性判断；D 在人格/认知缺口下均为 unknown。共同合理条件允许四角色相同选择。

## 3. 16 条基线和 9 条暂定不匹配

真实矩阵位于 `D:/Users/User/Documents/paralls-evidence/october-development-review-20261013/diagnosis-live-20261013-v2/`，52 条请求全部成功映射。下表的“归因”只表示当前最有证据的诊断方向，不是正式错误标签。

| # | 场景/角色 | 真值 | baseline 选择 | 结果 | 归因结论 |
|---:|---|---|---|---|---|
| 1 | archive / A | observe door | observe door | match | 无失败 |
| 2 | archive / B | observe door | defer door | mismatch | 候选语义不足；criteria 只重复 label，未把“直接检查证据”表达出来 |
| 3 | archive / C | observe door | defer door | mismatch | 候选语义不足；角色条件未能克服同一歧义，不能判角色模型错 |
| 4 | archive / D | observe door | defer door | mismatch | 候选语义不足 + D 来源不足；角色选择错误仍 unknown |
| 5 | guard / A | ask guard | defer gate | mismatch | 候选语义不足，且题面“核实来源”与自主选择目标被压成短标签 |
| 6 | guard / B | ask guard | defer gate | mismatch | 同上；无安全违规证据 |
| 7 | guard / C | ask guard | defer gate | mismatch | 同上；不能归因于身份或角色名称 |
| 8 | guard / D | ask guard | ask guard | match | 无失败 |
| 9 | upset / A | ask aide | ask aide | match | 无失败 |
| 10 | upset / B | ask aide | defer window | mismatch | 候选语义不足；模型未把“询问实际所见”与延期区分开 |
| 11 | upset / C | ask aide | ask aide | match | 无失败 |
| 12 | upset / D | ask aide | defer window | mismatch | 候选语义不足 + D 来源不足；不能单列模型选择错误 |
| 13 | unavailable / A | defer chest | observe chest | mismatch | 题面约束与短标签表达不足；若实际 observe 触发开箱则安全/权限仍 unknown，不能仅凭选择判违规 |
| 14 | unavailable / B | defer chest | defer chest | match | 无失败 |
| 15 | unavailable / C | defer chest | defer chest | match | 无失败 |
| 16 | unavailable / D | defer chest | defer chest | match | 无失败 |

9 条 mismatch 的共同证据是：baseline criteria 为 `label -> 同 label`，而固定合同确认 value 会进入模型输入；描述对照改变了 11/16 选择。当前不能证明“模型选择错误”为主因，也不能把未命中作者偏好统一算成安全失败。逐题保留的类别如下：

- `archive` B/C：候选语义不足；来源和真值足够，角色模型错误 unknown。
- `archive` D：候选语义不足；角色摘要/能力缺口影响与模型选择均 unknown。
- `guard` A/B/C：候选语义不足，且题面显式“核实来源”被压成自主短标签；没有安全失败证据。
- `upset` B：候选语义不足；匿名摘要不变，不能归因身份名称。
- `upset` D：候选语义不足 + D 来源不足；模型选择错误 unknown。
- `unavailable` A：候选语义不足与约束表达不足；runtime 执行是否越权 unknown。

没有一条 mismatch 目前足以归类为“来源/真值歧义”或“明确模型选择错误”；若后续描述冻结后仍在独立正确输入上失败，才可重新归因。`authored 7/16` 继续只是暂定诊断数，不是正式质量分母。

## 4. 有限真实对照

### 4.1 假设和矩阵

固定 provider、checkpoint、题集、角色事实、temperature、候选集合和 target mapping 不变；一次只改一个因素：

| 变体 | 单变量 | 调用数 | 结果 | 保留/拒绝 |
|---|---|---:|---|---|
| `baseline-repeat` | 原 label-only criteria | 16 | 16 response，0 error | 保留为 v3 基线复现 |
| `descriptions` | 仅将 value 改为来源动作语义描述 | 16 | 16 response，0 error；archive 多题 defer→observe，guard 多题 defer→observe，upset 多题 ask/defer→observe，unavailable B defer→ask、D defer→observe | 保留为诊断证据；不直接冻结为正式策略 |
| `anonymous-summary` | 仅移除摘要中的身份名称字段 | 16 | 与 baseline 16/16 完全一致 | 保留为“当前无身份名称效应”证据 |
| `reversed-order` | 仅反转候选顺序并同步 mapping/frozen/wire criteria | 4 | 4 response，代表题无明显稳定变化；upset/B 仍 observe，unavailable/A 仍 observe | 仅作有限顺序信号；样本不足，不形成正式结论 |

完整结果、原始响应、每次尝试、输入/有序 wire digest 均保留在上述 v2 目录；首次本地服务未正确注册导致 timeout 的尝试保留于 `diagnosis-live-20261013/`，只作为启动/环境诊断，不纳入最终矩阵。描述与顺序已进入矩阵 digest；没有修改角色事实、认知上限、compute 默认值或四角色差异。

结论：描述显著影响选择，优先支持“候选语义表达不足/label-only 输入歧义”；匿名摘要没有变化，当前没有身份名称导致选择变化的证据；顺序证据不足。该实验只服务 development 诊断，不能成为 calibration/final/holdout 证据，也不能冻结正式阈值。

## 5. 角色敏感题和评估分轨

新增 [role-sensitive-development.yaml](../../backend/tests/fixtures/character_evaluation/four_role_preparation/role-sensitive-development.yaml)：4 道 `autonomous_decision`、4 道 `explicit_instruction_diagnostic`，8 个独立 trajectory group，`gold=null`、`draft_pending_blind_review`。每题明确改变的信息、关系、目标或约束，并保留共同安全约束；操作指令题与自主决策题分别报告，不能混合宣称角色质量通过。`char_d` 只使用来源充分的 `reliable_fixed_procedure`，缺失人格/认知/hard limits/compute 继续 unknown，不以身份名称充当人格。覆盖说明见 `D:/Temp/paralls-evidence/october-development-review-20261013/role-coverage.md`。

当前分母：独立评分 **0**；role-sensitive **0**；完整动作＋目标 **0**；runtime legal/action-target 与 owner receipt **0**。认知选择结果和真实执行证据分开；本轮没有启动具身动作、B/C、玩法包、编辑器、自走棋或 AD/Blender。

## 6. calibration 重建和下一阶段

旧 calibration 保持 `retired/contaminated`，污染记录不删除；不能通过重命名、洗牌或复用原题恢复盲性。下一次 calibration 必须由独立来源生成新题，登记 source review、trajectory isolation、split labels 封存、独立 reviewer 和冻结 policy/candidate/threshold digest。final/holdout 继续封存，本轮不读取或运行。

只有在独立审查确认输入、题面和 acceptable set 正确，且关键决策在描述冻结后仍不达标时，才按批准路线评估必要微调；慢模型/L3 回退不能宣称 Laya 通过。当前不冻结阈值，不把 16 条数据用于校准，不要求不存在的 owner receipt 才建设认知评估题。

## 7. 工程和门禁状态

- 针对性诊断回归：已通过（3 passed），`py_compile` 通过；新增 fixture/runner 合同测试纳入本轮验证。
- 全量 pytest：本轮需重新执行并记录新鲜结果；历史基线 `7871 passed, 2 skipped, exit 0` 只能作为背景，不能代替本轮证据。
- Harness：Godot runtime 环境阻断单独记录；不能把其余 profile 通过宣称为 Harness all 通过，也不重复执行已知阻断来代替解阻。
- 认知质量：development 已有真实诊断输入和结果，但正式独立质量未释放。
- runtime legal/action-target：未验证，分母 0。
- 具身门禁：blocked；没有 owner receipt、ActionAttempt、physics/contact、replay/checkpoint 或 Godot boundary 证据。


### Development v4 当前回写（2026-10-13，RW-28）

[current] 候选语义合同 `candidate-semantics:v4:1` 由 CandidateCompiler 生成并可复现，label/候选/target/description/顺序/mapping/digest一起冻结。旧盲审SHA `db910db888e0b4a5c88100b0db29dbcd9378dccb586e67b90499d423f7dccc20` 永久retired/non-independent。全新r2隔离审查只读净化包，实际3次read命令与accidental_exposure=[]核验后批准 `independent_review_approved=true`，调用前冻结48行真值。

48次真实调用完成：原16条明确指令诊断独立正式分母16、命中4；新增8题×4角色中autonomous16/explicit16分轨，正式分母均0，因为没有来源要求必然角色差异、三个候选都可接受。不得把相同选择判为失败。动作＋目标分母仍0；A/B/C缺认知、hard limits、compute、authority；D另缺人格，均不补默认值。provider error/mapping rejection=0，CPU p50=793.945ms、p95=910.455ms。原v3→v4选择变化6/16，历史description→v4变化11/16，有输入与设备混杂，不能写成质量提升；旧7/16不是正式正确率。

48条完整追溯与wire一致；state无截断，18种label+description中3种被48token上限截去末尾句号，语义完整。候选合同和新审查已通过，但role-sensitive题仍不能区分质量，calibration blocked，不触发微调。A-Cognition仅development证据；A-Embodied未运行/blocked；Godot本批禁止且历史环境blocked；Harness all未运行且不能称通过。backend-contract/change-lifecycle通过并cleanup passed；全量pytest最终重跑结果见后续工程验证记录。

完整来源、逐题覆盖、三张边界图与证据索引见 [审查11](../审查/11-development-v4真值审查与候选语义冻结.md)。本批偏离原设计的部分为先冻结认知fixture语义、分轨审查，不把fixture别名升级为动作注册/owner执行；新增题的来源条件仍不足以要求不同答案。[planned] 先改善有来源可区分development题，满足门禁后才独立新calibration；[deferred] 无新增延期能力。


### RW-28 最终工程验证与清理（2026-10-13）

新鲜全量 `python -m pytest -v`：**7920 passed、2 skipped、1 failed、106 warnings，1464.29s，exit1**。唯一失败为 `test_main_cold_start.py::test_independent_population_fixture_and_verification_cold_entry[seed]`，population offline dialogue fixture 查找 activation_active 事件时 StopIteration。独立复跑 **1 passed、22.09s、exit0**，根因未证实，不能用复跑覆盖全量失败；pytest full gate **not clean**。该模块本批未修改，未扩展到population/owner/B-C修复。

相关focused76项与v4 runner20项通过；backend-contract、change-lifecycle、docs Harness均exit0、cleanup passed。Harness all本批未运行（用户禁止Godot且历史环境blocked），不称通过。本轮自有临时目录已在导出退休preparation及SHA后删除；未创建自有provider/helper，已有用户Laya服务与系统wslrelay保留，git status --short -- .harness无本批改动，已有资料保留。

日志与机器可读状态见外部证据根 `D:/Users/User/Documents/paralls-evidence/october-development-v4-20261013/` 的 pytest-full-final.log、pytest-cold-start-rerun.log、verification-summary.json、repeatability.json和cleanup.json。本记录替代此前“最终pytest正在执行”的状态，不替换历史证据。calibration仍blocked，A-Cognition未正式接受、A-Embodied/Godot未验收。
