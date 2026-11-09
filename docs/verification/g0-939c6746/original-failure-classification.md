# G0 当前失败根因分类

- 日期：2026-11-09；代码 HEAD：`5321266dbd882f45eb6a24dd7b328e9f56746228`。
- 当前基线 **108 失败 / 33 文件**；历史 201 不适用于更新后的代码与扩大后的测试集合。
- 四类按实际堆栈、测试输入与源码分类；环境项仍计失败。未知根因为 0 不代表产品契约已获批准。
- 每项完整错误类型、阶段、原始/规范化堆栈、SHA-256、源码帧与理由见 [机器快照](failures_baseline_5321266d.json)。

| 类别 | 数量 |
|---|---:|
| 环境差异 | 43 |
| 已知缺陷 | 5 |
| 测试过时 | 60 |
| 未知根因 | 0 |

## 阻塞决定

**G0 未通过，G1 未放行。** B1 是规格明确要求先修复的幂等缺陷。B2/B3/B4 涉及投影、提交接入或恢复身份；须在独立缺陷/契约轨道处理并重新验证，或提供经审查的精确迁移边界排除证据。当前没有这种排除证据。不得在结构重构里顺手改变语义。

“测试过时”包含旧工具调用和冻结 fixture 漂移，不意味着删除失败测试；应更新契约输入并确认原保护仍成立。环境项只允许作为带说明的对照噪声，不能从总数消失。

## 逐项记录

### F001 · 测试过时

`tests/test_action_window_temporal_owner.py::test_changed_duplicate_cannot_replace_frozen_time_input[cutoff_tick-2]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：0fc54364 明确把每窗口事件从 4 改为 5，增加 terminal_outcome_recorded；这些断言仍要求 head=4 或没有 terminal 事件。重试并未另增一个窗口。
- 证据：`backend/app/gameplay/p5/investigation_conflict.py:30`；`git:0fc543643367e98237545ffb09370753268badfd`；`backend/tests/test_3d_scripted_mystery_action_replay.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F002 · 测试过时

`tests/test_action_window_temporal_owner.py::test_changed_duplicate_cannot_replace_frozen_time_input[sampled_at-1]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：0fc54364 明确把每窗口事件从 4 改为 5，增加 terminal_outcome_recorded；这些断言仍要求 head=4 或没有 terminal 事件。重试并未另增一个窗口。
- 证据：`backend/app/gameplay/p5/investigation_conflict.py:30`；`git:0fc543643367e98237545ffb09370753268badfd`；`backend/tests/test_3d_scripted_mystery_action_replay.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F003 · 测试过时

`tests/test_action_window_temporal_owner.py::test_changed_duplicate_cannot_replace_frozen_time_input[source_revision-source@2]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：0fc54364 明确把每窗口事件从 4 改为 5，增加 terminal_outcome_recorded；这些断言仍要求 head=4 或没有 terminal 事件。重试并未另增一个窗口。
- 证据：`backend/app/gameplay/p5/investigation_conflict.py:30`；`git:0fc543643367e98237545ffb09370753268badfd`；`backend/tests/test_3d_scripted_mystery_action_replay.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F004 · 测试过时

`tests/test_action_window_temporal_owner.py::test_changed_duplicate_cannot_replace_frozen_time_input[settlement_window-value3]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：0fc54364 明确把每窗口事件从 4 改为 5，增加 terminal_outcome_recorded；这些断言仍要求 head=4 或没有 terminal 事件。重试并未另增一个窗口。
- 证据：`backend/app/gameplay/p5/investigation_conflict.py:30`；`git:0fc543643367e98237545ffb09370753268badfd`；`backend/tests/test_3d_scripted_mystery_action_replay.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F005 · 测试过时

`tests/test_action_window_temporal_owner.py::test_durable_restart_preserves_time_pins_and_original_receipt`

- 错误：`AssertionError`；阶段：`call`。
- 根因：0fc54364 明确把每窗口事件从 4 改为 5，增加 terminal_outcome_recorded；这些断言仍要求 head=4 或没有 terminal 事件。重试并未另增一个窗口。
- 证据：`backend/app/gameplay/p5/investigation_conflict.py:30`；`git:0fc543643367e98237545ffb09370753268badfd`；`backend/tests/test_3d_scripted_mystery_action_replay.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F006 · 测试过时

`tests/test_calibration_preclosure.py::test_offline_wire_preserves_unknowns_targets_and_source_memory`

- 错误：`ValueError`；阶段：`call`。
- 根因：旧离线准备工具的 permission 条件被当前 compiler 判为 unknown，冻结候选为空；Laya 拒绝无候选。调用工具/fixture 未跟随候选冻结契约。
- 证据：`scripts/verification/prepare_calibration_preclosure.py:105`；`backend/app/character_agent/gateway/laya_provider.py:59`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F007 · 测试过时

`tests/test_character_agent_runtime.py::test_character_agent_runtime_player_suggestion_path_uses_continuity_floor_under_local_only_planner`

- 错误：`AssertionError`；阶段：`call`。
- 根因：连续性规划发布的语义意图已归一化为 observe_target；旧断言要求 observe。L4 执行映射仍可映射到 action:observe，不能把决策意图和动作名混同。
- 证据：`backend/app/character_agent/runtime/runtime_loop.py:5697`；`backend/app/character_agent/planning/l3_planner.py:1821`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F008 · 环境差异

`tests/test_character_agent_runtime_persistence_wiring.py::test_main_runtime_wires_character_storage_next_to_durable_graph`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试用仓库根相对路径；正式入口 cwd=backend，故 backend/app/main.py 变成 backend/backend/app/main.py，或 assets/characters/profiles 解析为空。真实根文件存在。
- 证据：`backend/tests/test_character_agent_runtime_persistence_wiring.py`；`backend/tests/test_p2dr_authored_bakery_authority_reclosure.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F009 · 环境差异

`tests/test_character_cognition_admission.py::test_child_admission_survives_process_exit_before_parent_receipt`

- 错误：`CalledProcessError`；阶段：`call`。
- 根因：子进程 PYTHONPATH 未包含正确根/测试路径。backend cwd 下再次 resolve backend 导致嵌套路径，或子进程无法导入 scripts.verification。失败在 import 阶段，未验证硬退出恢复。
- 证据：`backend/tests/test_character_cognition_admission.py:165`；`backend/tests/test_siming_admission.py:194`；`diagnostic-probes-v2.json`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F010 · 测试过时

`tests/test_character_development_runner.py::test_runner_rejects_changed_wire_and_truth_before_any_provider_call`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F011 · 测试过时

`tests/test_character_development_runner.py::test_runner_uses_real_adapter_mapping_and_flushes_diagnostic_only_results`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F012 · 测试过时

`tests/test_character_development_runner.py::test_runner_preserves_rejected_real_response_and_does_not_grade_it`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F013 · 测试过时

`tests/test_character_development_runner.py::test_runner_stops_changed_input_version_and_retains_already_issued_call`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F014 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_preparation_has_48_frozen_rows_and_char_d_unknowns`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F015 · 测试过时

`tests/test_character_development_v4_runner.py::test_lead_approval_cannot_replace_reviewer_approval`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F016 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[unapproved]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F017 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[exposure]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F018 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[read_log]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F019 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[sha]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F020 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[missing_judgment]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F021 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[unverified]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F022 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[candidate]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F023 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[source]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F024 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[question_kind]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F025 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[cohort]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F026 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[duplicate_pair]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F027 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[missing_pair_source]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F028 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_gate_rejects_before_network[missing_unknowns]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F029 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_real_adapter_evidence_and_separate_track_denominators`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F030 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_evaluable_scope_and_provider_failure_denominators[False]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F031 · 测试过时

`tests/test_character_development_v4_runner.py::test_v4_evaluable_scope_and_provider_failure_denominators[True]`

- 错误：`ValidationError`；阶段：`call`。
- 根因：旧 v4 准备工具传 cognition_policy={}，当前 CognitionPolicy 有九个必填字段；在模型调用之前校验失败，18 项不是 18 个独立网络故障。
- 证据：`scripts/verification/run_character_development_v4.py:107`；`backend/app/character_agent/gateway/model_gateway.py:62`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F032 · 测试过时

`tests/test_character_evaluation_preparation.py::test_preparation_materializes_frozen_frames_and_independent_reference_universe`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F033 · 测试过时

`tests/test_character_evaluation_preparation.py::test_model_input_never_contains_grading_answers`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F034 · 测试过时

`tests/test_character_evaluation_preparation.py::test_final_and_independent_holdout_remain_unopened`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F035 · 测试过时

`tests/test_character_evaluation_preparation.py::test_same_authority_trajectory_cannot_cross_splits`

- 错误：`AssertionError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F036 · 测试过时

`tests/test_character_evaluation_preparation.py::test_missing_or_hidden_targets_cannot_receive_fixture_admission`

- 错误：`AssertionError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F037 · 测试过时

`tests/test_character_evaluation_preparation.py::test_abo_projection_does_not_inherit_runtime_numeric_defaults`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F038 · 测试过时

`tests/test_character_evaluation_preparation.py::test_reference_universe_detects_compiler_omission`

- 错误：`AssertionError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F039 · 测试过时

`tests/test_character_evaluation_preparation.py::test_fixture_profiles_have_source_evidence_without_abo_defaults`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F040 · 测试过时

`tests/test_character_evaluation_preparation.py::test_authored_profile_reaches_shared_wire_without_private_backbone`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F041 · 测试过时

`tests/test_character_evaluation_preparation.py::test_preparation_is_repeatable_and_full_wire_matches_runtime_serializer`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F042 · 测试过时

`tests/test_character_evaluation_preparation.py::test_empty_development_selection_cannot_claim_ready`

- 错误：`ValueError`；阶段：`call`。
- 根因：冻结评测策略的 source_pins 与当前受跟踪角色源不一致。char_a 预期 8e8f3292519a7879f2f16eca2d64be7b90467010dc7641689a8e6b9821879463，实际/git blob 均 9c41753ac79644e8a4a81779b2ff7a9e49f04e28439e5489c052b7fef166ef88；不是 CRLF 漂移。source_changed 拒绝是当前保护行为。不得自动刷新语料哈希。
- 证据：`scripts/verification/prepare_character_evaluation.py:25`；`backend/tests/fixtures/character_evaluation/four_role_preparation/development-policy.yaml:127`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F043 · 已知缺陷

`tests/test_character_memory_consistency_flow.py::test_actual_interaction_failure_reaches_l3_and_new_evidence_clears_recheck_reason`

- 错误：`AssertionError`；阶段：`call`。
- 根因：新知识 valid_at=4 已存在，却被 recall 的 480-token/4条预算裁掉（435 tokens，2 event+1 observation，0 knowledge，truncated=true）。L3 用裁剪后的 recall.memory 生成 verification context，看不到比失败 tension 更晚的证据，旧 recheck_reason 未清除。
- 证据：`backend/tests/test_character_memory_consistency_flow.py:255`；`backend/app/character_agent/planning/l3_planner.py:731`；`diagnostic-additional.json`。
- 阶段门：B2：影响角色记忆投影/决策输入；G1 前须独立修复或以明确迁移边界实证排除该投影路径，不可默认豁免。

### F044 · 测试过时

`tests/test_character_mind_frame_consumers.py::test_l3_prepared_request_carries_frozen_mind_frame`

- 错误：`ValueError`；阶段：`call`。
- 根因：旧 planner fixture 缺少当前必须绑定的 turn context；在 l3 prepare 的边界保护处拒绝。
- 证据：`backend/tests/test_character_mind_frame_consumers.py`；`backend/app/character_agent/planning/l3_planner.py:651`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F045 · 测试过时

`tests/test_character_mind_frame_models.py::test_mind_frame_rejects_rebinding_to_another_actor_or_turn`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture 同时有 actor/turn 不匹配，当前先拒绝 actor mismatch；旧测试只接受 turn 字样。错误仍被拒绝，断言对校验顺序过度绑定。
- 证据：`backend/tests/test_character_mind_frame_models.py:209`；`backend/app/character_agent/models/mind_frame.py:228`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F046 · 测试过时

`tests/test_character_runtime_needs_affect_flow.py::test_l2_reasoning_context_preserves_effective_profile_and_need_tension_state`

- 错误：`TypeError`；阶段：`call`。
- 根因：三个旧 stub 分别不接受 model_dump(mode=json)、prepare_perceived_event(capability_envelope=...)、prepare_intent_plan(capability_envelope=...)。运行时捕获后走 fallback，旧记录变量为空；不能用 stub 失败证明真实 provider 行为。
- 证据：`backend/tests/test_character_runtime_needs_affect_flow.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F047 · 测试过时

`tests/test_character_runtime_needs_affect_flow.py::test_runtime_ingest_character_perceived_event_passes_effective_profile_and_need_tension_state_into_l2`

- 错误：`AssertionError`；阶段：`call`。
- 根因：三个旧 stub 分别不接受 model_dump(mode=json)、prepare_perceived_event(capability_envelope=...)、prepare_intent_plan(capability_envelope=...)。运行时捕获后走 fallback，旧记录变量为空；不能用 stub 失败证明真实 provider 行为。
- 证据：`backend/tests/test_character_runtime_needs_affect_flow.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F048 · 测试过时

`tests/test_character_runtime_needs_affect_flow.py::test_runtime_ingest_character_perceived_event_passes_effective_profile_need_tension_and_dynamic_state_into_l3`

- 错误：`AssertionError`；阶段：`call`。
- 根因：三个旧 stub 分别不接受 model_dump(mode=json)、prepare_perceived_event(capability_envelope=...)、prepare_intent_plan(capability_envelope=...)。运行时捕获后走 fallback，旧记录变量为空；不能用 stub 失败证明真实 provider 行为。
- 证据：`backend/tests/test_character_runtime_needs_affect_flow.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F049 · 环境差异

`tests/test_character_turn_embodied_episode.py::test_archive_door_turn_has_one_contract_receipt_and_confirmed_episode`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F050 · 环境差异

`tests/test_character_turn_embodied_episode.py::test_turn_correlation_requires_contract_identity_and_rejected_settlement_does_not_mutate`

- 错误：`TypeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F051 · 环境差异

`tests/test_economy_random_command_application.py::test_real_fastapi_websocket_controller_bind_then_random_command`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F052 · 测试过时

`tests/test_economy_random_replay_participant.py::test_shared_cut_replays_ten_domain_participants_after_cadence_and_restart`

- 错误：`AssertionError`；阶段：`call`。
- 根因：重开 fixture 构造 PresenceAuthority(store) 未注入 sources；当前历史重验 spawn 要求 sources，原始 helper 却有 sources。回放参与者装配不完整。
- 证据：`backend/tests/test_economy_random_replay_participant.py:332`；`backend/app/population_continuity/presence_runtime.py:169`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F053 · 测试过时

`tests/test_economy_temporal_replay_application.py::test_economy_temporal_application_checkpoint_tail_survives_durable_reopen`

- 错误：`AssertionError`；阶段：`call`。
- 根因：checkpoint 带 social 状态，重开 replay_scoped_tail 仅传 inventory；当前回放拒绝 replay_social_participant_missing。旧恢复 fixture 不完整，不能静默忽略 social。
- 证据：`backend/tests/test_economy_temporal_replay_application.py:102`；`backend/app/world_runtime/replay_participants.py:1865`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F054 · 测试过时

`tests/test_esm_physical_channel_runtime.py::test_physical_effects_merge_through_orchestration_unified_result_family`

- 错误：`AssertionError`；阶段：`call`。
- 根因：旧 fixture 的 obj_box 未注册到当前 ESM 语义 authority；先 unsupported_object，再 semantic_authority_required，未进入断言所期待的旧物理交互路径。
- 证据：`backend/tests/test_esm_physical_channel_runtime.py`；`backend/tests/test_interaction_orchestration_runtime_service.py`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F055 · 测试过时

`tests/test_esm_physical_channel_runtime.py::test_semantic_only_behavior_remains_unchanged_when_physical_channel_exists`

- 错误：`AssertionError`；阶段：`call`。
- 根因：旧 fixture 的 obj_box 未注册到当前 ESM 语义 authority；先 unsupported_object，再 semantic_authority_required，未进入断言所期待的旧物理交互路径。
- 证据：`backend/tests/test_esm_physical_channel_runtime.py`；`backend/tests/test_interaction_orchestration_runtime_service.py`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F056 · 测试过时

`tests/test_gameplay_event_store_json_cache.py::test_cached_body_does_not_hide_sql_updates_or_corruption`

- 错误：`AssertionError`；阶段：`call`。
- 根因：损坏 JSON 与关闭 snapshot 仍 fail-closed，实际错误分别 json_codec_invalid / snapshot_closed；旧 regex 要求 row_invalid。不是成功读出坏行。
- 证据：`backend/app/gameplay/event_store.py:58`；`backend/app/gameplay/event_store.py:944`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F057 · 测试过时

`tests/test_gameplay_event_store_json_cache.py::test_close_clears_cached_content_and_prefetched_decode_does_not_retain_it`

- 错误：`AssertionError`；阶段：`call`。
- 根因：损坏 JSON 与关闭 snapshot 仍 fail-closed，实际错误分别 json_codec_invalid / snapshot_closed；旧 regex 要求 row_invalid。不是成功读出坏行。
- 证据：`backend/app/gameplay/event_store.py:58`；`backend/app/gameplay/event_store.py:944`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F058 · 已知缺陷

`tests/test_infra_package_declared_negotiated_exchange.py::test_package_exchange_rejects_corrupt_receipt_event_reference`

- 错误：`AssertionError`；阶段：`call`。
- 根因：测试向已提交 receipt 插入 missing:event 后精确重试仍 committed=true。Economy duplicate 仅校验 digest 并 get_by_idempotency 后直接返回，未验证事件引用。旧缺陷文档“已修复”不能覆盖本 HEAD 实测。
- 证据：`backend/tests/test_infra_package_declared_negotiated_exchange.py:343`；`backend/app/gameplay/economy_runtime.py:1269`；`../05-基线缺陷-幂等回放未校验.md`。
- 阶段门：B1：直接影响幂等收据/事件引用；按规格明确阻塞 G1，须独立缺陷轨道修复并重新建立基线。

### F059 · 测试过时

`tests/test_interaction_orchestration_runtime_service.py::test_mixed_path_calls_semantic_and_physical_then_merges_one_unified_result_family`

- 错误：`AssertionError`；阶段：`call`。
- 根因：旧 fixture 的 obj_box 未注册到当前 ESM 语义 authority；先 unsupported_object，再 semantic_authority_required，未进入断言所期待的旧物理交互路径。
- 证据：`backend/tests/test_esm_physical_channel_runtime.py`；`backend/tests/test_interaction_orchestration_runtime_service.py`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F060 · 测试过时

`tests/test_interaction_orchestration_runtime_service.py::test_interaction_orchestration_carries_advisory_skill_metadata_without_changing_authority_status`

- 错误：`AssertionError`；阶段：`call`。
- 根因：旧 fixture 的 obj_box 未注册到当前 ESM 语义 authority；先 unsupported_object，再 semantic_authority_required，未进入断言所期待的旧物理交互路径。
- 证据：`backend/tests/test_esm_physical_channel_runtime.py`；`backend/tests/test_interaction_orchestration_runtime_service.py`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F061 · 测试过时

`tests/test_inventory_cadence_revocation_commit.py::test_original_admitted_cadence_reaches_inventory_and_replays_without_write`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture read_set.temporal_pins={}，授权结算窗口当前要求 timeline_id。三项均先 settlement_window_invalid，append/撤权/race hook 尚未到达；需补齐时间上下文再验证原断言。
- 证据：`backend/app/population_continuity/inventory_owner_adapter.py:53`；`backend/app/population_continuity/inventory_owner_adapter.py:117`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F062 · 测试过时

`tests/test_inventory_cadence_revocation_commit.py::test_revocation_between_admission_check_and_inventory_append_is_zero_write[False]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture read_set.temporal_pins={}，授权结算窗口当前要求 timeline_id。三项均先 settlement_window_invalid，append/撤权/race hook 尚未到达；需补齐时间上下文再验证原断言。
- 证据：`backend/app/population_continuity/inventory_owner_adapter.py:53`；`backend/app/population_continuity/inventory_owner_adapter.py:117`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F063 · 测试过时

`tests/test_inventory_cadence_revocation_commit.py::test_revocation_between_admission_check_and_inventory_append_is_zero_write[True]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture read_set.temporal_pins={}，授权结算窗口当前要求 timeline_id。三项均先 settlement_window_invalid，append/撤权/race hook 尚未到达；需补齐时间上下文再验证原断言。
- 证据：`backend/app/population_continuity/inventory_owner_adapter.py:53`；`backend/app/population_continuity/inventory_owner_adapter.py:117`；`diagnostic-probes.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F064 · 测试过时

`tests/test_mind_frame_turn_boundary.py::test_legacy_diagnostic_frame_still_prepares_without_canonical_turn`

- 错误：`ValueError`；阶段：`call`。
- 根因：测试要求 legacy 消费，但 gateway 当前强制 frame_digest 与 turn_id；旧 payload 在绑定边界被拒绝。
- 证据：`backend/tests/test_mind_frame_turn_boundary.py`；`backend/app/character_agent/gateway/model_gateway.py:55`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F065 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_preflight_replays_same_grant_and_blocks_competing_attempts`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F066 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_expired_abandoned_door_grant_releases_only_its_local_occupancy_reservation`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F067 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_outcome_commits_once_and_duplicate_replays_without_second_mutation`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F068 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_range_and_revision_failures_do_not_mutate_state`

- 错误：`AssertionError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F069 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_rejected_terminal_receives_settlement_without_object_mutation`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F070 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_grant_remains_valid_for_a_bounded_physical_approach`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F071 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_state_change_after_preflight_rejects_as_door_state_stale`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F072 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_changed_duplicate_digest_is_rejected_without_second_mutation`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F073 · 环境差异

`tests/test_obj_archive_door_embodied_authority.py::test_archive_door_settlement_is_ledger_correlated_and_receipt_pins_object_result`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F074 · 环境差异

`tests/test_obj_archive_door_embodied_websocket.py::test_archive_door_route_rejects_terminal_outcome_from_a_different_connection`

- 错误：`RuntimeError`；阶段：`call`。
- 根因：fixture 的可信启动凭证 issued_at=100/expires_at=200；连接入口用当前墙钟 observed_at，故 trusted_local_launch_expired，继而 controller_binding_required/command 拒绝。不是对象动作提交自身的失败。
- 证据：`backend/app/main.py:3483`；`backend/tests/test_obj_archive_door_embodied_authority.py`；`diagnostic-probes-v2.json`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F075 · 环境差异

`tests/test_p2dr_authored_bakery_authority_reclosure.py::test_p2dr_uses_existing_authored_counter_schedule_to_commit_procurement`

- 错误：`KeyError`；阶段：`call`。
- 根因：测试用仓库根相对路径；正式入口 cwd=backend，故 backend/app/main.py 变成 backend/backend/app/main.py，或 assets/characters/profiles 解析为空。真实根文件存在。
- 证据：`backend/tests/test_character_agent_runtime_persistence_wiring.py`；`backend/tests/test_p2dr_authored_bakery_authority_reclosure.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F076 · 已知缺陷

`tests/test_population_long_session_recovery.py::test_kernel_implementation_change_is_rejected_even_without_tail[functools-wraps]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：f1e18067 有意把源码指纹改为手工 kernel_version=v1+函数形状。functools.wraps 的实现变化不改 digest；相同 code 重新 FunctionType 丢 return annotation 却改 digest。已定位契约分歧：当前算法不等于测试要求的自动实现变更检测；不能未经决策称测试过时或承诺回放等价。
- 证据：`backend/app/population_continuity/recovery.py:20`；`backend/tests/test_population_long_session_recovery.py:140`；`git:f1e18067`。
- 阶段门：B4：恢复身份/投影兼容性契约分歧；G1 前独立决定语义版本责任并实证排除或修复，不把手工签名当自动行为等价证明。

### F077 · 已知缺陷

`tests/test_population_long_session_recovery.py::test_kernel_digest_is_stable_across_source_paths_and_newlines`

- 错误：`AssertionError`；阶段：`call`。
- 根因：f1e18067 有意把源码指纹改为手工 kernel_version=v1+函数形状。functools.wraps 的实现变化不改 digest；相同 code 重新 FunctionType 丢 return annotation 却改 digest。已定位契约分歧：当前算法不等于测试要求的自动实现变更检测；不能未经决策称测试过时或承诺回放等价。
- 证据：`backend/app/population_continuity/recovery.py:20`；`backend/tests/test_population_long_session_recovery.py:140`；`git:f1e18067`。
- 阶段门：B4：恢复身份/投影兼容性契约分歧；G1 前独立决定语义版本责任并实证排除或修复，不把手工签名当自动行为等价证明。

### F078 · 环境差异

`tests/test_population_transport_metrics.py::test_current_rss_tracks_released_mapping_instead_of_process_peak`

- 错误：`CalledProcessError`；阶段：`call`。
- 根因：子进程 PYTHONPATH 未包含正确根/测试路径。backend cwd 下再次 resolve backend 导致嵌套路径，或子进程无法导入 scripts.verification。失败在 import 阶段，未验证硬退出恢复。
- 证据：`backend/tests/test_character_cognition_admission.py:165`；`backend/tests/test_siming_admission.py:194`；`diagnostic-probes-v2.json`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F079 · 测试过时

`tests/test_runtime_asgi.py::test_bootstrap_preserves_excluded_settings_and_real_http_enrollment`

- 错误：`RuntimeProcessError`；阶段：`call`。
- 根因：fixture 把所有 exclude 字段赋为 controlled-test-value 字符串；新增 physics_contact_authority_secrets 是 dict[str,str]。父模型未赋值校验，子进程 Settings.model_validate_json 在启动前 dict_type 失败。
- 证据：`backend/tests/test_runtime_asgi.py:225`；`backend/app/services/runtime_process.py:585`；`diagnostic-additional.json`；`run1-full.log:11329`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F080 · 环境差异

`tests/test_siming_admission.py::test_process_exit_recovery_keeps_atomic_admission_and_stage[before_commit]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：子进程 PYTHONPATH 未包含正确根/测试路径。backend cwd 下再次 resolve backend 导致嵌套路径，或子进程无法导入 scripts.verification。失败在 import 阶段，未验证硬退出恢复。
- 证据：`backend/tests/test_character_cognition_admission.py:165`；`backend/tests/test_siming_admission.py:194`；`diagnostic-probes-v2.json`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F081 · 环境差异

`tests/test_siming_admission.py::test_process_exit_recovery_keeps_atomic_admission_and_stage[after_commit]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：子进程 PYTHONPATH 未包含正确根/测试路径。backend cwd 下再次 resolve backend 导致嵌套路径，或子进程无法导入 scripts.verification。失败在 import 阶段，未验证硬退出恢复。
- 证据：`backend/tests/test_character_cognition_admission.py:165`；`backend/tests/test_siming_admission.py:194`；`diagnostic-probes-v2.json`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F082 · 环境差异

`tests/test_siming_admission.py::test_process_exit_recovery_keeps_atomic_admission_and_stage[result_ready]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：子进程 PYTHONPATH 未包含正确根/测试路径。backend cwd 下再次 resolve backend 导致嵌套路径，或子进程无法导入 scripts.verification。失败在 import 阶段，未验证硬退出恢复。
- 证据：`backend/tests/test_character_cognition_admission.py:165`；`backend/tests/test_siming_admission.py:194`；`diagnostic-probes-v2.json`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F083 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_removed_letter_hides_visual_label_and_collision`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F084 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_unified_validation_scene_contains_heavenly_runtime_probe`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F085 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_staging_request_reaches_the_opt_in_godot_probe`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F086 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_probe_waits_for_backend_reconnect_before_triggering_the_post_restart_tick`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F087 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_probe_marks_restart_only_after_staging_request_is_observed`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F088 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_character_perception_forward_matches_godot_negative_z_front`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F089 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_headless_autotest_capture_advances_a_scene_frame`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F090 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_avoids_setup_move_round_trip`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F091 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_allows_online_decision_latency`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F092 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_requires_authoritative_destruction_and_one_matched_reaction`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F093 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_binds_the_explicit_observation_to_char_b`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F094 · 环境差异

`tests/test_siming_heavenly_godot_static.py::test_heavenly_live_scene_suppresses_controller_setup_perception`

- 错误：`FileNotFoundError`；阶段：`call`。
- 根因：测试按 repo cwd 打开 scripts/object/InteractiveObject.gd、scripts/autoload/BackendBridge.gd 和 scenes/integration 下资源；正式 backend cwd 不能定位，根目录真实文件存在。仅静态读取，没有 Godot/UE 运行验收。
- 证据：`backend/tests/test_siming_heavenly_godot_static.py`；`run1-full.log`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F095 · 环境差异

`tests/test_siming_llm_tls_context.py::test_sequential_posts_reuse_one_verified_context_but_close_each_client`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F096 · 环境差异

`tests/test_siming_llm_tls_context.py::test_concurrent_first_posts_construct_only_one_context`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F097 · 环境差异

`tests/test_siming_llm_tls_context.py::test_context_is_lazy_and_isolated_between_providers`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F098 · 环境差异

`tests/test_siming_llm_tls_context.py::test_failed_context_initialization_can_retry[missing]`

- 错误：`Failed`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F099 · 环境差异

`tests/test_siming_llm_tls_context.py::test_failed_context_initialization_can_retry[invalid]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F100 · 环境差异

`tests/test_siming_llm_tls_context.py::test_context_preserves_ca_environment_precedence[file_over_directory]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F101 · 环境差异

`tests/test_siming_llm_tls_context.py::test_context_preserves_ca_environment_precedence[directory]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F102 · 环境差异

`tests/test_siming_llm_tls_context.py::test_context_preserves_ca_environment_precedence[default]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F103 · 环境差异

`tests/test_siming_llm_tls_context.py::test_ca_environment_change_applies_when_provider_is_rebuilt`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F104 · 环境差异

`tests/test_siming_llm_tls_context.py::test_transport_errors_keep_context_and_close_temporary_client[timeout-SimingLlmProviderTimeout]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F105 · 环境差异

`tests/test_siming_llm_tls_context.py::test_transport_errors_keep_context_and_close_temporary_client[http-SimingLlmProviderError]`

- 错误：`AssertionError`；阶段：`call`。
- 根因：本机 httpx=0.27.2，CI constraints=0.28.1。旧版 create_ssl_context 走 SSLConfig/ssl.SSLContext，不走测试 monkeypatch 的 ssl.create_default_context，contexts/ca_options 始终为空；不存在 CA 文件的环境行为也不同。版本/观测点不兼容，不推断 TLS 不安全。
- 证据：`backend/ci-constraints.txt`；`backend/tests/test_siming_llm_tls_context.py:27`；`backend/app/services/siming_llm_provider.py:263`；`diagnostic-additional.json`；`C:/Anaconda3/Lib/site-packages/httpx/_config.py:51`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F106 · 测试过时

`tests/test_stormnight_action_loop.py::test_case_open_then_existing_p5_action_window_commits_on_same_store`

- 错误：`AssertionError`；阶段：`call`。
- 根因：0fc54364 明确把每窗口事件从 4 改为 5，增加 terminal_outcome_recorded；这些断言仍要求 head=4 或没有 terminal 事件。重试并未另增一个窗口。
- 证据：`backend/app/gameplay/p5/investigation_conflict.py:30`；`git:0fc543643367e98237545ffb09370753268badfd`；`backend/tests/test_3d_scripted_mystery_action_replay.py`。
- 阶段门：非 G1 共享机制直接阻断；保留失败，后续对应路径单独修复。

### F107 · 已知缺陷

`tests/test_ws_protocol.py::test_worktable_finish_use_requires_the_authority_committed_engaged_state`

- 错误：`ValueError`；阶段：`call`。
- 根因：main 旧 worktable finish-use 路径先输出结果/修改 occupancy 再直接调用 ESM commit_interaction_state；当前持久化 ESM 明确禁止该直接 setter，抛 esm_object_durable_settlement_required。接入路径与持久化权威不一致。
- 证据：`backend/app/main.py:6330`；`backend/app/main.py:6362`；`backend/app/services/esm_service.py:1224`；`backend/tests/test_ws_protocol.py:1433`。
- 阶段门：B3：对象提交/投影接入缺陷；G1 前独立修复或以边界实证排除，不可只改异常断言。

### F108 · 测试过时

`tests/test_ws_protocol.py::test_websocket_character_agent_execution_emits_scheduling_round_trace`

- 错误：`AssertionError`；阶段：`call`。
- 根因：旧 approach action_request_bundle 请求已被 social_spatial_owner 明确拒绝；只返回 accepted=false/legacy_social_spatial_source_unavailable 的 ack。测试仍固定接收 13 条消息而超时，未发生调度轮执行。
- 证据：`backend/app/main.py:5680`；`backend/tests/test_ws_protocol.py:1701`；`diagnostic-additional.json:ws_direct`。
- 阶段门：非 G1 共享机制直接阻断；更新请求契约后再验调度轨迹。
