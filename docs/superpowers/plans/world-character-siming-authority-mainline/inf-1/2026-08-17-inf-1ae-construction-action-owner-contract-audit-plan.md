# INF-1AE Construction Action Owner-Contract Audit Plan

Status: `implemented narrow vertical and verified 2026-08-17`

1. Implement only the approved facility repair/compensation pair through the
   existing Construction owner and event store.
2. Do not add a generic action registry, writer, payment owner, or router.
3. Keep transform, payment, material, and service-completion proposals
   zero-write until separate owner contracts exist.
4. Focused evidence is `backend/tests/test_infra_construction_facility_repair.py`
   and `infra-construction-facility-repair`.
