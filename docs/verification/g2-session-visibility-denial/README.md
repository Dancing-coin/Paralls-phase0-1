# G2 session visibility denial boundary

- Branch: `codex/g0-b3-ingress-20261109`
- Runtime unit: commit `0b587890ba732686b3d1d565a73848e83640701a`
- Classification: separate security defect fix with an intentional network behavior change; not a behavior-preserving shared-mechanism migration or completed G2 authorization mechanism.
- G0 comparison source: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`
- Previous full G2 comparison: `59084f369ec6c19672b91e26770b81d9e17ef510`
- Status: bounded fail-closed repair verified; G2 visibility authorization and its performance gate remain open.

## Boundary behavior

The WebSocket session proposal probe previously accepted client-selected
session and actor references and synthesized participant acceptance. The
projection pull trusted a client-supplied session ID and read its event stream
without connection context. The handoff and carry/place probes similarly
accepted client-selected references and synthesized completion observations.
Commit `0b587890` makes each of those network routes return a fixed denial.
Known and unknown IDs receive identical replies, session pull denial happens
before any stream lookup, and no probe commits a domain event. A valid backend
binding alone is also insufficient when session-specific disclosure evidence
is absent.

The change leaves session, handoff and carry/place Owner services and their
atomic domain transactions intact. The tests still exercise those APIs
directly. `_build_committed_session_event_projection` remains an internal,
integrity-checked recovery helper, but the network pull no longer calls or
exposes it. The Godot verification probes now record domain settlement and
network denial separately; this does not validate a Godot client interaction.

This unit implements denial in the absence of authorization evidence. It does
not yet implement allowed projections for participants, observers, delivered
recipients or separately authorized debug sessions. Authoritative disclosure,
historical perception/identity recognition, delivery and trustworthy session
known-time facts are still missing. See the [boundary audit](../g2-visibility-budget/boundary-audit.md).

### Network compatibility impact

Every request to these four message routes is currently denied, including a
request from a bound participant. This is a temporary closure of unsupported
network operations, not selective authorization.

| WebSocket message | Previous behavior | Current behavior | Inspected Godot caller |
|---|---|---|---|
| `embodied_interaction_session_probe` | Created/recovered a handshake and automatically accepted participants | Fixed rejected ack; no session write | `scripts/verification/EmbodiedInteractionSessionProbe.gd` |
| `embodied_interaction_session_projection_pull` | Returned the next stored session projection or cursor result | Fixed denial before lookup; no ID/cursor in response | Same session probe |
| `embodied_handoff_probe` | Started and settled handoff from client-selected actor/asset references | Fixed rejected ack; no settlement | `scripts/verification/EmbodiedHandoffProbe.gd` |
| `embodied_grab_carry_place_probe` | Started and settled carry/place from client-selected references | Fixed rejected ack; no settlement | `scripts/verification/EmbodiedCarryPlaceProbe.gd` |

Those Godot live probes still require an accepted ack and corresponding
projection events. Static inspection therefore establishes that their former
network success contract is incompatible with this commit. Their associated
`embodied-interaction-session`, `embodied-handoff-authority`, and
`embodied-grab-carry-place-authority` profiles, and the dependent
`embodied-interaction-foundation-all` aggregation, must not be reported as
passing live integration based on backend denial tests. This review did not
run Godot or the broad runtime harness. Local consumers and direct Owner APIs
remain separate paths; passing their tests cannot replace the disabled network
workflow.

The changed tests retain direct domain, private-field, forged-bus and durable
recovery protections while asserting the new network denial. Unchanged test
outcomes in the full comparison demonstrate no additional failures in that
recorded suite; because network expectations changed, they do not demonstrate
preservation of the previous network behavior. Track `0b587890` as its own
security defect commit, outside G1 refactor accounting, and give it no credit
toward G2 positive authorization, three-time or epoch exit criteria.

## Verification environment and commands

Environment: Windows 11 `10.0.26200`, Python 3.12.2 from
`D:/Temp/paralls-g0-py312/Scripts/python.exe`, package SHA-256
`b97ab506b7c2702733b2769e69a6e75f648cfb62024788c81eb1b39e09f600c7`, equal to
the G0 environment snapshot. The full runner used the frozen G0 scope
`backend/tests/` and its recorded runner/script. Targeted output and full
artifacts are included in this directory.

Focused regression command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_embodied_interaction_session.py backend/tests/test_embodied_interaction_session_runner.py backend/tests/test_embodied_handoff_authority.py backend/tests/test_embodied_grab_carry_place_authority.py backend/tests/test_websocket_session_auth_service.py -q --junitxml=D:/Temp/g2-session-visibility-denial-targeted-20261110-r1/junit.xml
```

Result: **43 passed, 6 existing deprecation warnings**.

The JUnit breakdown is session 19, runner 2, handoff 5, carry/place 7, and
WebSocket session binding 10. Thus the first four files contain 33 cases and
the fifth adds 10; the six verification-script cases below are separate.

Review rerun on 2026-11-11 at `a8889e98`: the same five-file command returned
**43 passed, 6 warnings in 34.37s**. The documentation harness
`python scripts/verification/harness.py --profile docs` also passed, with
cleanup passed (run ID `e813c1062d5340c49ad051208aa969c1`). This review changes
only diagnostics and records; it did not rerun the 10,044-node baseline or
Godot integration.

The focused regression command also exercises the retained internal projection
integrity/recovery helper and proves that valid backend session binding alone
does not grant session access. The three edited verification-runner modules
were syntax-compiled. The related runner/profile static checks reported **6
passed**:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest scripts/verification/tests/test_verify_embodied_interaction_session.py scripts/verification/tests/test_harness_registry.py -q --junitxml=docs/verification/g2-session-visibility-denial/verification-script-junit.xml
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m py_compile scripts/verification/verify_embodied_interaction_session.py scripts/verification/verify_embodied_handoff_authority.py scripts/verification/verify_embodied_grab_carry_place_authority.py
```

Full baseline command, run from the repository root:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/g2-session-visibility-denial-baseline-20261110-r1 --freeze
```

Result: **10,044 collected; 10,001 passed, 39 failed, 2 skipped, 2 xfailed; 0 collection errors**. The runner exits 1 because it preserves the 39 accepted G0 failures. Relative to G0, all original 9,937 nodes retained their outcomes and all 107 additional nodes passed. Relative to the previous 10,041-node G2 run, the three added session denial cases passed and no prior outcome changed.

The failure set contains the same 39 test names, phases and error types as
G0. Four failure messages vary only in randomized pytest temporary directory
numbers. One timeout stack varies only in AnyIO's randomized cancellation
scope ID; the timeout, stable stack and error remain the same. The exact raw
differences and normalization are recorded in `baseline-comparison.json`.

## Performance gate

Review clarification (2026-11-11): 24.49 ms is a recorded sample, not budget
acceptance. The earlier 71–79 ms samples preceded the read-copy optimizations
`f60a487c` and `59084f36`; the implementation versions were different. Two
same-process copy-path diagnostics now show a 2.61–2.66 median ratio between
the former deep-copy expression and the current helper. The former path's p95
in this experiment is still only 43–45 ms, so the historical variability is
not fully explained. The diagnostic, raw samples, limits and commands are
linked from the [performance report](../g2-visibility-budget/report.md).
The candidate target remains unchanged and cannot authorize positive session
reads. Historical measurements are retained without rewriting their values.

The current provisional engineering budget is 10% maximum p95 overhead and
40 ms absolute p95 at 4,096 events. Earlier principal-specific economy view
runs exceeded those limits. On 2026-11-11, two fresh runs at the current HEAD
measured the existing owner, authority and denied-principal economy views at
up to 24.49 ms p95 and a maximum p95 ratio of 1.028 across 256, 1,024 and
4,096 event fixtures; those sample values fall below the candidate thresholds
without closing the performance gate. Raw samples
and the per-principal table are in `principal-view-run1.json`,
`principal-view-run2.json`, and `performance-comparison.json`.

This is an in-memory economy domain view with a caller-supplied principal, not
an authenticated session `read_as` path. It does not measure the missing
session disclosure authorization, network send, historical replay or durable
store contention. The fixed WebSocket denial avoids event-store scanning, but
that fast path cannot establish the cost or correctness of an allowed session
projection. Keep that G2 gate open until the actual authorized session path is
available for principal-specific measurement; do not use the economy sample
as proof of session access readiness. Earlier storage and fixture exceedances
remain documented in the shared performance report.

## Rollback and remaining scope

Runtime and regression changes are one commit and can be rolled back with:

```powershell
git revert 0b587890ba732686b3d1d565a73848e83640701a
```

That restores the prior harness routes and therefore restores the reviewed
untrusted ingress risk; do not use that rollback without a replacement access
boundary. Evidence archive changes can be reverted separately without changing
runtime behavior.

This unit does not complete G2. Positive session authorization, event/known/
presented time coverage, the authority epoch fence, D2–D10 decisions, and B3
Godot spatial sampling, credential renewal and end-to-end acceptance remain
open.
