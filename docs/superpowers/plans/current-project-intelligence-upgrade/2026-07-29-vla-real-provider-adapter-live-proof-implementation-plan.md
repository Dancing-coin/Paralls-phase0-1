# VLA Real Provider Adapter And Live-Proof Implementation Plan

- Date: `2026-07-29`
- Status: `implemented-live-proof-blocked`
- Design: `2026-07-29-vla-real-provider-adapter-live-proof-design.md`
- Extended by: `2026-07-30-advisory-vla-routing-and-tts-convergence-implementation-plan.md`

## Goal

Turn the existing contract-ready VLA slow path into a real, non-streaming,
OpenAI-compatible advisory provider integration while retaining its PQF, cache,
scheduler, bridge, and no-authority boundaries.

## Steps

1. Add focused failing tests for request formation, response projection,
   transport failure, and forbidden provider-output fields.
2. Implement the adapter with standard-library HTTP only. It accepts direct
   image artifact sources from PQF `stable_source_ref`; it neither reads Godot
   nor invents a URL for opaque refs.
3. Add provider-kind/model-version settings and document the secret-free env
   surface. Keep disabled, blocked, and local modes compatible.
4. Add an explicit live-proof command which creates a PQF from a supplied
   image artifact URL, performs a real call only after opt-in, and records
   redacted evidence.
5. Update readiness, runtime docs, and Kimi analysis status so configured,
   blocked, and live-verified states cannot be conflated.

## Verification

```powershell
python -m pytest -q backend/tests/test_vla_provider_backend_adapter.py backend/tests/test_vla_provider_backend_contract.py backend/tests/test_vla_percept_bridge.py backend/tests/test_model_provider_readiness.py
python scripts/verification/verify_vla_provider_backend.py
python scripts/verification/verify_model_provider_readiness.py
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile model-provider-readiness
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile all
```

The optional external proof is deliberately separate:

```powershell
python scripts/verification/verify_vla_provider_live.py --allow-live-call
```

It needs a real key and eligible image artifact URL. A blocked result is
evidence of a missing prerequisite, not a real-provider completion claim.

The two-tier model selection, scheduler/cache isolation, and escalation policy
are delivered and tracked by the 2026-07-30 convergence plan; this plan remains
the owner of the first HTTP transport and VLA proof command.
