# Failure, Recovery And Output Handoff Design

Failure policy is mandatory package content and is one of `release`, `loss`,
`rework` or `terminal`. The selected policy determines the fixed Construction
event vector; missing or ambiguous policy fails before mutation. Construction
never cancels another owner's reservation, refunds payment or writes Inventory
custody. It records only owner-owned failure or output evidence.

Inventory creates custody only from committed, revision-pinned Construction
output evidence and its own immutable mapping. Quantity, holder, container,
stream, privacy and receipt cannot be caller-selected. Full/tail replay
revalidates the complete provenance chain. Cross-domain compensation, payment,
material mutation and fanout remain separate owner contracts.

The certification handoff rejects a committed output quantity that disagrees
with the admitted certification content. If the source carries output quality,
the package must carry a quality policy and the value must be within its bounds;
otherwise certification is zero-write. Accepted quality evidence is retained
in the Construction certification projection for downstream Inventory replay.

Failure replay additionally requires the committed event to remain project
visible on the run's facility stream, with matching facility/recipe identity
and exact facility/pre-append stream-head revision pins. Any privacy, stream,
identity or source-vector tampering is fail-closed.

The certification handoff is proven against three immutable content instances
(bakery, mill and kiln) through the same family adapter; each preserves its
own recipe/output identity and replay pins without introducing a generic
cross-owner writer.

Inventory custody mapping now includes the immutable kiln
`recipe:clay-to-brick@1 -> item:brick@1` destination partition. Holder and
container remain mapping-owned; caller/package content cannot select them.

The Construction certification event
`gameplay.construction_production.production_output_certified@1` is also
source-controlled through the existing EventSchemaRegistry.

The Inventory handoff event `gameplay.inventory.production_output_received@1`
is likewise source-controlled through that same registry; no second registry
or schema authority is added.

`run_failed@1` also carries the ProductionRun's owner-issued reservation refs
and evidence unchanged. Replay compares that lineage to the started run and
rejects missing, extra, or altered reservation proof before changing status.

Failure admission also requires `failed_tick >= started_tick`; an event dated
before run start is rejected before append.

Replay enforces the same chronology fence and rejects a tampered failure event
whose `failed_tick` predates the committed ProductionRun start.
