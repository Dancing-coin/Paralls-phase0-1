# M3-3 P5 Durable Replay Path Audit

## Snapshot and Method

- Snapshot: A branch at `4e71754fe3a4ffb9ab5a64009782b056f8c95d85`.
- Static-only review. No code or test changed for this audit.
- Python AST inventory searched P5 methods for `get_by_idempotency`, `get_idempotency_record`, and `replay_duplicate`. Raw inventory: `F:\paralls-verification\thread-a\m3-3-p5-current-tip-audit-20261128\p5-replay-lookup-inventory.txt`.
- Candidate methods were then traced into their called Owner method or replay helper.

## Candidate Adapters

| Method | Durable lookup use | Receipt validation path |
|---|---|---|
| `bakery_theft_slice._resolve_components` | Reads whether the Social idempotency record exists to normalize the composed result status. | Calls `SocialFactAuthority.resolve`, which validates duplicates through `replay_duplicate`; it does not return the looked-up record. |
| `social_delivery_caller._deliver_notice` | Allows an exact retry to reach the owner after the source advances. | Calls `SocialDeliveryAuthority.record_delivery`, which validates its duplicate through `replay_duplicate`. |
| `social_delivery_caller.deliver_bound_receiver_notice` | Allows an exact retry past the source-head freshness check. | Forwards to `_deliver_notice`, then `record_delivery` validates through `replay_duplicate`. |
| `social_knowledge._record_private_follow_on_generic` | Detects an existing key after deriving the target stream revisions. | Calls `_replay_private_follow_on_duplicate`, which validates the transaction, two ordered acknowledgment events, command/transaction identity, source notice, causation, and correlation through `replay_duplicate`. |

## Direct Replay Callers

AST inventory found direct `replay_duplicate` use in `InvestigationConflictAuthority.resolve_action_window`, `confirm_world_death`, `ScriptedMysteryCaseAuthority.resolve_outcome` and `_append_phase`, `SocialDeliveryAuthority.record_delivery` and `expire_delivery`, and the SocialFactAuthority handshake, milling acknowledgment, private follow-on, and `resolve` paths. The Stormnight realtime adapter now calls the helper before its legacy or frozen-request retry handling.

The A-owned migrated command paths in Credential, Ownership, LandRight, Holdings, Pool, and package migration also call `replay_duplicate`. The municipal drought-assessment certificate remains a custom settlement-plan path with separate incomplete-receipt validation and focused evidence in `docs/verification/m3-3-municipal-certificate-replay-20261127.md`.

## Limits

- This audit establishes static call routing for the inspected P5 package and A-owned migrated Owners. It does not prove all repository replay paths are R2-complete.
- Shared storage, common-boundary files, and other gameplay/runtime domains still contain direct/custom idempotency handling. They require separate ownership and contract classification.
- M3-3 remains in progress. No production Gate configuration, deployment, or integration status is implied.
