# INF-2AD Municipal Drought Assessment Service Exchange

Status: `implemented and verified narrow content vertical; generic service payment remains blocked`

The row permits one provider payment after one committed, fulfilled `simple_service` contract for `service:municipal-drought-assessment@1` with `evidence:municipal-drought-assessment@1`. Government drought advice may inform product workflow but is not payment evidence and creates no payment trigger.

Matrix disposition: `new`. Terms, evidence, and outcome are distinct from tutoring, delivery, wage, tax, fixed offer, gift, and debt. Contract retains completion truth; existing Economy is the only settlement writer. Existing package-exchange events form a disjoint immutable package/outcome/proposal/source-contract partition with authority-only privacy, append receipt, full/tail replay, and terminal/no-compensation semantics.

| Field | Value |
| --- | --- |
| capability / family | `capability:package-declared-negotiated-exchange@1` / `outcome:package-declared-negotiated-exchange@1` |
| outcome | `outcome:municipal-drought-assessment-settlement@1` |
| package | `package:municipal-drought-services:v1`, `1.0.0`, `author:repo`, `trust:repo` |
| terms / evidence | `service:municipal-drought-assessment@1` / `evidence:municipal-drought-assessment@1` |
| price | `policy:municipal-drought-assessment-price@1`, fixed `12` `currency:local` minor units |
| target | `gameplay:economy`: receiver debit, provider credit, then fixed settled event |
| privacy | authority only |
| idempotency / receipt | existing owner-derived key and `append_batch()` receipt |
| replay / lifecycle | existing package-exchange full/tail reader; terminal, no reversal/refund/compensation/retry/fanout/material/advisory write |

The record uses manifest pair `(2, "1.0")` with one outer `economic_outcomes` item. Its extension is structurally complete but has no binding request: current schema has no valid one-to-one mapping from an outcome declaration to an outer economic outcome, and inventing one would be false. Existing Economy still enforces immutable catalog contract `inf:package-declared-negotiated-exchange@1` at append time. No platform change or generic descriptor is introduced.

Unknown/inactive/digest-conflicting package, untrusted author, terms/evidence mismatch, incomplete/foreign source contract, party/consent/account ambiguity, insufficient funds, price/currency mismatch, stale revision, duplicate/changed duplicate, private evidence, and replay conflict are pre-append zero-write.

Account resolution is exact-one by fixed party and `currency:local`: a second
same-currency account for either party is ambiguity, not an implicit default,
and rejects before the debit/credit/settled vector is built.

Implementation: author/freeze canonical v2 package bytes with adapter digests; install/activate through existing immutable registry; RED-to-green source/party/price/privacy/duplicate/receipt/replay tests; independent Harness; synchronize governing records. This admits one content row, not generic service payment.

Closure evidence: the immutable municipal-drought-services package is frozen and
digest-verified; the existing Contract/Economy owners pass focused source,
party, price, privacy, idempotency, receipt, and full/checkpoint-tail replay
tests plus the independent `inf2ad-municipal-drought-assessment-exchange`
Harness. This supersedes the historical package-authoring gate for this row;
the generic payment/transfer boundary remains unchanged.
