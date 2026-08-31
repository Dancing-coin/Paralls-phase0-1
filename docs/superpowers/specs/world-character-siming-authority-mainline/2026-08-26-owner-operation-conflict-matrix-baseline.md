# Owner Operation Conflict Matrix Baseline

Status: `approved baseline inventory; read-only admission preflight input`

## Scope

This baseline indexes the immutable contracts currently returned by
`GovernedAuthorityContractCatalog`. It is the initial comparison set for the
[owner-operation conflict matrix](2026-08-26-owner-operation-conflict-matrix-design.md).
Detailed source predicates, package pins, and lifecycle rules remain in each
row-specific contract; this table identifies the canonical fact partition that
prevents duplicate implementation.

`implemented` means the catalog row and its owner vertical have evidence.
`admitted` means immutable catalog governance is present but the row is not a
new autonomous implementation target. Neither term broadens a fact claim.

## Construction And Survival

| Operation key | Fact claim / fixed partition | Owner | Contract ref | Event family | Scope | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `construction:facility:repair@1` | condition repair and its fixed compensation pair | ConstructionProductionAuthority | `inf:construction-facility-repair@1` | `facility_repaired`, `facility_repair_compensated` | project | implemented |
| `construction:facility:bakery-reinforcement@1` | `bakery -> bakery_reinforced` | ConstructionProductionAuthority | `inf:construction-facility-bakery-reinforcement@1` | `facility_transformed` | project | implemented |
| `construction:facility:oven-to-kiln@1` | frozen v1 `oven -> kiln` partition | ConstructionProductionAuthority | `inf:construction-facility-package-declared-transform@1` | `facility_transformed` | project | implemented |
| `construction:facility:mill-reinforcement@1` | frozen v2 `mill -> mill_reinforced` partition | ConstructionProductionAuthority | `inf:construction-facility-mill-reinforcement@1` | `facility_transformed` | project | implemented |
| `construction:facility:mill-decommission@1` | `mill_reinforced active -> decommissioned` | ConstructionProductionAuthority | `inf:construction-facility-mill-decommission@1` | `facility_decommissioned` | project | implemented |
| `construction:facility:operational-verification@1` | completed production run -> facility operational verification record | ConstructionProductionAuthority | `inf:construction-facility-operational-verification@1` | `facility_operationally_verified` | project | implemented |
| `construction:facility:public-use-enable@1` | exact project-visible operationally verified oven -> public-use status enabled | ConstructionProductionAuthority | `inf:construction-facility-public-use-enable@1` | `facility_public_use_enabled` | project | implemented |
| `construction:public-project:workshop-bench@1` | exact Organization public-project work-order fulfillment -> Construction project-step completion | ConstructionProductionAuthority | `inf:construction-public-project-step-completion@1` | `public_project_step_completed` | project | implemented |
| `construction:facility:operational-verification@1` | committed completed production run -> facility operational verification record | ConstructionProductionAuthority | `inf:construction-facility-operational-verification@1` | `facility_operationally_verified` | project | implemented |
| `construction:facility:mill-reinforced-public-use@1` | completed verified run on active `mill_reinforced` plus frozen v2 reinforcement provenance -> public-use enabled | ConstructionProductionAuthority | `inf:construction-facility-mill-reinforced-public-use@1` | `facility_public_use_enabled` | project | implemented |
| `construction:maintenance:expiry@1` | fixed maintenance state/obligation lifecycle | ConstructionProductionAuthority | `inf:construction-maintenance-state-expiry@1` | `maintenance_state_*` | project | implemented |
| `survival:state:expiry@1` | fixed Survival state/obligation lifecycle | SurvivalAuthority | `inf:survival-state-expiry@1` | `state_*`, `obligation_*` | project | implemented |
| `inventory:production:output-receipt@1` | completed recipe output -> inventory custody/stock receipt | InventoryAuthorityService | P1D Bakery reference owner boundary | `output_received` | owner-scoped | implemented_reference |

The three `facility_transformed` rows are valid disjoint partitions only
because their source/target kinds, package/digest/descriptor pins, and
idempotency/replay vectors are exact. No unlisted kind pair belongs to this
family.

## Read-Only Capability Partitions

These rows are tracked here to prevent duplicate consumer work, but they are
not additional catalog writers or generic capability registries:

| Operation key | Fact claim / fixed partition | Owner boundary | Evidence / target | Scope | Status |
| --- | --- | --- | --- | --- | --- |
| `civilization:capability:read@1` | authority-scoped capability lifecycle/read view | `CivilizationCapabilityAuthority` | `gameplay:civilization_capability:{jurisdiction_ref}`; activated/revoked/corrected | authority_only | implemented |
| `civilization:capability:supply-binding@1` | frozen capability view gates one Organization supply fragment | `PopulationPlanner` proposal -> `OrganizationAuthority` | `commerce_commitment_accepted` on `gameplay:organization:{organization_ref}` | project target, authority source | implemented |
| `civilization:capability:inspection-binding@1` | frozen capability view gates one Government inspection fragment | `PopulationPlanner` proposal -> `GovernmentAuthority` | `inspection_recorded` on `gameplay:government:{organization_ref}` | project/actor target, authority source | implemented |

The capability rows preserve opaque source digests, owner-local receipts,
privacy and full/checkpoint-tail replay. Work, semantic, unlisted consumers,
progression, and generic capability-to-owner routing remain zero-write.

## Economy, Government, Organization, And Debt

| Operation key | Fact claim / fixed partition | Owner | Contract ref | Event family | Scope | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `economy:wage:payment@1` | fixed wage payment ledger vector | Econ1 EconomyAuthority | `inf:economy-wage-payment@1` | `wage_paid`, account debit/credit | mixed | implemented |
| `economy:commerce:delivery-payment@1` | delivery-bound payment/compensation | EconomyAuthority | `inf:economy-commerce-delivery-payment@1` | delivery payment, debit/credit | authority_only | implemented |
| `economy:tax:payment@1` | pinned tax payment/compensation/reopen vector | EconomyAuthority | `inf:economy-government-tax-payment@1` | tax payment, obligation, debit/credit | authority_only | implemented |
| `economy:package:negotiated-exchange@1` | one immutable package exchange vector | EconomyAuthority | `inf:package-declared-negotiated-exchange@1` | exchange, debit/credit, inventory/right transfers | authority_only | implemented |
| `economy:service:municipal-drought-assessment@1` | fulfilled exact municipal drought-assessment contract -> fixed 12-unit service settlement | EconomyAuthority | `inf:package-declared-negotiated-exchange@1` | package exchange debit/credit/settled | authority_only | implemented |
| `economy:service:facility-commissioning-review@1` | fulfilled exact facility commissioning-review Contract -> fixed 12-unit service settlement | EconomyAuthority | `inf:package-declared-negotiated-exchange@1` | package exchange debit/credit/settled | authority_only | implemented |
| `economy:service:public-workshop-session@1` | fulfilled exact public-use-enabled oven Contract -> fixed 12-unit public-workshop session settlement | EconomyAuthority | `inf:package-declared-negotiated-exchange@1` | package exchange debit/credit/settled | authority_only | implemented |
| `economy:public-project:budget-commitment@1` | exact Construction public-project step -> fixed authority-only 12-unit budget commitment | EconomyAuthorityService | `inf:economy-public-project-budget-commitment@1` | `public_project_budget_commitment_recorded` | authority_only | implemented |
| `economy:public-project:budget-reservation@1` | exact INF-2AF commitment -> one owner-derived `currency:local` account reservation | EconomyAuthorityService | `inf:economy-public-project-budget-reservation@1` | `budget_reserved` | authority_only | implemented |
| `economy:public-project:budget-consumption@1` | matching reservation plus completed public-workshop activity -> consumed authority-only marker | EconomyAuthorityService | `inf:economy-public-project-budget-consumption@1` | `public_project_budget_consumed` | authority_only | implemented |
| `economy:public-project:budget-close@1` | exact consumed marker plus funded execution -> terminal account-neutral close marker | EconomyAuthorityService | `inf:economy-public-project-budget-close@1` | `public_project_budget_closed` | authority_only | implemented |
| `government:treasury:collector-identity@1` | collector account admission identity only | GovernmentTreasuryCollectorAuthority | `inf:government-treasury-collector@1` | `collector_account_admitted` | authority_only | implemented |
| `economy:wage:accrual-obligation@1` | worker wage obligation lifecycle | Econ1 EconomyAuthority | `inf:economy-wage-accrual-obligation@1` | wage obligation/accrual lifecycle | project | implemented |
| `economy:production:wage-accrual@1` | committed Production evidence -> wage accrual | Econ1 EconomyAuthority | `inf:branch-work-wage-admission@1` | `wage_accrued` | project | implemented |
| `economy:tax:obligation@1` | account-neutral tax obligation lifecycle | EconomyAuthority | `inf:economy-tax-obligation@1` | `tax_*` obligation lifecycle | authority_only | implemented |
| `economy:scheduled-transfer:policy@1` | exact same-currency scheduled transfer policy | EconomyAuthority | `inf:economy-scheduled-transfer-policy@1` | account transfer lifecycle | authority_only | implemented |
| `government:inspection:policy@1` | commercial inspection policy register/revoke | GovernmentAuthority | `inf:government-inspection-policy@1` | inspection policy events | project | implemented |
| `government:inspection:passed-promotion@1` | fixed passed-inspection promotion | GovernmentAuthority | `inf:government-inspection-promotion@1` | `inspection_recorded` | project | implemented |
| `government:inspection:failed-promotion@1` | fixed failed-inspection remediation | GovernmentAuthority | `inf:government-failed-inspection-promotion@1` | `inspection_recorded` | project | implemented |
| `organization:operating-window@1` | operating-window lifecycle | OrganizationAuthority | `inf:organization-operating-window@1` | window lifecycle | mixed | implemented |
| `organization:production-work-contribution-acceptance@1` | committed Production completion evidence accepted against one organization-summary schedule/work-order binding | OrganizationAuthority | `inf:organization-production-work-contribution-acceptance@1` | `production_work_contribution_accepted` | project | implemented |
| `organization:public-workshop-activity@1` | fulfilled INF-2AG public-workshop Contract -> provider Organization activity record | OrganizationAuthority | `inf:organization-public-workshop-activity@1` | `public_workshop_activity_recorded` | project | implemented |
| `organization:public-milling-activity@1` | fulfilled INF-2AL milling Contract -> fixed provider Organization milling activity record | OrganizationAuthority | `inf:organization-public-milling-activity@1` | `public_milling_activity_recorded` | project | implemented |
| `organization:public-project:execution@1` | exact public-workshop activity plus consumed budget -> `funded_and_executed` project fact | OrganizationAuthority | `inf:organization-public-project-execution@1` | `public_project_execution_recorded` | project | implemented |
| `government:public-project:execution-acknowledgment@1` | exact funded execution plus consumed/reservation/acquisition provenance -> administrative acknowledgment | GovernmentAuthority | `inf:government-public-project-execution-acknowledgment@1` | `public_project_execution_acknowledged` | authority_only | implemented |
| `government:public-milling-notice@1` | exact INF-4AL milling activity -> project notice on acquisition-derived jurisdiction | GovernmentAuthority | `inf:government-public-milling-notice@1` | `public_milling_notice_recorded` | project | implemented |
| `organization:supply:promotion@1` | fixed Organization supply promotion | OrganizationAuthority | `inf:organization-supply-promotion@1` | commerce commitment accepted | project | implemented |
| `debt:simple:settlement@1` | fixed simple-debt issue/payment/correction lifecycle | DebtAuthorityService | `inf:simple-debt-settlement@1` | simple-debt event vector | authority_only | implemented |

Shared account debit/credit events are owner-local companion facts. They do not
make payment or transfer a generic operation; each root outcome above has its
own source, pins, receipt, replay, and terminal partition.

The P1D Bakery `run_finished -> output_received` sequence is already an
implemented owner partition: Construction owns completion, while Inventory
owns the output receipt. A proposed “production output into inventory” row is
therefore `duplicate_closed` unless it names a distinct product fact rather
than rewrapping the existing receipt.

| Operation key | Fact claim / fixed partition | Owner | Contract ref | Event family | Scope | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `economy:bakery:aggregate-sale@1` | Bakery aggregate-demand bread sale/account posting | Econ1 EconomyAuthority | P1D Bakery reference owner boundary | sale/account posting | owner-scoped | implemented_reference |

## Ecology And Cross-Owner Consumer Partitions

| Operation key | Fact claim / fixed partition | Target owner | Contract ref | Event family | Scope | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `ecology:frost:state-expiry@1` | ecology-owned frost crop-state lifecycle | EcologyHazardAuthority | `inf:ecology-frost-state-expiry@1` | `crop_state_*` | project | implemented |
| `ecology:drought:state-expiry@1` | ecology-owned drought-state lifecycle | EcologyHazardAuthority | `inf:ecology-drought-state-expiry@1` | `drought_state_*` | project | implemented |
| `ecology:weather-rain:crop-recovery@1` | exact rain front plus unique damaged target-region crop -> fixed `+5` health recovery partition | EcologyHazardAuthority | `inf:ecology-weather-rain-crop-recovery@1` | `crop.recorded` with immutable recovery provenance | project | implemented |
| `weather-front:construction:maintenance@1` | fixed weather-front -> Construction maintenance | ConstructionProductionAuthority | `inf:weather-front-construction-maintenance@1` | maintenance state vector | project | implemented |
| `weather-front:economy:quote@1` | one weather-front -> Economy quote | EconomyAuthority | `inf:weather-front-economy-quote@1` | `dynamic_quote_published` | project | implemented |
| `weather-front:economy:quote-fanout@1` | fixed two-quote same-owner partition | EconomyAuthority | `inf:weather-front-economy-quote-fanout@1` | `dynamic_quote_published` | project | implemented |
| `weather-front:survival:cold@1` | weather:frost -> Survival cold | SurvivalAuthority | `inf:weather-front-survival-cold@1` | Survival apply/open pair | project | implemented |
| `weather-front:survival:heat@1` | weather:heat -> Survival overheated | SurvivalAuthority | `inf:weather-front-survival-heat@1` | Survival apply/open pair | project | implemented |
| `weather-front:survival:dehydration@1` | weather:drought -> Survival dehydrated | SurvivalAuthority | `inf:weather-front-survival-dehydration@1` | Survival apply/open pair | project | implemented |
| `weather-front:survival:hydration@1` | weather:rain -> Survival hydrated | SurvivalAuthority | `inf:weather-front-survival-hydration@1` | Survival apply/open pair | project | implemented |
| `weather-front:organization:supply@1` | one weather-front -> Organization supply | OrganizationAuthority | `inf:weather-front-organization-supply@1` | commerce commitment accepted | project | implemented |
| `weather-front:organization:supply-fanout@1` | fixed Organization supply fanout | OrganizationAuthority | `inf:weather-front-organization-supply-fanout@1` | commerce commitment accepted | project | implemented |

`drought_process_advanced` is not a partition of the weather-front dehydration
row. It remains a process fact and cannot be used to bypass the source claim.

## Current Unformed Partitions

| Operation key | Disposition | Reason |
| --- | --- | --- |
| `construction:unformed:next@1` | owner_contract_blocked | no independent committed source and product outcome; maintenance rows are duplicate/closed |
| `economy:package:next@1` | candidate_only / blocked | INF-2AG closes one exact public-workshop package/service row; remaining Slot B/C item or service, source, party/account, currency, privacy, and lifecycle fields remain `TBD` |
| `ecology:consumer:next@1` | owner_contract_blocked | no exact target owner/outcome beyond the listed fixed edges, including the distinct INF-3W recovery partition |
| `branch:consequence:next@1` | owner_contract_blocked | branch evidence cannot substitute for Production/domain truth; population/social truth owner is absent |
| `social:delivery:fulfillment@1` | conflict_rejected | project-visible delivery completion cannot be widened into a public SocialFactAuthority relationship/reputation fact; an authority-only fact would not satisfy the product feedback loop. A future row requires explicit public fulfilment/consent evidence and its own source/privacy contract. |
| `government:jurisdiction:drought-advisory@1` | implemented | `inf:weather-front-government-drought-advisory@1`; exact project-visible drought weather-front plus pinned Ecology region/jurisdiction projection -> existing Government advisory issuance only |
| `contract:government:drought-assessment@1` | implemented | exact committed project-visible Government advisory -> existing Contract owner fixed municipal assessment contract; authority-only and no payment/completion fanout |
| `contract:municipal-drought-assessment:fulfillment@1` | implemented | exact active INF-3S municipal assessment Contract record -> existing Contract owner fixed completion/fulfilled pair; generic Contract create, complete, fulfill, and terminate entry points reject these terms; Economy settlement and Ownership certificate remain separate consumers |
| `government:drought:assessment-acknowledgment@1` | implemented | exact INF-4U authority-only certificate -> existing Government authority-only acknowledgment on the originating advisory; generic Ownership initial-title/transfer/package-exchange fragment cannot reserve or move the certificate identity; project advisory presentation remains unchanged |
| `organization:drought:response-commitment@1` | conflict_rejected | a Government drought advisory identifies a jurisdiction/region, not one committed Organization subject or budget/grant/commitment vector. The later municipal Contract fixes two organization parties but still supplies no committed recipient character, membership, role, shift, operating window, work order, effective interval, or budget/commitment proof. Caller-selected organization/worker binding or fixture inference would create a forbidden router/default. A future row requires a committed jurisdiction-to-organization authorization plus a separately committed work-assignment projection with privacy/revision pins. |
| `presentation:government:drought-advisory@1` | implemented | fixed existing-row read extension: backend-issued jurisdiction scope -> `GovernmentAuthority.drought_advisory_view_for` -> exact WebSocket/Godot presentation message; no actor-scope substitution, event append, or truth owner |

These rows are negative partitions: a proposed row matching one must supply a
new product decision and pass every conflict check before it can become `new`.

## 2026-08-29 Autonomous Row Resolution Addendum

| Operation key | Fact claim / fixed partition | Owner | Status |
| --- | --- | --- | --- |
| `construction:mill-flour-output-certification@1` | exact active `mill_reinforced` completed fixed mill-flour run -> project-visible Construction output certification | `ConstructionProductionAuthority` | implemented |
| `economy:industrial-facility-reinforced-mill-flour-output-purchase@1` | INF-1AM certificate -> fixed Inventory provider lot -> v7 8-unit Economy purchase | Inventory + Economy existing owners | implemented |
| `ecology:grain-harvest@1` | mature wheat admission -> terminal project-visible Ecology grain harvest | `EcologyHazardAuthority` | implemented |
| `social:public-milling-notice-acknowledgment@1` | committed public milling notice -> two actor-private acknowledgments | `SocialFactAuthority` | implemented |
| `inventory:grain-harvest-custody@1` | committed grain harvest -> fixed district milling cooperative grain custody | `InventoryAuthorityService` | implemented |
| `organization:grain-intake@1` | fixed Inventory grain custody -> organization grain intake record | `OrganizationAuthority` | implemented |

The five implemented rows are disjoint immutable partitions. Grain custody
uses fixed row literals and an owner-derived item id; no default or
caller-selected coordinate is permitted.

## Evidence And Maintenance

Catalog contracts are the source for owner, stream, event, scope, receipt, and
replay identity. Row contracts supply source, package, lifecycle, and payload
partitions. Every future autonomous decision updates this baseline and the
row-specific decision record before code changes begin.
