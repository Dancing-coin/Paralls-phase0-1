# Reservation, Scheduling And Concurrency Design

Construction derives due work from committed owner events; no scheduler or
coordinator is added. Inventory issues material/tool reservations, Organization
issues worker/shift evidence, Economy issues budget/labor holds, and
Government/Skill issue their own proofs. Construction stores references and
exact revision vectors only.

Facility slot occupancy and grid occupancy are checked against the current
Construction stream head. Competing commands resolve by append revision;
losers receive structured zero-write conflict results. A due check revalidates
all source streams, package/descriptor/policy pins and privacy before append.
Full and checkpoint-tail replay derive the same reservation references and
conflict outcomes from the single event store.

Reservation admission is exact-set: provided refs must equal the declared
owner requirements, and evidence maps may not contain undeclared keys. Extra
refs or evidence fail closed before any Construction mutation.

The same exact-set and canonical-order checks are enforced during `run_started`
replay, so checkpoint-tail reconstruction cannot accept a reservation payload
that append-time admission would have rejected.
