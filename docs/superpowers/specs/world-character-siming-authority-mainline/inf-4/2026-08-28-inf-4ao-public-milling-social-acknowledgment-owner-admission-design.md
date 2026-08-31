# INF-4AO Public Milling Social Acknowledgment Owner-Admission Contract

Status: `implemented narrow vertical; generic social expansion remains blocked`

## Exact Product Row

```text
committed project-visible Government
  gameplay.government.public_milling_notice_recorded@1
  for the completed public milling service
-> existing SocialFactAuthority
-> exactly two actor-private acknowledgment histories
```

The two participants are derived from the committed milling Contract:

1. `organization:district-milling-cooperative`
2. the acquisition owner/receiver recorded as the Contract's second party

The caller cannot choose participants, streams, privacy, event family,
jurisdiction, or acknowledgment content.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:social-public-milling-notice-acknowledgment@1` / `outcome:social-public-milling-notice-acknowledged@1` |
| owner / catalog | existing `SocialFactAuthority`; `inf:social-public-milling-notice-acknowledgment@1`; descriptor `descriptor:social-public-milling-notice-acknowledgment@1` |
| source | one committed project-visible `gameplay.government.public_milling_notice_recorded@1`, linked INF-4AL activity, INF-2AL Contract created/fulfilled pair, and INF-1AL acquisition |
| participants | fixed provider plus acquisition-derived Contract receiver; exactly two distinct parties |
| targets | `gameplay:social:public-milling-notice-acknowledgment:{participant_ref}` |
| event | `gameplay.social.public_milling_notice_acknowledged@1` |
| privacy / subject | actor-private, one event visible only to each derived participant |
| idempotency | `social:public-milling-notice-ack:{notice_event_id}:{notice_revision}:{provider_target_revision}:{receiver_target_revision}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; Social full/checkpoint-tail recipient view |
| lifecycle | terminal acknowledgment; no reopen, compensation, fanout, attendance, relationship, reputation, or downstream social action |

Each event carries the source notice, activity, Contract, acquisition and
revision pins, plus the immutable P5 registry/schema/catalog identities. The
event payload is recipient-safe and does not copy Contract party arrays.

## Zero-Write Rules

Unknown, private, stale, malformed, multiple-party, provider/receiver
binding-conflict, duplicate, changed-duplicate, unregistered schema/catalog,
or any caller-selected stream/event/privacy/participant input rejects before
append. A duplicate with the identical source and command identity returns an
append-derived `duplicate_replayed` receipt without new events.

## Boundary

This row reuses the existing SocialFactAuthority and adds no generic social
route, router, registry, owner, relationship writer, attendance model,
population truth, payment semantics, or mutation of Government notice,
Contract, Economy, Organization, Construction, or acquisition facts.

## Evidence

`test_inf4ao_public_milling_social_ack.py` and the
`inf4ao-public-milling-social-ack` Harness verify the exact two-party
derivation, source/provenance/revision pins, actor-private visibility,
append-derived receipt, zero-write fences, duplicate behavior, and
full/checkpoint-tail replay equivalence.
