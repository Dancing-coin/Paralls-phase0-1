# Runtime Boundary Audit

Date: 2026-07-01

## Naming Rule

A module may be named `Runtime` only when it owns tick/cadence, lifecycle/session continuity, and orchestration across multiple child services.

`RuntimeState` is allowed only for state objects. Services, subsystems, registries, projections, routers, providers, contracts, and verifiers must not be named runtime hosts.

## Audit Table

| Current or legacy name | Responsibility | Should be runtime? | Canonical name | Changed now | Migration risk |
| --- | --- | --- | --- | --- | --- |
| `CharacterAgentRuntime` | Character loop, cadence, continuity, and service orchestration | Yes | Keep | No | Low |
| `SimingRuntime` | Siming high-level loop, candidate handling, read-model orchestration | Yes | Keep | No | Low |
| Godot runtime / `*RuntimeProbe.gd` | Godot scene execution and runtime verification | Yes for scene/probe context | Keep | No | Low |
| `SessionRuntime` | Structured player input routing and small position cache | No | `SessionInputRouter` | Yes, compatibility alias kept | Low |
| `RuntimeSpatialOccupancyField` | Dynamic L1 occupancy state model | No | `SpatialOccupancyField` | Yes, compatibility alias kept | Low |
| `RuntimeSpatialOccupancyService` | L1 occupancy update service | No | `SpatialOccupancyService` | Yes, compatibility alias kept | Low |
| `CharacterRuntimeState` | Godot character state object | State only | Keep with state-only boundary | No | Low |
| `CharacterEmbodimentAssetRuntime` | Asset registry/preload/realization planning API | No | `CharacterEmbodimentAssetRegistry` | Yes | Medium; old GDScript path removed |
| `l1-world-fact-runtime` | Harness verification profile | No product runtime | Compatibility profile name only | Documentation clarified | Low |
| `L1 runtime` plan language | L1 world fact services/subsystem integration | No | `System L1 world fact subsystem` / `runtime-facing L1 services` | Yes | Low |
| `ESMService` | Authority settlement service | No | Keep `ESMService` | No | Low |

## Hard Boundaries

- Do not add an L1 main loop.
- Do not add an L1 event bus.
- Do not add an L1 scheduler.
- Do not add L1 authority.
- Do not bypass `raw_fact_event -> candidate percept -> CharacterPerceivedEvent`.
- Do not turn ESM into a runtime host.
