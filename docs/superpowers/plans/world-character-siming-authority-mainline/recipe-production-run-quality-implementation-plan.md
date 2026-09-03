# Recipe/Run/Quality Implementation Plan

Add typed recipe batch, output-quality and wear/failure policy validation using
existing run methods. RED tests cover reservations, batch bounds, finish
provenance, policy omission, duplicate/tamper and replay. Gate: Construction
output evidence green without direct Inventory writes; rollback is binding
disablement only.

Run-start replay now rejects stream/privacy/facility-source tampering whenever
the corresponding Facility projection is available, while preserving legacy
source-less run records.

Finish replay now rejects stream/privacy/facility-source tampering with a
stable `production_run_finish_source_conflict` error.

Finish replay now rejects malformed output quantity/quality values with the
stable `production_run_finish_output_invalid` error.
