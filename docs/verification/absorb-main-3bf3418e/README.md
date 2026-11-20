# absorb-main 基线 3bf3418e

记录的被测 HEAD：`3bf3418e404af69f98f367acdaa2a59c8d4cdb20`；本记录提交为其后续文档提交。Windows 11，Python 3.12.2：`D:\Temp\paralls-g0-py312\Scripts\python.exe`；`PYTHONPATH` 前置 `F:\codex-temp\paralls-merge-baseline-20261119-m\backend`，运行前 `app.__file__` 为该目录下 `app\__init__.py`。全量串行，使用 G0 `run_baseline.py`；M2 的独立 TEMP、输出和完整控制台日志位于 F 盘。四次环境、逐节点结果、失败原始堆栈、测试文件和节点清单、JUnit 与 P/G/M2 控制台日志在 [evidence.zip](evidence.zip)，SHA-256 `b2998db3af6c136cfb7593fb0856ae4c0150622a2a001e14a961ddcb873939c9`。M1 未捕获完整控制台日志，完整节点结果和 JUnit 已保留；M2 补采了完整日志。

| 运行 | 收集 | 通过 | 失败 | skipped | xfailed |
|---|---:|---:|---:|---:|---:|
| P `2cacbdd5` | 10101 | 10075 | 22 | 2 | 2 |
| G `49f52dd5` | 10180 | 10135 | 41 | 2 | 2 |
| M1 `3bf3418e` | 10392 | 10366 | 22 | 2 | 2 |
| M2 `3bf3418e` | 10392 | 10366 | 22 | 2 | 2 |

M1/M2 每个节点的全部阶段和状态相同，22 个 `(节点, 阶段, 错误类型)` 及 G0 规范化堆栈哈希均相同；无收集错误、运行期间源码哈希未变。M 的 22 项同样在 P/G 均失败，20 项哈希也相同。task45、task8 两项哈希随 worktree 路径变化；替换路径后原始堆栈相同，按节点+阶段+错误类型比较，不视作通过。G 的 19 项失败转通过列于下表，不计进度。

SQLite 两个节点在 P/G/M1/M2 均以 `concurrent WAL checkpoint requires SQLite 3.51.3+` 跳过；当前 SQLite 3.43.1，标为**环境未验证项**，不计通过。另两个节点四次均 xfail，原因是缺少命名 Life adapter。

## 失败集合

来源按 `(节点, 阶段, 错误类型)` 标注；哈希为 M2 的 G0 规范化堆栈 SHA-256。完整堆栈在压缩包。

| 节点 | 阶段 | 类型 | 来源 | 规范化堆栈哈希 |
|---|---|---|---|---|
| `tests/test_calibration_repair_contracts.py::test_all_22_repaired_budgets_equal_fixed_official_usage` | call | ModuleNotFoundError | 两者 | `c5fde2e3e760db6a7cd955a5cbb86569be2e951c2adb158fecd4a234898d6cd6` |
| `tests/test_character_agent_runtime_persistence_wiring.py::test_main_runtime_wires_character_storage_next_to_durable_graph` | call | FileNotFoundError | 两者 | `355d730b6a5e0c22cba5d8e0b8028ef6defd8bb04d33dccc4608a06fa993031d` |
| `tests/test_character_cognition_admission.py::test_child_admission_survives_process_exit_before_parent_receipt` | call | CalledProcessError | 两者 | `83c273f3da8d9c4e2d0047c5b75cfd2e0997202c1fd8ead52511ee7a89653572` |
| `tests/test_character_task45_behavior.py::test_task45_headless_probe_observes_shared_path_and_contact_contract` | call | AssertionError | 两者 | `0e5eab3393f7fb2d57fcab866830b55c183a508c91c53445c4a37f8e43e33520` |
| `tests/test_p2dr_authored_bakery_authority_reclosure.py::test_p2dr_uses_existing_authored_counter_schedule_to_commit_procurement` | call | KeyError | 两者 | `ee6e2bcf5b4df9823d4db3f10f2a055a1c2889fc4834cfb8d3ad828cf8824852` |
| `tests/test_population_transport_metrics.py::test_current_rss_tracks_released_mapping_instead_of_process_peak` | call | CalledProcessError | 两者 | `25c741199bf0ff3aeb6f12187de0c465cd8f1186c43253b7d90fb6983f1dc30c` |
| `tests/test_role_presentation_adapter_contract.py::test_task8_headless_registry_probe_resolves_profiles_and_blocks_rejected_registration` | call | AssertionError | 两者 | `7562de1e9c2d9d6c7312a6fa3bc34d5a233ec958fa9956543b673c428e967032` |
| `tests/test_siming_admission.py::test_process_exit_recovery_keeps_atomic_admission_and_stage[before_commit]` | call | AssertionError | 两者 | `b8a350d4e35c6c6e32cc453fcf290276d37d51188dfdeae19537ac61f6af0e49` |
| `tests/test_siming_admission.py::test_process_exit_recovery_keeps_atomic_admission_and_stage[after_commit]` | call | AssertionError | 两者 | `fbe2f1b213dbf32da7e323367e2016420a53876bb35b3ae78ffd84b68931ce11` |
| `tests/test_siming_admission.py::test_process_exit_recovery_keeps_atomic_admission_and_stage[result_ready]` | call | AssertionError | 两者 | `034c39be55208ed83d0c616e0a7f50df2b0780df871f46f0008c473330fbf18e` |
| `tests/test_siming_heavenly_godot_static.py::test_removed_letter_hides_visual_label_and_collision` | call | FileNotFoundError | 两者 | `ff7981ecfd809b288ca97dd913e5d4bd695c599a01e3ed5658b8120c9331f3e8` |
| `tests/test_siming_heavenly_godot_static.py::test_unified_validation_scene_contains_heavenly_runtime_probe` | call | FileNotFoundError | 两者 | `175cea5eab359cb1fdf7ec1dde4ebce037277c707a4eb1eb4b2c72a3aa19947d` |
| `tests/test_siming_heavenly_godot_static.py::test_staging_request_reaches_the_opt_in_godot_probe` | call | FileNotFoundError | 两者 | `d78e73c3aee2b1d5672165d36560d36cf7faa3a3aefba5c23c31b9a352e348ac` |
| `tests/test_siming_heavenly_godot_static.py::test_probe_waits_for_backend_reconnect_before_triggering_the_post_restart_tick` | call | FileNotFoundError | 两者 | `919a836179f02f9e85cf128cbed7e73c9dc6178c689642148972bad8bd972902` |
| `tests/test_siming_heavenly_godot_static.py::test_probe_marks_restart_only_after_staging_request_is_observed` | call | FileNotFoundError | 两者 | `6bc8e578b5e86fa977643b3b9226f08a04241d249228f647dc460fa9a02ecb26` |
| `tests/test_siming_heavenly_godot_static.py::test_character_perception_forward_matches_godot_negative_z_front` | call | FileNotFoundError | 两者 | `e721460db7b78fd4e64656506598ff4338932e90523781ea57abf78b50627a8d` |
| `tests/test_siming_heavenly_godot_static.py::test_headless_autotest_capture_advances_a_scene_frame` | call | FileNotFoundError | 两者 | `f3820ee2fd510bcbdf77ecc1874e7b17e85cc608013fd19ca8de4a177e300004` |
| `tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_avoids_setup_move_round_trip` | call | FileNotFoundError | 两者 | `2e7d94e74a8ce28d1c3b0f97269c4428c53ea2daec02df2a68fbaa94b74cc983` |
| `tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_allows_online_decision_latency` | call | FileNotFoundError | 两者 | `32be942f694353b7b651db0f5c84e2b8eecbf24e1fb1bfcce6f12fddba2c50bd` |
| `tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_requires_authoritative_destruction_and_one_matched_reaction` | call | FileNotFoundError | 两者 | `7c3d5e5640db31fc67f5d307eff7e2aa31bd118b74fe14611def61c07cea197d` |
| `tests/test_siming_heavenly_godot_static.py::test_heavenly_probe_binds_the_explicit_observation_to_char_b` | call | FileNotFoundError | 两者 | `e4e001b5e26c732b7a053349468b07251b9aa9a3f7a511501c88080b2e635ca3` |
| `tests/test_siming_heavenly_godot_static.py::test_heavenly_live_scene_suppresses_controller_setup_perception` | call | FileNotFoundError | 两者 | `0a98c30658b015b4baccccdcc787e384711dc3d82c192b09b52b2c55cc453e11` |

## 合同选择

- `get_event` 的 closed 与损坏 JSON 单行读取使用 `gameplay_snapshot_row_invalid`，保留原始 `__cause__`；批量读取保留细分。依据 main `05568fdc`、`be6225cb` 及基线测试，本次 `8d426b5f`、`3bf3418e`。
- 普通 action window 写四类事件，不写终局事件。依据 main `36a2f928`，测试对齐 `94f6fa1a`；终局归具名 Owner 的设计尚缺生产写入路径，见下。
- 未登记事件类型映射 `None`。依据 main `2dc10780` 的 FactType registry 和用户裁决；仅已登记 schema 的名称第二段用作当前域命名。

## 已知缺口

1. `gameplay.conflict.terminal_outcome_recorded` 在当前生产代码未发现写入者，相关读取方由测试夹具驱动；归司命线，非此次迁移引入。来源提交：main `36a2f928`（2026-11-09，从普通窗口移除该事件）。核对命令 `rg -n "terminal_outcome_recorded" backend/app/gameplay/p5 backend/app/gameplay`：命中 action graph 允许集合、schema 注册及读取校验，未命中构造该事件的写入点。
2. `FACT_TYPE_REGISTRY` 对已登记事件从 schema 名第二段取域，与 v2 Owner 登记命名不同；main 的 `app.models.fact_type` 与 G3 的 `app.gameplay.fact_type_registry` 是不同机制。它不向未登记名称猜测域。来源提交：main `2dc10780`（2026-11-09，FactType registry 替换字符串订阅）。

## 五组冻结选集

- [ownership.json](ownership.json)：24 节点；对应 `ownership-nodeids.txt`。
- [modifier.json](modifier.json)：12 节点；对应 `modifier-nodeids.txt`。
- [equipment.json](equipment.json)：87 节点；对应 `equipment-nodeids.txt`。
- [inventory.json](inventory.json)：56 节点；对应 `inventory-nodeids.txt`。
- [shared-replay.json](shared-replay.json)：990 节点；对应 `shared-replay-nodeids.txt`。

五组可重叠：保留原五组节点；按关键词吸收 G3 修改测试文件中的对应域节点，公共组还包含 G3 修改测试文件的所有 905 个 M 收集节点（含改名后的 credential 测试）。这是一份明示扩展的保守选集，不把重叠计为唯一节点。旧 39 项不再作为判据。

以下示例使用 Python 3.12.2，输出目录必须不存在；比较脚本按 40 个节点串行分批调用 G0 runner，校验收集、状态与失败阶段/错误类型，保留每批日志、JUnit 和结果；失败转通过单独报告。将 `ownership` 换成任一组名即可：

```powershell
& D:\Temp\paralls-g0-py312\Scripts\python.exe docs/verification/absorb-main-3bf3418e/compare_selection.py `
  --repo F:\codex-temp\paralls-merge-baseline-20261119-m `
  --selection docs/verification/absorb-main-3bf3418e/ownership.json `
  --output F:\codex-temp\selection-ownership-NEW
```

## G 失败、M 通过的 19 节点

| 节点 | 分类和证据 |
|---|---|
| `tests/test_calibration_preclosure.py::test_offline_wire_preserves_unknowns_targets_and_source_memory` | 意外修复：main 增加诊断候选许可处理，G 为 frozen candidates 缺失。 |
| `tests/test_character_agent_runtime.py::test_character_agent_runtime_player_suggestion_path_uses_continuity_floor_under_local_only_planner` | 意外修复：main c8102d4a 调整 continuity floor 建议意图映射，G 的 observe_target 与断言不符。 |
| `tests/test_character_development_runner.py::test_runner_rejects_changed_wire_and_truth_before_any_provider_call` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_development_runner.py::test_runner_uses_real_adapter_mapping_and_flushes_diagnostic_only_results` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_development_runner.py::test_runner_preserves_rejected_real_response_and_does_not_grade_it` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_development_runner.py::test_runner_stops_changed_input_version_and_retains_already_issued_call` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_preparation_materializes_frozen_frames_and_independent_reference_universe` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_model_input_never_contains_grading_answers` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_final_and_independent_holdout_remain_unopened` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_same_authority_trajectory_cannot_cross_splits` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_missing_or_hidden_targets_cannot_receive_fixture_admission` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_abo_projection_does_not_inherit_runtime_numeric_defaults` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_reference_universe_detects_compiler_omission` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_fixture_profiles_have_source_evidence_without_abo_defaults` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_authored_profile_reaches_shared_wire_without_private_backbone` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_preparation_is_repeatable_and_full_wire_matches_runtime_serializer` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_character_evaluation_preparation.py::test_empty_development_selection_cannot_claim_ready` | 其他：main e25faa6c 更新评测 source pin；旧 G 因 char_a source_changed 提前失败，M 通过；这是测试来源数据变化。 |
| `tests/test_mind_frame_turn_boundary.py::test_legacy_diagnostic_frame_still_prepares_without_canonical_turn` | 意外修复：main f80352da、ca34a82a 接受未绑定诊断 frame，G 因 gateway requires a frozen mind frame 失败。 |
| `tests/test_ws_protocol.py::test_websocket_character_agent_execution_emits_scheduling_round_trace` | 其他：main 3f6768ca 更新 WS 测试为绑定协议和 barrier；G 为接收超时，属于测试合同变化，不能断言运行环境原因。 |

## 两边都改过但 Git 未报冲突的文件

以下为相对 `5321266d` 的路径、两侧增删行数和每个 diff hunk 所在上下文；完整机器可读摘要也在 [unconflicted-diff-summary.txt](unconflicted-diff-summary.txt)。其中 `test_fact_type_registry.py` 在 G3 后续提交改名，M 保留两侧不同测试。

| 文件 | main 改动 | G3 改动 |
|---|---|---|
| `backend/app/character_agent/planning/l3_planner.py` | 冻结 frame 的诊断兼容及校验 | 提供未解决张力条目 |
| `backend/app/character_agent/runtime/runtime_loop.py` | 适配认知入口签名及 frame 兼容 | 已知世界时间、记忆载入和延迟后物化收据 |
| `backend/app/gameplay/event_schema_registry.py` | 导出声明的 gameplay 事件类型 | 注册 social delivery v2 |
| `backend/app/main.py` | FactType 订阅、司命发布和运行时初始化调整 | 世界时钟、记忆和具身入口调整 |
| `backend/app/services/siming_population_capability.py` | 活动阶段扩为八值 | 记忆候选传递 world_ref |
| `backend/app/world_runtime/replay_checkpoint.py` | 按清单恢复 social authority | 支持 social delivery v2 回放 |
| `backend/tests/test_fact_type_registry.py` | 模型层事件 FactType 注册与过滤测试 | gameplay 凭证 FactType 注册与状态机测试，后续改名保留 |
| `backend/tests/test_verification_audit.py` | 更新玩家 motor 链夹具 | 增加 motor 链正例和两个 missing 反例 |
| `scripts/verification/CharacterAgentExecutionProbe.gd` | target_ref 规范化检查和角色调整 | 更新探针角色 |
| `scripts/verification/run_character_development_v4.py` | 诊断 cognition policy 输入调整 | 为诊断输入准备 recall |

```text

backend/app/character_agent/planning/l3_planner.py
main 16	3	backend/app/character_agent/planning/l3_planner.py
@@ -647,0 +648,15 @@ class CharacterAgentL3Service:
@@ -650,2 +664,0 @@ class CharacterAgentL3Service:
@@ -1836 +1849 @@ class CharacterAgentL3Service:
49f52dd5 2	0	backend/app/character_agent/planning/l3_planner.py
@@ -703,0 +704 @@ class CharacterAgentL3Service:
@@ -719,0 +721 @@ class CharacterAgentL3Service:

backend/app/character_agent/runtime/runtime_loop.py
main 9	5	backend/app/character_agent/runtime/runtime_loop.py
@@ -12,0 +13 @@ import json
@@ -753,2 +754,3 @@ class CharacterAgentRuntime:
@@ -823,3 +825,4 @@ class CharacterAgentRuntime:
@@ -2471,0 +2475 @@ class CharacterAgentRuntime:
49f52dd5 73	8	backend/app/character_agent/runtime/runtime_loop.py
@@ -163,0 +164 @@ class CharacterAgentRuntime:
@@ -189,0 +191 @@ class CharacterAgentRuntime:
@@ -1862 +1864,4 @@ class CharacterAgentRuntime:
@@ -1865 +1870 @@ class CharacterAgentRuntime:
@@ -1962,0 +1968,2 @@ class CharacterAgentRuntime:
@@ -2633,0 +2641,5 @@ class CharacterAgentRuntime:
@@ -2636,0 +2649 @@ class CharacterAgentRuntime:
@@ -2637,0 +2651,17 @@ class CharacterAgentRuntime:
@@ -2640 +2670,7 @@ class CharacterAgentRuntime:
@@ -2641,0 +2678,7 @@ class CharacterAgentRuntime:
@@ -2644 +2687 @@ class CharacterAgentRuntime:
@@ -2646,0 +2690,5 @@ class CharacterAgentRuntime:
@@ -2667 +2715 @@ class CharacterAgentRuntime:
@@ -2674 +2721,0 @@ class CharacterAgentRuntime:
@@ -2691,0 +2739 @@ class CharacterAgentRuntime:
@@ -2743,0 +2792,3 @@ class CharacterAgentRuntime:
@@ -2746 +2797 @@ class CharacterAgentRuntime:
@@ -2847,0 +2899,13 @@ class CharacterAgentRuntime:
@@ -2919 +2983 @@ class CharacterAgentRuntime:
@@ -2925,0 +2990 @@ class CharacterAgentRuntime:

backend/app/gameplay/event_schema_registry.py
main 13	0	backend/app/gameplay/event_schema_registry.py
@@ -412,0 +413,13 @@ def register_stormnight_scripted_mystery_event_schemas(registry: EventSchemaRegi
49f52dd5 5	0	backend/app/gameplay/event_schema_registry.py
@@ -51,0 +52,5 @@ SOCIAL_DELIVERY_EVENT_SCHEMAS = (

backend/app/main.py
main 74	45	backend/app/main.py
@@ -225,0 +226 @@ from app.services.siming_event_consumer import SimingEventConsumer
@@ -355,0 +357,27 @@ _siming_cognition_failure = None
@@ -395 +423 @@ def _build_siming_cognition(pipeline):
@@ -407 +435,3 @@ def _handle_siming_authority_event(event):
@@ -412 +442,3 @@ def _handle_siming_authority_event(event):
@@ -729 +761,7 @@ def _build_population_driver() -> PopulationCadenceDriver | None:
@@ -1649,0 +1688 @@ def _assemble_runtime_state(runtime_settings: Settings, cleanup: ExitStack) -> R
@@ -2216 +2255 @@ def _reset_runtime_state(*, restore_gameplay: bool = False) -> None:
@@ -2222,0 +2262 @@ def _reset_runtime_state(*, restore_gameplay: bool = False) -> None:
@@ -2229,14 +2269,14 @@ def _reset_runtime_state(*, restore_gameplay: bool = False) -> None:
@@ -2250 +2290 @@ def _reset_runtime_state(*, restore_gameplay: bool = False) -> None:
@@ -2283 +2323,2 @@ def _handle_siming_environment_request(event: AuthorityEvent) -> None:
@@ -2285,22 +2326,5 @@ def _handle_siming_environment_request(event: AuthorityEvent) -> None:
@@ -3182,0 +3207,2 @@ def _commit_configured_trusted_local_gameplay_mirror_live_probe(
@@ -3590,0 +3617,2 @@ async def websocket_endpoint(websocket: WebSocket) -> None:
@@ -5187 +5215 @@ def _handle_envelope(
@@ -8892,0 +8921 @@ def _publish_world_result_authority_event(
@@ -8902 +8931 @@ def _publish_world_result_authority_event(
49f52dd5 210	258	backend/app/main.py
@@ -320,0 +321,15 @@ durable_embodied_combat_adapter: DurableEmbodiedCombatAdapter | None = None
@@ -1488,0 +1504 @@ def _assemble_runtime_state(runtime_settings: Settings, cleanup: ExitStack) -> R
@@ -2110,0 +2127 @@ def _reset_runtime_state(*, restore_gameplay: bool = False) -> None:
@@ -3694,0 +3712,14 @@ async def websocket_endpoint(websocket: WebSocket) -> None:
@@ -5155 +5186 @@ def _handle_envelope(
@@ -5162,0 +5194,12 @@ def _handle_envelope(
@@ -6097,0 +6141,68 @@ def _handle_envelope(
@@ -6658,40 +6769,2 @@ def _handle_embodied_interaction_session_probe(envelope: Envelope) -> list[dict[
@@ -6702 +6775 @@ def _handle_embodied_interaction_session_probe(envelope: Envelope) -> list[dict[
@@ -6704,0 +6778 @@ def _handle_embodied_interaction_session_probe(envelope: Envelope) -> list[dict[
@@ -6738,46 +6812,15 @@ def _handle_unified_character_action_foundation_probe(envelope: Envelope) -> lis
@@ -6785,5 +6828,16 @@ def _handle_embodied_interaction_session_projection_pull(envelope: Envelope) ->
@@ -6792,45 +6846,25 @@ def _handle_embodied_interaction_session_projection_pull(envelope: Envelope) ->
@@ -6839,5 +6873,21 @@ def _embodied_session_event_envelope_from_authority_event(event: AuthorityEvent)
@@ -6845,3 +6895,2 @@ def _embodied_session_event_envelope_from_gameplay_event(event: object) -> dict[
@@ -6850,6 +6899,6 @@ def _embodied_session_event_envelope_from_gameplay_event(event: object) -> dict[
@@ -6857,29 +6905,0 @@ def _embodied_session_event_envelope_from_gameplay_event(event: object) -> dict[
@@ -6890,35 +6910,3 @@ def _handle_embodied_handoff_probe(envelope: Envelope) -> list[dict[str, object]
@@ -6929 +6917 @@ def _handle_embodied_handoff_probe(envelope: Envelope) -> list[dict[str, object]
@@ -6931,0 +6920 @@ def _handle_embodied_handoff_probe(envelope: Envelope) -> list[dict[str, object]
@@ -6934 +6922,0 @@ def _handle_embodied_handoff_probe(envelope: Envelope) -> list[dict[str, object]
@@ -6972,38 +6960,2 @@ def _handle_embodied_grab_carry_place_probe(envelope: Envelope) -> list[dict[str
@@ -7014 +6966 @@ def _handle_embodied_grab_carry_place_probe(envelope: Envelope) -> list[dict[str
@@ -7016,0 +6969 @@ def _handle_embodied_grab_carry_place_probe(envelope: Envelope) -> list[dict[str
@@ -7019 +6971,0 @@ def _handle_embodied_grab_carry_place_probe(envelope: Envelope) -> list[dict[str

backend/app/services/siming_population_capability.py
main 1	1	backend/app/services/siming_population_capability.py
@@ -324 +324 @@ class PopulationSimulationCapability:
49f52dd5 1	0	backend/app/services/siming_population_capability.py
@@ -1149,0 +1150 @@ class PopulationSimulationCapability:

backend/app/world_runtime/replay_checkpoint.py
main 6	0	backend/app/world_runtime/replay_checkpoint.py
@@ -307,0 +308,6 @@ def replay_scoped_tail(*, store, checkpoint_ref, tail, expected_result_digest=No
49f52dd5 1	0	backend/app/world_runtime/replay_checkpoint.py
@@ -118,0 +119 @@ def _replay_readable_event(event):

backend/tests/test_fact_type_registry.py
main 34	0	backend/tests/test_fact_type_registry.py
@@ -0,0 +1,34 @@
49f52dd5 57	0	backend/tests/test_fact_type_registry.py
@@ -0,0 +1,57 @@

backend/tests/test_verification_audit.py
main 3	3	backend/tests/test_verification_audit.py
@@ -832 +832 @@ def test_phase0_audit_proves_motor_owned_forward_and_patrol_motion_from_runtime_
@@ -834,2 +834,2 @@ def test_phase0_audit_proves_motor_owned_forward_and_patrol_motion_from_runtime_
49f52dd5 18	0	backend/tests/test_verification_audit.py
@@ -843,0 +844,18 @@ def test_phase0_audit_proves_motor_owned_forward_and_patrol_motion_from_runtime_

scripts/verification/CharacterAgentExecutionProbe.gd
main 15	4	scripts/verification/CharacterAgentExecutionProbe.gd
@@ -6,0 +7 @@ const ALL_CHECKS_COMPLETE_MARKER := "character_agent_execution_probe:all_checks_
@@ -24,0 +26,10 @@ func _run_probe() -> void:
@@ -81 +92 @@ func _run_probe() -> void:
@@ -86 +97 @@ func _run_probe() -> void:
@@ -99,2 +110,2 @@ func _run_probe() -> void:
49f52dd5 2	2	scripts/verification/CharacterAgentExecutionProbe.gd
@@ -81 +81 @@ func _run_probe() -> void:
@@ -86 +86 @@ func _run_probe() -> void:

scripts/verification/run_character_development_v4.py
main 2	1	scripts/verification/run_character_development_v4.py
@@ -120 +120 @@ def prepare_v4(*, repo: Path, reviewer_input: dict[str, Any]) -> dict[str, Any]:
@@ -121,0 +122 @@ def prepare_v4(*, repo: Path, reviewer_input: dict[str, Any]) -> dict[str, Any]:
49f52dd5 5	1	scripts/verification/run_character_development_v4.py
@@ -22,0 +23 @@ from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
@@ -107 +108,4 @@ def prepare_v4(*, repo: Path, reviewer_input: dict[str, Any]) -> dict[str, Any]:
```
