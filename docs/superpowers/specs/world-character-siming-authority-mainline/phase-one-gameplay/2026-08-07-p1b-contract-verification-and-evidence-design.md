# P1B Contract Verification And Evidence Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose

为 [Gameplay Foundation Shared Contract Closure (P1A)](../character-gameplay-foundation/2026-08-07-gameplay-foundation-shared-contract-closure-design.md)
定义第一阶段正式的验证规格。P1B 是 evidence/ Harness package，不是新的 runtime、
authority、event store 或验证专用事实源。

## Dependencies

- P1A Gameplay Foundation Shared Contract Closure；
- existing Gameplay Foundation verification matrix；
- `GameplayEventStore`、replay、checkpoint、outbox、projection 和 Godot mirror；
- existing embodied interaction affordance/authority profiles。

## Verification Profiles

正式 plan 必须为下列 profile 选择稳定名称，并把生成物写入
`.harness/verification/`：

| Gate | Required proof | Required evidence |
| --- | --- | --- |
| P1B-G1 contract | identity、semantic、action/fact、Rule IR、reservation、settlement、profile、package、projection schema | contract report、schema fixtures、owner matrix |
| P1B-G2 generality | 两个结构不同的 contract fixture 复用同一 contract | cross-fixture trace、schema diff、owner diff |
| P1B-G3 reliability | success、failure、permission、stale revision、duplicate、zero-write | event batch、receipt、failure envelope、idempotency evidence |
| P1B-G4 replay | full replay 与 checkpoint+tail、projection rebuild、upcast | replay hashes、checkpoint metadata、migration log |
| P1B-G5 reservation | reserve、consume、release、expire、compensate 的幂等和冲突 | reservation lifecycle trace |
| P1B-G6 profile/revision | world profile 改粒度不改 canonical settlement；active revision 被固定 | session pin、digest、cross-profile replay |
| P1B-G7 package gate | dependency/schema/capability/compatibility/migration conflict fail closed | manifest validation report |
| P1B-G8 scope | actor、creator-debug、public、Godot view 过滤一致 | projection samples、redaction report |

## Required Contract Fixtures

### Fixture A: effect/resistance

输入为一个带材料/性质的实体和一个环境 effect。fixture 必须证明：

- SemanticSnapshot 使用固定 registry revision；
- resistance 被接受或拒绝时都有 deterministic trace；
- 失败不产生部分领域事件；
- creator-debug 能看 trace，但不能写 authority。

### Fixture B: object/ownership/action

输入为一个结构化 ActionIntent 和一个受审阅对象。fixture 必须证明：

- embodied adapter 只能提交 PhysicalFact；逻辑交互可以提交 LogicalFact；
- object、custody、ownership 和 action result 不互相复制 canonical truth；
- Godot 只消费 committed result；
- 重复 command 返回原 receipt。

这两个 fixture 不等同于两个完整玩法。P1C 只选择一个正式垂直样板。

## Failure And Replay Requirements

每个 profile 必须至少覆盖：

- unknown schema/version；
- missing dependency、schema conflict、capability conflict；
- stale expected revision；
- duplicate idempotency key 和 payload mismatch；
- unknown/expired/final reservation；
- disabled state group 的 hidden tick/write rejection；
- projection rebuild failure 不改变 event truth；
- checkpoint+tail 与 full replay hash 一致。

验证脚本不得从 projection 修复 event history，不得调用任意内容包代码作为 migration，
也不得把测试 fixture 当作 NPC 或生产世界状态。

## Acceptance

P1B 通过需要：

1. 所有 profile 的 focused tests 通过；
2. P1A 所有前置 foundation profiles 继续通过；
3. fresh JSON/MD reports、NDJSON traces 和 replay fixtures 存在；
4. 没有新增 store、bus、runtime、scheduler 或隐藏写入口；
5. P1C 可以只引用这些 contract，不再定义自己的事件/规则/回放协议。
