# M0-1 Runtime to Owner and FactType candidates

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`; latest coordination baseline checked was `0ecf65aae1698fabba06f06491f7800abdc1728a` and differs only in coordination docs.
- Commands: `Get-ChildItem backend\app\gameplay -Recurse -Filter '*_runtime.py'`; read-only Python AST scan of event_type/stream_id dictionary keys and constant assignments; `rg -n 'REGISTERED_OWNER_IDS|gameplay\.' ...`.
- Scan time: 2026-11-22 Asia/Shanghai.
- Conclusion level: static-only. The rows are candidates, not Owner rulings. AST literal extraction does not resolve every dynamic event type, stream interpolation, caller, or event definition. `fact_type_registry.py:11` currently registers only `Credential`, `Ownership`, and `Economy / Market`.
- Formal Owner name source: `D:\Users\User\Documents\Unreal Projects\Paralls-docs\docs\architecture-v2\04-Owner\01-Owner定义.md:28-54`. The prose says “23” at line 196, while the native and stewarded tables contain 10 + 12 = 22 names at lines 28-54. Combat occurs in an example at lines 93-101, not in either Owner table. This discrepancy is unresolved here.

## Runtime mapping

Event and stream column gives a representative statically located write declaration or write literal. Dynamic values are labelled as such. Candidate primitive is inference only.

| Runtime | Event type and definition evidence | Stream evidence | Candidate Owner | Candidate primitive (inference) | Second-truth / notes |
|---|---|---|---|---|---|
| `ability_runtime.py` | dynamic `event_type`, line 234 | dynamic `stream_id`, line 234 | Equipment / Body-Resource, unresolved | pool (inference) | reads resources and equipment; candidate only |
| `action_consequence_runtime.py` | source event is read/consumed at lines 69, 89 | source stream | LifeState / Body-Resource, unresolved | machine (inference) | consequence writer is elsewhere |
| `action_window_runtime.py` | event payload construction around line 281 | action window stream | Command / Dispatch, unresolved | process (inference) | time-window control state |
| `adventure_basic_mirror_runtime.py` | authored mirror event | mirror stream | no separate Owner candidate | none | projection/mirror path |
| `bakery_reference_runtime.py` | bakery workflow events; caller evidence in `population_continuity/vertical.py` | bakery, account, and related streams | Production / Facility; Economy / Market | process, pool (inference) | cross-domain orchestration |
| `civilization_capability_runtime.py` | event passed through at line 232 | capability stream | no exact formal Owner match | machine (inference) | service input adapter |
| `construction_production_runtime.py` | `facility_operationally_verified` line 2800; `production_output_certified@1` line 2977; public project and facility events at lines 3360-6762 | constructed per operation | Production / Facility; Government / Policy candidates | machine, process (inference) | imports private `_canonical_digest` from `patch_runtime.py:54` |
| `contract_runtime.py` | `record_created` lines 399, 505, 645, 802; `service_completion_recorded` lines 926-1250; `record_fulfilled` lines 937-1309 | `_STREAM = gameplay:contracts`, line 270 | split candidates: Government / Policy; Production / Facility; Economy / Market | process (inference) | see Contract fact list below; one generic runtime spans domains |
| `credential_runtime.py` | dynamic `event_type`, line 468 | `gameplay:credentials`, line 201; ownership stream line 202 | Credential | process (inference) | shared replay helper is used |
| `daily_rhythm_runtime.py` | registered FactTypes at lines 14-17; initial state at 54-55 | daily rhythm state | Survival candidate | pool, machine (inference) | overlaps B0 hot state |
| `debt_runtime.py` | dynamic event at line 910; debt settlement writes include debt and commerce families | `_DEBT_STREAM`, `_CONTRACT_STREAM`, `_COMMERCE_STREAM`, `_ECONOMY_STREAM`, lines 486-489 | Economy / Market | process (inference) | reads/writes cross-domain streams; `_digest` local |
| `ecology_platform_runtime.py` | platform declaration events | platform-defined | no exact formal Owner match | process (inference) | package/platform concern |
| `ecology_runtime.py` | crop/resource events at lines 2318, 2503, 2507; multiple dynamic event values | event-derived | Production / Facility or Survival candidates | pool, process (inference) | imports private economy admission functions at line 25 |
| `econ1_economy_runtime.py` | wage/purchase events at lines 244, 619, 827, 1010 | event-derived | Economy / Market | process (inference) | shared boundary requiring handoff before changes |
| `economy_platform_runtime.py` | platform-defined events | platform-defined | no exact formal Owner match | process (inference) | no direct Owner assignment inferred |
| `economy_runtime.py` | public project/budget/market event literals at lines 2922-4597 | `gameplay:economy`, line 5180 | Economy / Market | pool, process (inference) | shared boundary; imports `ContractProjector` |
| `equipment_runtime.py` | dynamic `event_type`, line 926 | dynamic `stream_id`, line 926 | Equipment | pool, machine (inference) | local replay/digest implementation requires per-file check |
| `frost_farm_runtime.py` | `farm.crop_frost_evaluated`, line 126 | derived from farm/crop context | Production / Facility or Survival candidates | pool (inference) | separate from `_runtime.py` users of ecology |
| `gift_runtime.py` | `gameplay.commerce.gift_settled`, line 42 | ownership and commerce streams, lines 79-80 | Economy / Market; Ownership | bond, process (inference) | cross-domain transaction |
| `government_treasury_runtime.py` | `gameplay.government_treasury.collector_account_admitted`, line 81 | runtime-selected | Government / Policy; Economy / Market | pool (inference) | treasury/account boundary |
| `inventory_platform_runtime.py` | platform-defined events | platform-defined | Inventory / Resource candidate | holdings (inference) | platform concern |
| `inventory_runtime.py` | inventory harvest/mill/custody constants lines 28-38; production output at 2267 | provider stream passed by caller, line 1508 | Inventory / Resource | holdings, pool (inference) | reads production/ecology evidence |
| `land_right_runtime.py` | `gameplay.ownership.right_transferred`, line 155 | ownership stream, line 34 | Ownership / Property | bond (inference) | credential stream cross-read |
| `life_state_runtime.py` | conflict death source and life event constants, lines 16-17 | runtime-selected | LifeState | machine (inference) | source event from conflict domain |
| `modifier_runtime.py` | modifier event family | runtime-selected | Status / Effect or Body / Resource | pool, machine (inference) | effect/attribute read dependencies |
| `organization_government_runtime.py` | government and organization events, lines 923-7014 | multiple streams | Government / Policy; Population / Work; Economy / Market | process, bond (inference) | spans several fact families |
| `organization_government_social_platform_runtime.py` | `social.population_signal_recorded@1`, line 23 | platform-defined | Social / Influence candidate | process (inference) | platform event |
| `ownership_runtime.py` | `gameplay.ownership.right_granted`, line 412 | dynamic stream, line 504 | Ownership / Property | bond (inference) | Bond implementation belongs to mechanism work |
| `patch_runtime.py` | patch manifest/state events, including schema digests | patch streams | no formal Owner candidate | none | shared mechanism; `_canonical_digest` consumed cross-runtime |
| `reference_data_runtime.py` | reference data events | reference stream | no exact formal Owner match | none | static/reference data concern |
| `resource_body_runtime.py` | dynamic event at line 1230 | dynamic stream, line 1230 | Body / Resource | pool, machine (inference) | shared hub |
| `p5/scripted_mystery_case_runtime.py` | scripted case event family | case stream | Information / Intelligence candidate | process (inference) | P5 runtime; local event declarations |
| `soul_effect_runtime.py` | event definitions are in adjacent authority modules | effect streams | Status / Effect candidate | process (inference) | no direct event literal found by this AST pass |
| `soul_fact_runtime.py` | event family in authority path | soul stream | no exact formal Owner match | machine (inference) | reads soul state |
| `soul_runtime.py` | event family in authority path | soul stream | no exact formal Owner match | machine (inference) | local state/authority combination |
| `survival_runtime.py` | survival state/obligation event family | actor survival streams | Survival | pool, machine (inference) | imports `rejected_result` lazily in a function |

The recursive glob contains 36 files, including the nested `p5` runtime. The following in-scope service and population-continuity modules also call `append_batch`; dynamic event values are shown as unresolved rather than inferred.

| Writer module | Event type evidence | Stream evidence | Candidate Owner / primitive (inference) | Notes |
|---|---|---|---|---|
| `services/economy_random_command_service.py` | dynamic batch, append at line 87 | dynamic | Economy / Market; process | caller supplies batch |
| `services/embodied_authority_settlement_service.py` | `gameplay.embodied.street_settled@1`, lines 92-94; append line 283 | `gameplay:embodied:street-owner`, line 92 | Combat / LifeState candidates; process | additional combat path |
| `services/embodied_carry_place_authority_service.py` | dynamic batch, append line 399 | dynamic | Presence / Movement; place | embodied authority |
| `services/embodied_custody_inventory_authority_service.py` | `gameplay.inventory.item_transferred_in/out`, lines 97, 270; append lines 188, 352 | `gameplay:inventory:{...}`, lines 154, 331 | Inventory / Resource; holdings | two write methods |
| `services/embodied_handoff_authority_service.py` | dynamic batch, append line 293 | dynamic | Presence / Movement; place | handoff authority |
| `services/embodied_interaction_session_service.py` | dynamic batch, append line 602 | dynamic | multiple candidate domains | session settlement |
| `services/equipment_command_service.py` | `gameplay.character.life_state_changed`, line 361; append lines 104, 114 | body, character-life, equipment, inventory streams, lines 184-188 | LifeState, Body / Resource, Equipment, Inventory / Resource | multi-Owner fragment candidate |
| `services/equipment_prediction_service.py` | dynamic batch, append line 49 | prediction, character-life, body, inventory, equipment streams, lines 71, 108-146 | Equipment / Body / Inventory candidates | prediction and settlement path |
| `services/esm_service.py` | `gameplay.esm.object_settled` and `personal_action_disclosed`, lines 27, 33; appends 776, 839 | object/learning streams, lines 616-618, 804 | Information / Intelligence candidate | ESM service owns this write path |
| `services/resource_conversion_service.py` | `gameplay.resource.converted`, lines 192, 257; appends 65, 200 | `gameplay:resources:{...}`, line 145 | Body / Resource; pool | resource conversion |
| `population_continuity/activation.py` | `gameplay.ecology.region.recorded`, line 597; append lines 304, 486, 514, 682, 779 | survival/ecology streams, lines 52-82, 594 | Survival; ecology fact owner unresolved | mixed activation effects |
| `population_continuity/batch.py` | government inspection line 1300; survival obligation family lines 1482-1486; wage event line 1797; append lines 1323, 2023 | organization/economy/government/survival streams, e.g. lines 452-455, 883, 1231-1233 | Population / Work; Government; Economy / Market; Survival | multi-domain batch settlement |
| `population_continuity/branch_preview.py` | branch preview events lines 327-455; government inspection lines 869-891; append lines 388, 497, 838, 994 | branch-preview, organization, government streams, lines 147, 689, 875 | Government / Policy; Population / Work candidates | isolated branch/evolution records |
| `population_continuity/presence_runtime.py` | dynamic event batch, append lines 113, 133 | character life stream, lines 104, 195 | Presence / Movement; place | intent/presence workflow |
| `population_continuity/runtime_publication.py` | dynamic batches, append lines 118, 690 | dynamic | Population / Work; process | publishes runtime state |
| `population_continuity/world.py` | dynamic batches, append lines 205, 1032 | dynamic | Population / Work; process | world tick settlement |

Some runtime and service event lists remain dynamic and therefore are not complete from syntax literals alone. A complete set needs event producer/schema resolution and caller tracing, which was not established by this scan.

## S-1 Combat facts

Combat writes are distributed across multiple modules. This answers code placement only and does not decide whether Combat becomes an Owner.

| File | Event / fact | Evidence |
|---|---|---|
| `backend/app/gameplay/canonical_combat_authority.py` | faction relation, threat relation, encounter begin/end | constants lines 23-28; writes lines 89, 496, 699, 728, 887 |
| `backend/app/gameplay/physics_contact_receipt.py` | `gameplay.combat.physics_contact_receipt_recorded` | constant line 22; write line 163 |
| `backend/app/gameplay/combat_durable_adapter.py` | `gameplay.combat.embodied_settlement_recorded` | constant line 23; write line 273 |
| `backend/app/services/embodied_authority_settlement_service.py` | street-combat result is staged and persisted through event specs | method lines 235-279; volatile settlement lines 292-375 |

The combat adapter consumes a committed hit and writes threat/encounter follow-on facts (`combat_durable_adapter.py:81-145`, `canonical_combat_authority.py:812-887`). These are distinct write/consume roles.

## S-8 Contract fact families

The runtime emits a shared event family. `contract_runtime.py:187-190` names `record_created`, `record_fulfilled`, `record_terminated`, and `service_completion_recorded`; write sites include lines 399-1309. Stream is `gameplay:contracts` at line 270. Caller evidence is from imports and call sites: government drought assessment (`organization_government_runtime.py` and `economy_runtime.py`); facility commissioning review (`construction_production_runtime.py` and `economy_runtime.py`); public workshop and public milling session (`organization_government_runtime.py`, `bakery_reference_runtime.py`, and `economy_runtime.py`); simple service completion (`contract_runtime.py:1287-1311`).

| Contract purpose | Event family | Caller evidence | Candidate fact domain only |
|---|---|---|---|
| Municipal drought assessment / government evaluation | `gameplay.contract.record_created`, `service_completion_recorded`, `record_fulfilled` | contract call sites in `contract_runtime.py:1217-1266`; consumers in `economy_runtime.py:1214-1222` | Government / Policy |
| Facility commissioning review / facility acceptance | same contract family | facility fulfillment construction in `contract_runtime.py:926-986`, `1011-1060` | Production / Facility |
| Public workshop service | same contract family | `contract_runtime.py:1068-1148`; callers in `organization_government_runtime.py` | Economy / Market or Production / Facility |
| Public milling session / mill service | same contract family | `contract_runtime.py:1203-1266`; callers in `organization_government_runtime.py` | Economy / Market or Production / Facility |
| Generic simple service | `service_completion_recorded`, `record_fulfilled` | `contract_runtime.py:1287-1311` | depends on service evidence |

Formal v2 Owner labels are candidates from `01-Owner定义.md:28-54`. The migration spec records an S-8 decision to split by fact domain, while the migration plan still says unresolved at lines 84-88 and 150. This inconsistency is escalated in the README.
