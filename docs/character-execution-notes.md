# Character Execution Notes

Required shell capabilities:

- explicit driver mode: `ai` / `player`
- explicit move target API
- explicit look target API
- explicit action dispatch API
- no hard dependency on patrol-only motion for all roles
- same shell usable by `A`, `B`, and `C`

Player-driven C rule:

- player input should eventually drive character `C`'s active role surface
- player should not permanently bypass the shared role shell
- current demo may keep the existing player character while introducing the `C`-ready handoff points
