# INF-2AL Public Milling Session Owner-Admission Contract

Status: `implemented narrow vertical; generic service/payment remains blocked`

## Exact Product Row

```text
committed project-visible Construction
  facility_public_use_enabled@1
  row_ref = construction:facility-mill-reinforced-public-use@1
  facility_kind = mill_reinforced
+ one exact fulfilled Contract service
  service:industrial-facility-public-milling-session@1
-> existing EconomyAuthorityService
-> one fixed package exchange at 8 currency:local
```

The service represents one paid public milling session offered by the fixed
`organization:district-milling-cooperative` provider to the facility owner's
committed receiver party. It does not create production output, consume
materials, transfer inventory/ownership rights, alter facility state, or open
market pricing or generic payment semantics.

## Fixed Business Contract

| Field | Fixed value |
| --- | --- |
| package | `package:industrial-facilities:v6`, version/patch `6.0.0`; immutable adapter-derived declaration/content digests |
| frozen digest pins | `declaration_digest=sha256:899988c037e90a9c93ccd5e5348178ad3f54aa018fdd26af3c9aa90870803205`; `content_digest=sha256:389f485869fc35684b2cdf80b84fba1245535416bdd2afa4f490c3767d9cd243` |
| source | exact INF-1AL project-visible public-use event, with one earlier v2 reinforcement, operational verification, acquisition, facility/project and stream-head pins |
| terms/evidence | `service:industrial-facility-public-milling-session@1` / `evidence:industrial-facility-public-milling-session@1` |
| provider/receiver | provider fixed `organization:district-milling-cooperative`; receiver derives from committed acquisition `owner_ref` |
| capability/outcome | `capability:package-declared-negotiated-exchange@1` / `outcome:industrial-facility-public-milling-session-settlement@1` |
| binding/predicate | `binding:industrial-facility-public-milling-session@1` / `predicate:construction-facility-mill-reinforced-public-use-enabled@1` |
| policy/price | `policy:industrial-facility-public-milling-session-price@1`; fixed `8 currency:local`; `consent:mutual@1` |
| target owners | Contract owns service lifecycle on `gameplay:contracts`; Economy owns debit, credit and settled event on `gameplay:economy` |
| privacy | source project; Contract/Economy settlement authority-only |
| lifecycle | service active -> fulfilled; settlement terminal/no compensation, reversal, refund, retry-as-new, fanout or combined receipt |

## Owner And Replay Boundaries

`ContractAuthorityService` owns the exact record-created and service-completion/
fulfilled pair. `EconomyAuthorityService` uses the existing immutable
package-declared negotiated-exchange handler for this one v6 outcome. Each
owner keeps its own append-derived receipt and full/checkpoint-tail reader;
there is no coordinator or aggregate receipt.

The Economy source resolver accepts only the uniquely fulfilled milling service
with the exact parties and evidence kind. The package handler derives the
provider/receiver accounts and fixed amount from the active v6 manifest;
caller-selected accounts, price, currency, package, owner or event are
zero-write.

## Zero-Write Rules

Unknown/inactive package, digest mismatch, unknown terms/evidence/outcome,
wrong or multiple INF-1AL source, non-reinforced or disabled facility, missing
or private/stale/forged source, binding/project conflict, missing/multiple
account, insufficient funds, price mismatch, invalid consent, stale Contract
or Economy head, invalid/mismatched idempotency key, duplicate with changed
proposal, unadmitted descriptor/catalog, or any payment/material/inventory/
output/permit/technology/weather/social extension rejects before the relevant
owner append. Exact duplicates replay only the original owner-local result.

## Conflict Matrix Result

Disposition: `new`, disjoint from INF-2AE and INF-2AG because the source row,
service identity, provider partition, package revision, price policy and
outcome ref are distinct. Existing Contract and Economy owners are reused;
no generic service/payment/transfer or settlement authority is introduced.

## Evidence

The focused `INF-2AL` tests, immutable catalog/descriptor guards, independent
`inf2al-public-milling-session` Harness, and the broader INF/INFRA regression
prove the fixed source, package digest, service lifecycle, account/price
admission, privacy, idempotency, receipts, zero-write and replay boundaries.
