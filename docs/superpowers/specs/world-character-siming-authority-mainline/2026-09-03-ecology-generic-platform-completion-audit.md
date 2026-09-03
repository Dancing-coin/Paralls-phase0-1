# General Ecology Platform Completion Audit

Status: `implemented-and-verified`

| Requirement | Evidence |
| --- | --- |
| v3/platform 2.0 typed content | `ecology_platform_content.py` strict models and 5 focused tests |
| Region graph and local grid | `ecology_platform_runtime.py` region/cell records, topology pins and replay tests |
| Environment/resource/crop/species state | owner-local record APIs, deterministic close order and checkpoint-tail tests |
| Seven hazard families | `ecology_hazard_platform.py` lifecycle/recovery/propagation tests; 4 focused hazard tests plus 16 legacy INF propagation tests |
| Bounded propagation | precompiled topology only, budget/cycle/stale/private zero-write coverage |
| Six owner-bound consumers | `ecology_consumer_platform.py` exact rows and 13 admission tests; existing target-owner catalog rows remain authoritative |
| Population/Godot boundary | read-only `ecology_presentation.py` and presentation tests; Population signal remains non-settling |
| Event schema admission | `register_general_ecology_platform_event_schemas()` and registry-backed runtime test |
| Replay/privacy/idempotency/receipt | core, hazard, consumer and legacy Ecology suites; full/checkpoint-tail parity asserted |
| Harness | `ecology-generic-platform` profile: 57 passed |
| Repository regression | `python -m pytest -q`: 4481 passed; compileall and diff check passed |
| August scope | Mainline and INF docs continue to record August INF A-D as `not complete` |

The Ecology platform is complete as an owner-bound, deterministic platform.
This does not complete or alter August INF A-D.
