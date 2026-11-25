# M5-3 Package Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Persist `pack.migrated` as an L4 control-plane event and resolve the active immutable package set at historical global sequences.

**Architecture:** Register the event in the existing schema factory. Add a read-only package archive catalog, a per-world migration authority using the existing `GameplayEventStore` API, and a replay resolver that validates the migration chain. Production startup wiring remains deferred because the application has no v2 rule-pack consumer.

**Tech Stack:** Python 3.12.2, Pydantic models already used by gameplay runtimes, existing EventSchemaRegistry and GameplayEventStore APIs, pytest.

**Spec:** `docs/superpowers/specs/2026-11-25-m5-3-package-migration-design.md`

## Global Constraints

- Do not modify `event_store.py` or `models.py`.
- Do not add a gameplay Owner or FactType for package lifecycle metadata.
- Do not modify `main.py` without a production v2 package consumer and cross-boundary coordination.
- Keep event payload fields aligned with the formal `pack.migrated` contract.
- Use Python 3.12.2, `PYTHONPATH` for the A worktree backend, and F-drive pytest temp/output paths.
- Do not merge to `integration` or `main`.

## Review Focus

- Reusing an idempotency key with a changed migration payload must reject without writing.
- A retry of an already committed migration must replay its receipt before checking current active pins.
- A `from` set that differs from the latest package set must reject with zero writes.
- A missing package identity or changed archived content hash must fail closed.
- Replay before, at, and after the migration global sequence must select the correct package set.

---

### Task 1: Register the platform migration event

**Files:**
- Modify `backend/app/gameplay/event_schema_registry.py`
- Test `backend/tests/test_package_migration_runtime.py`

**Interfaces:**
- Event type is `pack.migrated`, schema version is `1`.
- `create_stormnight_event_schema_registry()` registers this platform event.
- `gameplay_schema_event_types()` must not classify `pack.migrated` as a gameplay event.

- [x] Add tests that the schema factory registers `pack.migrated@1` and that it is absent from gameplay graph event discovery.
- [x] Run those tests and verify they fail because the event is not registered.
- [x] Register the immutable EventSchema identity and keep the non-gameplay namespace behavior.
- [x] Run the new tests and `backend/tests/test_gameplay_event_schema_registry.py`.

### Task 2: Add immutable package archive lookup and sequence replay

**Files:**
- Create `backend/app/gameplay/package_migration_runtime.py`
- Test `backend/tests/test_package_migration_runtime.py`

**Interfaces:**
- `PackageRef(pack_id: str, pack_version: str)` is the serialized package identity.
- `PackageArchive(packages: Sequence[LoadedPack], expected_content_hashes: Mapping[PackageRef, str])` indexes one immutable `LoadedPack` per identity and rejects missing or mismatched trusted hash pins.
- `resolve_package_set_at(events, archive, global_sequence, initial_packages=None)` returns the active `LoadedPack` tuple.

- [x] Add tests for package lookup, conflicting and changed content hashes, no-migration initial packages, inferred first `from` pins, replay before/at/after migration, and invalid `from` chains.
- [x] Run the tests and verify they fail because the archive and resolver do not exist.
- [x] Implement the immutable archive index and chain-validated global-sequence resolver.
- [x] Run all package migration tests.

### Task 3: Add the platform migration authority

**Files:**
- Modify `backend/app/gameplay/package_migration_runtime.py`
- Test `backend/tests/test_package_migration_runtime.py`

**Interfaces:**
- `PackageMigrationAuthority(store, archive, world_ref)` uses stream `platform:rule-packs:<world_ref>`.
- `migrate(command_id, idempotency_key, expected_revision, from_packages, to_packages, migration_ref, affected_fact_types)` appends exactly one `pack.migrated` event.
- The authority principal is `authority:platform:rule-pack-migration`.

- [x] Add tests for successful commit, duplicate retry, changed duplicate rejection, stale source set, expected-revision conflict, unknown target archive identity, and rejection zero-write behavior.
- [x] Run the tests and verify each expected failure is observed.
- [x] Implement duplicate replay before current-state checks, validate the complete source set and target archive identities, then append through `build_atomic_event_batch` and `GameplayEventStore.append_batch`.
- [x] Run the package migration tests and `backend/tests/test_gameplay_event_schema_registry.py`.

### Task 4: Freeze regression selection and record scope

**Files:**
- Create `docs/verification/selection/m5-3-package-migration.json`
- Create `docs/verification/m5-3-package-migration-20261125.md`
- Update `docs/v2-coordination/board.md`, `handoff.md`, and `daily/2026-11-25.md`

- [ ] Run final targeted tests with TEMP, TMP, and basetemp under a new F-drive run directory.
- [ ] Run M5-3 and the appropriate frozen Ownership/shared-replay selections, then record exact counts and any environment failure without relabeling it as success.
- [ ] Register the focused M5-3 nodes at the implementation commit and record deferred production startup wiring.
- [ ] Check `git diff --check`, stage only listed paths, commit, and push the A branch.
