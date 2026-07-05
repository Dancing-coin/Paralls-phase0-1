# 当前项目感知身份验证矩阵实施计划

- 状态：`implemented-and-focused-verified`
- 日期：`2026-07-05`

上位设计：

- [2026-07-05-current-project-perception-identity-verification-matrix-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-perception-identity-verification-matrix-design.md)

## 1. 目标

新增 focused tests 与 verifier，证明完整 identity 设计不是“字段全了”，而是“行为正确”。

## 2. 实施范围

- `backend/tests/*perception*`
- `backend/tests/*actor_scene_knowledge*`
- `backend/tests/*siming_global_situation*`
- `scripts/verification/verify_perception_input_alignment.py`
- `scripts/verification/harness.py` / profile registry

## 3. 实施步骤

1. 新增 unit tests 覆盖同拍/跨拍/同物/异物/多 actor 场景
2. 新增 focused verifier：`verify_perception_input_alignment.py`
3. 增加 harness profile：`perception-input-alignment`
4. 把该 profile 纳入适当聚合验证入口

## 4. 验收

- [x] 行为矩阵场景全部有 automated proof
- [x] verifier 报告含完整 identity lineage
- [x] 失败时可直接定位是时间、对象还是视角问题

## 5. 验证证据

- `python -m pytest -q backend/tests/test_perception_identity_verification_matrix.py scripts/verification/tests/test_harness_registry.py`
- `python scripts/verification/verify_perception_input_alignment.py`
- `python scripts/verification/harness.py --profile perception-input-alignment`
- `.harness/verification/perception-input-alignment-report.json`
- `.harness/verification/perception-input-alignment-report.md`

## 6. 覆盖矩阵

- fact 链和 provider 链同拍同物 -> 同一对象：`fact-provider-same-capture-same-object`
- fact 链和 provider 链跨拍 -> 不得误判同拍：`fact-provider-cross-capture-not-same-tick`
- actor A/B 同拍看同物 -> 同对象不同私有属性：`multi-actor-same-capture-same-object-private-attributes`
- actor A/B 同拍看近邻不同物 -> 不误合并：`multi-actor-same-capture-nearby-different-objects-not-merged`
- VLA 后补 advisory -> 标记为后补，不伪装原拍：`vla-late-advisory-not-original-capture-result`
- Siming multi-actor 汇总 -> 不丢 object/time identity：`siming-multi-actor-summary-retains-object-time-identity`
