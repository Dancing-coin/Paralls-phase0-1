# TTS Voice Profile Adapter Implementation Plan

Status: `implementation-active`

Date: `2026-07-31`

## Prerequisite Decisions

1. Confirm the presentation-gender choices for `char_b` and `char_c`; neither
   choice will edit the character dossier.
2. Audition and approve one Flash basic voice per actor from the candidate list
   in the companion design.
3. Confirm whether the first catalog source is the official Flash Excel export
   only, or also includes an authorised cloned/designed voice inventory.

## Implementation Steps

1. [x] Add strict Pydantic models for `tts_voice_profile.v1`, catalog entries, and
   binding validation under the TTS presentation boundary.
2. [x] Add versioned, non-secret template assets for an imported Flash catalog and
   approved actor bindings. Do not add API credentials, signed preview URLs, or
   raw provider audio to source control.
3. [x] Implement a controlled XLSX catalog importer/normalizer and a
   deterministic candidate-ranking helper. It accepts explicit provider/model/
   revision inputs, treats ranking as advisory, and cannot create or approve a
   runtime binding.
4. [x] Extend configuration so the profile-binding resolver takes precedence over
   `TTS_VOICE_MAP_JSON` when enabled. Retain the JSON map as the legacy fallback
   and retain `TTS_MODE=stub` unchanged.
5. [x] Validate provider, model, voice ID, catalog revision, and approval
   before calling `TTSProvider`. On validation failure use the existing stub
   fallback and expose only a non-sensitive presentation failure reason.
6. [x] Add the optional authored `presentation_instruction` transport behind a
   disabled-by-default feature flag, catalog allowlist, and provider capability
   declaration. It is not sourced from dialogue generation, affect, or Siming.
   Current production adapters declare this capability unsupported, so enabling
   a preset falls back before any provider request until an adapter is verified.
7. [x] Add a provider-catalog capability surface. The current DashScope adapter
   declares its supported Flash model, catalog contract, configuration-pinned
   catalog revision policy, complete WAV output, and instruction capability;
   the generic OpenAI-compatible adapter declares only its configured model.
   DashScope Plus, cloning/design, or a second provider require their own
   explicit capability declaration and tests before an approved binding can use
   them.
8. [x] Add focused tests for catalogue parsing, model mismatch rejection, profile
   isolation from dossiers, legacy map fallback, approved binding resolution,
   and no-regression `tts_audio.v1` clips.
9. After operators approve final voices, update the local `.env.tts` mapping or
   approved binding asset, run one guarded live synthesis per actor, then run
   the existing Godot playback probe.
10. [x] Add strict `character_voice_source_asset.v1` manifest models and a YAML
    loader. The manifest may reference only `secure_asset://` source material;
    it carries source-audio refs, content hashes, rights/consent references,
    retention/revocation state, and no raw audio bytes.
11. [x] Add a controlled enrollment service whose caller supplies an authorised
    short-lived HTTPS source URL through a storage-owned issuer interface. The
    service returns a candidate provider enrollment record but cannot approve a
    runtime voice binding.
12. [x] Add the DashScope Qwen-Audio enrollment adapter. It must use the
    configured enrollment endpoint, request
    `model=voice-enrollment`/`action=create_voice`, bind the request to one
    target TTS model, and avoid persisting the signed source URL.
13. [x] Add tests for manifest validation, consent/revocation rejection, source
    URL validation, provider request shape, returned voice-ID extraction, and
    the non-approved candidate handoff to `tts_voice_profile.v1`.
14. [x] Add no HTTP endpoint until an authenticated operator/admin boundary and
    a secure source-asset store are selected. A public game client must never
    trigger enrollment.

## Verification

```powershell
python -m pytest -v backend/tests/test_tts_service.py backend/tests/test_config_runtime_modes.py
python -m pytest -v
python scripts/verification/verify_tts_provider_live.py --allow-live-call --evidence-run-id <opaque-run-id> --actor-id <approved-actor-id>
python scripts/verification/verify_tts_godot_playback.py --allow-live-call --evidence-run-id <opaque-run-id> --actor-id <approved-actor-id>
python scripts/verification/harness.py --profile all
```

The live commands are run only after credentials, quota, and approved voice IDs
are available. Their output must not disclose API keys, signed audio URLs, or
raw audio payloads.

## Deferred Work

- Dynamic emotion generation, token-level audio streaming, lip sync, and
  expressive instructions derived from cognitive or Siming state.
- Automatic voice cloning from unverified material.
- Silent cross-provider/model voice substitution.
- A general runtime asset lookup system; the voice manifest is initially an
  asset-management index and must respect the existing asset-library readiness
  gate.
