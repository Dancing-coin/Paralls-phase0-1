# General Inventory Platform Design

Status: `implemented-and-verified`

Inventory is the canonical owner of item definitions, instances, stackable
lots, nested containers, custody, reservations, condition and transport. It
does not own title/lease/lien, accounts/payment, production/facility facts,
equipment activation, survival needs, ecology resources or government policy.

The model is a unique item instance plus compatible stackable lots. Containers
form a fixed directed acyclic graph. Transport reuses the same custody
projection with `stored -> in_transit -> delivered|lost|rejected`.

All content uses Manifest v3/platform 2.0 strict models and author-ordered
arrays. Quantity, weight, quality, durability and expiry are projection-derived;
caller values are untrusted claims. Cross-owner actions use descriptor-bound,
precompiled recipes and existing owner fragments through
`SettlementPlan -> GameplayEventStore.append_batch()`.

Reservation types are quantity, capacity and custody/transport. They retain
source event, owner-issued purpose, expiry and revision pins. Inventory policy
owns condition/expiry lifecycle; Ownership/Contract owns legal rights.

Existing purchase, gift, harvest, production-output custody and equipment rows
remain read-only compatibility baselines. No generic router, coordinator,
writer, second runtime or implicit scheduler is introduced.
