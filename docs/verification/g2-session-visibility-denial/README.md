# G2 session visibility denial boundary

- Branch: `codex/g0-b3-ingress-20261109`
- Runtime unit: commit `0b587890ba732686b3d1d565a73848e83640701a`
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

The current provisional engineering budget is 10% maximum p95 overhead and
40 ms absolute p95 at 4,096 events. Earlier principal-specific economy view
runs exceeded those limits. On 2026-11-11, two fresh runs at the current HEAD
measured the existing owner, authority and denied-principal economy views at
up to 24.49 ms p95 and a maximum p95 ratio of 1.028 across 256, 1,024 and
4,096 event fixtures; those rows meet the provisional thresholds. Raw samples
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
