# DG-P6/P7 Opening Gate Review Plan

Status: `completed; DG report fresh-green; P6/P7 remain gated`

## Work packages

1. Review F0-F2 completion, stale evidence, unresolved risks and ownership.
2. Confirm the fixed chain `P5 -> foundation -> P6 -> P7`.
3. Produce the opening matrix for P6A/B/C/D and P7A/B/C/D, including what may
   be prepared in parallel and what is a hard implementation predecessor.
4. Assign evidence owners, report paths, Harness `run_id`, commit, run date,
   compatibility decision, expected future profile IDs, rollback targets and
   stop conditions.
5. Publish the checklist without renaming or reordering existing phase files.

## Opening criteria

- P6A/B: F0, F1A, F1B and capability/privacy denial evidence;
- P6C/D: F1C, F2, package activation/rollback/audit/replay evidence;
- P7A-D: P6D governance evidence plus read-only, branch replay,
  reproducibility and robotics safety profiles.

## Done/blocked

Done means one reviewed checklist, owner matrix and dependency graph exist.
Missing predecessor evidence keeps the next track planned/blocked. Any future
phase rename, reorder or P6D dependency change requires a separate migration
decision record.

The current run set proves only F0 evidence-baseline, bounded F1 foundations,
and F2 taxonomy. It does not open P6/P7; generic F1 contracts and future
successor profiles remain required.

## Freshness review

Accept evidence only from the current commit or a named compatible commit with
unchanged owner, write path, contract/schema revision, projection/privacy rule,
Harness assertion, and migration/rollback behavior. Any such change invalidates
the successor proof and requires a predecessor plus downstream rerun. Staged or
future-dated documentation is never executable proof.
