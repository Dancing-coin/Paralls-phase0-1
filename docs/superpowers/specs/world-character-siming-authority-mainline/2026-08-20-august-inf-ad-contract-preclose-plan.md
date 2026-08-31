# August INF A-D Contract Pre-Close Plan

Status: `historical documentation/audit plan; INF-1AH subsequently implemented and verified; August INF A-D not complete`

## Boundary

This packet prepares row-specific Owner-Admission Contracts without changing
runtime, manifest schema or bytes, digest, descriptor/catalog, tests, Harness,
or business events. Frozen packages are source evidence only. Existing narrow
rows are references and are not new business facts.

At the time of this plan, the only candidate close to approval was INF-1AH.
Its new immutable decommission package had approved literals, adapter-verified
digest claims, and frozen v3 bytes, but still needed separate descriptor/catalog
admission. The
literal set was limited to package/version, author/trust, definitions/typed
content, policy, and explicit dependency-array choices; declaration/binding/
capability/outcome identities derived mechanically. INF-2/3/4 have no additional complete committed
source-to-owner facts after the terminal discovery audits; their candidate
slots remain explicit blocked records rather than invented rows.

## Shared Owner-Admission Contract Invariants

Every candidate record below must carry these fields before approval:

| Field | Required rule |
| --- | --- |
| capability/outcome | one exact row-local id; never a generic family |
| owned facts | only the fixed source owner and target owner facts |
| non-owned facts | caller, agent, dossier, package, Ecology, branch, and other-domain facts remain read-only or rejected |
| source/evidence | committed event/view kind, source revision, privacy, subject binding |
| owner/write | fixed existing owner, target stream, event family, write revision |
| idempotency/receipt | authority-derived key; receipt only from target `append_batch()` |
| replay | existing owner full and checkpoint-tail replay with equal digest |
| lifecycle | terminal, reversal, retry, and compensation semantics are literal, not inferred |
| event vector | exact fixed event family/revision/payload set; no caller-selected fragment |
| admission pins | package -> declaration -> binding -> policy -> descriptor -> catalog, in that order |
| zero-write | unknown, multiple, unadmitted, digest mismatch, missing/private/stale evidence, binding conflict, revision conflict, duplicate/change duplicate all reject before append |

Caller, package, or agent may not select authority coordinates, privacy,
receipt, compensation, or settlement fragments.

## Candidate Disposition

| Group | Candidate slots | Current result |
| --- | --- | --- |
| INF-1 | 1AH mill_reinforced -> decommissioned; two unformed slots | historical: one candidate then approval-ready; it is now implemented and verified. The two unformed slots remain blocked. This table is not INF-1 completion accounting. |
| INF-2 | package-defined economic outcome; service outcome; inventory/economic outcome | all owner-contract blocked or already implemented reference rows; no new fact |
| INF-3 | unlisted Ecology source edge; drought-process substitute; additional weather-front edge | all owner-contract blocked; existing finite map is terminal evidence |
| INF-4 | committed branch/Production evidence consequence; branch-work wage reference; branch inspection/supply sibling reference | only existing fixed rows are implemented references; no new generic promotion |

Detailed field-by-field records and implementation sequencing are in the four
group registers and plans linked from the corresponding INF README files.

## Approval Order

1. Historical completed gate: INF-1AH package literals and explicit empty
   arrays were approved, then the distinct v3 record was authored, validated,
   and frozen.
2. Historical completed gate: exactly one descriptor and catalog row was
   admitted through the existing read-only binding path; the later row-specific
   lifecycle runtime is independently implemented and verified.
3. Approve any INF-2/3/4 row only after its source owner, target owner, event
   vector, privacy, replay, and terminal semantics are separately closed.
4. Only after contract approval may a future implementation plan write RED
   tests, runtime, descriptor/catalog data, or Harness evidence.

No section in this packet is `approved`, `implemented`, or `August INF A-D
complete`.
