# M1-1 Bond formal delta audit

## Attribute contract

The formal Bond specification in `docs/architecture-v2/02-原语/02-六原语规格.md` §4 defines a closed attribute set by Bond type: ownership `share`, custody `capacity`, authority `command_scope` and `delegable`, affiliation `rank` and `slot`, obligation `amount`, `unit`, and `due_tick`.

The A implementation's `_bond_attributes` in `backend/app/gameplay/ownership_runtime.py` validates value types, finite Decimals, and an eight-entry limit, but accepts arbitrary string keys. This matches the M1-1 task-card instruction to remove the key whitelist and normalize Decimal attributes, while differing from the external formal specification. The user-authorized implementation was retained. The formal document is read-only from this worktree, so this is an unresolved specification delta, not a runtime fix in this audit.

## Expiry lifecycle

The formal specification says world-clock expiry emits `bond.expired` at the expiration boundary. The implementation exposes `OwnershipAuthorityService.expire_bond` and filters expired bonds from `active_bonds` at a supplied tick. A repository search found no production caller of `expire_bond`; current production references are its definition and the Bond tests. Consequently, query-time visibility is implemented, while scheduled durable expiry is not demonstrated.

## Verification and disposition

- Static source review only. No tests ran.
- No code or external documentation changed.
- M1-1 remains pending gate review. Closing it requires reconciling the authorized open-key behavior with the formal closed-key schema, and wiring a world-clock expiry caller through an owned scheduler/Process path.
