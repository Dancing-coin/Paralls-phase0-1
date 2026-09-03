# Organization / Government / Social Generic Platform Design

Status: `implementation-authorized`

Date: `2026-09-03`

## Purpose

This design authorizes the federated Organization/Government/Social generic
platform under the world-character-Siming-authority mainline. It expands the
three owner families with closed typed content, exact state machines, and
precompiled owner recipes while preserving existing narrow rows and owner
boundaries.

## Architecture

- `GameplayPatchManifest v3` paired with `platform_schema_version="2.0"`
- Organization, Government, and Social keep separate facts, streams, and
  projections
- Cross-owner work is composed only through precompiled owner recipes and the
  existing `SettlementPlan -> GameplayEventStore.append_batch()` spine
- Population emits public signals only; any materialization is explicit and
  typed. It creates no Population-owned truth: a separately admitted target
  Character or Organization owner must allocate identity and append its own
  canonical creation fact.
- No mega owner, generic writer, router, coordinator, registry, scheduler, or
  second runtime

## Global Constraints

- Existing Organization/Government/Social narrow rows remain read-only
  compatibility baselines.
- Caller-shaped authority coordinates are rejected.
- Digest, visibility, revision, and source pins are mandatory on every
  admitted request.
- Unknown, stale, duplicated, or cross-owner claims fail closed before
  mutation.
- Full replay and checkpoint-tail replay must remain equivalent for every
  family.

## Family Portfolio

| # | Subsystem | Owner | State machine | Stream family | Guardrail |
|---|---|---|---|---|---|
| 1 | Organization membership, roster and role state | OrganizationAuthority | proposed -> admitted -> active -> suspended -> revoked -> archived | `gameplay.organization.membership` | no employee shadow state |
| 2 | Organization work windows and assignment state | OrganizationAuthority | planned -> open -> assigned -> started -> completed/failed -> closed | `gameplay.organization.work` | no payroll or scheduler |
| 3 | Government policy, permit and inspection state | GovernmentAuthority | draft -> published -> effective -> superseded -> revoked | `gameplay.government.policy` | no generic legal router |
| 4 | Government notice, acknowledgment and resolution state | GovernmentAuthority | drafted -> issued -> acknowledged -> disputed -> resolved -> archived | `gameplay.government.notice` | no public social writer |
| 5 | Social relationship, reputation and knowledge state | SocialFactAuthority | observed -> recorded -> visible -> hidden -> revoked | `gameplay.social.relationship` | no generic social writer |
| 6 | Social shared-expression, attendance and visibility state | SocialFactAuthority | invited -> joined -> observed -> left -> redacted | `gameplay.social.shared_expression` | no second social runtime |
| 7 | Population signal and explicit materialization state | Social signal projection; target Character/Organization owner on admission | signaled -> proposed -> admitted -> identity_allocated -> target_owner_created | rejected | `gameplay:social:population:{signal_ref}` | signal-only, no settlement |
| 8 | Precompiled owner recipe catalog and settlement bridge | All three owners through pinned recipes | registered -> pinned -> admitted -> retired | `gameplay.recipe.catalog` | no generic router/writer |
| 9 | Compatibility, replay and projection boundary | All three owners via read-only baselines | baseline -> compatible -> verified -> retired | `gameplay.compatibility.replay` | preserve narrow rows |

## Acceptance

This platform is valid only when:

1. the nine families remain closed and owner-bound
2. every cross-owner flow is recipe-bound and precompiled
3. Population stays signal-only and materialization remains explicit
4. existing narrow rows remain read-only compatibility baselines
5. each family can prove privacy, idempotency, zero-write rejection, and full
   plus checkpoint-tail replay

## Summary

This is a federated owner platform, not a generic authority layer.
