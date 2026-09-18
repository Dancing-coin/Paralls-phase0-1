# Harness Clean State Checklist

结束验证或提交前逐项检查，运行时完成声明仍须对应真实运行证据。

## Verification

- [ ] 记录本次命令、revision、通过/失败/blocked 项及验证范围。
- [ ] 根据改动执行 focused tests、相关 profile；广泛变更运行 `python scripts/verification/harness.py --profile all`。
- [ ] Godot 或真实跨边界验证缺失时明确记录，不以 smoke/contract 代替。

## Evidence And Cleanup

- [ ] 清理前已构造失败摘要；必要原始证据已显式导出到仓库外。
- [ ] 最终摘要包含 cleanup_status；本轮临时根、缓存、隔离副本及拥有的进程已回收。
- [ ] 复用的 backend、用户已有文件和无关修改保留原状。
- [ ] 检查 `.harness/` 实际目录和 `git status --short -- .harness`；没有生成报告、日志、数据库、截图或运行目录。仅看 Git 状态无法发现 ignored 产物。

## Source Inputs And Handoff

- [ ] profiles、rules、模板和必要案例未被忽略，可以审查与提交。
- [ ] 有长期价值的根因与复现方法已经审查，记录在 `docs/harness-playbook.md` 或最小夹具中。
- [ ] 交接记录明确当前验证限制、必要重跑命令、导出位置及保留责任；静态台账不标记实时 pass。
