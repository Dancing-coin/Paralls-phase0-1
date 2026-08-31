# INF-4AI P5 Actor-Private Expression Implementation Plan

Status: `implemented and verified narrow vertical; generic social/session expansion remains blocked`

> **For agentic workers:** The platform, package, descriptor, and row gates listed below were subsequently approved and executed. This file is retained as the implementation record; it does not authorize any broader Social operation.

**Goal:** Express one exact completed two-party `handshake` source as two actor-private Social shared-experience facts while preserving existing P5 and INF owner boundaries.

**Architecture:** Reuse the existing injected immutable `P5PolicyRegistry`, `EventSchemaRegistry`, `GovernedAuthorityContractCatalog`, `SocialFactAuthority`, `GameplayCommandEnvelope`, `SettlementPlan`, and `GameplayEventStore`. Add only the literal event/schema/descriptor vocabulary required by INF-4AI; no generic session adapter, registry writer, router, coordinator, or second store is introduced.

**Tech Stack:** Python 3, Pydantic frozen models, existing event-schema registry, existing append-batch spine, pytest, repository Harness.

---

## Scope Gate And Disposition

Execution required all of these independent approvals, which are now recorded
as satisfied for this exact row:

1. INF-4AI owner contract and P5 actor-private expression amendment;
2. the immutable P5 handshake package content and derived digest;
3. the exact descriptor/catalog row;
4. the row runtime approval.

The exact static P5 vocabulary, immutable package binding, descriptor/catalog
row, owner adapter, focused tests, Harness, and runtime are implemented and
verified. The earlier `admission-evidence pending` status is historical and
superseded. Every unapproved or broader Social operation remains zero-write;
this plan does not authorize a generic route or a new owner.

## Files And Ownership Map

| File | Single responsibility in this plan |
| --- | --- |
| `backend/app/gameplay/p5/registry.py` | Preserve immutable P5 registry validation and add the exact event/stream vocabulary only when the approved registry revision is supplied. |
| `backend/app/gameplay/event_schema_registry.py` | Register and validate the exact event schema digest in the existing schema registry; no dynamic registration API is added. |
| `backend/app/gameplay/governed_contract_catalog.py` | Add one static descriptor and one static catalog contract for Social shared-experience; retain read-only tuples and closed scope validation. |
| `backend/app/gameplay/p5/social_knowledge.py` | Verify the committed handshake source, derive the two actor-private target streams, append the fixed vector, and replay the owner-local projection. |
| `backend/tests/test_inf4ai_p5_actor_private_expression.py` | Focused RED-to-green tests for the exact row. |
| `scripts/verification/verify_inf4ai_p5_actor_private_expression.py` | Independent Harness selectors and evidence report. |
| `.harness/profiles/inf4ai-p5-actor-private-expression.json` | Harness profile declaration; no package or runtime registration. |
| `docs/superpowers/specs/.../inf-4/2026-08-27-inf-4ai-handshake-shared-experience-owner-admission-design.md` | Row contract, blocker and boundaries. |
| `docs/superpowers/specs/.../character-gameplay-foundation/2026-08-27-inf-4ai-p5-actor-private-expression-amendment-design.md` | Platform/P5 expression amendment and approval gates. |

No new file may introduce a registry writer, generic resolver, generic social
operation, owner, event bus, store, clock, scheduler, or coordinator.

## Task 1: Lock the immutable vocabulary

**Files:**

- Modify: `backend/app/gameplay/event_schema_registry.py`
- Modify: `backend/app/gameplay/p5/registry.py`
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_inf4ai_p5_actor_private_expression.py`

- [x] Add the exact static identities from the approved amendment:

```text
event_type       = gameplay.social.handshake_shared_experience_recorded
schema_version   = 1
schema_ref       = schema:p5:social:handshake-shared-experience-recorded
descriptor_ref   = descriptor:social-handshake-shared-experience@1
capability_ref   = capability:social-handshake-shared-experience@1
outcome_ref      = outcome:social-handshake-shared-experience-recorded@1
predicate_ref    = predicate:embodied-completed-two-party-handshake@1
effect_ref       = effect:social-handshake-shared-experience-recorded@1
catalog_ref      = inf:social-handshake-shared-experience@1
```

- [x] Extend the existing closed projection-scope vocabulary with exactly
  `actor_private`; the validator must require a concrete `character:` subject
  and derive the event visibility as `actor:{participant_ref}`. Arbitrary
  scope strings remain invalid.
- [x] Add the exact stream grammar
  `^gameplay:social:shared-experience:character:[^:]+$` to the existing P5
  registry data. The grammar must reject empty, multi-subject, non-character,
  or caller-shaped stream identifiers.
- [x] Keep all existing P5 registry revisions valid and fail closed when the
  exact event/schema/descriptor is absent or has a conflicting digest.
- [x] Add RED assertions that the old registry/catalog rejects the new event
  before the approved vocabulary is installed. The failure must be a typed
  unknown schema/descriptor result, not a Python import error.

**Verification:**

```powershell
$env:PYTHONPATH='backend'
python -m pytest -q backend/tests/test_inf4ai_p5_actor_private_expression.py -k 'vocabulary' --basetemp=.pytest-tmp/inf4ai-vocabulary
```

Expected RED result before implementation: the exact new event/schema is
unregistered. Expected GREEN result after implementation: one exact static
registration is accepted and an altered digest, scope, or grammar remains
zero-write.

## Task 2: Define the immutable P5 handshake package binding

**Files:**

- Modify: `backend/app/gameplay/p5/registry.py`
- Create only after package approval: the existing approved P5 package-content
  artifact location selected by the platform manifest plan
- Test: `backend/tests/test_inf4ai_p5_actor_private_expression.py`

- [x] Represent the package as one immutable `P5PolicyRegistry` revision, not
  a mutable registration call. It must pin `registry_ref`,
  `registry_revision`, registry digest, package ref/revision/digest, event
  schema digest, and the owner adapter allowance.
- [x] Require the package declaration to name only the approved predicate,
  effect, event schema, and reader metadata. It must not carry owner,
  stream, visibility, receipt, idempotency, compensation, or arbitrary code.
- [x] Preserve the current injected-registry construction used by P5 slices;
  if production wiring is needed, pass the immutable revision through the
  existing application composition boundary rather than adding a registry
  singleton or writer.
- [x] Add tests for missing, malformed, mismatched, disabled, and conflicting
  package digest claims. All must leave the event store unchanged.

## Task 3: Add the exact governed descriptor/catalog row

**Files:**

- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_inf4ai_p5_actor_private_expression.py`
- Regression: `backend/tests/test_infra_governed_authority_contract_catalog.py`

- [x] Add exactly one `GovernedAuthorityContract`:

```text
contract_ref        = inf:social-handshake-shared-experience@1
contract_kind       = contract_admission
owner_ref           = authority:p5:social
stream_pattern      = gameplay:social:shared-experience:{participant_ref}
event_type          = gameplay.social.handshake_shared_experience_recorded
projection_scope    = actor_private
receipt_reader_ref  = GameplayEventStore.append_batch
replay_reader_ref   = SocialFactAuthority.handshake_shared_experience_view_for
```

- [x] Add exactly one `OwnerOperationDescriptor` with the capability,
  outcome, predicate, and effect identities above. The tuple remains static,
  sorted, immutable, and read-only.
- [x] Require operation validation to reject project, authority-only, public,
  multiple-stream-unbound, caller-selected, or unknown scopes for this row.
- [x] Update catalog regression expectations only after the descriptor is
  separately approved. No generic Social descriptor is allowed.

## Task 4: Write focused RED tests before owner implementation

**Files:**

- Create: `backend/tests/test_inf4ai_p5_actor_private_expression.py`

- [x] Build a real committed `InteractionSession` using the existing
  `EmbodiedInteractionSessionService`: proposal, non-initiator acceptance,
  authorization, realization, two completed observations, and committed
  terminal event.
- [x] Assert exact success produces two target events, one per participant,
  with actor-private visibility, fixed `handshake` interaction kind, source
  session event/revision, and no private terms, pose, reservation, score,
  confidence, or timestamp fields.
- [x] Assert zero-write for unknown source, wrong semantic action, one
  participant, incomplete observation, private/foreign source, stale source
  head, target head conflict, missing descriptor, and digest conflict.
- [x] Assert exact duplicate returns the original append-derived receipt and
  changed duplicate is rejected without new events.
- [x] Assert each participant's view contains only its own event. An outsider
  receives an empty view.
- [x] Assert full replay and checkpoint-tail replay produce equal refs,
  payloads, source vectors, and projection digest.

Run before implementation:

```powershell
$env:PYTHONPATH='backend;backend/tests'
python -m pytest -q backend/tests/test_inf4ai_p5_actor_private_expression.py --basetemp=.pytest-tmp/inf4ai-red
```

Expected RED result: the exact owner method/descriptor is unavailable. Do not
turn an import or syntax failure into a passing RED test.

## Task 5: Implement the owner-bound verifier and fixed append vector

**Files:**

- Modify: `backend/app/gameplay/p5/social_knowledge.py`

- [x] Add one method named
  `record_completed_handshake_shared_experience` with explicit source event
  id/revision and target-head inputs. All coordinates are validated against
  committed source and static catalog data; caller values never select owner,
  stream, event, privacy, receipt, or fragment.
- [x] Verify the exact seven-event source sequence on one session stream:
  `proposed`, `accepted`, `authorized`, `realizing`, two completed
  `participant_observed` events, and `committed`.
- [x] Verify exactly two distinct `character:` participants, fixed
  `semantic_action=handshake`, acceptance by the non-initiator, committed
  settlement ref, and `session_public_safe` source visibility.
- [x] Derive target streams, event payloads, idempotency key, read/write
  revision vectors, descriptor pins, and actor-private visibility in the
  owner. Append one same-owner two-stream batch through the existing
  `GameplayCommandEnvelope -> SettlementPlan -> append_batch()` path.
- [x] Return an append-derived `SettlementReceipt`; never create a combined
  cross-owner receipt or a marker-only event.
- [x] Keep lifecycle terminal and history-only: no correction, reversal,
  compensation, relationship score, reputation, attendance, payment,
  material, or generic session adapter.

## Task 6: Implement and verify the owner-local replay reader

**Files:**

- Modify: `backend/app/gameplay/p5/social_knowledge.py`

- [x] Add `handshake_shared_experience_view_for(participant_ref,
  checkpoint_at=None)` with exact `character:` validation.
- [x] Filter by actor-private visibility and participant-owned stream; do not
  expose counterpart-private fields or source session private terms.
- [x] Rebuild the same deterministic payload set for full and checkpoint-tail
  reads and include source/session and target stream revisions in the digest.
- [x] Fail closed for negative, incompatible, or ahead checkpoints.

## Task 7: Add the independent Harness

**Files:**

- Create: `scripts/verification/verify_inf4ai_p5_actor_private_expression.py`
- Create: `.harness/profiles/inf4ai-p5-actor-private-expression.json`

- [x] Define selectors for exact source/append, zero-write/privacy/duplicate,
  and full/tail replay.
- [x] Run only the focused test names from Task 4 and write
  `.harness/verification/inf4ai-p5-actor-private-expression-report.json`.
- [x] Include row, owner, source stream, target stream grammar, event type,
  privacy, descriptor/catalog pins, committed event ids, receipt, and replay
  hashes in the report.
- [x] Mark external Heavenly runtime limitations separately; never treat
  `MODEL_PRICE_NOT_CONFIGURED` or missing live credentials as code success or
  test success.

## Task 8: Full verification and documentation closeout

**Files:**

- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-15-inf-mainline-completion-audit.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-17-inf-mainline-continuation-checkpoint.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-12-inf-remaining-scope-dependency-design.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-4/README.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-blocker-taxonomy.md`

- [x] Run the focused INF-4AI tests and Harness.
- [x] Run the P5 social regression, complete INF-focused corpus, continuation
  gate, docs Harness, `compileall`, and `git diff --check`.
- [x] Keep all frozen packages unchanged and retain separate owner receipts
  and replay pins.
- [x] Record `implemented narrow vertical` only if every exact test and
  Harness selector is green. Otherwise record the exact failure as a row-level
  blocker.
- [x] Keep `Goal active` and `August INF A-D not complete` until every required
  row is either implemented with evidence or formally dispositioned.

## Rollback And Non-Migration Rules

- Existing P5 registry revisions and existing event meanings are immutable.
- A failed vocabulary or package validation installs nothing and writes no
  candidate, active-set change, event, receipt, or outbox entry.
- Disabling the future P5 handshake package blocks new admission only; it does
  not delete historical Social events.
- Historical events retain their original schema, package, descriptor,
  privacy, and reader pins. A missing reader fails replay closed.
- No migration from `relationship_fact_recorded` is permitted because its
  timestamp/confidence/decay semantics differ from shared-experience history.

## Plan Self-Review

- Spec coverage: source vector, owner, event/schema, actor-private scope,
  binding, idempotency, receipt, replay, zero-write, and prohibitions each map
  to Tasks 1-8.
- Placeholder scan: no task relies on a TBD value; all identities are the
  exact amendment literals above. Package digest remains an approval input,
  not an invented value.
- Type consistency: the existing names `P5PolicyRegistry`,
  `SocialFactAuthority`, `GameplayCommandEnvelope`, `SettlementPlan`,
  `GameplayEventStore.append_batch()`, and `SettlementReceipt` are used
  consistently.
- Scope: no task creates a new owner, generic route, registry writer,
  coordinator, settlement authority, or second runtime/store/bus/clock.
