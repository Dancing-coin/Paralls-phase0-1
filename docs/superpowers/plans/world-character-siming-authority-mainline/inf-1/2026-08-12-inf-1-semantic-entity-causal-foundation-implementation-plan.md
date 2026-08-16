# INF-1 Semantic, Entity, And Causal Foundation Implementation Plan

Status: `implemented-and-verified for the documented vertical; broader extension lanes remain pending`

Date: `2026-08-12`

## Objective

Make `INF-1` executable and auditable as an independent mainline package over
the already existing bounded slice. This plan governs both the current verified
foundation and the remaining work needed before `INF-1` can be described as a
fully closed package rather than a partial verified sample.

## Existing code and proof baseline

The current bounded code/proof surface is:

- `backend/app/gameplay/semantic_registry.py`
- `backend/app/gameplay/entity_causal_projection.py`
- `backend/app/gameplay/shared_contracts.py`
- `backend/app/gameplay/event_store.py`
- `backend/app/gameplay/replay.py`
- `backend/tests/test_infra_semantic_entity_causal.py`
- `.harness/profiles/infra-semantic-entity-causal.json`

This baseline proves the documented semantic/entity/causal vertical. The
remaining-gap ledger exists to prevent that bounded proof from being treated as
generic cross-domain rule closure.

## Work packages

1. **INF-1A: contract lock and owner map.**
   Freeze the package boundary in the independent spec/plan tree. Every future
   extension must name its owner file, append path, privacy scope, replay
   proof, and rejection behavior before code changes begin.

2. **INF-1B: semantic registry and snapshot invariants.**
   Preserve and extend only the existing `semantic_registry` path for tag
   definition, assignment, inheritance, selector, parameter merge, revision
   pinning, and immutable snapshot digest behavior. Reject any proposal that
   needs a second semantic truth store or mutable snapshot owner.

3. **INF-1C: event-derived dossier and causal projection.**
   Preserve and extend only the rebuildable dossier path in
   `entity_causal_projection.py`. New dossier fields must derive from committed
   event history and remain full-replay and checkpoint-tail equivalent.

4. **INF-1D: proposal-only rule bridge.**
   If semantic or rule logic expands, it must remain proposal-only until an
   existing owner converts accepted results into typed events and commits
   through `GameplayEventStore.append_batch()`. No generic rule layer may
   append world truth directly.

5. **INF-1E: privacy and permission closure for the package slice.**
   Extend tests and profile checks so authority, actor, and debug views have
   explicit filtering rules. Do not upgrade backend-only filtering into generic
   transport or creator security claims.

6. **INF-1F: replay, migration, and rollback hardening.**
   Any schema or reader extension must prove deterministic full replay,
   checkpoint-tail replay, stale/duplicate handling, compatible migration, and
   fail-closed rollback semantics without historical event mutation.

7. **INF-1G: evidence refresh and gap ledger.**
   Each material extension must refresh the focused profile report and update
   the August-analysis mapping so bounded proof and remaining gaps stay visible.

## Focused verification plan

The package-specific verification lane is:

```powershell
python -m pytest backend/tests/test_infra_semantic_entity_causal.py -q
python scripts/verification/harness.py --profile infra-semantic-entity-causal
python scripts/verification/harness.py --profile all
git diff --check
```

Completed evidence: `.harness/verification/infra-semantic-entity-causal-report.json`
contains separate successful checks for semantic construction, authority append,
idempotency, revision conflict zero-write, privacy, checkpoint-tail replay,
meta-rule trace, and effect lifecycle. The final repository suite completed
with `2504 passed` (one pre-existing pytest-asyncio configuration deprecation
warning).

The focused profile must enumerate package assertions rather than aliasing a
generic broader pass/fail result.

## Acceptance assertions

The focused package evidence must prove:

1. tag definition and assignment validation;
2. inheritance loop and conflict rejection;
3. stable semantic snapshot digest for the same inputs;
4. constrained selector behavior;
5. entity/relationship dossier rebuild from committed events;
6. causal-parent query correctness;
7. checkpoint-tail replay equivalence with full replay;
8. stale/duplicate/idempotent behavior as declared by the package;
9. zero committed writes on rejected requests; and
10. filtered read scopes that do not widen privacy beyond the allowed view.

## Blockers and refusal conditions

Keep `INF-1` `planned` or `blocked` if any of the following is true:

- a proposed change introduces a second runtime, event store, scheduler, or
  social/world truth store;
- semantic logic writes directly outside `GameplayEventStore.append_batch()`;
- replay cannot reproduce the same canonical dossier/causal result;
- privacy/debug surfaces expose data beyond their declared scope;
- migration requires mutating retained historical events; or
- evidence is stale, missing, or only borrowed from a broader contract-sample
  profile.

## Explicit non-goals for this plan

This plan does not authorize or claim:

- a generic untrusted effect/state scripting language or all-domain lifecycle coverage;
- full ecology/disaster or population simulation;
- complete creator package runtime;
- direct Godot/model/Siming world write capabilities;
- a generic untrusted scripting surface; or
- replacing the existing authority/event/replay spine.

## Completion rule

The documented INF-1 vertical is complete: the independent formal spec and
plan, owner-scoped code, focused tests, focused Harness report, and explicit
remaining-gap ledger agree on the package boundary. Any expansion remains
planned until it receives the same independent evidence.
