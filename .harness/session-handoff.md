# Harness Session Handoff

本文件是静态交接模板，不代表最新一次运行已通过，也不要求保存运行日志。

## 交接时记录

- 当前目标、来源 revision 与未完成范围。
- 本轮命令、run_id、通过/失败/blocked 结论及 cleanup_status。
- Godot/backend/真实边界消息是否实际验证；静态检查无法覆盖的部分。
- 显式导出证据的位置、保留期限与负责人；未导出时记录重新验证命令。
- 必要的已审查案例或回归夹具链接，避免复制完整日志。

## Stable Entry Points

- 运行与证据契约：`docs/harness.md`
- 清理与陈旧报告案例：`docs/harness-playbook.md`
- Profile 清单：`.harness/profiles/`；suite：`.harness/suites.json`
- 本地完整门禁：`.harness/ci/local-ci-gate.ps1`
- 广泛验证：`python scripts/verification/harness.py --profile all`

## Known Verification Limits

Hosted CI 的 smoke/contract 不提供 runtime 或 release 覆盖。清理后的文字摘要不可代替新证据；缺少环境的项目必须保持未验证状态。只有独立验收边界确有需要时才新增 profile/rule，其他改动复用现有入口。
