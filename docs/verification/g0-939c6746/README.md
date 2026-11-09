# G0 candidate baseline, 2026-11-09

This is evidence for review, not G0 approval. Runtime source under test was
`939c674681c3f2c648c3286bd27b381bb3a7490a` on
`codex/g0-b3-ingress-20261109`; the original baseline was `5321266d`.
The evidence-only commit containing this file comes after the tested source.

## Reproduction

Two serial runs used Windows, Python 3.12.2, the same virtual environment,
`backend` working directory and the frozen `run1/test-files.json`. The runner
collected `tests`, disabled pytest's cache provider, and captured every node,
phase, outcome and failure stack in `run1/results.json` and `run2/results.json`.
`invocation.json` and `environment.json` record arguments, dependency versions,
source hashes and status. A copy of the runner is [run_baseline.py](run_baseline.py);
the second run used the first run's manifest. Python 3.12.2 differs from CI's
3.12.14 and this environment lacks the optional `tokenizers` dependency.
The [raw archive](raw-runs.zip) preserves the original output bytes, including
the manifest used for its recorded SHA-256; the readable JSON copies may have
Git-normalized line endings. Extract the original manifest when reproducing.

For example, from the evidence branch worktree in PowerShell, using the same
Python environment and an unused destination for each path:

```powershell
$g0Evidence = (Resolve-Path 'docs/verification/g0-939c6746').Path
$g0Checkout = 'D:/Temp/paralls-g0-review-source'
$g0Raw = 'D:/Temp/paralls-g0-review-raw'
$g0Output = 'D:/Temp/paralls-g0-review-run'
git worktree add --detach $g0Checkout 939c674681c3f2c648c3286bd27b381bb3a7490a
Expand-Archive -LiteralPath "$g0Evidence/raw-runs.zip" -DestinationPath $g0Raw
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' "$g0Evidence/run_baseline.py" `
  --repo $g0Checkout --output $g0Output `
  --manifest "$g0Raw/paralls-g0-939c6746-run1/test-files.json"
```

On 2026-11-09 a separate clean checkout at the pinned source collected the same
9,922 nodes in the same order, with matching package and manifest hashes. A
targeted execution of the five G1 node lists plus the player object, spatial
ingress, character recall and long-session recovery files collected 375 items
and passed all 375. [reproduction-check.zip](reproduction-check.zip) preserves
the collection and targeted results, invocations and environment. This used
the same local virtual environment and operator as the original runs; it is
not independent reviewer reproduction.

Both runs collected 9,922 nodes and produced 9,879 passed, 39 failed, two
skipped and two xfailed. The capture schema groups xfails with skips. Node
order, per-node outcome, failure order, phase and error type matched; source,
manifest and package hashes matched and the worktree remained clean during
both runs. One normalized stack hash differs: the scheduling trace timeout
contains a different asyncio cancel-scope runtime identifier; the exception
and deadline are otherwise the same. This is a repeated local run, not an
independent reviewer reproduction or a portable environment image.

## Failure classification

All 39 nodes also failed in the earlier Python 3.12 baseline at `a10f75a7`.
Of these, 38 also failed in the original 3.13 baseline; the remaining
`test_all_22_repaired_budgets_equal_fixed_official_usage` passed there but
fails here because `tokenizers` is absent. Original per-node reasons are
retained in [original-failure-classification.md](original-failure-classification.md);
its historical links and counts refer to the separate Paralls-docs baseline.
The current raw stacks and exact node names are in both results files.

Current categories, retaining all failures in the baseline:

- 20 environment failures: 12 Godot static checks and two profile/source
  checks use root-relative paths from `backend`; five subprocess checks cannot
  import test modules or `scripts` with the inherited paths; one calibration
  check lacks `tokenizers`. These failures do not establish those behaviors.
- 15 historical evaluation tests fail at the `char_a.yaml` frozen source pin.
  The old pinned content exists at `19551f49`; changing the pin would falsify
  that evaluation's provenance.
- Four remaining legacy-contract failures: calibration has no admitted frozen
  candidate, a continuity assertion expects `observe` instead of the current
  `observe_target`, a legacy diagnostic frame conflicts with the gateway's
  frozen-frame requirement, and an unbound WebSocket approach cannot produce
  the historical scheduling trace. The last trace is still referenced by a
  verification script and needs a separately authorized equivalent test.

These explanations delimit the failures; they do not claim the affected
diagnostic or integration paths are accepted. No current failure in the five
named G1 regression lists remains. Reviewers should assess the retained
failures and whether the client limitation below is acceptable for G1.

## Blockers and G1 scope

- B1: `test_package_exchange_rejects_corrupt_receipt_event_reference` and
  related invalid-receipt cases pass in both runs.
- B2: `test_active_tension_prioritizes_latest_focused_knowledge_within_budget`
  and malformed-target coverage pass in both runs.
- B3: `test_player_object_ingress.py` covers bound spatial samples, an actual
  WebSocket interaction, exact retry, rejected sources and projection repair;
  it passes in both runs. The Godot client does not send these samples, and
  credential renewal and real Godot-to-server interaction are not verified.
  This is an explicit G5/client integration limitation, not evidence of an
  end-to-end fix. The old unbound path is rejected.
- B4: `test_population_long_session_recovery.py` covers the published digest,
  changed kernel rejection, checkpoint corruption and recovery in both runs.

All historical nodes in the adjacent G1 lists remain collected and passed in
both runs: ownership 5, modifier 11, equipment 72, inventory 49, and shared
replay 201. Lists may overlap; these numbers must not be added as unique tests.
On top of that frozen baseline, `test_modifier_digest_preserves_nested_decimal_representation`
and `test_equip_duplicate_rejects_each_invalid_receipt_boundary_without_writes`
add 15 cases covering nested Decimal representation and equipment receipt,
transaction, event identity, stream and visibility rejection without writes or
bridge side effects. The five historical lists plus these cases passed 345 tests
on Python 3.12.2 from `backend` on 2026-11-09. These are additional nodes, not
part of the two 9,922-node runs above. Extend each set for actual callers before
its migration; the tests do not prove all possible Decimal or equipment inputs.

At test commit `8fa4bc0a6c3d561b1320b5a43ce64e2657acf75a`, those 15
supplemental nodes were run twice using the same Python 3.12.2 environment and
`backend` working directory. Both runs passed all 15 in identical collection
order, with matching dependency hashes and unchanged source. The original
results, collected node IDs, invocations and environment snapshots are in
[supplement-8fa4bc0a.zip](supplement-8fa4bc0a.zip). These targeted runs do not
replace a full-suite run at the later commit.

The [historical source and gate analysis](original-sources-and-gates.md)
records the v1/v2 delivery conflict and maps D2-D10 to their dependent stages.
Its relative links refer to the original Paralls-docs repository. These
decisions remain open. This evidence does not approve G1, close those decisions,
or establish UE, Godot runtime, or Demo acceptance. Technical-lead review and
approval remain outstanding; the local author cannot assert independent review.
