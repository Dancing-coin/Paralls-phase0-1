# M6-5 Production Assembly Static Audit

## Scope

Read-only audit at A branch commit `195c2795d` of the M6-5 runtime assembly, trusted command outputs, reaction handlers, package loading, dispatch callers, and physical-input recovery. No source code or runtime behavior was changed by this audit, and no tests were run for it.

## Production Call Graph

| Concern | Evidence | Finding |
|---|---|---|
| Runtime construction | `backend/app/main.py:2002` | `build_m6_5_siege_runtime` is called during runtime assembly. |
| Trusted outputs | `backend/app/main.py:1994-1998` | Main registers outputs for `morale.refold`, `presence.reevaluate`, and `information.update_knowledge`. |
| Transaction dispatch | `backend/app/main.py:2230` | Committed transactions are sent to `m6_5_siege_runtime.after_transaction_dispatched`. |
| Morale handler | `backend/app/gameplay/m6_5_siege_runtime.py:347-349` | `morale.refold` is handled by `MoraleRefoldAuthority.refold_after_casualty`. |
| Presence handler | `backend/app/gameplay/m6_5_siege_runtime.py:350-355` | `presence.reevaluate` is handled by `PlacePassabilityAuthority.commit_assessment`. |
| Information handler | `backend/app/gameplay/m6_5_siege_runtime.py:357-364` | `information.update_knowledge` consumes committed delivery and authoritative world tick. |
| Conditions and packs | `backend/app/gameplay/m6_5_siege_runtime.py:320-341`, `367-371` | M6-5 and Information packs are loaded or resolved, and `facility_breach@1` is bound to `_is_breach_entry`. |
| Physical-input recovery | `backend/app/gameplay/m6_5_siege_runtime.py:213-269` | Startup scans durable signed Gate and Presence inputs and reconciles Facility/Place owner writes. |
| Obligation projection | `backend/app/gameplay/m6_5_siege_runtime.py:168-170` | `impact_gate_obligations()` rebuilds obligation state from stored evidence. |

## Remaining Runtime Gap

`impact_gate_obligations()` exposes a rebuilt projection, but no production caller dispatches or settles the formal durable obligation lifecycle. The existing recovery method reconciles signed physical inputs and Owner writes only. Therefore M6-5 production assembly for Gateway/L5, Morale/Presence/Information handlers, trusted outputs, package conditions, and physical-input recovery exists; formal `impact_gate` obligation execution and its restart recovery remain unimplemented. This audit does not establish production deployment, authoritative Gate values, live UE transport, or a complete siege run.

## Conclusion

Static-only. No test or runtime result is claimed.
