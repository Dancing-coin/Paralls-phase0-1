# INF-1 Owner-Admission Candidate Register

Status: `August Construction candidate inventory: INF-1AH, INF-1AL, and INF-1AM implemented and verified; remaining slots are owner-contract blocked or duplicate/closed; this is not INF-1 completion accounting`

## Scope Of This Register

This register accounts only for the three bounded Construction candidate slots
opened by the 2026-08-20 audit. It does **not** measure the full INF-1 package,
whose verified foundation, Survival, Ecology, Economy, weather-front, and
earlier Construction rows are tracked in the [INF-1 specification tree](README.md).
Accordingly, the register is neither a completion percentage nor evidence that
INF-1 is complete. The current formal INF-1 disposition remains: verified
finite rows, with broader lifecycle and owner-matrix extensions incomplete.

## Common Contract Record

For every formed row: source evidence is committed and project-visible; the
owner derives authority coordinates, privacy, idempotency, receipt, and
compensation. The exact append vector is one fixed owner event batch. Full and
checkpoint-tail replay must produce the same projection digest. Unknown,
multiple, unadmitted, digest-mismatched, missing/private/stale evidence,
binding conflict, revision conflict, duplicate, and changed duplicate are
zero-write before append.

## Candidate INF-1AH (implemented and verified)

| Field | Fixed contract |
| --- | --- |
| capability/outcome | `capability:construction-facility-mill-decommission@1` / `outcome:construction-facility-mill-decommission@1` |
| owned/non-owned | Construction owns facility lifecycle; package owns only typed definitions; caller/agent/other domains own none of the result |
| source/evidence | committed project-visible `facility_acquired@1(mill)` plus exact frozen v2 `facility_transformed@1(mill -> mill_reinforced)`; source event and stream revisions pinned; subject `facility_ref + project_ref=plot_ref` |
| owner/stream/event/write revision | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; one `gameplay.construction_production.facility_decommissioned@1`; current facility revision + stream head |
| idempotency/receipt/replay | authority-derived facility/source-vector key; `append_batch()` receipt only; Construction full/checkpoint-tail readers |
| terminal/reversal/compensation | terminal v1 `active -> decommissioned`; no reactivation, retry-as-new, reversal, cancellation, refund, compensation, or fanout; started ProductionRun rejects pre-append with no substitute event |
| exact event vector | one facility-decommissioned event retaining facility kind, project, source pins, prior lifecycle `active`, next lifecycle `decommissioned` |
| admission pins | frozen v3 package -> declaration -> binding -> policy -> descriptor -> catalog; frozen v2 pins remain source evidence only |
| closure evidence | owner-bound verifier/reducer/append, exact receipt, full/tail replay, terminal zero-write tests, and independent Harness; see the lifecycle runtime closure |

## Candidate INF-1-SLOT-B (owner-contract blocked; not formed)

No committed source/state and exact Construction outcome remain after the
terminal discovery audit. Missing fields: source event kind/revision,
facility/state binding, capability/outcome id, event family/revision, policy,
privacy, idempotency, receipt, replay, terminal/reversal/compensation, and
package/descriptor/catalog pins. Recommendation: do not name a row until a new
business source and target decision is approved.

## Candidate INF-1-SLOT-C (duplicate/closed)

The tempting `maintenance_due -> maintenance_state_dispelled` shape is an
existing narrow row, not a new business fact. Reusing it would duplicate an
admitted row and risk a second lifecycle writer. Missing/new-row status is
therefore not a contract; preserve zero-write and do not reopen discovery.

## Candidate INF-1AL (implemented existing-row extension)

The exact project-visible `facility_operationally_verified@1` event for an
active `mill_reinforced` facility, together with one earlier frozen v2
`mill -> mill_reinforced` transformation event, produces the Construction-owned
`facility_public_use_enabled@1` fact. Its fixed descriptor/catalog partition,
owner-derived idempotency, project privacy, append receipt, zero-write fences,
and full/checkpoint-tail replay are recorded in the
[INF-1AL contract](2026-08-28-inf-1al-mill-reinforced-public-use-owner-admission-design.md)
and independent Harness. INF-1AJ remains oven-only; no generic facility
availability operation is admitted.
