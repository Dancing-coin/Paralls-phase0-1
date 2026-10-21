# Calibration 前置收口实施计划

状态：用户本轮八项要求授权执行；只收口前置，禁止正式 calibration/final/holdout 和微调、具身、owner、Godot、B/C、玩法包、编辑器、自走棋、AD/Blender。

规格：本轮用户要求；十月规格05的模型与评估门禁；审查03/05/11。使用 systematic-debugging、writing-plans、TDD、harness-verification 与 verification-before-completion。直接在既有脏工作区做小范围可逆修改，不提交/回退既有用户变化。

## 任务与验收账本

- [x] 1. 读取历史完整 traceback、cold-start fixture/入口与最近 diff；独立有界 lane 复现原因。只在确证后修根因、补回归；不以重复通过覆盖失败，不修改原测试期望，不扩展 owner。
- [x] 2. 批准拆为 reviewer_independent_approval、lead_audit_approval、formal_truth_usable。保留原 reviewer/read log/主代理批准，并对旧误称独立批准登记更正；新 verifier 拒绝单独主代理批准、污染、改输入与不完整真值。
- [x] 3. 独立来源作者建立24条新题、6个新轨迹，三轨分开；先生成只含五类metadata的manifest。新 reviewer 无历史上下文、只读净化新题输入；冻结独立acceptable sets后主代理审计。
- [x] 4. v5 description语义压缩和option-level tokenizer gate。保留v4原合同可重建；固定tokenizer文件SHA、实际label+description原始串计数strict <48；无计数/超限必须拒绝。
- [x] 5. 离线前置生成器建立source→MindFrame→U/P→wire证据和source/provider/device/token pins。禁止模型调用；分清fixture决策分母与完整runtime动作分母；threshold仍未预登记时blocked。
- [x] 6. focused 80 passed、v4 runner 21 passed；代码冻结后的完整 `python -m pytest -v` 为 7937 passed、2 skipped、exit 0（23:51）；backend-contract Harness exit0/cleanup passed；git diff --check 无错误（仅既有 CRLF 警告）；仓库外证据已导出，`.harness` 无本轮增量，wslrelay PID59520 保持。
- [x] 7. 回写审查03/05、新审查12、规格05、计划01、角色01/02回写、回写README和十月README。新审查含所有三图；分别报告A-Cognition/A-Embodied/Godot/Harness all。

## 文件责任

cold-start lane：population_continuity/vertical.py与新fixture回归，仅必要时修改。
token lane：CandidateCompiler、Laya provider与两组现有测试。
来源作者：calibration_preclosure_20261013新fixture目录，不写标签。
独立reviewer：仅仓库外review-input.json及reviewer-truth.json，不读旧题、模型响应/评分、final/holdout。
主代理：批准字段、前置生成器/测试、v4兼容、全量验证、文档与清理。

## 门禁

独立审定可计算的非零认知决策分母不等于已测正确率；runtime legality、owner permission、实际话语、execution receipt未验证，完整动作分母保持0。角色差异只改风格不计分。char_d unknown不得补值。无真实exit0不记pytest clean。旧calibration污染永久退休；final/holdout不读。预登记阈值、provider/device和输入实际token pins缺失时保持calibration blocked；慢模型不替代Laya质量。

## 证据与执行记录

仓库外证据根：`D:/Users/User/Documents/paralls-evidence/october-calibration-preclosure-20261013/`。结果随执行记录，不用既有日志代替新鲜验证。

## 冻结输入与中间证据

冷启动历史failure底层callback原因仍未定位；新增fixture诊断与拒绝回归，不称根因修复或既有无关flaky。v1审查仅6条explicit诊断；另建v2，由另一位fresh reviewer冻结22条fixture决策（8 autonomous / 6 explicit / 8 role-sensitive）。v2 reviewer、lead audit、formal truth三个字段分别true且scope只限这些fixture决策；runtime/owner/话语/receipt不批准，完整动作分母0。char_d未知维度未填补。

v4原48 input/wire/mapping digests离线全部相同。v5全题实际token最大46、strict <48且aggregate head gate通过。源profile/dossier SHA与MindFrame/wire逐项验证；metadata manifest仅五字段。代码和新题冻结后的 full pytest 已真实 exit 0；第一次14%中断与修复前失败日志均保留，不能替代最终 gate。

相关Harness docs/backend-contract/change-lifecycle分别exit0且cleanup passed。本轮不运行Harness all/Godot，保留系统wslrelay。剩余calibration门：live checkpoint attestation（health revision null）与阈值预登记；本轮模型调用0。最终full exit、diff与清理结果以审查12唯一结果区块及外部verification-summary.json为准。


[2026-10-14 RW-32后续执行] 原计划于RW-31后被用户明确扩展为修复及同轮诊断。共享provider完整预算2091/256、fail-closed与独立CPU provider均完成；合成预检及22条请求完成，usage均无截断。修复focused10 passed、character-policy-calibration Harness passed。正式评分因v3 truth approval=false且独立复核不能沿用旧批准而阻断。全量pytest为7947 passed/2 skipped、exit0；Harness all本轮exit1、cleanup passed，不得用子profile替代。详见RW-32。
