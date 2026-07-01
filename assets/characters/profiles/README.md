# Character Profiles

This directory stores Stage 2 structured-file-first profile truth for character agents.

Each YAML file is intended to be the editable source for the Stage 2 eight-layer profile structure
before runtime wiring grows around it.

The top-level eight layers should always exist. Non-mandatory detail layers may stay as empty
structured objects until later authoring, while the Stage 2 runtime-critical identity, trait,
value/taboo, capability/constraint, style, and conversation fields are expected to be explicitly authored.
