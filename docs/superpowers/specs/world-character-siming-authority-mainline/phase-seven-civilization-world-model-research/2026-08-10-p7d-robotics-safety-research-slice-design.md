# P7D Robotics Safety Research Slice

Status: `design-only; implementation not authorized`

## Purpose

Define a future sandbox for embodied/robotics research without letting real
sensors, model output or remote actuation control gameplay truth. Godot remains
presentation; any physical adapter is separate from the authoritative world.

## Safety Contract

A robotics experiment pins simulation scene, controller/model version, sensor
source, latency/failure model, action envelope, safety envelope, stop condition,
operator authorization and audit trace. It first targets simulation-only,
bounded low-level actions. Physical actuation requires an independent safety
review, hardware interlock, operator emergency stop and explicit non-authority
classification.

## Gate

Test stale sensor, delayed command, safety-envelope violation, emergency stop,
audit completeness, sandbox isolation and no fact append. Sim-to-real,
autonomous real-world action and an embodied truth writer are excluded.
