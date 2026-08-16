# INF-4D Isolated Owner-Disposition Branch Design

Status: `implemented and verified for isolated owner-mapping analysis; branch-domain consequences and promotion remain blocked`

## Scope

This package extends the existing non-production branch buffer with one
replayable evaluation record per candidate. It does not invoke an owner fragment
or append to `GameplayEventStore`; it records only whether a candidate maps to
an already-approved production owner contract for isolated analysis.

| Branch candidate kind | Isolated disposition | Existing production owner contract |
| --- | --- | --- |
| `supply` | `admitted_owner_analysis` | `OrganizationAuthority.build_commerce_commitment_fragment` |
| `inspection` | `admitted_owner_analysis` | `GovernmentAuthority.build_commercial_inspection_fragment` |
| all others | `blocked_owner_mapping` | none |

Branch records remain in `BranchPreviewAuthority`'s isolated in-memory buffer,
never `GameplayEventStore`, and projection is rebuilt only from those records.
The `CharacterProfile` registry remains identity-only input. Household,
organization, social, population and NPC truth remain with their existing
production owners; branch promotion is unsupported.

## Completion boundary

Focused tests prove deterministic record order, distinct admitted and
blocked projections, checkpoint-tail equivalence, zero production writes,
privacy/base/profile rejection and unsupported promotion. This does not claim
that a branch executes domain consequences, creates a branch event store,
settles an Organization/Government fragment, or enables promotion. Evidence:
`.harness/verification/infra-isolated-branch-owner-disposition-report.json`.
