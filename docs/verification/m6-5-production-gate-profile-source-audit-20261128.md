# M6-5 production Gate profile source audit

## Static findings

- The formal siege demo defines the `breach` transition and states that Presence reevaluates passability independently. Its `impact_gate` contract defines four cross-host steps. It does not assign numeric integrity thresholds.
- `FacilityGateProfileSettings` requires `integrity_lower`, `integrity_upper`, `integrity_initial`, `breach_threshold`, and `breach_reset_threshold`. The existing validator enforces ordering and bounds.
- Runtime configuration reads `SIEGE_FACILITY_GATE_PROFILES_JSON`; `siege_facility_gate_profiles` defaults to an empty list. The test values `40` and `45` are fixtures and are not an authoritative production profile.
- A scoped search for `breach_threshold` and `breach_reset_threshold` in the formal Architecture v2 documents and migration spec/plan found no production numeric profile.

## Disposition

No threshold values were invented or added. Providing production values requires the gameplay/deployment authority to supply a versioned profile for the target world and gate, including its bounds, initial value, breach/reset thresholds, and impact deltas. The existing runtime configuration boundary can consume that profile. Production deployment and a live siege remain unverified.

This was a static audit. No tests ran and no runtime or deployment configuration changed.
