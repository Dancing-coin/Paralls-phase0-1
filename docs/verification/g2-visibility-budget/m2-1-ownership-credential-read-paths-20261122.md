# M2-1 Ownership 与 Credential 读取边界增量盘点

代码快照 `e349187e56be87b1df729cf807162657a886cff6`。沿用 [G2 读取路径盘点](g2-visibility-budget/read-path-inventory.md) 的主体与可信权威/恢复分类。覆盖 M1-1 涉及的读取链，其他域的全库计数沿用各自快照。

| 读取入口 | 分类 | 实际调用关系与授权证据 |
|---|---|---|
| `credential_runtime.py:192` `verify_right_holder_presentation` | 面向主体的决策接口 | 读取事件后重建 Credential、Inventory、Ownership，返回含凭证 ID、权利引用和拒绝原因的决策。参数 `presenter_ref` 表示被检查的主体。源码调用搜索只在测试中发现该公开方法的调用，生产认证及授权入口未核实。 |
| `land_right_runtime.py:126` `transfer` | 可信权威 | 一次读取事件快照，重建产权和凭证。第 154 行调用内部 `_verify_presentation_from_events`，判定结果用于拒绝或继续提交。调用链在 `adventure_basic_reference.py:802` 返回交易结果。 |
| `credential_reference_chain.py:97` `freeze_inputs` | 可信权威 | 第 143 行 `execute` 取冻结输入供 Resolver 决策，使用权益、凭证及持有者库存投影。投影值用于准备命令，入口返回提交结果。 |
| `credential_runtime.py:350`、第 419、456、623 行 | 可信权威 / 幂等恢复 | 授权提交前重建旧记录与当前投影。重复命令按原批次的事件 ID 查回提交凭据。 |
| `adventure_basic_closure.py:67` `capture_adventure_basic_closure` | 可信恢复 / 验证 | 从在线、全量重放和 checkpoint-tail 的事件序列构造领域 facade，核对 Ownership 与 Credential 投影的序列化结果。主体接收方未发现。 |
| `adventure_basic_reference.py:821`、第 1102 行 | 已知样例读取，应用去向未核实 | 样例公开方法直接返回 Ownership 投影。已搜索 Backend 入口与直接调用，未发现用于主体输出的生产证据。 |
| `fixed_offer_purchase.py:172`、第 263 行和 `gift_runtime.py:122` | 可信权威 | 发布交易、购买与赠与时重建 Ownership，检查卖方或赠与方的权利。此处只核对调用。 |
| `ownership_contract_debt_sample.py:103`、第 114 行 | 样例流程内部 | 从 Ownership 投影读取抵押物权利。其余域的生产下游留给对应迁移单元。 |

使用 `rg -n 'verify_right_holder_presentation|_verify_presentation_from_events|CredentialProjector\(|OwnershipProjector\(|CredentialReferenceChain\(|LandRightTransferAuthority\(' backend/app backend/tests scripts -g '*.py'` 枚举显式读者，并逐行阅读上表中的函数。动态调用与生产配置未核实。M2-2 的认证主体、资格解析、事件到可见性声明的映射及 `known_time` 仍待接入，见 H-A-005。此表为静态证据。

## 2026-11-26 M6-5 读取边界增量

本节以 A 分支 `3aa0ea31` 为代码快照，静态追加 M6-5 Information、Morale、Presence 路径。未运行测试，也不替代各域的 U7/`read_as` 验证。

| 读取入口 | 分类 | 实际调用关系与授权证据 |
|---|---|---|
| `InformationAuthority.publish_siege_report` | 可信权威 / 幂等恢复 | 校验签名、来源事件、source stream revision 与当前 head；精确重试通过持久幂等 receipt 取回原报告事件。报告事件和 delivery outbox audience 均限定 `actor:<recipient>`。该方法负责发布和投递，不提供主体查询入口。 |
| `InformationAuthority.update_knowledge` / `update_from_delivery` | 已提交事件触发的可信权威写入 | L5 handler 只在已提交 delivery 触发后执行；核对 recipient、delivery transaction receipt、report stream revision、当前可见 delivery 与知识流 revision 后提交 recipient 私有知识事实。`rg` 未发现生产主体读取该报告/知识事实的查询 API。 |
| `MoraleRefoldAuthority.refold_after_casualty` | 可信权威决策 / 回放恢复 | 按 casualty 的 `global_sequence` 读取 Organization garrison roster 和成员 LifeState 前缀，计算存活比例后写 Morale Pool；未知或无效输入拒绝写入。其 `projection` 方法在 `backend/app` 无调用点，源码调用搜索只命中测试。 |
| `PlacePassabilityAuthority.commit_assessment` 与 `state` | 可信权威输入校验 / 投影读取 | assessment 校验 Facility breach、可信证据事件、transaction Owner 与 revision；`state(gate_ref)` 从 Place stream 重建当前状态。`rg` 未发现生产主体读取调用，现有命中来自测试和 authority 内部恢复。 |

搜索依据：`rg -n 'morale\.projection|presence\.state|information\.view|information.*knowledge' backend/app backend/tests scripts`；并逐行检查 `information_runtime.py`、`morale_refold_runtime.py`、`place_passability_runtime.py` 与 `m6_5_siege_runtime.py`。这些新增路径当前属于可信权威/恢复或测试查询，不证明已经提供 `read_as(principal)` 主体读取能力。principal 资格解析、FactType visibility 授权和 `known_time` 仍由 M2-2 处理。

## 2026-11-26 current-tip M6-5 read-path classification

Code snapshot: A tip `ad6ef57cc575ff87b0daa86cfec1552d93a51942`. This is static call-graph evidence for the current M6-5 implementation. No tests were run.

| Read path | Classification | Evidence and scope |
|---|---|---|
| `InformationAuthority.publish_siege_report` (`information_runtime.py:118-267`) | Trusted signed publisher command and idempotent recovery | Validates authority signature, source event/stream/revision and report window. It reads the idempotency receipt to recover the original private report event, then publishes to `actor:<recipient>` and records delivery. `main.py:3069-3093` is a signed-input command route, not a report query route. |
| `InformationAuthority.update_from_delivery` / `update_knowledge` (`information_runtime.py:273-314`) | Trusted post-delivery Owner write | The L5 reaction handler at `m6_5_siege_runtime.py:357-363` runs on the committed delivery event. It checks delivery/report and recipient evidence before appending recipient-scoped knowledge. No production caller returns a subject's report or knowledge projection. |
| `MoraleRefoldAuthority.refold_after_casualty` (`morale_refold_runtime.py:71-155`) | Trusted Owner decision and historical replay input | Reads the committed death event, Organization roster and member LifeState histories at the death's `global_sequence`, then pins current source heads for the Morale Pool commit. The L5 handler at `m6_5_siege_runtime.py:347-349` is the production caller. `projection` at lines 157-164 has no production caller in `backend/app`; observed callers are tests. |
| `PlacePassabilityAuthority.commit_assessment` / `_commit_impact_assessment` (`place_passability_runtime.py:56-155,215-270`) | Trusted assessment validation and idempotent recovery | Resolves committed breach/impact and evidence events, checks transaction ownership and pinned source heads, then writes Place. Production entry points are the signed Presence route (`main.py:3053-3066`) and L5 reaction (`m6_5_siege_runtime.py:350-356`). The route returns the assessment receipt/result to its input caller. |
| `PlacePassabilityAuthority.state` (`place_passability_runtime.py:272-285`) | Owner-internal projection read | Rebuilds current passability to validate transitions. Callers are within the Presence authority; no subject-facing production read route was found. |

Searches covered `backend/app`, `backend/tests`, and `scripts` for the authority methods, report/knowledge routes, and `morale.projection` / `presence.state` callers. Information reports and knowledge are actor-scoped, and the inspected HTTP routes are input/write routes. No production principal-facing query for these three domains was identified in the inspected A call graph. This is a bounded static result, not proof about external callers. `read_as` enforcement, principal qualification, visibility-to-FactType mapping, and `known_time` remain M2-2 work.

## 2026-11-26 current-tip Ownership/Credential caller classification

Code snapshot: A tip `29976744c6b43a4f67c71c9fc2fa9196f3de4281`. Static search and direct-call tracing update the earlier `e349187e` snapshot classifications.

| Read path | Current classification | Evidence and scope |
|---|---|---|
| `CredentialPresentationValidator.verify_right_holder_presentation` (`credential_runtime.py:192-197`) | Candidate subject decision API; no production caller found | `rg -n verify_right_holder_presentation backend/app backend/tests` finds the definition and test callers only. It returns an authorization decision for a supplied `presenter_ref`, not a fact projection. |
| `LandRightTransferAuthority.transfer_title` (`land_right_runtime.py`) | Trusted Owner write precondition | The transfer path calls the validator's private `_verify_presentation_from_events` over its frozen event inputs, then uses the decision to accept or reject an Ownership write. Search found no production HTTP/Gateway route for this method in `main.py`; scenario invocation is in the sample facade. |
| `CredentialAuthorityService` (`credential_runtime.py:350,419`) | Trusted Owner command validation and idempotent replay | Reads are used to reconstruct credential links before issue/revoke writes. They do not expose event payloads to the requesting principal. |
| `OwnershipAuthorityService` methods (`ownership_runtime.py:356,372,413,469,553,632,685,768,891,972,1143,1216`) | Trusted Owner command validation, revision checks, and evidence resolution | Each read precedes a write or validates a source/contract. No production player-facing query endpoint was found in `main.py`. The municipal certificate path checks a fulfilled Contract before granting a right; package exchange checks the seller's current right. |
| `CredentialReferenceChain.freeze_inputs` (`credential_reference_chain.py:101`) | Trusted resolver input snapshot | Its production-in-module caller executes the declared resolver and uses the frozen Inventory/Credential/Ownership projections to prepare domain writes. It is not a principal query API. |
| `AdventureBasicScenario*.read_*` methods (`adventure_basic_reference.py`) | Sample/debug projections; not established as production reads | Ownership and Credential projection reads at lines 821 and 1102, and neighboring scenario snapshots, have direct callers in tests and `adventure_basic_closure.py`; no production `main.py` route or non-sample service caller was found. |
| `capture_adventure_basic_closure` (`adventure_basic_closure.py:82,87`) | Trusted replay/checkpoint verification | Compares live, full replay, and checkpoint-tail rebuilt projections. It is an evidence harness, not a subject output path. |
| `fixed_offer_purchase`, `gift_runtime`, `ownership_contract_debt_sample` | Trusted domain preconditions or sample-only | Purchase/gift writers verify the seller/donor right before append. The collateral reader is a sample flow and remains outside a production read claim. |

No Ownership/Credential production subject-facing query path was identified in the inspected A call graph. This does not establish that callers elsewhere cannot expose these results. The public validator remains an unconnected candidate interface, and any future production route must pass through a principal-aware boundary. The exact direct callers and unresolved deployment surface are static-only; M2-2 remains responsible for enforcement once the event-time and principal qualification contracts are available.

## 2026-11-27 M6-5 impact Pipeline read-path update

Code snapshot: A branch tip `2a46df6303228993161ccb9f02e1f789083b4134`. Static search covered `backend/app`, `backend/tests`, and `scripts` for `record_gate_impact_v2`, `record_presence_assessment`, `impact_gate_obligations`, `recover_physical_input_obligations`, and `impact_pipeline`.

| Read path | Classification | Evidence and scope |
|---|---|---|
| `M6_5SiegeRuntime._bind_impact_pipeline` and `_resolve_facility_layer` | Trusted Owner settlement input | Called from signed Gate-impact processing and durable recovery. It reconstructs the obligation snapshot from the authenticated impact event sequence, binds the compiled Pipeline to that four-stream revision vector, and evaluates the registered Facility resolver. `FacilityGateLayeredAuthority.apply_signed_impact` validates the plan against the signed impact and current Pool state before committing. |
| `M6_5SiegeRuntime._resolve_presence_assessment` | Trusted Presence settlement input | Called after signed Presence evidence is stored. It evaluates the registered Presence resolver; `PlacePassabilityAuthority` checks the plan's state and exact source events against the signed receipt before writing Place. A mismatch rejects without writing Place facts. |
| `M6_5SiegeRuntime.impact_gate_obligations` | Test projection API; no production caller found | Searches found calls only in M6-5 tests. It rebuilds obligation metadata and is not exposed by `main.py`. |
| `/api/v2/siege/gate-impact-input-v2`, `/api/v2/siege/presence-assessment-input` | Signed command ingress and result response | `SiegePhysicalInputAuthority` validates each receipt signature before storing it. The route invokes the corresponding Owner workflow and returns the input evidence and command result. These routes do not expose arbitrary Pipeline or obligation queries. |
| `recover_physical_input_obligations` at `main.py` startup | Trusted durable recovery | Reconciles committed signed inputs with idempotent Facility and Presence Owner receipts. It is not a subject-facing reader. |

No production principal-facing query for Pipeline or impact-gate obligation projections was found in the inspected call graph. This remains bounded static evidence and does not establish the absence of external callers. It does not implement `read_as`, principal qualification, visibility-to-FactType mapping, or `known_time`; those remain M2-2 work. No tests were run for this classification.

## 2026-11-27 current-tip shared-mechanism call-site update

Code snapshot: A tip `bc639342`. Static search covered `backend/app` and `backend/tests` for `OwnerCommitBuilder` and `StoreReadSnapshot`.

| Mechanism | Current production call sites | Classification |
|---|---|---|
| `OwnerCommitBuilder.build` | `credential_runtime.py:547`, `holdings_runtime.py:796`, `ownership_runtime.py:1269`, `pool_runtime.py:657` | Shared append-envelope construction after each domain has validated its own inputs. It does not select a principal, expose a projection, or choose FactType visibility. |
| `StoreReadSnapshot` | `credential_runtime.py:273`, `land_right_runtime.py:55` | Trusted Owner read snapshot used by Credential and LandRight validation/presentation paths. It supplies immutable event tuples to internal decision and write preparation code. |

The only non-production `StoreReadSnapshot` reference found was `backend/tests/test_owner_runtime_base.py`. `OwnerCommitBuilder` has its unit tests plus the four production domain call sites above. No subject-facing production query or `read_as(principal)` route was found in this increment. This is static call-graph evidence only. Principal qualification, selector semantics, FactType visibility mapping and `known_time` remain M2-2 work.

## 2026-11-27 current-tip Information subject-read update

Code snapshot: A tip `805ec4215db73eeba178b5fbefc90c44c09c55cd`. Static inspection covered `backend/app/main.py`, `backend/app/gameplay/read_as.py`, `backend/app/gameplay/information_runtime.py`, `backend/app/gameplay/m6_5_siege_runtime.py`, and related WebSocket/runtime tests.

| Read path | Current classification | Evidence and scope |
|---|---|---|
| WebSocket `information_report_read` (`main.py:5543-5589`) | Principal-facing, recipient-private report read through `GameplayReadAs` | Requires an active bound session, a request actor in `binding.allowed_actor_refs`, a live session lease, a non-future `as_of_tick` checked against `_session_world_clock_tick()`, and a configured M6-5 runtime. Calls `read_as` with `INFORMATION_REPORT_FACT_TYPE` and `report_ref`. The reader requires the registered Information-owned private FactType with exactly `recipient_of(subject)` and delegates to `InformationAuthority.read_report_for_recipient`, which checks the report and committed delivery chain as of the requested tick. |
| WebSocket `information_knowledge_read` (`main.py:5591-5637`) | Principal-facing, recipient-private knowledge read through `GameplayReadAs` | Applies the same binding, actor, lease, and authoritative-clock checks. Calls `read_as` with `INFORMATION_KNOWLEDGE_FACT_TYPE` and `report_event_id`. The reader applies the same narrow FactType contract and delegates to `InformationAuthority.read_knowledge_for_recipient`, which verifies the committed private report/delivery/knowledge chain as of the requested tick. |
| `GameplayReadAs.read_as` (`read_as.py`) | Narrow production read boundary for two registered Information FactTypes | Validates the principal/scope request, checks Owner, `private` visibility, the exact recipient selector, EventSchema mapping, and scope keys. It rejects unsupported delay/distortion models and `secret`/`debug_only`. Other FactTypes have no reader implementation through this boundary. |

These are production subject-facing reads for Information, contrary to the earlier snapshots that found none. They do not establish generic selector qualification or visibility execution. Ownership/Credential, Morale, and Presence remain without an identified principal-facing production read in the inspected call graph. Historical qualification for other selectors, FactType-wide visibility enforcement, legacy domain-stream attribution, other-owner reader classification, and complete U7 remain M2-2 work. This is bounded static call-graph evidence; tests were not run for this documentation update.

## 2026-11-27 current-tip Holdings and Pool caller update

Code snapshot: A tip `a3d347ff0495871faa29234ad16e0a0157ef9165`. Static searches covered `backend/app/gameplay/holdings_runtime.py`, `pool_runtime.py`, `facility_integrity_runtime.py`, `facility_gate_layered_runtime.py`, `morale_refold_runtime.py`, `main.py`, and tests for `HoldingsAuthorityService.project`, `_read`, `PoolProjector`, and production routes.

| Read path | Current classification | Evidence and scope |
|---|---|---|
| `HoldingsAuthorityService._read` (`holdings_runtime.py:721-726`) | Trusted Owner command preconditions | Called within Holdings mutations to rebuild the current FactType projection for revision, lot, reservation, quantity, and capacity checks. `HoldingsAuthorityService.project` (`:718-719`) has no production caller in `backend/app`; no subject-facing Holdings route was found in `main.py`. |
| `PoolAuthorityService._read` (`pool_runtime.py:593-596`) | Trusted Owner command preconditions | Called by Pool commands to validate current value, reservation, bounds, or threshold transitions before append. It is private to the authority and no production subject-facing Pool route was found in `main.py`. |
| `PoolProjector` in Facility and Morale | Trusted Owner settlement/rebuild input | Facility and Morale use the projector to validate or calculate domain-owned writes and historical recovery. These are not subject query APIs. Morale's public `projection` helper still has no production caller in `backend/app`; existing calls are tests. |

This closes the current A-side static classification for Holdings and Pool reads. It does not establish the absence of readers outside the inspected application tree and does not implement `read_as` for these domains. Future migrated subject-facing reads still need classification; generic selector qualification, FactType-wide visibility enforcement, legacy stream attribution, and full U7 remain M2-2 work. Static only; no tests ran.
