# INF-3R Drought Government Advisory Implementation Plan

Status: `implemented and verified`

1. Completed: add focused RED tests for the exact source, jurisdiction pin, privacy,
   revision, duplicate, catalog/descriptor, full replay, and checkpoint-tail
   replay rules.
2. Completed: add an independent `infra-weather-front-government-drought-advisory` Harness
   profile and verifier with success and zero-write selectors.
3. Completed: extend only `GovernmentAuthority` with the fixed advisory intent, verifier,
   projector branch, receipt reader, and canonical append vertical.
4. Completed: add one immutable descriptor and one immutable governed catalog row after
   the tests prove their required fields.
5. Completed: verify the focused suite, independent Harness, replay/privacy/idempotency/
   receipt evidence, docs profile, and diff check.
6. Completed: update the owner-operation baseline, completion audit, remaining-scope,
   INF-3 README, blocker taxonomy, and continuation checkpoint. Do not mark
   August INF A-D complete.

No generic Government policy registration, weather router, restriction state,
payment, material effect, fanout, compensation, scheduler, second runtime, or
caller-selected authority coordinate is in scope.
