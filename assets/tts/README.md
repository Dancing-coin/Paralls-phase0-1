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
