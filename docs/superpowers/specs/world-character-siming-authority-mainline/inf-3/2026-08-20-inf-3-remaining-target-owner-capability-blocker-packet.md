# INF-3 Remaining Target-Owner Capability Blocker Packet

Status: `INF-3W implemented narrow vertical; remaining target-owner capability rows remain blocked`

## Scope And Existing Boundary

This packet excludes the implemented narrow `weather:drought` weather-front
to Survival dehydration edge (`INF-3Q`) and exact project-visible drought front
to Government advisory edge (`INF-3R`). It reads only committed Ecology,
Survival, Construction, Organization, Economy, activation/population, and
other existing owner facts. It does not repeat owner discovery and does not
create an owner, router, consumer registry, generic fanout, compensation
authority, second runtime, or write path.

The later exact INF-3W `weather:rain -> unique damaged crop recovery` row is
also excluded from the remaining slots. Its owner-derived selector, fixed
policy, provenance partition, privacy, replay and idempotency rules are
specific to that row and cannot become a generic crop or weather resolver.

The existing finite weather-front map remains closed:

- Construction maintenance edge and fixed same-owner Construction fanout;
- Organization supply edge and fixed Organization supply fanout;
- Economy quote edge and fixed two-quote Economy fanout; and
- Survival dehydration edge for exactly `weather:drought`.
- Ecology unique damaged-crop recovery for exactly `weather:rain`.

`EcologyConsumerAdmissionCheck` is read-only. It validates an already admitted
contract; it cannot choose a target owner, construct a fragment, register a
consumer, or append. A weather front is therefore not itself a target-owner
capability, and a process-progress event is not a substitute weather front.

## Municipal Contract Does Not Admit Organization Work

The implemented municipal assessment Contract fixes the provider and receiver
organization parties only. It is not Organization work authorization: the
existing schedule/work-order owner additionally requires a committed recipient
character, membership, assignment, role, shift, operating window, work-order
identity, effective interval, and the relevant privacy/revision pins. Treating
the provider party as any of those facts would introduce a caller/default
binding. Therefore the Contract adds no new legal Organization consumer row.

## Disposition Summary

No new row can currently satisfy the required shape `committed source event or
state -> one exact target-owner outcome`. The three remaining slots below are
documented blockers, not formed candidates.

| Slot | Current status | Existing source fact | Exact target outcome | Owner-Admission Contract |
| --- | --- | --- | --- | --- |
| INF-3-SLOT-A: unlisted weather-front single edge | `owner-contract blocked` | project-visible `gameplay.ecology.weather_front.propagated@1` is committed, but no new source-to-target pairing is selected | missing | required before any edge work |
| INF-3-SLOT-B: drought process-progress substitute | `unimplemented` and `owner-contract blocked` | committed Ecology `drought_process_advanced` is a process-progress fact | prohibited as a substitute for the weather-front row; no target outcome | not admissible without a separate source/target decision |
| INF-3-SLOT-C: additional weather-front consumer/fanout | `owner-contract blocked` | committed weather-front source exists, and finite existing target rows are already occupied | missing; fanout is not a single edge | required for one exact single edge only; generic fanout is forbidden |

## INF-3-SLOT-A: Unlisted Weather-Front Single Edge

This is the only remaining shape with a committed source event that could be
read by a future target owner. It is not a candidate yet because the target
owner and exact outcome are not uniquely determined.

| Required field | Current fact or blocker |
| --- | --- |
| Source event / revision / privacy | Source must be one committed `gameplay.ecology.weather_front.propagated@1` event with its Ecology stream id, event revision, current stream head, `source_region_ref`, `target_region_ref`, `weather_ref`, and `project` visibility. The current repository does not select a new source/target row or source-specific policy beyond the finite admitted map. |
| Target owner | Missing. Existing Survival, Construction, Organization, and Economy owners cannot be selected by weather label or by the read-only C4 check. |
| Target projection / event | Missing exact target projection, event family, state/effect or business consequence, and write revision. No new target semantic may be inferred from `weather_front.propagated`. |
| Stream | Missing target stream and target subject binding. The source Ecology stream is read evidence only and must not become the target stream. |
| Idempotency | Missing an authority-derived key including the exact source event id/revision, target subject, target revision, and fixed contract revision. Caller-selected target coordinates are zero-write. |
| Receipt | Missing target-owner append-derived receipt fields. There is no Ecology/target shared receipt and no generic receipt factory for an unlisted edge. |
| Full/tail replay | Missing target-owner projection and replay reader. Full replay and checkpoint-plus-tail replay must agree for the exact target event vector; C4's read-only admission result is not a replay projection. |
| Zero-write cases | Unknown/unadmitted edge; missing or wrong source event; private source; stale/mismatched Ecology revision or stream head; wrong region/subject binding; missing target revision; caller-selected owner/stream/event/privacy/receipt; multiple target rows; and any fanout request must reject before target fragment construction or `append_batch()`. |
| Duplicate / revision / privacy semantics | Missing row-specific rules. Existing rows reject changed duplicates and stale revisions, but their keys/scopes cannot be reused. Public, authority-only, or caller-selected privacy is not a default. |
| Terminal / reversal / compensation | Missing. No expiry, retry, reversal, compensation, reopen, or no-compensation rule can be inferred from INF-3Q or another target row. |
| Minimum business approval | Name one target owner, one exact target outcome/event vector, source eligibility and subject binding, target stream/revision, privacy scope, owner-derived idempotency, append receipt, full/tail replay, and terminal/reversal/compensation semantics. Then admit one immutable row-specific contract. |

## INF-3-SLOT-B: Drought Process-Progress Substitute

The committed `gameplay.ecology.drought_process_advanced` event is an Ecology
process-progress fact. It cannot be relabeled as the weather-front source used
by INF-3Q, and no target-owner outcome follows from it in the current facts.

| Required field | Current fact or blocker |
| --- | --- |
| Source event / revision / privacy | A committed process-progress event may carry its Ecology stream/event revision and project visibility, but no approved source rule binds it to a Survival actor/region or any other target owner. |
| Target owner | Missing. Survival dehydration is explicitly not admissible from this event; no other existing owner contract accepts it. |
| Target projection / event | Missing exact consequence. Substituting it for weather-front dehydration would violate source provenance; inventing a new state, resource, construction, economy, or social outcome is prohibited. |
| Stream | Missing target stream and target subject binding. Ecology process stream remains Ecology-owned. |
| Idempotency | Missing target-owner key and source-bound digest. No process-progress key can be treated as the weather-front dehydration key. |
| Receipt | Missing. Process advancement has no target-owner append-derived receipt for an unlisted edge. |
| Full/tail replay | Ecology process replay exists for the process row, but no target-owner projection/replay exists. Process replay cannot prove a consumer outcome. |
| Zero-write cases | Any attempt to use `drought_process_advanced` as a weather-front substitute; missing target owner/outcome; wrong/private/stale source; caller-selected target coordinates; duplicate or revision conflict; and any fanout or compensation request must reject before target append. |
| Duplicate / revision / privacy semantics | Missing for a target row. The source process event's duplicate/revision behavior does not establish target-owner idempotency or target privacy. |
| Terminal / reversal / compensation | Missing. Ecology process lifecycle and Survival dehydration expiry are separate facts; no target reversal, reopen, or compensation may be inferred. |
| Minimum business approval | Explicitly approve a distinct process-progress source-to-target business outcome, its existing target owner, exact event/stream/revision/privacy vector, receipt/replay, idempotency, and terminal/reversal/compensation policy. Without that decision this slot remains zero-write, not a weather-front edge. |

## INF-3-SLOT-C: Additional Weather-Front Consumer Or Fanout

The repository contains committed weather-front events and several finite
target-owner rows, including same-owner two-target fanouts. Those facts do not
form a new row. A fanout is multiple target outcomes, while the requested
capability shape is one exact target-owner outcome.

| Required field | Current fact or blocker |
| --- | --- |
| Source event / revision / privacy | Only the exact project-visible `weather_front.propagated@1` source, source event revision, Ecology stream head, region binding, and source privacy can be reused as read evidence. No new source selection is implied. |
| Target owner | Missing for an additional edge. Existing Construction/Organization/Economy/Survival rows are closed and cannot be generalized or duplicated. |
| Target projection / event | Missing one exact target state/effect/business event and target write revision. A list of targets or a multi-target plan is not one outcome. |
| Stream | Missing one target stream and subject binding. Multi-stream or multi-target writes would be fanout and require a separate owner-local contract for each edge. |
| Idempotency | Missing single-edge authority key and changed-duplicate rule. A fanout key cannot be used for a single edge. |
| Receipt | Missing one target-owner append-derived receipt. No combined Ecology/fanout receipt is allowed. |
| Full/tail replay | Missing target-owner full/checkpoint-tail projection. Ecology propagation replay and the finite C4 admission check do not replay target truth. |
| Zero-write cases | Unknown additional target; finite catalog mismatch; missing/private/stale source or assignment; target revision conflict; multiple targets/fanout; caller-selected owner/stream/event/privacy/receipt; duplicate/change mismatch; and any compensation request reject before target append. |
| Duplicate / revision / privacy semantics | Missing for the new edge. Existing edge-specific keys, project scopes, and source/target revision fences cannot be copied into another target row. |
| Terminal / reversal / compensation | Missing. No additional edge may inherit no-compensation, expiry, retry, or fanout semantics from INF-3Q or another owner. |
| Minimum business approval | Select one existing target owner and one target outcome only, then approve its source/assignment pins, stream/event/revision, privacy, idempotency, append receipt, full/tail replay, and terminal/reversal/compensation rules. A generic consumer framework or fanout approval is not valid. |

## Durable Blocker And Integration Rule

The terminal INF-3Q existing-owner audit, the implemented INF-3R Government
advisory row, and the current finite owner-contract matrix are durable blocker
evidence. No fourth discovery is warranted. The
next admissible artifact is admission evidence for one explicitly named
source-to-one-target-owner outcome; until then all three slots remain
owner-contract blocked or unimplemented as shown above.

`weather_front.propagated` is committed source evidence only.\
`drought_process_advanced` is committed process-progress evidence only.\
Neither creates a consumer framework, router, fanout writer, compensation
path, or target-owner state transition. Unknown, multiple, unadmitted,
private/stale, binding-conflicting, revision-conflicting, duplicate, and
changed-duplicate requests remain zero-write before any target owner's
`GameplayEventStore.append_batch()`.

## Evidence Consulted

- `backend/app/gameplay/ecology_runtime.py`
- `backend/app/gameplay/ecology_consumer_admission.py`
- `backend/app/gameplay/ecology_consumer_contract_adapter.py`
- `backend/app/gameplay/survival_runtime.py`
- INF-3Q audit/design/plan and INF-C4 admission design
- INF-3L weather-front owner-contract matrix
- INF-3 candidate register and candidate plan
- current completion audit, remaining-scope dependency design, continuation
  checkpoint, and `docs/harness.md`
