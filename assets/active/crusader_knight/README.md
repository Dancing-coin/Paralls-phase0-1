# Crusader Knight External Package

This active package is a runtime wrapper around the externally authored
`crusader_knight.glb`. The source asset remains unchanged; its SHA-256 digest,
source URI, canonical humanoid mapping, import/rest-pose policy, slots,
locomotion and action profiles are declared in `manifest.json`.

The package follows the external authoring contract: lower-case snake_case
clip aliases, metres, applied transforms, a stable root/rest pose, `-z`
forward and `+y` up. Semantic action IDs are independent from clip names and
all timing entries keep `atomic_sequence: []`.
