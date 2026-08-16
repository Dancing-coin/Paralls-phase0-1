# INF-2V Bounded Payroll And Operating-Window Closure Re-closure Plan

Status: `implemented bounded and independently verified 2026-08-16; broader INF-2 remains incomplete`

1. Add focused red coverage for the current owner split, committed-evidence
   wage path, paid/overdue outcomes, duplicate/revision/privacy fences, replay,
   and append-derived receipt behavior.
2. Keep the existing Organization-owned window writers and Economy-owned wage/
   account writers unchanged except for the smallest read-only receipt helper
   needed to prove receipt derivation.
3. Extend the independent verifier/report and retain the existing
   `infra-payroll-operating-window-closure` profile as a backend-only,
   non-generic proof.
4. The focused pytest file, verifier, Harness profile, diagnostics, and
   `git diff --check` are green; the package is therefore marked verified.

Do not introduce a scheduler, clock, second store, coordinator writer, generic
payroll policy, or cross-domain settlement abstraction.
