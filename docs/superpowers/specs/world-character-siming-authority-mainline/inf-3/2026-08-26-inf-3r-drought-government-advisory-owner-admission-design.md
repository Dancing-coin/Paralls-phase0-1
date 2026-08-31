# INF-3R Drought Front To Government Advisory Owner-Admission Contract

Status: `implemented narrow vertical; focused tests and independent Harness verified`

## Decision Record

### Product Objective

Make a committed, project-visible drought front legible as a jurisdiction-level
institutional response. The result is a project-scoped Government advisory
record and scoped outbox projection. A client presentation mapping remains a
separate delivery concern and is not claimed by this row. The advisory is an
evidence record, not an automated restriction or a hidden simulation
consequence.

### Alternatives Considered

| Candidate | Matrix disposition | Reason |
| --- | --- | --- |
| `run_finished -> inventory.output_received` | `duplicate_closed` | P1D already has the Construction completion and Inventory output-receipt partition. |
| Bakery aggregate sale/account posting | `duplicate_closed` | P1D already has the Economy sale/account partition. |
| delivery completion -> public social reputation | `conflict_rejected` | Project-scoped delivery evidence cannot widen into public Social facts; authority-only output would not provide the intended product loop. |
| drought front -> Government drought advisory | `new` | The advisory fact is unclaimed, project-visible, institutionally coherent, and has no economic, material, or population side effect. |

## Exact Row

```text
committed project-visible gameplay.ecology.weather_front.propagated@1
  where weather_ref = weather:drought
  and target_region_ref has a current exact Ecology region projection
  -> existing GovernmentAuthority
  -> gameplay.government.drought_advisory_issued@1
```

### Owned Fact

Government owns one historical, project-scoped advisory issuance fact:

```text
government drought advisory issued for jurisdiction_ref
because a committed drought front reached target_region_ref
```

The advisory is an immutable issued record. It does not become a mutable water
restriction state, permit revocation, tax rule, payment, inventory mutation,
production output, population fact, social reputation fact, or an Ecology
record.

### Non-Owned Facts

- Ecology owns the weather front, EnvironmentRegion, jurisdiction binding, and
  all weather/region revisions.
- Government does not alter weather, regional resources, crops, body states,
  permits, inspections, tax policy, accounts, inventory, ownership, production,
  social facts, or branch truth.
- The advisory creates no downstream enforcement, fanout, compensation,
  schedule, retry, reversal, or combined receipt.

## Fixed Authority Boundary

| Concern | Fixed value |
| --- | --- |
| capability | `capability:government-drought-advisory@1` |
| outcome | `outcome:government-drought-advisory@1` |
| descriptor | `descriptor:government-drought-advisory@1` |
| catalog contract | `inf:weather-front-government-drought-advisory@1` / `ecology_consumer` |
| owner | existing `GovernmentAuthority` / `actor_gameplay.government_domain` |
| target stream | `gameplay:government:advisory:{jurisdiction_ref}` |
| event family | `gameplay.government.drought_advisory_issued@1` |
| privacy | `project` only |
| receipt | append-derived `GameplayEventStore.append_batch()` receipt only |
| replay reader | fixed Government drought-advisory projector, full and checkpoint-tail |
| lifecycle | terminal historical issuance; no compensation, revocation, retry-as-new, or automatic restriction |

No caller, agent, package, or Ecology source may select these coordinates.

## Source Verification And Pins

The owner derives and validates all of the following before append:

1. One committed project-visible
   `gameplay.ecology.weather_front.propagated` event with
   `weather_ref=weather:drought` and non-empty `target_region_ref`.
2. Its exact Ecology stream id and event revision; the Ecology stream head must
   still equal that revision.
3. The current authority-scoped Ecology `EnvironmentRegion` projection for
   `target_region_ref`, including non-empty `jurisdiction_ref` and its exact
   region revision. The weather event's `target_region_revision` must equal the
   current region revision.
4. The target Government advisory stream head and the current advisory
   projection revision for that jurisdiction.
5. Fixed project privacy on source and target; a source cannot be widened from
   `project` to `public` or `authority_only`.

The advisory payload includes source event id/revision, Ecology stream id,
target region/ref revision, jurisdiction ref, expected Government stream
revision, descriptor/catalog refs, and the exact active policy revision.

## Fixed Idempotency And Event Vector

The owner-derived idempotency key is:

```text
government:drought-advisory:
weather_event_id:ecology_event_revision:target_region_ref:region_revision:
jurisdiction_ref:government_stream_revision:descriptor_revision
```

The sole event payload vector is:

```text
gameplay.government.drought_advisory_issued@1 {
  advisory_ref,
  jurisdiction_ref,
  target_region_ref,
  target_region_revision,
  weather_event_id,
  ecology_stream_id,
  ecology_event_revision,
  weather_ref = weather:drought,
  expected_government_revision,
  descriptor_ref,
  descriptor_revision,
  catalog_ref,
  policy_ref = policy:government-drought-advisory@1,
  policy_revision = policy:government-drought-advisory@1
}
```

Exact duplicates replay the original append receipt. A changed request under
the same key, a second advisory for the same weather event, or any stale pin is
zero-write.

## Replay And Rejection

The new Government projector rebuilds advisory records only from the exact
event vector above. Full replay and checkpoint-tail replay must agree on the
advisory ref, jurisdiction, source vector, and stream revision.

Before append, the row rejects with zero writes for unknown/wrong/private/stale
weather evidence; non-drought weather; missing or mismatched region/jurisdiction
projection; source or target stream revision conflict; catalog/descriptor
mismatch; duplicate or changed duplicate; unknown target stream; caller-selected
authority coordinates; and any request for restriction, payment, material,
production, compensation, fanout, public scope, or a second event.

## Conflict-Matrix Record

```text
operation_key = government:jurisdiction:drought-advisory@1
matrix_disposition = new
fact_claim = project-scoped Government advisory issuance for one pinned drought front
owner = existing GovernmentAuthority
event_partition = drought_advisory_issued only
package_claim = not_applicable
```

This row does not overlap existing Government inspection, permit, tax, branch
promotion, Economy quote, Organization supply, or Survival dehydration facts.

## Implementation Evidence

The fixed `GovernmentAuthority` verifier/projector/receipt branch and its
immutable descriptor/catalog row are implemented. The focused suite proves the
single advisory event, exact drought source, project privacy, Ecology and
region/jurisdiction revision fences, catalog failure, duplicate/change behavior,
append-derived receipt, and full/checkpoint-tail replay. The independent
`infra-weather-front-government-drought-advisory` Harness is green.

This closes only the exact advisory record. It does not authorize a water
restriction, permit change, policy lifecycle, payment, material effect,
production effect, population fact, compensation, fanout, or a generic
Government weather consumer.
