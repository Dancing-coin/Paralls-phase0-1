# M2-2 `read_as` contract audit

- Snapshot: A branch `thread-a/ownership-bond-followup-20261121` at `945953db2dee53212baa821b84deaa297c825ca7`.
- Scope: static comparison of the formal visibility/projection contracts with the gameplay event model, registries, and migrated Ownership/Credential call sites.
- Verification level: static only. No tests or runtime checks were run.

## Formal requirements checked

- `read_as(principal, scope, as_of_tick, fact_types)` is the gameplay read entry point.
- A read resolves principal visibility qualifications, applies FactType visibility and `learnable_by`, computes principal-specific `known_time` from `event_time`, applies distortion, and returns source Owner/revision, `event_time`, `known_time`, and `freshness`.
- FactType visibility has no default. Selectors include `world`, faction and subject-based selectors. `secret` and `debug_only` reads require explicit denial behavior.
- Projection inputs include principal, scope, `as_of_tick`, and FactTypes. The filter order is FactType, visibility, time, distortion, field projection.

Sources: external Architecture v2 `01-内核/02-可见性强制.md`, `01-内核/04-三本账与投影.md`, and `03-事实类型/04-FactType完整schema.md`; migration plan M2-2 and migration spec U6/U7.

## Current implementation evidence

| Requirement | A-tip evidence | Result |
|---|---|---|
| Persisted event occurrence time | `backend/app/gameplay/models.py:80-94` defines `GameplayEvent`; it has no `event_time`. `rg -n event_time backend/app/gameplay/models.py backend/app/gameplay/event_store.py` returned no matches. | Missing authoritative input. Global sequence and stream revision are ordering/version values, not a world tick. |
| Event schema to FactType and visibility | `backend/app/gameplay/event_schema_registry.py:18-22` registers only `event_type`, `schema_version`, and `schema_digest`. `backend/app/gameplay/fact_type_registry.py:31-86` maps known event names to domains and schema-declared names to a domain inferred from the event name. | No production mapping from each event type to a v2 FactType visibility declaration. |
| Selector qualification | `backend/app/gameplay/fact_type_registry.py:133-141` checks only that visibility is nonempty; the compiled `FactType` retains the visibility mapping. `rg -n principal backend/app/gameplay` finds principal references in domain authorization and privacy code, but no `principal_selector` interpreter or common qualification resolver. | No common qualification contract. The rule-pack validator's `learnable_by` matches preserve/narrow checks, not selector evaluation. |
| `read_as` entry point | `rg -n read_as backend/app` finds no gameplay implementation. The `character_agent` `read_ask` methods are a separate private-memory store and do not provide the world-fact projection contract. | Missing. |
| Actual migrated read consumers | `credential_runtime.py:195,350,419`, `credential_reference_chain.py:101`, `ownership_runtime.py:356,372,413,469,553,632,685,768,891,972,1143,1216`, and `adventure_basic_reference.py:250,253,256,543,556,818,821,1096,1099,1102,1105,1108` call `read_events()` for projections, validation, reference freezing, or scenario views. `adventure_basic_closure.py:82,87` reads for closure/rebuild comparison. `ownership_runtime.py:1126` uses `read_stream()` for contract projection. | Calls are enumerated statically, but each needs classification as trusted owner/recovery read versus principal-facing read before replacement. |

## Stop point and required inputs

M2-2 is blocked at the storage/authority contract boundary. Implementing the specified semantics requires a persisted source for `event_time` and a common way to resolve principals and event visibility. Adding an event field touches `models.py` and its persistence/replay contract, which the A boundary rules reserve for escalation. A cannot safely substitute commit order, a caller-supplied time, or current payload fields for world occurrence time.

Required before implementation:

1. Project-owner approval and cross-thread coordination for a backward-compatible persisted event-time source, including legacy event behavior and replay/checkpoint compatibility.
2. A runtime principal qualification source and the supported selector grammar/evaluation contract. The architecture schema names selectors but the codebase has no shared interpreter.
3. A production mapping from event types to FactType refs and visibility declarations, including behavior for legacy events with no mapping.
4. A call-site classification for the listed migrated-domain reads so trusted authority/recovery paths remain distinct from subject-facing reads.

No code, persisted event, or test contract was changed. Once the storage contract is authorized, the mechanism can be implemented in an A-owned read layer and wired to confirmed subject-facing consumers. M2-2 remains blocked until then.

## DoD status

| Item | Status |
|---|---|
| U1-U5 | Not applicable to this mechanism audit. |
| U6 | Static caller enumeration recorded; principal-facing classification remains incomplete. |
| U7 | Not met. Visibility declarations are not enforced by a gameplay read path. |
| U8 | Not applicable. |
| U9 | Static only; no tests or frozen selections run. |
| U10 | This file records the inspected source paths and the static-only status. |
| U11 | Not applicable to an audit with no code or domain migration. |

## 2026-11-26 current-tip caller classification addendum

- Current A tip inspected: `299767446515338576a615c36c6fccfa03cacda5`.
- Ownership/Credential caller classification is now recorded in `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`. The inspected reads are trusted Owner preconditions, trusted resolver snapshots, idempotent recovery, sample/debug views, or replay/checkpoint verification. `CredentialPresentationValidator.verify_right_holder_presentation` has test callers but no production caller in the inspected `main.py` call graph. No production subject-facing Ownership/Credential projection route was identified.
- This completes the static classification of the listed A-side Ownership/Credential callers for U6. It does not prove that no caller exists outside the inspected application and test trees, and it does not implement visibility enforcement. Newly migrated readers still require classification.
- U6 status: static caller inventory and classification recorded. U7 remains not met; M2-2 remains blocked on authoritative persisted event time, principal qualification and selector semantics, and event-to-FactType visibility mapping.

## 2026-11-27 optional event_time persistence increment

- Implementation base: `6bea74901c6a1649281016fa12d84676dafe5086`. Validation ran on the uncommitted A worktree change.
- `GameplayEvent.event_time` is now an optional strict nonnegative integer. Omitted legacy values load as `None` and are omitted again during serialization. Explicit values persist through durable close/reopen and snapshot export/import. No value is inferred from global sequence or stream revision.
- Persistence tests cover explicit-value round trip, legacy snapshots with the field absent, bool rejection with zero writes, and legacy serialization that omits unknown time. Initial compatibility selections exposed 21 equipment receipt failures and two shared-replay checkpoint hash failures because `None` was serialized. Field-level `exclude_if` restored the old serialized shape. Corrected equipment selection: 87/0/0; corrected shared-replay selection: 990/0/0.
- Focused event-store contract, persistence, and replay tests: 50 passed, 2 warnings. Focused event_time tests: 3 passed, 2 warnings.
- Frozen five selections: ownership 24/0/0, modifier 12/0/0, equipment 87/0/0, inventory 56/0/0, shared-replay 990/0/0. All 28 registered selections completed with zero problems and zero improvements.
- Full backend suite: 10,761 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings, exit 1, 28:27. Four failures reproduced on exact parent `6bea7490`: missing `tokenizers` in calibration repair, existing Godot CharacterMotor parse errors in task45, cold_ready resource bounds, and task8 registry-probe parse errors. The fifth node, recovery-measurement, failed only while inherited `GIT_CONFIG_VALUE_0` was malformed; with process-level `GIT_CONFIG_COUNT=0`, it passed on both parent and current worktree (1 passed each).
- Python was 3.12.2 at `D:\Temp\paralls-g0-py312\Scripts\python.exe`; `PYTHONPATH` pointed to the corresponding worktree backend and `app.__file__` resolved inside that worktree. Raw outputs, pytest temporary files, and caches are under `F:\paralls-verification\thread-a\m2-2-event-time-20261127-01\`.
- This increment does not implement the event-time producer, `read_as`, principal selector qualification, or event-type to FactType visibility mapping. M2-2 remains blocked and U7 remains unmet.
