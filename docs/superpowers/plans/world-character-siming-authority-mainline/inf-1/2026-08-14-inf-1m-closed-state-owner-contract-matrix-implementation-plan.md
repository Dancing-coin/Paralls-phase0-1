# INF-1M Closed State Owner Contract Matrix Plan

Status: `implemented and verified closed five-row matrix; generic routing remains incomplete`

1. [x] Audit the verified Survival, Construction and Ecology row contracts and
   record that their current registry/dispatch paths are split.
2. [x] Define the exact five-row owner/stream/event/privacy/revision matrix.
3. [x] Add focused failing tests for the shared reader and per-owner enforced
   lookup, including unknown and forged contract zero writes.
4. [x] Implement the immutable closed reader in `semantic_registry.py`; do not
   add an open registration or generic writer.
5. [x] Make the existing Survival, Construction and Ecology append boundaries
   verify their own fixed row before creating fragments.
6. [x] Add independent Harness checks and refresh existing focused replay and
   privacy evidence.
7. [x] Synchronize August analysis, root dependency spec/plan, INF-1 README,
   Harness documentation and package evidence after fresh full-suite proof.
