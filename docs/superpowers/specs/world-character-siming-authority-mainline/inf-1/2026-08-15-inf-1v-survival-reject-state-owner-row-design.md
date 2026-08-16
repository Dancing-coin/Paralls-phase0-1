# INF-1V Survival Reject State Owner Row Design

Status: `blocked admission audit`

INF-1 requires the minimal `StateDefinition` add/replace/refresh/reject
closure to be real owner behavior, not merely an evaluator branch. The
prospective `effect:overload_exposure -> state:overloaded` row has no approved
contract and must remain zero-write. This audit closes the discovered
unregistered-row bypass in `SurvivalAuthority`.

| Concern | Contract |
| --- | --- |
| Current status | no owner row, stream/event/projection/receipt contract approved |
| Required behavior | semantic proposals reject before append with `survival_state_owner_mapping_unregistered`; existing owner-local maintenance remains governed by its existing obligations contract |

No application may emit an event. A future row requires an explicit existing
owner contract before any implementation begins.
