# 可配置群体名单与剧本导入 Implementation Plan

> **For agentic workers:** 使用 superpowers:subagent-driven-development 分工实施和复核；过程文档不得提交。

**Goal:** 居民数由配置名单决定，结构化角色表直接导入，自然语言剧本生成可审阅草稿。

**Architecture:** `PopulationRoster(actor_ids=...)` 是启动时读取的不可变名单，同一快照传给角色运行时和群体调度器。12 人仅为默认 JSON 样例。离线命令从角色表生成配置，或调用既有 NON_RUNTIME_MODEL 配置的模型生成带原文证据的草稿；显式导出草稿后才成为运行配置。

**Tech Stack:** Python 3.11+, Pydantic 2, argparse/json/urllib，沿用 pytest。

**Spec:** 本次会话用户确认：12 人不可写死；支持角色表直接导入和自然语言生成可审阅名单。司命/真相/人物记忆既有边界不变。

## 约束与接口

- `backend/app/population_continuity/roster.py`: `PopulationRoster`，`actor_ids: tuple[str, ...]`；非空、唯一、ID 为小写 ASCII 字母数字开头，后续允许小写字母数字、下划线、点、连字符、@。禁止引用前缀、路径分隔符和空白；禁止包含 actor_private 或以 private/branch 结尾，避免触发既有 scope 检查。
- `load_population_roster(path: str | Path | None = None) -> PopulationRoster`；默认 `backend/assets/population/default_roster.json`；相对路径按仓库根解析；配置错误直接报错。
- `Settings.population_roster_path` / `POPULATION_ROSTER_PATH`；运行时重启加载一次，停止/恢复调度不重读。
- `WorldContinuityRuntime(..., roster: PopulationRoster | None = None)` 使用传入名单，不增加居民、不限制人数为 12。
- 结构化 JSON 支持运行配置 `actor_ids`、现有剧本 `actor_refs`（移除 `character:` 前缀）、显式 `characters` 角色表（actor_id/name/aliases）。只取角色表，不挖掘剧情事实和隐私字段。
- 自然语言工具草稿包含角色 ID、姓名、别名、逐字原文依据、源文件散列；同名别名由模型合并、人审消歧。模型响应需 schema 校验和原文依据核对，不静默伪造离线结果。
- 工具提供 import / analyze / approve 命令；源文件和输出不得相同，已有文件不得静默覆盖；运行时拒绝草稿 schema。
- 新居民仅获 dormant continuity 身份，完整 CharacterProfile 另行配置；Godot 不在本轮验证范围。

## Task 1：名单与运行时接线

**Files:** roster.py、default_roster.json、config.py、main.py、world.py；test_population_roster.py、test_population_continuous_runtime.py。

- [x] 编写并运行失败用例：任意人数非空名单、重复/非法 ID 拒绝；自定义 2/17 人完成持续轮转，不补默认人。
  ```python
  assert PopulationRoster(actor_ids=('one', 'two')).actor_ids == ('one', 'two')
  ```
- [x] 实现名单加载，`runtime_state.population_roster` 同步给注册与驱动；默认名单移入 JSON。
  ```python
  roster = load_population_roster(runtime_settings.population_roster_path)
  # CharacterAgentRuntime 和 WorldContinuityRuntime 共用 roster.actor_ids。
  ```
- [x] 确认剧本中含 @1 的角色引用通过通用投影路径；修改现有只针对样例的测试名称和导入。
- [x] 运行名单、持续模拟、世界窗口、群体边界回归；审阅差异。

## Task 2：离线剧本工具

**Files:** tools/production/population_roster.py、backend/tests/test_population_roster_import.py、docs/population-roster.md。

- [x] 失败测试覆盖现有 stormnight_case_content() 角色表，保证四名角色完整导入且不读取 truth_facts。
  ```python
  assert len(import_roster(stormnight_case_content().model_dump(mode='json')).actor_ids) == 4
  ```
- [x] 实现结构化导入、自然语言模型草稿（校验来源和 JSON）、显式审核导出；复用 NON_RUNTIME_MODEL 设置，使用 stdlib HTTP，不耦合角色私有上下文。
- [x] 使用可控本地 HTTP/传输替身验证自然语言往返、错误响应、证据不在原文、草稿不能直接加载；不得调用真实付费端点进行测试。
- [x] 写明配置、JSON 角色表、三条 CLI 命令、重启生效及草稿人审方式；默认样例 12 人不是上限。

## Task 3：验证与交付

**Files:** .env.example、docs/INDEX.md、docs/harness.md、scripts/verification/verify_population_continuous_runtime.py。

- [x] 更新环境示例与 harness：默认 12 人是样例证据，同时记录自定义人数的覆盖，不以固定 12 为准入条件。
- [x] 运行聚焦测试、完整 `python -m pytest -v backend/tests`、`python scripts/verification/harness.py --profile all`；持久化 `.harness/verification/` 证据，缺 Godot 如实标记。
- [x] 独立代码复核并处理有效发现；最终差异排除所有 docs/superpowers 文件。

## 执行记录

- 用户已确认两类导入都支持；无需重复征询。
- Ruling: 首期仅重启加载配置，不做热更新；避免调度名单与角色注册名单不同步。
- Ruling: 无模型配置时 analyze 明确报错；不以启发式假装自然语言模型分析成功。
- Ruling: 独立复核证实大小写不同 ID 可混淆权限，scope 保留词可阻断整个批次；在配置入口提前拒绝，不放松权限边界。

- Verification: full backend 5148 passed; population-continuous-runtime 192 passed; actual stormnight JSON -> CLI -> runtime advanced all 4 actors.
- Verification: all profile passed docs/boundaries/drift/backend-contract/godot-project then stopped at missing Godot executable; Godot deferred as requested.
- Review: runtime reviewer and final reviewer approved, no unresolved findings; real provider remains unverified.
