# Registered Learning Authority Implementation Plan

> Execute inline with superpowers:executing-plans. Preserve the historical working-tree learning changes; do not stage them as an incidental dependency.

**Goal:** Implement the real durable learning owner prerequisite for unified matrix R10, then return to production learning consumers.

**Architecture:** Reuse CharacterSkillRegistry, CharacterSkillState and GameplayEventStore. Internally registered source/outcome rules authorize an owner event; proposals and legacy in-memory counters do not authorize skill facts.

**Tech Stack:** Existing Python, Pydantic, pytest and Harness; no dependency additions.

**Spec:** [registered learning authority](../specs/2026-10-20-registered-learning-authority-design.md).

## Task 1: Source admission and real owner

- [x] Add focused RED tests in `backend/tests/test_registered_learning_authority.py` for committed source ownership, subject/privacy/outcome, registration mismatch, missing prerequisites and zero-write rejection.
- [x] Implement `backend/app/character_agent/skills/learning_authority.py`: immutable internal registrations, source proof lookup, same-store read CAS, original receipt and recorded learned state projection. Reuse baseline CharacterSkillState; avoid dependency on uncommitted episode classes.
- [x] Verify exact/changed duplicate, evidence reuse, source conflicts and prerequisite admission, append failure, strict schema, new owner instance and SQLite reopen. Test existing stable compiler consumption of the projected state. Prerequisites share the actor stream write CAS.
- [x] Run exact file-isolated focused tests and existing skill service/registry consumer tests: 39 passed, run `060b10b09b334dd7bc372a20bcb6cb69`; backend-contract `76752ae4862a4223be71c49ca28593b5` passed. Evidence exported and cleanup passed.
- [x] Review bounded owner, tests and documentation; commit as one batch. R10 remains partial until actual producer/caller and four-route evidence are present. No global schema registration or new public endpoint is claimed.

## Task 2: Production episode and outcome consumers

- [x] Add ESM owner-authorized personal-action disclosure with canonical source receipt, explicit scene/world mapping, actor-private field allowlist, source read CAS and durable exact/changed retry. Existing production bounded inspect consumer emits it before session outcome; failed session write retries both original receipts. ESM→disclosure→registered learning source consumption tested with controlled registered policy. Exact four-file isolation 141 passed (4 existing FastAPI deprecation warnings), run `666e911afa0c4212a0dee8644feeac2b`. Four-route acceptance remains open.

- [ ] Register sourced objects/rules for all four specified routes; use actual source owners, privacy/teacher context and time/resource policies.
- [ ] Replace nonempty-string authority admission in the legacy learning projection with original committed owner-event/receipt lookup; preserve exact retry and failure evidence.
- [ ] Route learned facts to the existing stable compiler before the next cognition turn, with capability revision invalidation. Verify actor/scope/revocation/source changes.
  - [x] Read one owner snapshot containing states, stream revision and original event refs.
  - [x] Bind runtime reader/world explicitly; preserve authored inputs and existing compiler precedence.
  - [x] Freeze the snapshot digest in the envelope; validate handoff and sync/durable result pins to reject concurrent learning updates.
  - [x] Bind the production runtime to the shared owner reader; preserve historical dirty code through exact source snapshot staging and HEAD-isolated evidence. 176 passed, run `9c33cb1d2e5f4c27837ca583005ff547`. Parent checkbox remains open for remaining grant/revocation/source admissions.
- [ ] Verify observation/imitation/guidance/practice/combat/review/research/mentorship/transfer stages and the specified mastery/difficulty dimensions without direct model skill writes.
- [ ] Add the admitted owner to the existing common replay cut, including checkpoint-tail, corruption rejection and recovery; keep model quality and final Godot gates separate.

Architecture, sequence and data flow are defined by the three linked spec diagrams. Task 1 implements the source-admission→owner→ledger→projection edges only.
