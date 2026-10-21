# Development 真值、归因与有限对照执行计划

> **For agentic workers:** 使用 systematic-debugging；实现者先完成针对性 RED/GREEN，主代理整合并验证。用户本轮已授权执行，持续执行无需再次审批。

**Goal:** 完成原16条 development 的真值审查与归因，核对固定官方 criteria 合同，并保留单因素真实对照的全部尝试。

**Architecture:** 沿用角色01/02/13、规格01/03/05及计划01 Task1C。诊断工具只消费既有仓库外冻结包，通过固定 provider 做认知选择；不修改心智、生产 wire schema、owner 或具身链。

**Tech Stack:** 现有 Python、pytest、固定 multilingual Laya。

**Spec:** 用户2026-10-13本轮七项要求；`docs/10月分析/规格/05-角色能力图谱、认知包络与动态算力规格.md` §4.2，`docs/10月分析/审查/05-第三项阿博评估档案与四角色夹具.md` §7.6。

## 约束与审查重点

- 保留 development-live-v3 原16条；final/holdout 不读取、不运行，污染 calibration 继续 retired。
- 审查先冻结可接受集合再比较输出，披露审查暴露；未获独立审定不增加正式分母。
- 合法、安全/隐私/权限、任务推进、角色一致性分别判断；unknown 保留。
- 不补角色能力/算力，不以身份名充人格，不删错误候选，不冻结阈值。
- 候选描述须来自通用动作语义；标签、candidate_id、target_refs、映射稳定。描述及顺序进入冻结清单和有序 digest。
- 真实对照一次一因素；完整动作＋目标分母仍0，认知记录不代替 runtime legal target/receipt。

## 执行台账

- [ ] 盲审：隔离子代理只读development事实与角色来源；外部冻结16条四维结论及hash，再比较结果。
- [ ] 官方合同：核对 source commit `68804629e8ccd9d616d48a40e87de9fabbeae069` 的 choice schema、criteria 消费、顺序与示例。
- [ ] 工具：新增 `scripts/verification/diagnose_character_development.py`；回归 `backend/tests/test_character_development_diagnosis.py`。先验证篡改拒绝、单因素、顺序digest、非法响应保留，再实现；不改生产adapter。
- [ ] 实验：原wire重测16、描述16、去身份名等价摘要16、代表题反序4，共52次上限。先写冻结矩阵再调用；失败同样保留，不择优重跑。描述轴仅在官方合同确认允许后执行。
- [ ] 逐题：原16条及全部对照与冻结真值比较，分别记原因类别、证据、unknown；不将偏好失配称安全失败。
- [ ] 新题：隔离 `role-sensitive-development.yaml`，至少三对自主决策与一对操作诊断，来源/轨迹/维度/缺口显式登记，不自动并入原16条。
- [ ] 回写：原角色01/02/13、规格05、计划01、审查记录及回写登记，引用本轮外部证据。
- [ ] 验证：focused测试、全量 `python -m pytest -v`、适用Harness。已知Godot阻断不重复用all代替解阻，分别记录未运行/blocked；检查本轮资源清理。

## 假设与保留规则

H1：label到同label虽可能合法，但动作语义不足可能诱发defer。只有官方允许描述且单因素对照改善任务推进，才保留为候选表达改进；不据此接受生产质量。

H2：身份名称可能影响选择。去除 `character_id` 与 `canonical_name`，保留职业、价值、能力和其余文本；如选择变化，只说明该摘要下的名称敏感，不能推断人格质量。

H3：候选位置可能影响选择。仅对四条代表题反转顺序，保持语义/映射；有变化记录敏感性，无变化也只限于样本。

原wire重测用于判断重测稳定性，不能用最好一次覆盖v3。单次有限对照不能估计总体正确率或因果效应；必要时下一阶段增加预登记重复及独立题，关键决策经独立审查仍不达标时按已批准路线准备必要微调。

证据根：`D:/Users/User/Documents/paralls-evidence/october-development-review-20261013/`；不删除用户已有证据。
