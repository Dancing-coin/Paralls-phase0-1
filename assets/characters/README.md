# Character Asset Staging

Place incoming `A/B/C` character assets here.

Recommended structure:

- `A/`
- `B/`
- `C/`
- `shared_animations/`

Preferred source formats:

- `.glb`
- `.gltf`

Pipeline intent:

- all three roles should pass through one shared `mixabridge`-ready skeleton and action pipeline
- `A/B/C` should not diverge into separate asset conventions
