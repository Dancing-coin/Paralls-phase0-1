# Scene Binding: `citystreets_209`

## Runtime shell

- Godot host shell: generic environment host / `EnvironmentStateNode`
- Imported model path after staging: `res://assets/active/citystreets_209/environment.glb`
- Required runtime ID: `environment_id = citystreets_209`
- Rotation correction: none expected
- Scale correction: none expected

## Anchors

| Semantic ID | Export record | Expected use |
| --- | --- | --- |
| `player_spawn` | `metadata/anchors.json#ANCHOR__player_spawn` | player spawn |
| `character_spawn:a` | `metadata/anchors.json#ANCHOR__character_spawn_a` | first character stand |
| `character_spawn:b` | `metadata/anchors.json#ANCHOR__character_spawn_b` | second character stand |
| `zone:validation` | `metadata/anchors.json#ANCHOR__zone_validation` | 32 m intersection sampling zone |
| `approach:nw_building` | `metadata/anchors.json#ANCHOR__approach_nw` | approach check |
| `contact:nw_building` | `metadata/anchors.json#ANCHOR__contact_nw` | contact check |
| `observation:intersection` | `metadata/anchors.json#ANCHOR__observation_intersection` | observation check |
| `placement:southwest` | `metadata/anchors.json#ANCHOR__placement_southwest` | placement check |
| `camera:primary` | `metadata/anchors.json#ANCHOR__camera_primary` | north-facing camera anchor |

## Collision and navigation

- Collision source: `collision.glb`
- Navigation geometry: `navigation.glb`
- Navigation metadata: `metadata/navigation.json`
- Visual mesh used as gameplay collision: `no`
- Known occupancy constraint: building and tree-trunk proxies block walkable input; roads, crosswalks, sidewalks, lamps, foliage, facade details, and traffic lights do not.

## State and action bindings

`FIXTURE__intersection_lighting` binds presentation states `dusk` and `street_lights_on` to `environment_id = citystreets_209`. The asset does not decide state or authority results.
