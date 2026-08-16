# INF-3F Ecology Weather-Front Wave Fanout Plan

Status: `implemented and verified; fixed two-wave Ecology-only row`

1. Re-run INF-3D path, INF-3E fanout and continuation-gate profiles; preserve
   their owner, consumer and replay evidence.
2. Add focused failing tests for the closed two-wave plan and its zero-write
   admission boundaries.
3. Add only the fixed policy and an `EcologyHazardAuthority` entrypoint that
   builds existing Ecology fragments and submits one append batch. This package
   leaves cross-domain edges to separately admitted packages such as INF-3G.
4. Add a separate Harness selector per capability, then synchronize INF-3,
   root formal documents, August analysis and harness guidance.
5. Run focused and predecessor tests, docs check, `git diff --check` and full
   `python -m pytest -q`.

Completion evidence: the policy/entrypoint began with a collection-failing RED
suite. The dedicated Harness report records one selector per capability at
`.harness/verification/infra-ecology-weather-front-wave-fanout-report.json`.
