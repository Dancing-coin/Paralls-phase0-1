# M6-5 production Gate input audit

## Scope

- A branch snapshot: `039a5b9bbba7b7190fa8a180a2da5e47dcaf524c`.
- Static inspection only. No runtime code or production configuration changed, and no tests ran.
- Read-only sources checked: Architecture v2 `02-守城Demo定义.md`, the first-phase county siege demo PRD, `.env.example`, `backend/app/config.py`, the M6-5 physical-input plan, and the layered impact evidence.

## Findings

- The formal demo defines the order and ownership boundary for `impact_gate`: door durability, latch durability, integrity, then separately committed Presence passability. It names `gate-03` as the demonstration target but supplies no durability, breach, reset, or impact-delta numbers.
- The searched PRD contains no authoritative numeric Gate profile. No deployment target or production content manifest was found in the repository.
- `.env.example` exposes `SIEGE_FACILITY_GATE_PROFILES_JSON` with `gate-03` values `40`, `45`, and `-20`, and explicitly labels the profile demonstration-only. The layered-runtime evidence traces those same values to a local probe. They are not production tuning.
- `Settings.siege_facility_gate_profiles` parses the environment profile. An empty profile leaves the Facility writer unconfigured, and the signed-input path reports `not_configured`; there is no production target at which to verify an external profile.

## Result

The configuration contract and local runtime path exist. Production Gate values and deployment remain unconfigured because the authoritative numeric content and target were not present in the inspected sources. Filling this gap requires the project/content owner to supply or approve, per deployed Gate, bounds and initial values for door durability, latch durability and integrity, breach enter/reset thresholds, and impact deltas keyed by versioned impact kind, plus the deployment target that loads the profile. No production value was inferred from the demonstration profile.

Evidence references: `docs/v2-coordination/handoff.md` H-A-111 and H-A-171; `docs/verification/m6-5-impact-gate-layered-execution-20261124.md`; `docs/verification/m6-5-siege-physical-inputs-plan-20261124.md`.
