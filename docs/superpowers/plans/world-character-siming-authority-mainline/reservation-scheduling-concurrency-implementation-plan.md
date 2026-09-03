# Reservation/Scheduling/Concurrency Implementation Plan

Reuse existing owner reservation and event revisions. RED tests cover slot/grid
conflict, stale source vectors, due revalidation and deterministic loser
results. Implement no scheduler; add only owner validation and replay evidence.
Gate: concurrent append and full/tail replay green.

The requirement validator now rejects undeclared reservation refs and evidence
keys, preserving exact owner-issued binding without introducing a scheduler or
coordinator.

ProductionRun start replay now validates reservation ref ordering, uniqueness,
evidence key equality, and owner/status/revision shape before projection state
is accepted.
