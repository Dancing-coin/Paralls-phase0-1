# TTS Voice Profile Adapter Design

Status: `implementation-active`

Date: `2026-07-31`

## 2026-08-02 Implementation Status

The presentation boundary now includes a controlled standard-library XLSX
normalizer and deterministic candidate-ranking helper. The importer requires
the provider, model, and catalog revision explicitly, rejects malformed or
duplicate voice IDs, and produces the existing `tts_voice_catalog.v1` shape.
Ranking accepts only explicit presentation criteria, returns an advisory
short-list, and cannot create or approve a `VoiceBinding`. The focused
`tts-voice-profile-adapter` profile proves this boundary alongside existing
binding and enrollment tests; it does not prove a live provider call or human
audition/approval.

An approved binding may now carry one authored `presentation_instruction`, but
only when `TTS_PRESENTATION_INSTRUCTIONS_ENABLED=true`, the exact preset is in
the catalog allowlist, and the selected adapter declares support. The current
DashScope and generic OpenAI-compatible adapters declare support as false, so
an enabled preset is rejected before a network request rather than silently
dropped or synthesized from dialogue/affect/Siming data.

## Purpose

The existing TTS path correctly maps an `actor_id` to one provider voice ID, but
it cannot explain whether that ID fits the character, whether it is supported by
the selected provider model, or how an operator should select from a large voice
catalog. This design adds a presentation-only voice profile adapter.

The adapter consumes authored presentation preferences and an imported provider
catalog, then resolves a previously approved `VoiceBinding` for each actor. It
does not participate in dialogue generation, character cognition, ESM authority,
world truth, persistence, or Siming.

## Provider Facts And Product Decision

For the current Model Studio model, `qwen-audio-3.0-tts-flash`, only four
system voices are available: `longanhuan_v3.6`, `longjielidou_v3.6`,
`loongeva_v3.6`, and `loongjohn`. Only the first two support Chinese, and only
`longanhuan_v3.6` is an adult voice. System voices alone cannot distinguish the
current three Chinese-speaking roles.

The selected model also offers 500+ imported basic cloned voices. Their IDs use
the form `qwen-audio-3.0-tts-flash-{suffix}` and are valid only for the Flash
model. This is the first expansion path. Model Studio voice cloning and voice
design are later operator-facing catalog sources, subject to provider terms and
recording-consent verification. A second provider remains possible through the
existing `TTSProvider` boundary, but it must import a separate catalog rather
than reuse DashScope IDs.

## Boundaries

### Inputs

The adapter may use only approved presentation information:

- `EmbodimentProfile.voice_baseline` (`volume`, `tone`)
- authored `style_expression_bias_layer.speech_style`
- an explicit presentation choice such as voice gender or age impression when
  the character dossier does not establish it
- a provider catalog's descriptive metadata and compatibility declarations

It must not read private truths, memories, relationships, current affect,
authority state, player input, or Siming output. A presentation choice cannot
backfill missing identity facts into a character dossier.

### Outputs

A selected binding is a versioned presentation asset, separate from the character
dossier, with at least:

```yaml
contract: tts_voice_profile.v1
actor_id: char_a
provider: dashscope_http
model: qwen-audio-3.0-tts-flash
voice_id: qwen-audio-3.0-tts-flash-longlanghongmo
catalog_revision: 2026-07-23
selection_status: approved
approved_by: human-listening-review
presentation_traits: [soft, measured, warm]
```

`TTSService` receives only the final provider voice ID after validation. The
existing `tts_audio.v1` payload is unchanged and continues to expose the
resolved `voice_id` only as presentation metadata.

## Catalog And Compatibility Contract

An imported `VoiceCatalogEntry` contains `provider`, `model`, `voice_id`,
`catalog_revision`, `language_tags`, optional `age_impression`, optional
`voice_gender_presentation`, `trait_tags`, `usage_tags`, and a local preview
reference or operator review reference. The runtime never downloads arbitrary
catalog URLs.

`VoiceBinding` validation must reject:

1. an unapproved or absent binding;
2. an unknown catalog voice;
3. a provider or model mismatch;
4. a binding without Chinese support when the dialogue locale requires Chinese;
5. a catalog revision that has been retired without an explicit compatibility
   waiver.

The validator returns a typed presentation error. Production dialogue retains
the current fallback-to-stub behavior. It never substitutes a different voice
silently.

## Selection Workflow

1. An operator imports a provider-issued catalog snapshot into a non-secret,
   versioned asset. The importer validates schema and deduplicates IDs.
2. The adapter derives candidate tags from the allowed authored presentation
   inputs and ranks candidates only as a decision aid.
3. A human auditions the short-list using neutral, command, and sensitive-line
   scripts. The human records the approved binding and any explicit
   presentation-gender decision.
4. CI validates every approved binding against the current catalog and provider
   model. A controlled live probe verifies a changed binding when credentials
   are available.
5. Runtime resolves the approved binding; otherwise it retains the legacy
   environment mapping and fails to the existing stub path.

For the current actors, the initial audition short-list is:

| Actor | Required presentation | Flash basic-voice candidates |
| --- | --- | --- |
| `char_a` | young adult, soft, low-volume, measured | `longlanghongmo` (female, 25, warm and friendly) |
| `char_b` | controlled, clipped, steady guard presence | `longyuzhihe` (male, 42, objective/calm); `longyimuling` (male, 38, steady/powerful) |
| `char_c` | bright, teasing, socially energetic | `longtongxuxian` (female, 24, lively/agile); `longyaolanxuan` (male, 25, playful) |

The catalog prefixes these IDs with `qwen-audio-3.0-tts-flash-`. B and C have
no authored gender identity in their current profile, so their final
gender-presenting voice requires an explicit presentation choice; it remains
outside character truth.

## Expression Controls

The next provider request contract may add an optional, allowlisted
`presentation_instruction` field. It is selected from authored voice-profile
presets such as `calm_guard` or `gentle_disclosure`; it is not generated from
runtime cognition or written back to it. The initial implementation must keep
this feature disabled by default until provider behavior and content limits are
tested. It is not a substitute for a suitable base timbre.

## Character Asset Library Placement

A cloned voice is a character presentation asset and should be managed beside
role-model, wardrobe, equipment, and prop bindings, but it has a different
security lifecycle from a GLB or texture.

The future character asset manifest may refer to a voice source as follows:

```yaml
asset_id: character_voice_source:char_a:take_01
actor_id: char_a
asset_kind: voice_reference
source_ref: secure_asset://characters/char_a/voice/take_01.wav
sha256: <content-hash>
rights_status: authorised
consent_ref: rights:voice-performer:agreement-2026-07
retention_policy: revocable
provider_enrollments:
  - provider: dashscope_http
    target_model: qwen-audio-3.0-tts-flash
    voice_id: qwen-audio-3.0-tts-flash-char-a-<provider-suffix>
    enrollment_status: active
```

`source_ref` resolves only inside an authorised asset-management or enrollment
tool. It is not a Godot `res://` resource, a public URL, a WebSocket field, or a
world/character fact. The TTS runtime stores and consumes only the provider
voice ID through the approved `tts_voice_profile.v1` binding.

For Model Studio Qwen-Audio-TTS, the official voice-cloning flow accepts a
10-20 second compliant audio sample, creates a voice with
`target_model=qwen-audio-3.0-tts-flash`, then returns a model-specific voice ID
for later synthesis. The enrollment worker must upload the source through a
short-lived authorised URL, record the returned ID and provider request audit
reference, and never commit raw source audio, signed URLs, or API credentials.

Voice cloning requires an explicit right/consent record from the human performer
or another applicable licence. It must support revocation: mark the enrollment
retired, remove its approved binding, request provider-side deletion where
available, and immediately return to an approved replacement or the existing
stub fallback.

The long-term asset topology is therefore:

```text
CharacterAssetManifest (visual / wardrobe / props / voice source refs)
  -> controlled enrollment workbench (voice source only)
  -> provider enrollment record (model-specific voice ID)
  -> approved tts_voice_profile.v1 binding
  -> TTSProvider -> existing tts_audio.v1 -> Godot playback
```

The manifest is an asset-management index, not a new runtime character asset
library. It must not bypass `CharacterReplica`, the existing art-pack adapters,
or the current authority boundaries.

## Alternatives

1. **DashScope Flash basic voices (recommended first):** broad Chinese voice
   variety without changing the existing audio transport or provider adapter.
2. **DashScope Plus:** two higher-tier system voices and the matching Plus basic
   catalog. It is a quality/cost/latency decision, not a way to reuse Flash IDs.
3. **Voice cloning:** use only a legally authorised, consented human reference;
   record ownership, provider voice ID, and revocation status outside runtime.
4. **Voice design:** commission provider-generated voices from a presentation
   brief, then import and audition them as catalog entries.
5. **Second provider:** add a named `TTSProvider` adapter plus its own catalog
   importer and WAV capability checks. Never put one provider's voice IDs in
   another provider/model binding.

## Acceptance Criteria

1. Existing stub mode, dialogue, character execution, ESM, and Siming paths are
   unchanged.
2. A Flash binding using a basic voice ID validates only against the Flash
   catalog and produces the existing complete WAV `tts_audio.v1` contract.
3. A CosyVoice or Plus voice ID is rejected for a Flash binding before the
   provider request; dialogue falls back to stub without changing text.
4. B and C cannot gain dossier gender identity through voice selection.
5. Every approved binding has catalog provenance and a recorded human listening
   review.
6. Catalog parser, validation, fallback, and approved-binding resolution are
   covered by focused tests; changed production bindings receive a guarded live
   proof and Godot playback proof.
