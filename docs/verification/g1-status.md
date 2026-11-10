# Architecture v2 G1 status

G1 selected migration tranche: exit conditions verified on 2026-11-10.

## Verified units

Each row is an independent commit with focused regression tests, a full G0
range comparison, archived raw evidence and a rollback boundary.

| Unit | Commit |
|---|---|
| ownership standard replay | `38baad8e` |
| gift standard replay | `f3800055` |
| credential standard replay | `949a7757` |
| land-right standard replay | `185528ba` |
| fixed-offer standard replay | `f7e8b2ae` |
| debt standard replay | `6174d8ee` |
| contract standard replay | `07f8e957` |
| ownership municipal-certificate rejected receipt | `6f0fb845` |
| Econ-1 wage rejected receipt | `0d2c5985` |
| survival rejected receipt | `db22569a` |
| contract rejected receipt | `68e7f644` |
| economy rejected receipt | `c607d42f` |

The shared helper remains deliberately narrow. Domain validation, event
payloads, digest algorithms, idempotency-key shapes, revision pins,
result-digest semantics and post-commit side effects stay in their domains.
Modifier Decimal handling and equipment receipt/bridge protections were not
changed. The world-admin barrier correction is separately committed as
`703ec8f4` and its race evidence is archived.

## Cumulative evidence

The final cumulative baseline used
`D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-economy-rejected-rerun --freeze`
from the repository root. It collected 9,982 nodes: 9,939 passed, 39 failed,
2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; all 45
accumulated added nodes pass; failure node/phase/error-type signatures match
the approved 39-node G0 set. The known WebSocket timeout stack differs only in
its runtime cancel-scope identifier. Collection errors are empty. Python,
OS, packages, dependency files and pytest environment match G0, and source
hashes stayed stable during the run. The first economy run and fixed rerun are
in [g1-economy-rejected-evidence.zip](g1-economy-rejected-evidence.zip).

## Boundary and remaining risk

This records the selected G1 migration tranche, not an approval to merge all
remaining runtime duplication. Candidate rejected-result call sites in
construction, inventory and organization-government, plus the separate
OwnerCommitBuilder and StoreReadSnapshot work, remain unstarted or require
their own decision and evidence. D2-D10 remain open. B3 Godot spatial
sampling, credential renewal and end-to-end interaction remain unverified.
The 39 approved G0 failures remain unchanged.
