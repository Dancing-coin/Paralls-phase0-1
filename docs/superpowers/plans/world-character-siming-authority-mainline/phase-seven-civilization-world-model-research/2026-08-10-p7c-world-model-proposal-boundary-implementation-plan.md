# P7C World-Model Proposal Boundary Implementation Plan

Status: `design-only; implementation not authorized`

1. Require P7A/B and security review; enumerate allowed read projections and
   model-output classifications.
2. Add tests for redaction, input digest, audit, expiry, confidence metadata,
   denied proposal and no writer dependency.
3. Expose a sandboxed proposal adapter only; route accepted candidates through
   P6 package governance or existing Gameplay authority validation.
4. Verify factual replay and model prediction remain visibly and structurally
   separate in all reports.

Stop for raw memory access, arbitrary generated code execution or direct event
append.
