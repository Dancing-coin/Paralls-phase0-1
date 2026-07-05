# 当前项目 Actor Scene Knowledge Lifecycle 实施计划

> 对应规格：
> [2026-07-02-current-project-actor-scene-knowledge-lifecycle-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-design.md)

**状态：** `implemented-and-verified`

**实际核对：** `actor-scene-knowledge-lifecycle` harness profile 已通过，报告为 `.harness/verification/actor-scene-knowledge-lifecycle-report.json`，覆盖 ASK store 隔离、revision/conflict/freshness/expiry、VLA advisory 主观知识和 active perception 闭环。

**目标：** 把现有角色 bundle ingestion 和 `ActorSceneKnowledgeEntry` 契约扩展为角色私有 knowledge store、主动感知闭环和冲突/新鲜度生命周期。

## 阶段 A：协议与 Store

目标文件建议：

- `backend/app/character_agent/reasoning/actor_scene_knowledge.py`
- `backend/tests/test_actor_scene_knowledge_runtime.py`

任务：

- [x] 定义 `ActorSceneKnowledgeStore`
- [x] 定义 revision/conflict/freshness/expiry 模型
- [x] 按 actor/session/scene 隔离 store
- [x] 支持 add/hit/revise/conflict/stale/expire

验收：

- 相同 subject 可修订而非覆盖
- 不同 actor store 不互通
- advisory entry 不可标记为 world truth

## 阶段 B：Bundle Ingestion 接线

目标文件建议：

- `backend/app/character_agent/reasoning/l1_perception.py`
- `backend/app/character_agent/runtime/runtime_loop.py`

任务：

- [x] 从 `CanonicalPerceptBundle` 生成 ASK update
- [x] 把 VLA advisory 写入主观知识
- [x] 把 L1 structured facts 作为高优先来源
- [x] 把 interaction failure / embodied failure 写入冲突或重查线索

验收：

- bundle ingestion 后可观察到 ASK entry/revision
- L1 与 VLA 冲突时 ASK 记录 conflict，不覆盖 L1

## 阶段 C：主动感知闭环

目标文件建议：

- `backend/app/character_agent/reasoning/active_perception.py`
- `backend/tests/test_actor_active_perception_loop.py`

任务：

- [x] 定义 `ActivePerceptionRequest`
- [x] 定义 `ActivePerceptionResult`
- [x] 从 stale/conflict/failure 生成 request
- [x] request 输出到 PQF 构造入口
- [x] `ActivePerceptionResult` 携带 source refs、freshness、confidence、conflict refs 和 failure reason
- [x] result 回写 ASK store，并生成 revision/conflict/resolve 记录

验收：

- expected target missing 可触发 recheck
- repeated reachability failure 可触发 new PQF
- request 不绕过 Godot/L1 provider refs
- `ActivePerceptionResult` 可证明来自 PQF/provider 链路，而不是手工旁路输入
- result 回写后可观察到 ASK entry revision 或 conflict resolution

## 阶段 D：Trace 与 Harness

目标文件建议：

- `scripts/verification/verify_actor_scene_knowledge_runtime.py`
- `.harness/profiles/actor-scene-knowledge-lifecycle.json`

任务：

- [x] 落 ASK store/update trace
- [x] 证明隔离、冲突、新鲜度、主动感知闭环
- [x] 接入 docs/harness

验证命令：

```bash
python -m pytest -q backend/tests/test_actor_scene_knowledge_runtime.py backend/tests/test_actor_active_perception_loop.py
python scripts/verification/verify_actor_scene_knowledge_runtime.py
python scripts/verification/harness.py --profile actor-scene-knowledge-lifecycle
```

## 完成定义

完成后应能说：

> 角色已有独立 Actor Scene Knowledge lifecycle store，能从 percept bundle、VLA advisory、L1 facts 和失败结果更新主观知识，并通过 active perception request 回到 PQF/provider 链路。
