# TTS Voice Profile Adapter Presentation Boundary Closure Implementation Plan

- Date: `2026-08-03`
- Status: `repository-owned implementation and credential-free static boundary complete; final bindings, operator approval, and live proof remain external gates`
- Corresponding specs:
  - `docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-design.md`
  - `docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-design.md`
- Prior plan: `docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-implementation-plan.md`
- Scope: close only the remaining presentation boundary: provider/model/catalog capability declaration, operator-approved final bindings, guarded per-actor live synthesis, real-payload Godot consumption proof, redacted evidence, and fail-closed rollback behavior.
- Not covered: reimplementing the existing profile resolver, XLSX importer/ranking, source-manifest/enrollment primitives, TTS transport, dialogue generation, sentence queueing, token/audio streaming, lip sync, cognition- or Siming-derived expression, voice-cloning platform work, or a second voice-binding/provider-adapter contract.

## Execution Checkpoint (2026-08-04)

The fresh `tts-voice-profile-adapter` report is green. It proves the
credential-free profile/capability, catalog import, enrollment, fallback,
legacy-mode, and tracked-evidence-safety boundaries; its declared scope
explicitly excludes live synthesis, human audition, production-binding approval,
and Godot playback. The report is
`.harness/verification/tts-voice-profile-adapter-report.json`.

This does not close the presentation boundary. Before a guarded live run,
operators must still provide final `char_a`, `char_b`, and `char_c`
provider/model/catalog/binding selections, non-secret approval references,
rights/revocation state where applicable, live-call authorization/credentials,
and one allowed shared evidence run ID. The historical provider/Godot evidence
is retained as baseline only and cannot be relabelled as final-binding proof.
No code or static harness run may fabricate those inputs or bypass
`--allow-live-call`.

## 1. Current Baseline

### Implemented

- `backend/app/services/tts_voice_profiles.py` already defines and loads `tts_voice_catalog.v1`, `tts_voice_bindings.v1`, and `tts_voice_profile.v1`; it accepts only `approved` bindings and rejects unknown voices, provider/model mismatch, catalog-revision mismatch, and required-language mismatch.
- `backend/app/services/tts_voice_catalog_importer.py` already performs standard-library XLSX normalization and deterministic, presentation-only advisory ranking. It cannot approve or write a runtime binding.
- `backend/app/services/tts_service.py` already gives an approved profile precedence over `TTS_VOICE_MAP_JSON`, validates PCM mono WAV output, returns a bounded `tts_audio.v1` attachment, and falls back to the existing stub on provider or profile failure.
- `backend/app/services/tts_voice_enrollment.py` already has `character_voice_source_asset.v1`, a `secure_asset://`-only source manifest, rights/consent/revocation checks, controlled URL issuance, candidate-only enrollment records, and the DashScope Qwen-Audio enrollment adapter. No public enrollment endpoint exists.
- `presentation_instruction` is disabled by default and already requires the feature flag, catalog allowlist, and adapter declaration. Both current production adapters declare it unsupported, which causes pre-request fallback rather than silent omission.

### Focused Verification Already Present

- The latest `tts-voice-profile-adapter` report is dated `2026-08-03` and passes. Its log records `19 passed` for `backend/tests/test_tts_voice_profiles.py` and `backend/tests/test_tts_voice_enrollment.py`.
- The current focused tests prove candidate/approval rejection before a provider call, provider/model and language rejection, legacy-map preservation, instruction gating, catalog import/ranking, source-asset authorization, and candidate-only enrollment.

### Existing Real Provider And Godot Evidence

- `.harness/verification/tts-provider-live-report.json` records a `2026-07-31` DashScope `qwen-audio-3.0-tts-flash` ready 24 kHz mono WAV clip for `char_a`, voice ID `longanhuan_v3.6`.
- `.harness/verification/tts-godot-live-playback-report.json` and its log record a real DashScope dialogue payload reaching `SpatialVoiceController`, becoming an `AudioStreamWAV`, and starting playback without clip rejection or stub fallback.
- These reports prove the pre-existing provider/presentation path only. They do not identify an approved final `tts_voice_profile.v1` catalog snapshot, do not prove `char_b` or `char_c`, and must not be represented as closure evidence for final actor bindings.

### Operator Decisions Still Required

- Select one final provider voice ID for each actor, including an explicit presentation-only voice-gender choice for `char_b` and `char_c`; this choice must not change a dossier or character truth.
- Confirm the selected provider mode, model, and exact catalog revision; approve each binding after an operator listening review.
- For an enrolled/cloned voice, confirm source-asset rights/consent remains authorised and is not revoked. For system/basic provider voices, record that no source asset is used rather than fabricating one.

### Fresh Evidence Still Missing

- The active adapters now declare `TTSProviderCapabilities` and the resolver
  requires provider/model/catalog-contract compatibility, the configured
  catalog revision pin, mono PCM WAV output, and an operator approval reference
  before a profile binding can reach synthesis. The guarded provider and Godot
  verifiers also require an opaque shared evidence run ID and report only
  safe binding metadata. This repository-owned capability surface is complete.
- No redacted evidence bundle ties an operator approval reference, the final
  binding identity, and one guarded live call for every final actor.
- No Godot proof has been re-run against each final approved binding under the
  same allowed evidence run ID.

### Explicitly Deferred Long-Term Capabilities

- Sentence/pause queueing, token-level provider audio streaming, jitter buffering, lip sync, subtitles synchronized from audio, cancellation/retry queue semantics, and dynamic emotional voice generation.
- Generated or runtime-derived expressive instructions, automatic cloning from arbitrary material, and a general voice-cloning product surface.
- Provider catalog discovery over the public network at runtime. Catalog import remains an operator-controlled authored asset step.

### Formal-Document Versus Code/Evidence Reconciliation

The prior 2026-07-31 plan correctly leaves the provider-catalog capability surface and final approvals open. The current code has progressed beyond its earlier unchecked items for catalog import, binding validation, enrollment, and focused tests. Conversely, the historical live provider/Godot reports predate the final approvals and use `longanhuan_v3.6`, whereas the repository example catalog/binding is a candidate-only Flash basic-voice example. This plan treats code plus the latest reports as the baseline and requires new final-binding evidence; it does not infer that the example asset or historical voice is approved production truth.

## 2. Preconditions And Human Inputs

Before any guarded live call, the implementation owner must obtain and record outside secrets-bearing source control:

1. The final voice ID for `char_a`, `char_b`, and `char_c`, with their selected provider, model, and exact catalog revision.
2. An operator approval reference for each binding. It must identify the review/audition record and approver role, not a secret or raw preview URL.
3. The current source-asset rights/consent/revocation state for any cloned/enrolled voice. A system/basic catalog voice must be explicitly marked as not using an enrollment source asset.
4. Approval to invoke the real provider, including quota, timeout, cost ceiling, and network policy. The run must stop on a limit breach rather than retrying unboundedly.
5. One opaque, allowed evidence run ID shared by the live provider and Godot playback commands. It may be a release/change ID but must not contain a credential, provider temporary URL, or raw dialogue/audio.
6. Local/deployment-only `TTS_PROVIDER_API_KEY` availability through the existing ignored `.env.tts`, environment, or secret store. Neither the plan, asset, report, nor Git-tracked configuration may contain the key.

## 3. Phased Implementation

### Phase 1: Complete The Provider/Model/Catalog Capability Surface

**Goal**: make the existing adapter boundary explicitly declare which selected provider/model/catalog contract it can consume, so a profile binding cannot reach HTTP merely because separate strings happen to agree.

**File scope**: `backend/app/services/tts_service.py`, `backend/app/services/tts_voice_profiles.py`, `backend/app/config.py`, `backend/tests/test_tts_service.py`, `backend/tests/test_tts_voice_profiles.py`, `backend/tests/test_config_runtime_modes.py`, `.env.example`, and the existing `assets/tts/*.example.json` documentation/examples when their non-secret schema needs a new field.

**Tests to write first**:

1. A profile-enabled request with an adapter/provider capability mismatch, unsupported configured model, unsupported catalog contract, or catalog revision outside the adapter's explicit policy returns the normal stub fallback and leaves the fake provider call list empty.
2. A matching approved binding reaches a capable fake provider exactly once.
3. `presentation_instruction` remains rejected before the request for DashScope and generic OpenAI-compatible adapters, even if the catalog allowlists it and its feature flag is enabled.
4. Profile-disabled mode still resolves `TTS_VOICE_MAP_JSON` and never reads profile assets or applies catalog capability checks; `TTS_MODE=stub` remains unchanged.

**Implementation**:

1. Extend the existing `TTSProvider` contract in `tts_service.py` with one immutable, presentation-only capability declaration. It belongs to the existing adapter boundary, not a second adapter or binding contract.
2. The declaration must name the adapter/provider, selected model compatibility, accepted catalog contract/revision policy, complete-WAV output constraints already required by `tts_audio.v1`, and `presentation_instruction` support. It must contain no provider URL, key, raw response, or dynamic dialogue state.
3. Have `TTSVoiceProfileResolver` validate the loaded catalog and approved binding against that declaration before `synthesize()` makes a network request. Preserve the current catalog/binding/config comparisons; the descriptor adds a single audited cross-check rather than replacing them.
4. Give `DashScopeHttpTTSProvider` and `OpenAICompatibleTTSProvider` explicit fail-closed declarations. A model or catalog source that has not been declared compatible must require a deliberate adapter update and tests; it must not inherit another provider/model's voice IDs.
5. Add only non-secret configuration required to name the expected catalog capability/revision, if code review confirms configuration must anchor it rather than the catalog asset itself. Keep `TTS_PROVIDER_API_KEY` secret-only and leave legacy mapping semantics unchanged.
6. Keep catalog ingestion offline/controlled. This phase must not add a provider catalog HTTP fetch, a public catalog endpoint, or runtime mutation of catalog/binding files.

**Success standard**: focused tests prove every incompatible provider/model/catalog combination fails before the provider call, matching approved combinations pass, and legacy/stub behavior remains unchanged.

**Do not expand into**: a provider marketplace, live catalog browsing, generic capability negotiation, a second `TTSProvider`, or expressive/affect controls.

### Phase 2: Finalize Operator-Approved Voice Bindings

**Goal**: convert operator decisions into the existing, versioned presentation assets without making them character, cognition, or authority truth.

**File scope**: deployment-managed copies of the existing `assets/tts/voice_catalog.example.json` and `assets/tts/voice_bindings.example.json` shapes; `assets/tts/README.md`; optional existing `<actor_id>.yaml` source-manifest convention under `assets/characters/voice_sources/` only when enrollment is used; `.env.example` for non-secret path/flag documentation; `backend/tests/test_tts_voice_profiles.py` and `backend/tests/test_tts_voice_enrollment.py`.

**Tests to write first**:

1. A final asset with all three approved actor bindings, correct approver references, distinct actor IDs, exact catalog revision, and known voices resolves deterministically.
2. Candidate, retired, missing-approval-reference, duplicate actor, unknown voice, revision drift, and a revoked/unauthorised source asset each fail before provider request. The source-asset test applies only to the enrollment workflow; it must not require a source asset for a system/basic voice.
3. Changing a voice-gender presentation field cannot modify a character dossier, dialogue input/output, ESM payload, Siming payload, world truth, or character state.

**Implementation**:

1. Import a controlled provider catalog snapshot using the existing XLSX importer or validate the provider-issued non-secret JSON using the existing `tts_voice_catalog.v1` shape. Record provider, model, catalog revision, descriptive tags, and an opaque operator review reference only.
2. Use existing ranking only to create an audition shortlist. The operator listens to neutral, command, and sensitive lines, then supplies the final `voice_id` and approval reference. Ranking must not approve or rewrite a binding.
3. Record exactly one `tts_voice_profile.v1` binding per actor in the existing bindings asset. Set `selection_status: approved`, nonblank `approved_by`, exact provider/model/voice/catalog revision, and authored presentation traits. Keep `presentation_instruction` absent unless separately approved, catalog-allowlisted, feature-flagged, and capability-supported; current production adapters mean it remains absent/disabled.
4. For cloned/enrolled voices, load the existing secure source manifest through the controlled service, reject `pending`/`revoked` rights or absent consent, then carry only the candidate voice ID into the normal catalog-and-approval workflow. Do not expose an enrollment HTTP route.
5. For activation, set the existing non-secret paths and feature flag in ignored `.env.tts` or deployment configuration. Keep `.env.example` to names, blank values, and comments only. Retain `TTS_VOICE_MAP_JSON` as the rollback/legacy route.

**Success standard**: an asset review and focused tests prove each active actor has one approved, catalog-provenanced binding; no unapproved or revoked input reaches provider synthesis.

**Do not expand into**: identity/dossier editing, dynamic voice selection, raw voice-source storage, public enrollment, or approval automation.

### Phase 3: Guarded, Actor-Isolated Live Synthesis

**Goal**: prove that every final actor binding independently yields the existing complete `tts_audio.v1` clip under a bounded, explicitly authorised real-provider call.

**File scope**: `scripts/verification/verify_tts_provider_live.py`, its tests if present or new focused tests in existing TTS test modules, `backend/app/services/tts_service.py` only if the verifier exposes a real validation gap, `.harness/verification/` generated artifacts, and `docs/harness.md` if evidence semantics change.

**Tests to write first**:

1. The verifier refuses a missing/invalid allowed evidence run ID, incomplete provider configuration, profile disabled when a final-binding proof is requested, missing actor binding, unapproved binding, capability mismatch, or fallback result; it makes no live call in each preflight failure.
2. The verifier can run the existing `--actor-id` path independently for each actor and emits an aggregate/per-actor redacted result without audio payload, signed URL, API key, authorization header, or raw provider response.
3. A provider failure produces a fallback result while the text in the corresponding `DialogueResponse` is byte-for-byte unchanged and no cognition/ESM/Siming/world authority method is invoked.

**Implementation**:

1. Preserve `--allow-live-call` as the hard network opt-in. Add only backward-compatible arguments needed to bind the proof to the allowed opaque run ID and final actor set; the no-argument and existing single-actor behavior must remain understandable.
2. Preflight the approved binding and capability descriptor before synthesis. Enforce one bounded request per actor, the configured timeout, and an operator-defined quota/cost ceiling; do not silently retry or substitute another voice.
3. For every actor, assert `mode=clip`, `status=ready`, `content_type=audio/wav`, `encoding=base64`, PCM mono metadata at the configured sample rate, positive duration, payload budget compliance, and the expected final binding voice ID.
4. Report only the run ID, actor ID, provider/model/catalog revision, binding identity or non-reversible digest, voice ID where policy permits, output metadata, byte length/digest, success/fallback reason, and timestamps. Never write the payload, dialogue text, request/response body, signed URL, or secret.
5. A failure is evidence of failed closure, not an opportunity to mutate the binding automatically. Leave the approved previous binding intact and return the normal stub fallback for runtime service.

**Success standard**: one explicit live proof succeeds for every approved actor under the same allowed evidence run ID, and each result is independently attributable to the exact active binding.

**Do not expand into**: real-time streaming, batch generation, synthesis caching/persistence, voice audition UI, or provider retry orchestration.

### Phase 4: Reuse Godot To Prove Real Payload Consumption

**Goal**: prove the real provider result is consumed by the existing WebSocket/Godot presentation path, not merely accepted by the backend.

**File scope**: `scripts/verification/verify_tts_godot_playback.py`, `scripts/verification/TTSGodotLivePlaybackProbe.gd`, existing `scripts/audio/SpatialVoiceController.gd`, relevant focused tests in `backend/tests/test_tts_service.py`, and generated `.harness/verification/` reports/logs.

**Tests to write first**:

1. The Python verifier/Godot probe accepts a selected actor or configured actor list and refuses to claim success unless the dialogue response has `mode=clip`, the expected provider and final voice binding, no `voice_clip_rejected` marker, no `voice_stub_played` marker, and a real `AudioStreamWAV`.
2. A stub, invalid binding, capability mismatch, or provider fallback causes a non-success report and must not be relabelled as Godot playback proof.
3. Existing static controller checks continue to prove base64 decoding, WAV validation, bounded WebSocket buffer assumptions, `AudioStreamWAV.new()`, and the legacy stub log path.

**Implementation**:

1. Parameterize the existing live probe rather than creating a second playback path. It must submit the existing structured dialogue input, select the intended response actor, and record the expected non-secret binding identity.
2. Run the existing live backend setup and `SpatialVoiceController.play_voice(payload)` path. The proof marker must include only provider, actor, voice/binding-safe identifier, sample rate, channel count, and whether `AudioStreamWAV` was created/started.
3. Execute the probe once for every changed/final actor binding under the same evidence run ID as Phase 3. The old `char_a` proof remains historical baseline evidence only.
4. Keep audio as a completed dialogue attachment. Do not convert playback into a world event, ESM command, character-state write, or Siming input/output.

**Success standard**: Godot receives the live response, creates `AudioStreamWAV` from the actual base64 WAV, begins the spatial player, and records no clip rejection or stub playback for each final binding.

**Do not expand into**: human loudspeaker/audition certification, lip sync, clip queues, `AudioStreamGenerator`, or gameplay effects from audio playback.

### Phase 5: Generate Redacted, Auditable Evidence

**Goal**: make closure claims reproducible without committing or reporting sensitive audio/provider material.

**File scope**: `scripts/verification/verify_tts_voice_profile_adapter.py`, `verify_tts_provider_live.py`, `verify_tts_godot_playback.py`, `.harness/profiles/tts-voice-profile-adapter.json`, `.harness/verification/` generated reports, `docs/harness.md`, and `.gitignore` only if the existing ignore rules do not already cover a new generated artifact path.

**Tests to write first**:

1. Report serialization excludes values matching configured secrets, `Authorization` headers, `secure_asset://` source paths, HTTPS signed/query URLs, base64 audio fields, raw response fields, and raw dialogue text.
2. A tracked-file scan fails when a TTS evidence artifact or source asset contains a private key marker, signed URL, raw audio extension, or audio payload; it permits the existing versioned example JSON/YAML and metadata-only reports.
3. The static adapter profile remains explicitly `backend-only` and cannot return a real-provider/Godot-complete state merely because its focused pytest suite passes.

**Implementation**:

1. Use standard-library redaction and SHA-256 metadata only; do not add a package for reporting or XLSX handling.
2. Emit a small evidence manifest with the opaque run ID, source report paths, per-actor outcome, binding/catalog identity, approval-reference presence boolean or approved reference policy, WAV metadata, Git revision, and verifier version. It must state its proof class: static, focused backend, provider live, Godot playback, or human approval.
3. Keep generated outputs below `.harness/verification/`, which is already ignored. Do not add raw provider payloads to reports/logs, and do not copy them into docs.
4. Make the static harness report say exactly what it proves and link, by safe artifact name only, to separate live/Godot evidence when available. `harness.py --profile all` must remain a static/contract aggregate, not a credentialed live-call mechanism.

**Success standard**: evidence is attributable, redaction tests and tracked-file checks pass, and each report distinguishes its proof level without secrets or raw audio.

**Do not expand into**: a secret manager, centralized audit database, raw audio retention, or an external reporting service.

### Phase 6: Exercise Rejection, Revocation, And Rollback

**Goal**: prove the runtime fails closed for drift or invalid rights and can return to a known safe presentation path without silently using an incorrect voice.

**File scope**: `backend/app/services/tts_voice_profiles.py`, `backend/app/services/tts_voice_enrollment.py`, `backend/app/services/tts_service.py`, the three existing TTS test modules, verification scripts, example assets/readmes where rollback rules need documentation, and generated evidence only.

**Tests to write first**:

1. Provider/model/catalog-revision mismatch, catalog removal, unsupported capability, revoked/expired source asset, retired/unapproved binding, and invalid instruction each block before network synthesis.
2. An invalid profile binding falls back to the existing stub response and preserves dialogue text; it neither mutates the legacy map nor substitutes a catalog neighbor.
3. With profiles disabled, the same legacy `TTS_VOICE_MAP_JSON`/default voice behavior remains valid. With a deliberate rollback to a previous approved binding and matching catalog, the exact prior voice resolves deterministically.
4. Provider timeout, quota failure, and malformed WAV produce the normal stub fallback without any CharacterModelGateway, L2/L3 cognition, Siming, ESM, or world-truth call or state change.

**Implementation**:

1. Treat a catalog revision as immutable. A provider/model/catalog change requires a new imported catalog, a newly reviewed approved binding, focused tests, and fresh live/Godot proof; it cannot reuse a stale voice ID by implicit compatibility.
2. Define the operator rollback as one atomic configuration/asset deployment: restore the last reviewed catalog and binding pair with the same revision, or disable profiles and deliberately use the existing legacy map/stub. Never patch only one half of the pair.
3. On rights/consent revocation, mark the source enrollment/binding retired in the controlled asset workflow, remove it from the active approved set, request provider deletion where supported, and activate only a separately approved replacement or stub fallback.
4. Ensure fallback observability remains presentation-only (`tts_audio.v1` status/reason and Godot stub marker), with no write to ESM, gameplay authority, world truth, or character state.

**Success standard**: all drift/revocation/failure cases fail before provider use or return a bounded stub, every rollback is deliberate and traceable, and no test observes silent cross-voice substitution.

**Do not expand into**: automatic migration of provider voices, automatic re-enrollment, authority recovery, or runtime mutation of actor profiles.

### Phase 7: Align Documentation, Harness, And Closure Status

**Goal**: make the spec/plan/harness truth accurately separate code completion, human approval, and live runtime evidence.

**File scope**: this closure plan; `2026-07-31-tts-voice-profile-adapter-implementation-plan.md`; the corresponding adapter design only if capability fields alter its contract; `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`; `docs/INDEX.md`; `docs/harness.md`; `.harness/profiles/tts-voice-profile-adapter.json`; and generated evidence reports.

**Tests to write first**:

1. Documentation/profile checks assert the profile description says it does not call a real provider and does not approve production voices.
2. Verification-script tests ensure a live/Godot failure is reported as failed or blocked, never as static profile success.

**Implementation**:

1. Add this plan to the active mainline plan index and link it from the TTS entry in `docs/INDEX.md` if the documentation conventions require both.
2. Update the prior plan checklist/status only after each closure item has corresponding evidence. Update the spec status only after implementation, approval, provider proof, and Godot proof are all complete; do not turn a historical report into a current claim.
3. Keep the profile focused and credential-free. It should run binding/capability/enrollment/fallback tests and produce redacted static evidence; live scripts remain explicit opt-in operations.
4. Store only generated redacted reports/logs in `.harness/verification/` and retain their run IDs according to existing harness retention rules.

**Success standard**: repository entry docs, active plan status, profile description, and evidence reports use the same precise proof vocabulary.

**Do not expand into**: unrelated TTS streaming plans, current-project intelligence routing, dialogue protocol changes, or a mainline architecture rewrite.

## 4. File-Level Impact Surface

| Area | Expected change | Notes |
| --- | --- | --- |
| `backend/app/config.py` | Modify only if a non-secret expected catalog capability/revision setting is needed. | API keys remain `repr=False`, excluded, and local/deployment-only. |
| `backend/app/services/tts_service.py` | Extend the existing `TTSProvider` with its capability declaration and pre-request fail-closed check. | Do not add a second adapter contract. |
| `backend/app/services/tts_voice_profiles.py` | Reuse existing catalog/binding validation and add capability cross-check/approval completeness validation. | The existing contracts remain authoritative. |
| `backend/app/services/tts_voice_catalog_importer.py` | Modify only if the existing catalog schema needs non-secret capability provenance fields. | Retain first-sheet XLSX import and advisory-only ranking. |
| `backend/app/services/tts_voice_enrollment.py` | Narrow changes only for revocation handoff/evidence validation, if tests expose a gap. | No HTTP route or source-byte persistence. |
| `backend/tests/test_tts_service.py` | Add adapter-capability, failure isolation, and Godot-probe static regression tests. | Reuse current fake providers/WAV fixtures. |
| `backend/tests/test_tts_voice_profiles.py` | Add revision/capability/final-approval/legacy rollback cases. | Must assert zero provider calls on rejection. |
| `backend/tests/test_tts_voice_enrollment.py` | Add active source rights/revocation-to-binding boundary cases where applicable. | Do not force enrollment for provider system/basic voices. |
| `backend/tests/test_config_runtime_modes.py` | Add any new non-secret configuration parsing coverage. | Preserve `.env.tts` precedence behavior. |
| `scripts/verification/verify_tts_voice_profile_adapter.py` | Expand focused static/redaction checks and proof classification. | It must not call a provider. |
| `scripts/verification/verify_tts_provider_live.py` | Add run-ID/final-binding preflight and per-actor redacted live proof. | Keep `--allow-live-call` required. |
| `scripts/verification/verify_tts_godot_playback.py` and `TTSGodotLivePlaybackProbe.gd` | Parameterize the existing proof per final actor and emit safe consumption markers. | Reuse `SpatialVoiceController`; do not create another playback path. |
| `scripts/audio/SpatialVoiceController.gd` | No planned functional change unless a failing proof exposes a contract mismatch. | Existing complete-WAV decoder and stub fallback remain the consumer. |
| `.harness/profiles/tts-voice-profile-adapter.json` | Clarify/update focused profile inputs and result scope. | No credentials or live calls in harness profile. |
| `.harness/verification/tts-*.json`, `.md`, `.log` | Generated, redacted evidence only. | Already ignored by `.gitignore`; never track raw audio. |
| `assets/tts/README.md`, `voice_catalog.example.json`, `voice_bindings.example.json` | Update documentation/examples for any approved non-secret capability fields. | Production catalog/binding copies follow existing documented names/shapes and are deployment-managed. |
| `assets/characters/voice_sources/README.md` and existing `<actor_id>.yaml` loader convention | Optional manifest updates only for selected enrollment sources. | Raw recordings and signed URLs remain outside Git. |
| `.env.example` and ignored `.env.tts` | Document/use only non-secret flags, paths, provider/model/revision identifiers, legacy map, and opaque evidence run ID if implemented. | Never put `TTS_PROVIDER_API_KEY` value in an example/report. |
| `docs/harness.md`, `docs/INDEX.md`, plan/spec README and TTS plan/spec files | Update proof vocabulary, active-plan links, and final status when evidence exists. | Do not edit unrelated cognition/Siming/authority documentation. |

## 5. Verification Matrix

| Proof class | Command or review | What it proves | What it cannot prove |
| --- | --- | --- | --- |
| Static verification | `python scripts/verification/verify_tts_voice_profile_adapter.py` | Asset schema, controlled importer, capability/binding rejection, enrollment boundary, fallback/redaction checks. | Real provider synthesis, human approval, or Godot runtime consumption. |
| Focused backend | `python -m pytest -v backend/tests/test_tts_service.py backend/tests/test_tts_voice_profiles.py backend/tests/test_tts_voice_enrollment.py backend/tests/test_config_runtime_modes.py` | Exact pre-request fail-closed and legacy/stub behavior. | Credentials, actual provider catalog availability, or speaker playback. |
| Full backend regression | `python -m pytest -v` | No backend regression, including dialogue/audio contract consumers. | Live provider/Godot proof. |
| Existing adapter profile | `python scripts/verification/harness.py --profile tts-voice-profile-adapter` | Credential-free, focused adapter evidence. | Must remain explicitly non-live. |
| Backend contract aggregate | `python scripts/verification/harness.py --profile backend-contract` | Cross-boundary protocol shape remains valid. | Final voice approval or live audio. |
| Provider live proof | `python scripts/verification/verify_tts_provider_live.py --allow-live-call` plus the approved run-ID/actor arguments | Each approved actor produces a non-empty, budget-valid ready WAV clip with matching binding metadata. | Godot consumption or human hearing/audition. |
| Godot runtime playback | `python scripts/verification/verify_tts_godot_playback.py --allow-live-call` plus the same approved run-ID/actor arguments | The real dialogue audio payload is consumed through `SpatialVoiceController` as `AudioStreamWAV` without stub/rejection. | Human listening quality or authority correctness. |
| Full harness regression | `python scripts/verification/harness.py --profile all` | Registered non-credentialed repository profile aggregate remains green. | It does not upgrade static profile success to real-provider completion. |
| Secret/tracked-file check | Repository scan using standard-library verifier support plus `git ls-files`/`git diff --check` on TTS assets, docs, and generated paths. | No API key, signed URL, raw provider response, or raw audio is tracked/reported. | Secret-store correctness outside the repository. |
| Human voice approval | Operator audit against final catalog and audition scripts, recorded as a non-secret approval reference. | The selected voice is approved for presentation use. | Provider/Godot runtime behavior without the explicit live proofs. |

Run focused/static checks before operator calls. Run each live proof only after the Phase 2 asset is deployed and against the same allowed evidence run ID. Run the full backend and harness regressions after the final implementation/documentation change. A static profile pass must never be reported as provider or Godot completion.

## 6. Acceptance Criteria

1. Every active approved binding has an exact provider, model, voice ID, and catalog revision that matches the active catalog, configuration, and adapter capability declaration.
2. Candidate, retired, unknown, provider/model/revision-incompatible, capability-incompatible, or missing-approval bindings are rejected before the provider request; the only allowed runtime result is the existing fallback/stub presentation attachment.
3. A revoked, expired, unauthorised, or missing-consent voice source cannot enter enrollment or become an active runtime binding. A system/basic provider voice does not pretend to have a source asset.
4. Each final actor has one guarded live synthesis result with non-empty, format-valid, budget-valid mono PCM WAV metadata and the expected final binding identity.
5. Each final actor has a Godot runtime proof showing the actual provider payload is consumed, `AudioStreamWAV` is created, playback begins, and neither `voice_clip_rejected` nor `voice_stub_played` occurs.
6. Provider/configuration/WAV failures preserve the already-generated dialogue text and return a presentation fallback without calling or mutating `CharacterModelGateway`, L2/L3 cognition, Siming, ESM, world truth, gameplay authority, or character state.
7. `presentation_instruction` is still feature-flagged, catalog-allowlisted, authored-only, and adapter-capability-gated. For current DashScope/OpenAI-compatible adapters it fails closed before network synthesis.
8. `TTS_VOICE_MAP_JSON`, `TTS_DEFAULT_VOICE`, profile-disabled mode, and `TTS_MODE=stub` retain current behavior and tests.
9. Reports, logs, assets, docs, and tracked files contain no API key, authorization header, signed preview/download URL, raw provider request/response, raw dialogue content, or raw audio/base64 payload.
10. Documentation identifies the result as presentation-only and does not route TTS data into cognition, dialogue generation, Siming, ESM, world truth, or authority paths.

## 7. Risks And Rollback

| Risk | Fail-closed response | Rollback / recovery |
| --- | --- | --- |
| Provider/model/catalog revision changes | Reject the active profile before HTTP when any declared identity no longer agrees. | Deploy the prior reviewed catalog and binding pair together, or disable profiles and deliberately use the legacy map/stub. |
| Provider voice ID is withdrawn | Catalog validation removes/blocks it; no neighboring voice is selected. | Approve a replacement through the same catalog/audition/live-proof sequence, otherwise use stub. |
| Consent/rights become invalid | Enrollment rejects the source; active binding is retired/removed before use. | Request provider deletion where available, use a separately approved replacement or stub. |
| Timeout, quota, cost ceiling, or network failure | One bounded request returns normal fallback; no implicit retry loop. | Pause live proof, correct operator limits/configuration, retain current safe binding/stub path. |
| Provider live and Godot playback proof disagree | Mark closure failed; retain the two reports separately and investigate payload/decoder/configuration mismatch. | Do not approve deployment; restore prior known-good binding or stub after finding the boundary defect. |
| Binding asset deployment is partial or invalid | Resolver fails asset validation and synthesizes no provider clip. | Deploy the last catalog/binding pair atomically; never update only revision or binding half. |
| An incorrect voice might be silently adopted | Capability + catalog + binding + approval validation occurs before the request; fallback uses stub, not another profile voice. | Disable profiles or restore the reviewed pair; preserve legacy map only as an explicit operator rollback. |

## 8. Final Status Gate

At plan creation, the status is deliberately precise:

| Required state | Current status | Closure condition |
| --- | --- | --- |
| `implementation complete` | `complete for repository-owned scope` | Capability surface, tests, evidence redaction, fallback/revocation behavior, guarded live-verifier preflight, and documentation/harness alignment are implemented and pass. |
| `provider live proof complete` | `historical baseline only; not complete for final bindings` | Every approved final actor binding has a successful guarded provider report under the allowed run ID. |
| `Godot playback proof complete` | `historical baseline only; not complete for final bindings` | Every approved final actor binding has a matching real-payload `AudioStreamWAV` consumption report. |
| `operator approval pending` | `yes` | Final `char_a`/`char_b`/`char_c` voice IDs, B/C presentation choices, and approval references are recorded. |
| `deferred` | `yes` | Queueing, token/audio streaming, lip sync, and cognition/Siming-driven expressive control remain outside this plan. |
| `blocked` | `not globally blocked; human inputs gate live execution` | Mark `blocked` only if final approval, permitted provider access, quota/network authorization, or an allowed evidence run ID cannot be obtained after the implementation work is ready. |

The adapter presentation boundary may be marked closed only when all first three states are complete and operator approval is no longer pending. Until then, preserve the formal status `implementation-active`.
