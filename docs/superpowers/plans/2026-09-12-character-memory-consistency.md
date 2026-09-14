# 角色记忆一致性与受控纠正 Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本计划不要求并行子代理。

**Goal:** 让角色按照记忆能力和性格保留、核验、纠正自己的认知，并让司命能够按次申请受控的记忆修复；世界真相始终由原有权威负责。

**Architecture:** 在现有 Character Core、五池记忆、主动感知和版本存储上补齐闭环。普通核验只能使用角色实际获得的证据；司命修复由独立请求进入 Character Core，不能直接写五池。只处理当前角色、相关命题和明确请求，不新增全员轮询器。

**Tech Stack:** Python、Pydantic、现有事件/图存储、pytest、仓库 Harness；不增加依赖。

**Spec:** 本会话用户已批准的设计，见下方“已确认规则”；同时遵循 `docs/superpowers/specs/world-character-siming-authority-mainline/README.md` 和 `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-22-character-simulation-memory-seed-continuity-design.md` 的 Character Core 所有权、可见性和回放边界。当前用户对司命按次 Edit 的明确授权优先于旧文档的笼统禁止表述。

**Status:** 实施计划；尚未实现或验证下述新增功能。代码定位基于 2026-09-12 的 main。计划中的新增接口名称是拟议接口，不代表仓库已有能力。

## Global Constraints

- 世界的记忆在真相层，人物的记忆在记忆池；天道图谱是派生查询视图，不是新的权威。
- 真相冲突由权威结果裁定；角色不知道某件事，不影响它客观成立。
- 博闻强记保护已经获得的重要记忆，不赋予从未获得的知识；严谨影响核验倾向，两者独立。
- 观察、交流、查阅记录均必须有符合角色设定的获得过程；后台知道事实不能充当角色的证据。
- 司命直接纠正不常驻、不扫描全员；每次明确角色、记忆、原因、依据和授权。
- 修复更新有效认知并追加修订来源，保留历史经历；普通世界变化不自动改写人物记忆。
- 首版司命修复用于恢复已知事实或依据角色已获得的证据纠正；不扩展成任意植入秘密、抹除人格或虚构亲历。
- 首版以现有约十几人的群体为范围；本功能不扩展人数，不改群体调度主线。
- Godot 验证延期，不把后端通过描述为编辑器、具身感知或完整联调已通过。
- `docs/superpowers/` 仅本地使用，提交时必须排除；实施代码尽量合成一个便于审查的中文 commit。工作树集成使用 cherry-pick，推送按执行时的用户授权处理。

## 已确认规则如何成为验收行为

| 情形 | 处理与验收 |
| --- | --- |
| 9 点看见信在桌上，10 点信被移走 | 9 点的经历仍正确；未观察到变化的人可以暂时保留过时认知。不能静默获得 10 点的新位置。 |
| 针对同一对象、属性和有效时刻，角色获得互相排斥的证据 | 标记该命题待核验；严谨性影响行动选择，成功获取证据后再修订认知。 |
| 博闻强记者已亲眼看见信被毁，经过大量无关对话后又要使用它 | 先从本人的持久记忆找回依据；不能因为上下文截断而把信当作仍完好。 |
| 甲曾听乙说信还在，但后来获得信已被毁的可靠证据 | 保留“乙这样说过”的经历；修订“信现在还在”的信念，不把传闻当作客观状态。 |
| 权威记录与角色认知不同，但正确事实仍是秘密 | 世界结算服从权威；不给角色注入秘密，也不通过无来源的“你记错了”泄露秘密。 |
| 行动基于旧状态，实际执行时对象已失效 | 由权威拒绝并返回角色可获得的失败信息；失败触发核验，不回滚世界来迁就记忆。 |
| 司命修复重试、过期、越权或使用失效版本 | 同请求重试幂等；同键异载荷、越权、旧版本拒绝；不产生部分记忆更新。 |

## 当前实现基础与缺口

- `backend/app/character_agent/gateway/memory_recall.py`：默认每池 8 条、总预算 1200 个估算 token，裁剪的是模型上下文副本。这不是定时压缩持久记忆。
- `backend/app/character_agent/planning/l3_planner.py` 与 `gateway/model_gateway.py`：L3 先召回，网关再次按默认策略召回，必须防止角色专属预算被二次裁剪覆盖。
- `backend/app/character_agent/reasoning/actor_scene_knowledge.py`：已有来源、freshness、冲突、修订；当前冲突判定主要覆盖 L1/VLA 与失败信息，不是通用事实比较器。
- `backend/app/character_agent/reasoning/active_perception.py`：已有 conflict/stale 等触发和 PQF/provider 结果约束，可复用“再看一眼”。
- `backend/app/character_agent/models/knowledge_state.py`：已有 DISPUTED、ABANDONED 等知识状态；不另建重复枚举。上下文截断标记不属于知识真假状态。
- `backend/app/character_agent/runtime/runtime_loop.py`：continuity 支持 `supersedes` 和角色版本检查；当前 seed supersession 不等于通用有效记忆纠正。
- `backend/app/character_agent/storage/graph_memory_store.py`：已有历史版本与五池持久化；同时必须覆盖 `memory_store_router.py` 的轻量存储路径。
- `backend/app/services/siming_character_dispatch_adapter.py`：目前只接受 impulse/opportunity/fact_reveal，不能把它们直接当作 Edit 授权。

## Task 1：让“冲突”有结构化、带时间的判定

**Files:** 新建 `backend/app/character_agent/models/memory_consistency.py`；修改 `backend/app/character_agent/models/knowledge_memory.py`、`backend/app/character_agent/reasoning/actor_scene_knowledge.py` 及其写入/重建调用；测试 `backend/tests/test_character_memory_consistency.py`（新建）、`backend/tests/test_actor_scene_knowledge_runtime.py`。

**Interfaces:** 新增可选结构化命题 `MemoryFactClaim`，字段为 `scope_ref`（世界/分支）、`subject_ref`、`predicate`、`value`、`valid_at`、`source_ref`。首版使用有权威来源的对象位置、存在/损毁状态；历史自由文本不自动猜成结构化事实。新增纯比较函数 `compare_memory_claims(left, right)`，返回 `consistent | conflicted | not_comparable`。来源是否可信由调用方通过真实记录验证，纯函数不能代替授权或证据验证。

- [ ] 写表驱动失败测试：相同时间/对象/属性的不同值冲突；不同时间、分支、属性不直接比较；缺少结构化依据不臆断冲突。

```python
def test_claim_comparison_preserves_historical_observation():
    from app.character_agent.models.memory_consistency import MemoryFactClaim, compare_memory_claims
    old = MemoryFactClaim(scope_ref="world:main", subject_ref="obj_letter", predicate="location", value="desk", valid_at=9, source_ref="observation:9")
    moved = old.model_copy(update={"value": "drawer", "valid_at": 10, "source_ref": "observation:10"})
    contradiction = old.model_copy(update={"value": "drawer", "source_ref": "observation:other"})
    assert compare_memory_claims(old, moved) == "not_comparable"
    assert compare_memory_claims(old, contradiction) == "conflicted"
```

- [ ] 在 backend 执行 `python -m pytest tests/test_character_memory_consistency.py -v`，确认失败对应新增契约未实现。
- [ ] 加入最小结构化模型和比较逻辑；时间用世界有效时间，不能拿处理时间冒充。旧记录没有这些字段仍能加载；结构化字段必须贯穿事件标准化与图存储重建。

```python
def compare_memory_claims(left, right):
    key = lambda claim: (claim.scope_ref, claim.subject_ref, claim.predicate, claim.valid_at)
    if key(left) != key(right):
        return "not_comparable"
    return "consistent" if left.value == right.value else "conflicted"
```

- [ ] 把比较结果接到现有 ASK 冲突/修订及 KnowledgeState；未知、过时与矛盾分别处理。原有 VLA advisory 不能升级为世界真相。
- [ ] 运行上述测试及 `tests/test_actor_scene_knowledge_runtime.py`、`tests/test_character_graph_memory_store.py`。验收包含序列化/重启后仍能区分有效时间，不只验证纯函数。

## Task 2：按记忆能力召回，并消除 L3/网关二次裁剪

**Files:** 修改 `backend/app/character_agent/profile/models.py`、`gateway/memory_recall.py`、`gateway/model_gateway.py`、`planning/l3_planner.py`、`runtime/runtime_loop.py`；按实际调用补充 `storage/memory_store.py`、`storage/graph_memory_store.py`、`storage/memory_store_router.py` 的定向查询。测试复用 `backend/tests/test_character_memory_recall_policy.py`、`backend/tests/test_character_profile_models.py`、`backend/tests/test_character_graph_memory_routing.py`。

**Interfaces:** 在 `CapabilityConstraintLayer` 增加 `memory_retention: Literal["normal", "strong"] = "normal"`，明确表达能力。`CharacterMemoryRecallPolicy.select(memory, *, context)` 从有效 profile 解析策略；`CharacterModelGateway.prepare_run_request` / `run_task` 增加内部可选 `prepared_recall: MemoryRecallResult | None`，L3 传入同一召回结果，其他调用由网关统一选择。该对象由服务内部生成，不接受客户端或 LLM 自报“已验证”。

- [ ] 增加失败回归：相同已知经历、相同大量干扰记忆，strong 角色的当前目标关键事实始终进入最终模型请求；L3 局部决策与网关使用同一版本的事实。旧 profile 未声明字段时行为保持兼容。
- [ ] 执行 `python -m pytest tests/test_character_memory_recall_policy.py tests/test_character_profile_models.py -v`，确认新断言失败。
- [ ] 复用 `MemoryRecallResult` 贯通 L3/网关，不用一个自由布尔字段跳过所有检查。调用关系变为：

```python
# L3 内部：本地决策与模型共享本次选出的记忆。
recall = self._memory_recall_policy.select(normalized_memory_bundle, context=recall_context)
model_output = self._gateway.run_task(task_kind="l3_planning", context=model_context, prepared_recall=recall)
# 网关内部：只有未准备结果的调用才执行选择。
recall = prepared_recall if prepared_recall is not None else self._memory_recall.select(dict(context.get("memory", {}) or {}), context=context)
```

- [ ] normal 保留每池 8 条、总计 1200 估算 token；strong 首版以每池 16 条、总计 2400 估算 token 作为验证起点，优先保留当前命题的原始证据、来源和时间。这是待场景验证的内部预算，不是能力保证；不能只把 1200 改大就宣称“博闻强记”完成。
- [ ] 当前命题缺失时，运行时只向该角色自身存储作一次有界定向召回；按 subject/proposition/source 查询，不能用全世界真相补缺。超出预算时拆分检索或延后依赖该事实的决策，不能输出与已知关键事实相反的行动。记录缺失/截断与召回依据，保留持久记忆。
- [ ] 用真实网关请求捕获验证以下断言，并覆盖 light/graph 路由；重启后的强记角色仍找得到旧证据。

```python
assert "event:letter_destroyed" in {m["memory_id"] for m in request["context"]["memory"]["event_memories"]}
assert request["context"]["memory_recall"]["estimated_tokens"] <= request["context"]["memory_recall"]["token_budget"]
assert before_persisted_memories == after_persisted_memories
```

## Task 3：让角色通过正常行动核验和更新信念

**Files:** 修改 `backend/app/character_agent/reasoning/active_perception.py`、`planning/l3_planner.py`、`runtime/runtime_loop.py`、`storage/memory_store.py`；复用 `profile/personality_projection.py` 和 `memory/knowledge_memory.py`。测试 `backend/tests/test_actor_active_perception_loop.py`、`backend/tests/test_character_agent_runtime_memory_integration.py`。

**Interfaces:** 不增加独立核验调度器；现有 ASK 冲突/过时状态进入 L3，选择已有 observe/inspect_object/ask_probe 候选。严谨倾向使用现有 deliberation/analytical_control 等投影；记忆能力不替代性格。只有实际收到的感知结果、对话披露、获准查阅的内容能进入证据写回。

- [ ] 写失败用例：同一可见冲突下严谨角色更倾向核验；目标不可达时不能“看见”；对方未披露时不能“问出”；无权查阅时不能“读到”。
- [ ] 执行 `python -m pytest tests/test_actor_active_perception_loop.py tests/test_character_agent_runtime_memory_integration.py -v`，确认新增行为断言失败。
- [ ] 在现有候选打分与限制检查中接入冲突相关性、现有性格投影和行动可达性；保留必要的失败核验，不把强制权威约束变成性格可绕过的建议。复用 PQF/provider 路径，不能直接把后台权威状态包装成感知成功。
- [ ] 对话证据保留说话人及获知时间；记录证据要求实际可访问内容和结果来源。当前已核对入口不能证明“查阅记录”完整可用：实施时在相应对象权威交互中补最小读取结果；没有内容/权限/成功回执时返回不可用，不能用 inspect_object 名称冒充阅读完成。
- [ ] 成功证据由 Character Core 更新有效知识，旧经历保留；失败仍待核验。用以下场景断言验证，不能仅检查生成了一条核验意图。

```python
assert observed_result.provider_result_refs
assert updated_knowledge.source_event_id == received_evidence_id
assert updated_knowledge.proposition_key == original_knowledge.proposition_key
assert any(m.memory_id == original_event_memory_id for m in event_memories)
assert world_state_after_character_recheck == world_state_before_character_recheck
```

- [ ] 测试秘密事实完全没有进入角色输入；未激活角色只在收到合法经历或激活后更新，不由于后台诊断而提前知情。

## Task 4：司命按次申请纠正，由 Character Core 落账

**Files:** 在 Task 1 的 `backend/app/character_agent/models/memory_consistency.py` 增加请求/回执；修改 `backend/app/services/siming_character_dispatch_adapter.py`、`backend/app/character_agent/runtime/runtime_loop.py`、`backend/app/character_agent/storage/memory_store.py`、`backend/app/character_agent/storage/graph_memory_store.py` 及现有 continuity 持久化接线。测试新建 `backend/tests/test_character_memory_correction.py`，回归 `backend/tests/test_character_agent_seed_continuity.py`、`backend/tests/test_siming_character_dispatch_adapter.py`。

**Interfaces:** `MemoryCorrectionRequest` 包含 request_id、idempotency_key、actor_id、target_memory_refs、reason、source_refs、expected_character_revision、source_revision_vector、requested_at、expires_at。首版每次一个角色一个命题，修正内容从已验证的 source_refs 推导，不接受一段任意替换文本。`MemoryCorrectionReceipt` 包含 request_id、actor_id、status（applied/rejected）、reason、before_revision、after_revision、applied_memory_refs、source_refs。重试返回原回执。

运行时新增 `apply_memory_correction(request: MemoryCorrectionRequest, *, principal_ref: str) -> MemoryCorrectionReceipt`；principal_ref 由可信服务调用身份提供，再校验对应能力，不能从请求载荷复制。应用入口放在现有 Character Core runtime，不建立第二个记忆所有者。

- [ ] 增加失败测试：允许的已知记忆修复、无权限、过期、跨角色、缺失来源、秘密来源、旧角色版本、失效权威来源、同键异载荷、同请求重试和提交中断恢复。
- [ ] 执行 `python -m pytest tests/test_character_memory_correction.py -v`，确认新能力尚不存在导致失败。
- [ ] 单独识别 Edit 请求，与 catalyst/fact_reveal 路由区分；实际调用身份与有限范围权限来自服务端可信上下文，不能信任 payload 的 `authorized=true`。无授予时拒绝，执行一次后结束；不新增扫描任务。
- [ ] Character Core 按下列顺序执行；复用现有事件批次和版本检查，不直接复用“只看幂等键就接受”的捷径。

```text
校验请求形状、调用身份、目标范围和有效期
  -> 规范化完整请求并计算摘要
  -> 查询旧回执：同键同摘要返回；同键不同摘要拒绝
  -> 读取目标记忆与来源；确认时间、角色已知范围和来源版本
  -> 校验角色 expected revision；生成修订候选
  -> 原子提交修订事件、有效视图版本和回执依据
  -> 返回回执；图谱可从已提交事件重建
```

- [ ] 普通事件仍只能写正常经历，不能自称 memory correction 绕过上面的权限入口。修正标明后台纠正来源，不伪造角色从未有过的亲历事件。
- [ ] light 与 graph 两路从同一修订语义投影；图存储保留 supersedes 关系。验证旧经历存在、有效认知改变、世界权威不变，断电重启不出现“回执成功但记忆未生效”或反向情况。
- [ ] 在相关本地设计中明确旧禁止条款的狭窄例外：司命可请求 Edit，但实际五池写入仍归 Character Core；不扩大其他司命消息的权限。

## Task 5：用可回放场景证明功能，而非只证明接口存在

**Files:** 新建 `backend/tests/test_character_memory_consistency_flow.py`、`scripts/verification/verify_character_memory_consistency.py`、`.harness/profiles/character-memory-consistency.json`；更新 `docs/harness.md` 的后端能力与限制说明。沿用仓库 Harness 报告规范，不另建验收框架。

- [ ] 建立确定性后端场景：A 看见信在桌上；B 随后销毁信；A 尚未获知；A 的操作被权威拒绝；A 经合法感知或交流获知新事实并更新信念。再注入大量无关对话，强记 A 不再把已知被毁的信当成完好。
- [ ] 增加可查阅/不可查阅记录的证据对照、严谨/非严谨选择对照，以及单次 Siming 修复与重启重试。测试角色不得通过读取测试期望值获得事实，世界与角色两侧独立断言。
- [ ] `verify_character_memory_consistency.py` 调用该场景并输出源事件、核验行为、记忆版本、修复回执及隐私否定断言；新增 profile 的 `requires_godot` 必须为 `false`。
- [ ] 按顺序运行；每条失败均保留实际原因，不能用历史报告覆盖。

下面的 `python` 指可用的项目 Python 解释器。当前会话 PATH 中的 `python.exe` 指向失效的 WindowsApps 别名；执行前确认项目虚拟环境或实际解释器路径，不把命令未启动视为测试通过。

```powershell
# 工作目录：backend
python -m pytest tests/test_character_memory_consistency_flow.py tests/test_character_memory_correction.py -v
python -m pytest -v
# 工作目录：仓库根目录
python scripts/verification/harness.py --profile character-memory-consistency
python scripts/verification/harness.py --profile character-continuity-recovery
python scripts/verification/harness.py --profile siming-actor-memory-read
python scripts/verification/harness.py --profile all
git diff --check
```

- [ ] 若 all 因缺失 Godot 无法全绿，如实记录延期项；本阶段只报告后端验收，不宣称 Godot 或完整集成通过。新会话按本计划运行同一后端场景，有 Godot 时再补具身观察和可见反馈证据。
- [ ] 检查用户规则逐项有行为证据；提交仅显式列出本次运行时代码、测试和 Harness 文件，排除 `docs/superpowers/`。本次计划编写不创建新 Goal、不变更既有完成状态；后续按用户明确的执行/Goal 指令推进。

## 实施顺序与首个可交付结果

顺序为 Task 1 → Task 2 → Task 3 → Task 4 → Task 5。前三项先形成“记得住、会核验、能更新”的正常角色行为，再接入司命修复，避免自然纠错依赖天道反复介入。

首个可演示结果是信件场景在后端从世界结算到人物认知完整跑通。预算数字本身、supersedes 字段存在、提出核验意图或旧 Harness 通过，都不能单独作为本功能完成证据。
