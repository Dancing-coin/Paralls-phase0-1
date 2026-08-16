# F0 Owner Map

状态：`reviewed baseline; no new owner introduced`

| 能力面 | 现有 owner | 现有写入/投影路径 | 证据入口 | 不能推导出的能力 |
| --- | --- | --- | --- | --- |
| 玩法事实与跨域结算 | Gameplay domain authorities | `GameplayCommandEnvelope` -> `SettlementPlan` -> `GameplayEventStore.append_batch()` | P1-P5 reports, `gameplay-foundation-event-spine` | 通用世界语义引擎 |
| 规则与玩法包 | `GameplayPatchRuntime` / `GameplayPatchLifecycleAuthority` | proposal evaluation; lifecycle events through append batch | `gameplay-patch-runtime-report.json`, patch tests | P6 完整 creator control plane |
| 关系、知识、隐私 | Character Core + `SocialFactAuthority` + scoped projections | social event streams and redacted recipient views | P5B/P5D reports, `backend/app/gameplay/p5/social_knowledge.py` | family simulator or social truth store |
| 具身呈现 | embodied authority + Godot mirror | authority result -> scoped mirror | embodied profiles, `godot-gameplay-mirror` | local presentation as world truth |
| 世界事实/ESM/司命 | `world_runtime`, ESM, Siming event path | high-level proposal/catalyst -> existing authority | boundaries/mainline evidence | Siming direct world write |
| 回放与证据 | `GameplayEventStore` replay + Harness | full/checkpoint-tail replay and generated reports | P1-P5 reports, `.harness/verification/` | total repository green claim |

## Owner rule

缺少 owner 的条目进入 `f0-gap-register.md`，不能通过新增一个并行 store、bus、clock、scheduler、NPC truth store 或 social truth store 来“补齐”。
