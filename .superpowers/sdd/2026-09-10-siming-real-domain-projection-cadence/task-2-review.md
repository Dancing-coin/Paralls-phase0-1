# Task 2 Review

Commit reviewed: `6a26f3b` (`发布授权领域群体节拍`)

Spec compliance: ❌
Task quality: Needs fixes

Findings: 5

## Findings

### [P1] Compatible projection vectors are incorrectly required to equal the whole cadence vector

File: `backend/app/main.py:915-923`

The Task 2 plan requires legacy projection vectors to be compatible/contained
in `cadence.base_revision_vector` (plan line 214). The publisher instead
requires `projection.revision_vector == cadence.base_revision_vector`. A cadence
that pins multiple source streams therefore rejects valid projections that pin
only their own source stream(s), and assembled Production/Inventory/Social/Tax
projections are silently excluded from the published union whenever the
cadence contains additional streams. Compare each projection's keys and
values against the cadence vector without requiring identical key sets, while
still checking current store heads.

### [P1] The publisher does not verify that the cadence source is an authorized source projection

File: `backend/app/main.py:882-902`

The only source authorization check is that some committed event exists at the
caller-provided stream/revision. Any current GameplayEvent stream (for example
an unrelated inventory or economy stream) can therefore be presented as
`cadence_source_ref` and published as an authorized cadence. The global plan
requires cadence authorization to come from an existing committed world-mode,
activation, or schedule projection. Validate the source event/projection type,
visibility, and its binding to the cadence before publishing; otherwise this
public seam bypasses the cadence authority boundary.

### [P1] Caller-supplied legacy projections are admitted without capability/source validation

File: `backend/app/main.py:913-927`

`legacy_projections` are accepted solely on ref uniqueness, scope, and revision
vector checks. A caller can inject an arbitrary payload with a public or
organization-summary scope, including an unregistered behavior or owner-bound
fields, and have it enter `population_cadence_event` without the source
controlled capability/Owner admission required by the approved decision
surface. Keep this seam limited to the existing typed legacy supply row (or
validate its capability, source refs, and allowed payload shape before unioning
it).

### [P2] Published projection order depends on caller tuple order

File: `backend/app/main.py:913-927, 950-952`

The event serializes `accepted.values()` in insertion order. Reordering
`legacy_projections` changes the event payload and downstream digest even with
the same cadence and facts, while the surrounding read-set/assembler contract
requires deterministic ordering. Serialize projections sorted by `ref` after
validation.

### [P2] Task 2 commit includes unrelated Task 1 source/assembler edits and does not test the domain union

Files: `backend/app/population_continuity/domain_projection_sources.py:94-102,283-292`, `backend/app/population_continuity/store_projection_assembler.py:57-166`

The brief limits Task 2 implementation changes to `main.py` and the two focused
test files. This commit also changes Task 1 projection-source and assembler
behavior, making the review boundary and rollback unit unclear. More
importantly, the new publication test asserts only the cadence envelope and
never asserts that assembled domain projections are present in
`population_projections`; the exact-vector bug above can therefore pass the
reported 48-test suite while the stated union behavior is unproven. Keep the
Task 1 hardening in its own reviewed commit and add a publisher test with a
multi-stream cadence plus at least one assembled projection.

## Verification

Review was static only; tests were not rerun. The implementer report claims 48
focused tests passed, `compileall` passed, and `git diff --check` passed. The
five findings above block approval. No second runtime/store/bus/clock/scheduler
was added by this commit, and the game-start path still delegates through one
explicit publisher call.
