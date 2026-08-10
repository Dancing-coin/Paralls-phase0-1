# P7D Robotics Safety Research Slice Implementation Plan

Status: `design-only; implementation not authorized`

1. Require P7C, an independent safety/security review and explicit hardware
   authority before any non-simulation work.
2. Start with simulation-only fixtures for latency, sensor fault, stop and
   safety-envelope denial; keep experiment logs separate from world truth.
3. Verify operator authorization, emergency stop, audit and zero gameplay fact
   write under all fault paths.
4. Treat physical actuation as a new approval gate, not an extension of this
   document.

No production robot control is authorized by this plan.
