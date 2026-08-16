# INF-4B Isolated Branch Evolution Design

Status: `implemented and checkpoint-verified; isolated analysis branch only`

`BranchPreviewAuthority` owns no world truth and no event store. Its isolated
in-memory analysis buffer contains a fixed descriptor and deterministically
ordered `branch_candidate_proposed` records. The buffer can be replayed from a
local checkpoint plus tail into a projection hash. INF-4M supersedes this
document's earlier no-append statement only for an explicit, redacted,
creator-debug snapshot on the existing non-production branch stream. It still
emits no production event or receipt that could be treated as production
authority.

Inputs stay pinned to the production base digest/boundary, fixed seed,
calibration digest, revision refs and existing `CharacterProfile` identity.
Malformed base/input/profile rejects with zero production writes. `promote()`
is explicit `branch_promotion_unsupported`; promotion, new population/social
truth and generic branch scenario consequences remain blocked until separately
approved owner mappings exist.
