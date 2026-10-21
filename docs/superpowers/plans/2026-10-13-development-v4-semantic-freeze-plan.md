# Development v4 候选语义冻结与独立真值执行计划

状态：实现、独立审查和48次development运行完成；最终全量pytest已完成但1 failed，正式工程gate未clean；用户本轮七项要求为授权与验收合同。替代旧有限对照计划的后续执行；不再次运行 baseline/description 对照。

来源：角色01/02/13，规格05，计划01 Task1C，审查03/05/10/11，`docs/ai-engineering-workflow.md`。

1. 修复 CandidateCompiler 描述合同并版本化：注册意图语义、目标关系、已知条件与未验证执行边界；保持 stable wire labels、完整 U/P、顺序与 digest。每个族和篡改输入先 RED 后 GREEN。
2. 仓库入口生成只含事实、来源角色条件、候选语义、可见性及 rubric 的12场景输入（原4场景×4角色＋新8场景×4角色）。旧16题为 explicit_instruction_diagnostic 回归 cohort，另两轨独立报告。
3. 全新上下文 reviewer 仅允许读取外部净化文件；冻结48行集合、来源、排除理由、unknown与执行未验证字段。主代理核对实际read log和 accidental exposure 后才批准；旧盲审永远 retired/non-independent。
4. 新v4入口依据同一净化包重建角色来源→effective profile→MindFrame→compiler→wire。char_d 的人格、认知、hard limits、compute和authority保持unknown。复现描述与mapping gate通过才允许网络调用。
5. 固定原source/checkpoint/artifact，运行16条诊断回归与32条role-sensitive角色调用，保留完整请求、U/P、候选、响应、延迟和冻结审查输入。无owner/runtime target证据，动作＋目标分母恒0。
6. focused tests、全量pytest、适用非Godot Harness；Godot与all环境阻断独立披露。本轮禁止Godot运行，禁止读取封存题、calibration、微调与具身范围。
7. 回写审查、规格、计划、原始设计偏离与登记；导出仓库外证据，清理仅本轮拥有的provider/helper/temp。保留全部用户原有资料和系统wslrelay。

文件责任：semantic_contract子代理负责compiler/provider及测试与当前source pins；v4_runner子代理负责新准备/运行入口与测试；主代理负责盲审包、隔离审查、整合、实测与文档。回滚点为本轮增量文件/改动，禁止撤销既有用户变化。

未达到独立真值门禁时不调用、不评分；题面/候选缺陷主导、来源无法要求角色差异、共同安全行为无法分轨解释时calibration仍blocked。此阶段不声明A-Cognition或A-Embodied验收。

结果与三张边界图：[审查11](../../10月分析/审查/11-development-v4真值审查与候选语义冻结.md)。role-sensitive正式分母0，calibration继续blocked。


### RW-28 最终工程验证与清理（2026-10-13）

新鲜全量 `python -m pytest -v`：**7920 passed、2 skipped、1 failed、106 warnings，1464.29s，exit1**。唯一失败为 `test_main_cold_start.py::test_independent_population_fixture_and_verification_cold_entry[seed]`，population offline dialogue fixture 查找 activation_active 事件时 StopIteration。独立复跑 **1 passed、22.09s、exit0**，根因未证实，不能用复跑覆盖全量失败；pytest full gate **not clean**。该模块本批未修改，未扩展到population/owner/B-C修复。

相关focused76项与v4 runner20项通过；backend-contract、change-lifecycle、docs Harness均exit0、cleanup passed。Harness all本批未运行（用户禁止Godot且历史环境blocked），不称通过。本轮自有临时目录已在导出退休preparation及SHA后删除；未创建自有provider/helper，已有用户Laya服务与系统wslrelay保留，git status --short -- .harness无本批改动，已有资料保留。

日志与机器可读状态见外部证据根 `D:/Users/User/Documents/paralls-evidence/october-development-v4-20261013/` 的 pytest-full-final.log、pytest-cold-start-rerun.log、verification-summary.json、repeatability.json和cleanup.json。本记录替代此前“最终pytest正在执行”的状态，不替换历史证据。calibration仍blocked，A-Cognition未正式接受、A-Embodied/Godot未验收。
