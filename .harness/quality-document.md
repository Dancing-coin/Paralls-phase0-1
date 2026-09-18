# Harness Quality Document

这是一份静态能力说明，`verification_status=not_evaluated`。具体 revision 是否通过必须依据本轮报告；不以固定字母评级或台账中的 pass 代替执行。

| 能力 | 审查入口 | 实际验证要求 |
| --- | --- | --- |
| Profile 与 rule registry | `.harness/profiles/`、`.harness/rules/`、`registry.py` | registry 测试与对应 profile |
| 临时证据与清理 | `run_context.py`、`.harness/retention-policy.json` | 正常、异常、嵌套、导出、路径边界回归及 cleanup_status |
| 结果身份与失败判断 | `harness.py`、`evidence.py` | 旧轮次、旧 attempt、退出码/报告矛盾等故障注入 |
| Python/Godot 集成 | runtime profiles 与 trace | 运行 backend、真实边界消息、可见场景结果 |
| CI | `.harness/ci/local-ci-gate.ps1`、`.github/workflows/harness.yml` | 本地与 hosted 分别实测；hosted 静态通过不代表 release |
| 经验与候选 | `docs/harness-playbook.md`、`.harness/evolution/` | 评估记录摘要与身份校验；Skill 收益另需独立任务对照 |

检查步骤见 `.harness/clean-state-checklist.md`。`.harness/features.json`、`.harness/evaluator-rubric.md` 与来源 taxonomy 是审查输入，不是实时执行记录。
