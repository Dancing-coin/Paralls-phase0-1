# P7A Civilization And Cross-Jurisdiction Projection Implementation Plan

Status: `design-only; implementation not authorized`

1. Require P6D governance evidence and classify available source projections.
2. Add read-only aggregation/provenance tests, including audience redaction and
   policy-pinned recomputation.
3. Implement only a derived projection/report boundary over committed facts;
   no aggregate writer or undisclosed social fact.
4. Verify deterministic rebuild from checkpoint plus tail and audit source refs.

Stop if a projection needs to settle government, economy or character state.
