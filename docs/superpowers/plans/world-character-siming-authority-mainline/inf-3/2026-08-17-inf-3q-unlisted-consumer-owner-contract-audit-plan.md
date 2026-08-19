# INF-3Q Unlisted Consumer Owner-Contract Audit Plan

Status: `the exact drought-to-dehydration row is implemented and verified; other unlisted consumer edges remain owner-contract blocked`

1. Preserve C4 rejection and zero-write behavior for every unlisted edge
   except the separately approved committed
   `weather:drought -> state:dehydrated` row.
2. Keep the immutable catalog closed except for the fixed cold, heat, and
   dehydration Survival target rows. Do not add a generic weather value,
   target-domain fragment, fanout, retry, or router surface.
3. The approved drought row uses only committed `weather_front.propagated`,
   not `drought_process_advanced`; it pins the project-visible profile-region
   assignment, fixed Survival event vector, privacy, idempotency, receipt, and
   replay, with no compensation/reopen behavior.
4. Any future unlisted edge still needs its own exact Owner-Admission Contract,
   RED suite, and independent Harness before runtime code.
