# F0 Evidence Manifest

状态：`fresh baseline; generated predecessor evidence`

基线提交：`7b6866293e16ed6d7053666ebf4d7bf80f4f2873`（2026-08-11）

本轮 P5 前置运行证据：

| Profile | Run archive | 结果 |
| --- | --- | --- |
| `phase5a-quest-objective-evidence` | `.harness/verification/runs/run-20260812-102629-087693/` | green |
| `phase5b-relationship-reputation-knowledge` | `.harness/verification/runs/run-20260812-102637-957652/` | green |
| `phase5c-investigation-stealth-conflict` | `.harness/verification/runs/run-20260812-102645-063906/` | green |
| `phase5d-investigation-vertical-slice` | `.harness/verification/runs/run-20260812-102652-233692/` | green |
| `post-p5-capability-foundation-docs` | `.harness/verification/runs/run-20260812-100427-719841/` | green, documentation-only |

## Freshness rule

这组证据只支持上述 commit 和未改变的 owner、写路径、schema/revision、隐私投影、Harness 断言、迁移/回滚行为。任一变化都使后继 F1/F2/DG 证据失效并要求重跑。未来日期文档不是运行证据。
