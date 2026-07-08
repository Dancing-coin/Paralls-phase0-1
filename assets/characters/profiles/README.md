# Character Profiles

This directory stores Stage 2 structured-file-first profile truth for character agents.

Each YAML file is the editable source for authored profile truth before runtime wiring grows around it.

The shipped profile truth now includes the original authored core layers plus:
- `need_hierarchy_layer`
- `temperament_response_layer`
- `long_term_personality_drift_layer`

`need_hierarchy_layer` and `temperament_response_layer` are authored truth, not runtime state.
`long_term_personality_drift_layer` stores only durable profile-drift authoring and policy
for slow cross-scene change. It must not be used as per-scene runtime mood, temporary state, or drift history.
