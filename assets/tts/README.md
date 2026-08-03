# TTS Voice Profile Assets

`TTSVoiceProfileResolver` loads two presentation-only JSON assets when
`TTS_VOICE_PROFILES_ENABLED=true`:

- `voice_catalog.json`: voices valid for exactly one provider and model.
- `voice_bindings.json`: one approved voice binding per actor.

Start with the adjacent `.example.json` files, copy them to a local or
deployment-managed location, then set `TTS_VOICE_CATALOG_PATH` and
`TTS_VOICE_BINDINGS_PATH`. The configured paths may be absolute or relative to
the repository root.

Do not put API keys, provider temporary URLs, raw audio, or unlicensed voice
samples in these assets. `selection_status` must be `approved` before a binding
is used for synthesis. The resolver validates the binding against the catalog
and the configured `TTS_MODE`/`TTS_PROVIDER_MODEL` before it makes a provider
request.

These files are presentation configuration. They do not alter character dossier
identity, dialogue generation, authority, world truth, or Siming.

For a provider Excel export, a controlled authoring or release tool may call
`import_xlsx_voice_catalog(...)` from
`backend/app/services/tts_voice_catalog_importer.py`. It reads the first XLSX
worksheet, requires explicit provider/model/catalog-revision inputs, and emits
the same catalog schema. Its candidate ranking helper only produces a
deterministic review short-list; it cannot create or approve bindings. Exported
catalogs still need a human audition record before an approved binding is used.

`presentation_instruction` is optional authored presentation metadata on a
binding. It is disabled by default and must exactly match the catalog's
`allowed_presentation_instructions`; it reaches a provider only when that
adapter explicitly declares support. Do not populate it from generated dialogue,
affect, Siming, player input, or world state.
