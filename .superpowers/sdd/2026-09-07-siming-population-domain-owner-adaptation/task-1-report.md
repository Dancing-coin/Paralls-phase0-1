# Task 1 Report: Baseline and Capability-Adapter Matrix

## Changed files

- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-07-siming-population-domain-owner-adaptation-design.md`
  - Added the immutable five-row admission matrix, explicit status values,
    source/Owner/capability mappings, privacy and replay gates, and the
    distinction between domain contracts and population capabilities.
- `backend/tests/test_siming_population_domain_owner_matrix.py`
  - Added three focused assertions for exact statuses, design-note alignment,
    and prohibited generic owner/writer/event-store expansion.
- `docs/harness.md`
  - Documented the matrix gate and its backend-only verification command.

## Verification

`python -m pytest -q backend/tests/test_siming_population_domain_owner_matrix.py`

```text
3 passed, 1 warning in 0.49s
```

`python scripts/verification/check_docs.py`

```text
overall_docs_passed=True
docs_index_paths_exist=proved
superpowers_specs_have_plans=proved
harness_profiles_documented=proved
harness_registry_documented=proved
agents_md_is_short_entry_map=proved
```

`git diff --check`

```text
passed (no output)
```

## Commit

`726c792589d7383098b60776438d5773f4e1deea`

## Concerns

The parent worktree already contained the untracked implementation plan; it
was intentionally left out of this Task 1 commit. No runtime capability or
Owner adapter was added, so later tasks must implement and independently prove
each matrix row before promotion.
