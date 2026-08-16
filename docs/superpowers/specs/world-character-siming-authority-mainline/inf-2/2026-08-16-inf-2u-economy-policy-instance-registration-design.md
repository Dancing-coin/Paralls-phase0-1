# INF-2U Economy Policy-Instance Registration

Status: `implemented and verified; narrow existing-Economy scheduled-transfer policy-instance admission only`

## Purpose

INF-2U replaces one part of the INF-2 caller-open-policy blocker with an
owner-bound policy-instance contract. It does not create a generic policy
registry or permit callers to select an owner, stream, event family, fragment,
or settlement writer.

The existing `EconomyAuthorityService` may admit a typed request for a
scheduled account-transfer policy instance. Economy remains the sole owner of
the policy facts, accounts, obligation lifecycle, payment/terminal events, and
append-derived receipt.

## Closed contract

| Field | Contract |
| --- | --- |
| Registration owner | existing `actor_gameplay.economy_domain` / `EconomyAuthorityService` |
| Stream | existing `gameplay:economy` only |
| Register/revoke events | `gameplay.economy.scheduled_transfer_policy_registered` / `..._revoked` |
| Consumer | the same Economy owner, before opening `policy:economy_scheduled_account_transfer@1` obligations |
| Policy instance | fixed scheduled-transfer kind; one opaque policy-instance ref, debit/credit account refs, amount cap, active interval and owner-selected revision |
| Privacy | authority-only event/outbox/view; project or caller scopes reject before append |
| Revision/idempotency | exact Economy stream head, canonical typed-request digest, existing principal/idempotency dedupe |
| Settlement | existing open/due/settled/cancelled/expired lifecycle and Economy account debit/credit fragment only |
| Receipt/replay | only the existing one `GameplayEventStore.append_batch()` result and `EconomyProjector`/lifecycle replay |

## Admission

A caller may submit a typed proposal only. `EconomyAuthorityService` validates
account existence, same currency, positive bounded amount, nonempty instance
reference, authority-only scope, and its own stream revision before it creates
the owner fragment. The event snapshot becomes the only admitted source for a
later obligation. A revoked, stale, forged, cross-currency, over-cap, or
unregistered instance is zero-write rejected.

The caller never supplies an `OwnerAuthorizedFragment`, stream id, event type,
receipt, terminal outcome, or payment event. The obligation coordinator stays
planner-only and cannot append.

## Non-goals

This does not permit arbitrary policy kinds, Government-owned payment terms,
cross-domain atomic settlement, account reservation release, or a generic
policy registry. It is one extensible instance surface within an already
existing Economy owner, not closure of all INF-2 policy/settlement work.

## Verified evidence

The focused INF-2U suite now proves policy register success, duplicate/reused-
key handling, stale revision, authority-only privacy, forged or cross-currency
proposal rejection, revocation, unregistered/revoked open rejection, bounded
amount rejection, existing due settlement, full and checkpoint-tail replay,
and redacted outbox/receipt. The package now carries its own Harness profile,
`infra-economy-policy-instance-registration`, alongside predecessor
`infra-economy-scheduled-transfer-obligation` and
`infra-event-derived-bounded-due-lifecycle-view` evidence.
