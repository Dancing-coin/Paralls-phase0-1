# Task 1 实现报告

状态：已完成（契约与聚焦测试已验证）。

实现内容：

- 新增冻结、禁止额外字段的群体 cadence/read-set、owner receipt、batch report、cycle result 契约。
- 新增角色模拟 seed、memory candidate、continuity command/receipt、memory materialization receipt 契约。
- `PopulationCadenceInput.from_authority_event` 支持结构化 cadence pin 校验，拒绝缺失、撤销、过期和 scope 不兼容输入。
- `PopulationReadSet.from_inputs` 对 projection 按 ref 排序并基于规范 JSON 生成稳定 SHA-256 摘要。
- `SimingInputType` 增加 `population_cadence_input`，未修改 event consumer。

边界：未修改 runtime orchestration、planner、CharacterAgentRuntime、activation 或 Harness profile；未引入第二 runtime/store/bus/clock/scheduler。

## Round 1 修复

- 恢复批准的 canonical cadence 字段：`cadence_id`、`world_mode_ref`、`world_mode_revision`、`cadence_source_ref`、`cadence_source_revision`；旧字段仅作为受控输入兼容，不改变 canonical 序列化。
- 在 cadence 模型校验前剥离 envelope scope，并对不匹配 scope 返回 `cadence_scope_incompatible`。
- 强制 cadence source pin 完整且 revision 合法；read-set 拒绝重复 projection ref。
- owner receipt、memory candidate、seed、continuity command/receipt 与 projection revision vectors 统一拒绝负数、布尔值和空 key。
- 新增 scope mismatch、重复 projection、非法 revision vector 回归测试。

修复验证命令与结果：

- `python -m pytest -q backend/tests/test_siming_population_contracts.py` -> 7 passed
- `python -m pytest -q backend/tests/test_population_continuity.py` -> 15 passed
- `git diff --check` -> passed

## Round 2 修复

- legacy `source_refs` / `source_revision_vector` 兼容解析现在严格要求单一 source ref、单一 revision key 且两者一致；不一致返回 `revision_vector_invalid`，缺失或数量不符返回 `cadence_source_pin_incomplete`。
- `PopulationCadenceInput.from_authority_event` 复制嵌套 cadence payload 后再剥离 envelope-only `scope`，重复解析 scope mismatch 不会修改原始事件。
- 新增 legacy source pin mismatch 与 repeated scope mismatch payload-preservation 回归测试。

修复验证命令与结果：

- `python -m pytest -q backend/tests/test_siming_population_contracts.py` -> 9 passed
- `python -m pytest -q backend/tests/test_population_continuity.py` -> 15 passed
- `git diff --check` -> passed
