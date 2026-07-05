# 当前项目感知输入对齐层实施计划

- 状态：`proposed`
- 日期：`2026-07-05`

上位设计：

- [2026-07-05-current-project-perception-input-alignment-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-perception-input-alignment-design.md)

## 1. 目标

在不强行合并 fact 链和 provider 链的前提下，引入统一输入时空 envelope，使两条链在输入阶段对齐，并为多角色私有视角分发建立共同基准。

完成后应能回答：

- 这一条 `CharacterPerceivedEvent` 和这一份 `CanonicalPerceptBundle` 是否属于同一拍输入？
- `char_a` 与 `char_b` 是否在同一 capture window 下各自拥有独立视角？
- `VLAProviderResult` 是否来自某次明确的输入 capture？

## 2. 非目标

- 不在本计划中重写 authority event bus
- 不在本计划中完成 full `L4 -> CharacterActor` 收敛
- 不在本计划中引入新的 live model provider
- 不在本计划中合并或删除全部 provider

## 3. 代码范围

预计涉及：

- `backend/app/world_runtime/intelligence_upgrade.py`
- `backend/app/world_runtime/l1_perception_frame.py`
- `backend/app/world_runtime/l1_runtime_perception_bridge.py`
- `backend/app/world_runtime/vla_provider.py`
- `backend/app/world_runtime/vla_percept_bridge.py`
- `backend/app/services/candidate_percept_service.py`
- `backend/app/services/per_character_percept_filter.py`
- `backend/app/character_agent/reasoning/actor_scene_knowledge.py`
- `backend/app/character_agent/reasoning/active_perception.py`
- `backend/app/services/siming_global_situation.py`
- 相应 tests / verification / docs

## 4. 实施阶段

### 阶段 1：定义统一输入对象

新增：

- `PerceptionInputFrame`

要求：

- schema 明确
- 带 `capture_id`
- 带时空和视角 ref
- 不承担 authority 语义

完成定义后先补 focused tests。

### 阶段 2：fact 链挂接 capture_id

让以下对象可追溯同一输入 capture：

- `RawFactEvent`
- `CandidatePerceptEvent`
- `CharacterPerceivedEvent`

要求：

- 不破坏当前 fact 路线主行为
- 兼容旧 payload / test fixture

### 阶段 3：provider 链挂接 capture_id

扩展：

- `SampleInputRef.runtime_source_refs`
- `PerceptionQueryFrame`
- `CanonicalPerceptBundle`

要求：

- Character 与 Siming 继续保持上下文隔离
- 不允许 `shared` namespace

### 阶段 4：bridge 升级

升级 `L1RuntimePerceptionBridge`：

- 由“单 actor assembler”转向“capture-aware assembler”
- 接收 `PerceptionInputFrame`
- 组装 Character / Siming 两侧 frame 和 bundle 时显式带上 `capture_id`

### 阶段 5：下游消费方接入

至少让以下模块识别并保留 `capture_id`：

- `ActorSceneKnowledge`
- `ActivePerceptionRequest / Result`
- `VLAProviderRequest / Result`
- `SimingGlobalSituationSnapshot`

### 阶段 6：验证与文档

补：

- focused backend tests
- runtime verification extension
- architecture docs and plan tree index

## 5. 具体验收点

### 5.1 数据模型

- [ ] `PerceptionInputFrame` schema 存在
- [ ] `capture_id` 是必填且稳定可追踪
- [ ] actor/camera/listener refs 字段存在

### 5.2 fact 链

- [ ] `CandidatePerceptEvent` 保留 `capture_id`
- [ ] `CharacterPerceivedEvent` 保留 `capture_id`
- [ ] 旧 fact route 测试不回退

### 5.3 provider 链

- [ ] `PQF` 保留 `capture_id`
- [ ] `CanonicalPerceptBundle` 保留 `capture_id`
- [ ] `VLAProviderRequest` 继承 `capture_id`

### 5.4 bridge

- [ ] bridge 在 Character / Siming frame 与 bundle 中保留同一 capture 身份
- [ ] 多角色调用至少能证明“同 capture window + 不同 actor context”

### 5.5 runtime verification

- [ ] 新增 focused verifier 或扩展 existing verifier
- [ ] 输出能证明同拍对齐与上下文隔离

## 6. 验证命令

最低要求：

```powershell
python -m pytest -q backend/tests
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile l1-world-fact-runtime
```

推荐新增 focused verifier：

```powershell
python scripts/verification/verify_perception_input_alignment.py
```

## 7. 风险

1. 旧 fixtures / tests 可能大量依赖当前无 `capture_id` 的 shape
2. `L1RuntimePerceptionBridge` 现状偏单 actor，升级后容易扩大 blast radius
3. 若直接把 `capture_id` 写进 authority 链，可能误伤现有边界，应仅限感知链和其下游感知消费对象

## 8. 执行建议

建议按最小风险顺序：

1. 先补 schema 与 unit tests
2. 再改 fact 链 payload
3. 再改 provider / PQF / bundle
4. 最后升级 bridge 与下游消费

不要一开始同时改：

- authority event bus
- projector
- ESM result family

这些不属于本计划的核心责任。
