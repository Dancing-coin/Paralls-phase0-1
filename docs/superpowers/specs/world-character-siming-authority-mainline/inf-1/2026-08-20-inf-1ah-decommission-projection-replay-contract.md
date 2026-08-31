# INF-1AH Decommission Projection And Replay Contract

Status: `implemented and verified for the exact INF-1AH lifecycle row; generic lifecycle remains blocked`

## Construction-Owned Lifecycle Projection

For this exact row only, a facility lifecycle status has the closed vocabulary:

```text
active | decommissioned
```

`active` is reconstructed only when the projector sees the complete
project-visible, revision-pinned `facility_acquired(mill)` plus frozen exact
v2 `mill -> mill_reinforced` source vector and no accepted decommission event.
`decommissioned` is reconstructed only from the fixed
`gameplay.construction_production.facility_decommissioned@1` vector. No other
facility kind, missing value, package declaration, or caller assertion creates
a lifecycle status.

The decommission event must preserve `facility_kind=mill_reinforced`,
`project_ref`, condition, run rows, reservation refs, output references, and
all non-Construction facts. It changes only lifecycle status and increments
the Construction facility revision once.

## Pre-Append Source Gate

The owner derives and pins the acquisition event, exact frozen reinforcement
event, facility/project binding, source event revisions, current facility
revision, and facility stream head. It additionally scans the committed
Construction projection: any `ProductionRun` with the same `facility_ref` and
`status=started` rejects the command with zero writes. The rejection must not
cancel a run, release reservations, discard output, compensate, refund, or
emit a second event.

## Full And Checkpoint-Tail Replay

Full replay and checkpoint-tail replay must produce equal values for:

- the facility lifecycle status;
- the facility revision and unchanged `facility_kind`;
- the facility/project binding; and
- the Construction source revision vector, including the facility stream.

A checkpoint must preserve the row-specific lifecycle result and source vector
needed to replay only the ordered tail. The tail reader accepts exactly the
same source/decommission vector validation as full replay. Missing or
inconsistent lifecycle source data, stale vector entries, mismatched project
binding, wrong event family, wrong lifecycle transition, or an altered kind is
a replay failure, never a default or repair write.

## Terminal Boundary

The projection admits no reactivation, downgrade, compensation, fanout,
payment, material, inventory, output, maintenance, weather, or cross-domain
consequence. Exact idempotency may replay the append-derived receipt only;
changed idempotency is zero-write. The historical pre-implementation boundary
is preserved above; the exact projector change, catalog row, tests, Harness,
and append vertical were later approved and verified only for INF-1AH. This
contract still does not authorize any other lifecycle row.
