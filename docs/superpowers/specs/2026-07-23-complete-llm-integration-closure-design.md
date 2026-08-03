# Complete LLM Integration Closure Design

Date: `2026-07-23`

Status: approved

## Purpose

This spec closes the remaining real-provider gap for the repository's declared
character and Siming LLM surfaces without changing their authority boundaries.

It does not treat provider readiness, schema-shaped fallback output, or an
isolated HTTP success as real-provider closure. Completion requires separate,
durable live evidence for:

1. character dialogue
2. character `L2` reasoning
3. character `L3` planning
4. Siming DeepSeek app wiring

## Decisions

The following decisions are normative for the implementation plan.

### Character Configuration

- `CHARACTER_MODEL_*` is the only committed runtime configuration contract for
  the character gateway.
- `DEEPSEEK_*`, `QWEN_*`, and `SEED_DOUBAO_*` may be mapped into
  `CHARACTER_MODEL_*` by an operator before process start, but character runtime
  code must not consume those aliases implicitly.
- `CHARACTER_MODEL_PROVIDER_KIND` selects the provider. Provider-correlated
  endpoint and model defaults must never leak across providers.
- `CHARACTER_MODEL_ROUTE_OVERRIDE` must be unset for normal online proof.
- `DIALOGUE_MODE=online` is required for dialogue live proof.
- Repository-safe defaults remain `DIALOGUE_MODE=stub` and an uncredentialed
  provider configuration. This closure does not commit a real key or enable paid
  model calls by default.
- DeepSeek is the required target for this closure run. This does not reverse the
  readiness documentation's broader Qwen/Seed provider recommendations.

Precedence is fixed as follows:

| Character setting | First | Second | Missing behavior |
| --- | --- | --- | --- |
| provider | `CHARACTER_MODEL_PROVIDER_KIND` | repository default | live proof fails if not `deepseek` |
| endpoint | `CHARACTER_MODEL_ENDPOINT` | provider-correlated safe default | live proof fails if host is not the intended provider |
| key | `CHARACTER_MODEL_API_KEY` | none | live proof fails |
| model | `CHARACTER_MODEL_MODEL` | provider-correlated safe default | live proof records the resolved model |
| timeout | `CHARACTER_MODEL_TIMEOUT_SECONDS` | repository default | invalid or non-positive values fail config loading |
| route | unset `CHARACTER_MODEL_ROUTE_OVERRIDE` | normal router resolution | any override fails normal-route proof |
| dialogue mode | `DIALOGUE_MODE=online` | repository default `stub` | non-online mode fails dialogue proof |

### Siming Configuration

- The approved Siming backend-chain proof contract remains authoritative.
- Siming live proof consumes the real settings loaded by `backend/app/config.py`.
- The verifier must not force `SIMING_LLM_MODE`, provider order, endpoint, model,
  timeout, or routes, and must not replace `app.main.settings` with synthesized
  values.
- The required credential is `SIMING_LLM_API_KEY` or the key declared on the
  selected `SIMING_LLM_ROUTES_JSON` route. `DEEPSEEK_API_KEY` is not a Siming
  credential fallback.
- A route-level key is the sole intentional extension to the 2026-06-25 proof's
  global-key rule. Legacy global mode still accepts only `SIMING_LLM_API_KEY`;
  every other real-settings, failure, chain, redaction, and no-retry rule from
  that approved proof remains unchanged.
- The closure route is either the legacy global route or one explicit route, not
  both. Route mode requires a filled `route_id`, `provider`, `endpoint`, `model`,
  `timeout_seconds`, `enabled`, and key.
- `SIMING_LLM_MODE=http` and `deepseek_chat` as the selected first enabled route
  are required for the DeepSeek live proof.
- The proof has no retry. Timeout changes require a measured failure record and
  a human-approved timeout ceiling.

### Strict Live Semantics

- Syntactic normalization is allowed before validation, including JSON decoding
  and scalar-to-list conversion where the declared contract permits it.
- Required semantic fields must not be invented to make live proof pass.
- In particular, missing or empty `active_goal_frame.primary_goal` fails the L3
  live scenario.
- Local continuity fallback remains available where the runtime already supports
  it, but fallback output is recorded separately and cannot satisfy live closure.
- Planner-side shaping cannot occur before gateway validation and is therefore
  not an allowed L3 contract-repair strategy.

## Scope

This closure covers only:

- character dialogue generation through `DialogueService`
- character `L2` reasoning through `CharacterAgentL2Service`
- character `L3` planning through `CharacterAgentL3Service`
- Siming candidate generation through `AuthorityEventBus -> SimingRuntime.tick()`
- readiness, live-proof, closure-ledger, and documentation alignment

It does not cover:

- real TTS
- VLA real-provider completion
- non-runtime multimodal production rollout
- a generalized multi-vendor orchestration redesign
- broad character-runtime work unrelated to provider closure
- production model-quality or narrative-quality claims

## Source Of Truth

Use these sources in order for this closure:

1. this spec
2. `docs/superpowers/specs/2026-06-25-siming-backend-chain-proof-design.md`
3. `docs/superpowers/specs/2026-06-19-deepseek-character-model-gateway-design.md`
4. `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
5. `docs/superpowers/specs/2026-06-15-siming-phase1-llm-authority-bus-runtime-design.md`
6. `docs/superpowers/plans/2026-06-25-siming-backend-chain-proof-implementation-plan.md`
7. `docs/superpowers/plans/2026-06-19-deepseek-character-model-gateway-implementation-plan.md`
8. `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`
9. `docs/superpowers/plans/2026-06-15-siming-phase1-llm-authority-bus-runtime-implementation-plan.md`
10. `docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-03-current-project-model-provider-readiness-implementation-plan.md`

The world-character-Siming-authority mainline remains the repository-level
architecture source. This closure cannot create a second model entry point,
private authority bus, direct world mutation path, or remote low-level control
path.

## Carry-Forward Matrix

| Historical requirement | Current state | Closure ownership |
| --- | --- | --- |
| Character gateway/router/provider/validator boundary | landed and unit-tested | preserve; regression-test |
| DeepSeek chat-completions request/response translation | landed | preserve; exercise in live proof |
| Character local and hybrid fallback | landed | preserve; explicitly exclude from live success |
| Character provider-correlated config precedence | open; current defaults can cross provider identity | implementation plan configuration task |
| Character dialogue real-provider proof | open | character live-proof dialogue scenario |
| Character L2 real-provider proof | partially observed, no durable proof | character live-proof L2 scenario |
| Character L3 real-provider contract | open; required goal frame can fail | strict L3 contract task and live scenario |
| Broad non-provider character L1/L3/L4/actor work | retained by broad runtime plans | outside this closure |
| Siming provider inside `SimingRuntime.tick()` | landed and unit-tested | preserve; boundary-test |
| Siming policy/feasibility/producer/AuthorityEventBus chain | landed | preserve; app-wiring live proof |
| Siming deterministic component proof | landed | preserve |
| Siming real-settings DeepSeek proof | open; verifier drift synthesizes settings | repair verifier before timeout work |
| Provider readiness ledger | landed | keep separate from live evidence |
| Full regression and secret checks from older plans | still required | final verification gate |

No historical unchecked box is silently declared complete by this matrix.
Anything marked outside this closure remains owned by its existing broad plan.

## Character Live-Proof Contract

Add one explicit-only character provider proof that writes a redacted JSON and
Markdown report under `.harness/verification/`.

The proof must run three independent scenarios in one process initialized from
the actual target configuration:

### Dialogue Scenario

- construct the normal `DialogueService` with the real `CharacterModelGateway`
- require `DIALOGUE_MODE=online`
- require no `CHARACTER_MODEL_ROUTE_OVERRIDE`
- issue a dialogue request with a non-secret fixture context
- prove a real provider request was attempted
- require non-empty `content` and an allowed non-empty `tone`
- require provider/model/route evidence and `fallback_used=false`

### L2 Scenario

- invoke the actual `CharacterAgentL2Service` entry point
- use a schema-valid private snapshot and perceived-event fixture
- prove the request went through `CharacterModelGateway` and the real transport
- require validator success, non-empty interpretation fields, finite bounded
  `salience_score`, allowed risk/ambiguity/opportunity values, and
  `fallback_mode is None`
- require the returned model to be consumed as a `CharacterInterpretation`

### L3 Scenario

- invoke the actual `CharacterAgentL3Service` entry point with a validated L2
  interpretation fixture or the successful live L2 result
- prove the request went through the gateway and real transport
- require non-empty candidate and recommended intent lists
- require selected intent membership, non-empty rationale, and non-empty
  `active_goal_frame.primary_goal`
- require local viability/triple-filter consumption to succeed
- require `planning_status=model` and no fallback

The proof must fail, not skip, when configuration, credentials, transport,
schema, validator, or downstream-consumer checks fail. It must not print keys,
full prompts, full responses, or private character context.

## Siming Live-Proof Contract

The repaired proof must validate the real loaded configuration before it resets
runtime state. Missing or inconsistent configuration fails at
`credential_check`.

The required chain is:

```text
real app settings
-> app.main.reset_runtime_state()
-> app.main.authority_event_bus.publish(proof_event)
-> SimingEventConsumer
-> SimingRuntime.tick()
-> configured DeepSeek provider
-> policy and feasibility
-> SimingEventProducer
-> AuthorityEventBus
-> audit and read model
```

Success requires:

- an explicit candidate with `source="llm"`
- provider output validation without semantic field synthesis
- accepted policy and feasibility results
- a concrete downstream `siming.*` dispatch event
- audit and read-model evidence with the proof correlation id
- a redacted report entry named `app_wiring_live_deepseek_chain`

HTTP 200, component fake-provider success, timeout fallback, or a runtime rebuilt
from verifier-created settings is not success.

## Readiness And Closure Evidence

Readiness remains a configuration and boundary ledger. Its overall pass may
legitimately include disabled, blocked, or configured-unverified rows, so it is
never used alone as closure evidence.

Add a separate LLM closure report that consumes, rather than rewrites:

- the model-provider readiness report
- the character live-proof report
- the Siming backend-chain report
- full regression and boundary verification results

The closure report passes only when all four live scenarios pass and the
readiness rows identify the same configured provider/model family. It must not
promote a readiness row to `real_provider_verified` unless the readiness system
is explicitly changed to consume durable real-call evidence.

## Required Human Inputs

Before live execution, the operator must provide values outside tracked files:

### Character

- `CHARACTER_MODEL_PROVIDER_KIND=deepseek`
- `CHARACTER_MODEL_API_KEY`
- `CHARACTER_MODEL_ENDPOINT`
- `CHARACTER_MODEL_MODEL`
- `CHARACTER_MODEL_TIMEOUT_SECONDS`
- `DIALOGUE_MODE=online`
- confirmation that `CHARACTER_MODEL_ROUTE_OVERRIDE` is unset

### Siming Legacy Global Route

- `SIMING_LLM_MODE=http`
- `SIMING_LLM_PROVIDER_ORDER=deepseek_chat`
- `SIMING_LLM_API_KEY`
- `SIMING_LLM_ENDPOINT`
- `SIMING_LLM_MODEL`
- `SIMING_LLM_TIMEOUT_SECONDS`

### Siming Route Mode

If route mode is selected instead, the operator must provide one complete
`SIMING_LLM_ROUTES_JSON` entry and must not also configure a competing legacy
global provider order for the proof. The entry requires:

- `route_id`
- `provider=deepseek_chat`
- `endpoint`
- `model`
- `api_key`
- `timeout_seconds`
- `enabled=true`

The operator must also confirm network access, account/model availability,
acceptable paid-call use, and the maximum acceptable live-proof timeout.

## Architecture Constraints

- `CharacterModelGateway` remains the only character business-facing model
  entry point.
- `CharacterStructuredOutputValidator` remains inside the gateway and validates
  before output reaches L2/L3 consumers.
- Character model output cannot write world truth, ESM authority, physical
  success, body truth, or low-level direct-control commands.
- `SimingRuntime.tick()` remains the only layer allowed to call Siming providers.
- Only `SimingEventProducer` may publish accepted Siming authority events.
- `AuthorityEventBus` remains the cross-system runtime channel.
- Readiness and live proof remain separate evidence classes.
- Secrets remain outside tracked docs, tests, reports, logs, and commits.

## Definition Of Done

This spec is fully executed only when:

1. the character configuration precedence table is implemented and tested
2. character dialogue live proof passes through normal service and gateway wiring
3. character L2 live proof passes through gateway, validator, and typed consumer
4. character L3 live proof passes strict semantic validation and local viability
5. Siming live DeepSeek proof passes using unmodified loaded app settings
6. all four live entries exist in durable redacted evidence
7. the closure aggregator passes without treating readiness as live proof
8. local/stub/hybrid behavior and authority boundaries remain green
9. full backend tests and the full non-live harness pass
10. tracked-file secret scanning passes
11. historical plans and documentation point to this closure without changing
    the status of unrelated broad-runtime work

Any missing credential, timeout, fallback, invalid output, policy rejection,
feasibility rejection, or missing downstream evidence leaves the relevant live
scenario open.
